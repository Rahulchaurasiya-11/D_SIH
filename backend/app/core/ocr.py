"""
OCR pipeline: image preprocessing variants, engine selection, segment fusion.

Extracted from the original monolithic `main.py`. Two behavioural changes:

  * The engine is initialised lazily on first use instead of at import time. The
    old module-level warm-up made `import main` take ~10s and crash the whole
    process if a model download failed.
  * This module raises `ValueError` rather than `HTTPException`, so it stays a
    plain library that tests and CLI tools can call without FastAPI.
"""

import io
import logging
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps

logger = logging.getLogger("legal_metrology_ocr")

_engine = None
_engine_name = "none"

# Two OCR detections are treated as the same physical line when their bounding-box
# centres are closer than this (in original-image pixels) and one text contains the
# other. Tuned against the existing demo images; loosening it merges adjacent
# declaration lines, tightening it duplicates them across preprocessing variants.
_DEDUPE_CENTRE_DISTANCE_PX = 25.0


def get_ocr_engine():
    """
    Returns the OCR callable, preferring PaddleOCR and falling back to the RapidOCR
    ONNX runtime (much lighter, no paddlepaddle wheel). Returns None when neither is
    installed - callers then rely on client-side OCR or manual text entry.
    """
    global _engine, _engine_name
    if _engine is not None:
        return None if _engine == "UNAVAILABLE" else _engine

    try:
        from paddleocr import PaddleOCR

        logger.info("Initialising PaddleOCR (angle classification on, sensitive detection thresholds)...")
        _engine = PaddleOCR(
            use_angle_cls=True, lang="en",
            det_db_thresh=0.3, det_db_box_thresh=0.5, max_text_length=50,
        )
        _engine_name = "paddleocr"
        return _engine
    except Exception as paddle_err:
        logger.info("PaddleOCR unavailable (%s); trying RapidOCR ONNX.", paddle_err)

    try:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
        _engine_name = "rapidocr_onnx"
        logger.info("RapidOCR (PP-OCRv4 ONNX) initialised.")
        return _engine
    except Exception as rapid_err:
        logger.warning("No server-side OCR engine available (%s). "
                       "Client-side OCR and manual entry still work.", rapid_err)
        _engine = "UNAVAILABLE"
        _engine_name = "none"
        return None


def engine_name() -> str:
    get_ocr_engine()
    return _engine_name


def preprocess_image_for_ocr(img_np: np.ndarray) -> List[Tuple[str, np.ndarray, float]]:
    """
    Builds enhanced variants of the image to counter the things that actually break
    label OCR in a shop: motion blur, glare off plastic film, faint low-contrast
    printing, and low-resolution phone crops.

    Returns a list of (variant_name, image, scale_factor).
    """
    variants: List[Tuple[str, np.ndarray, float]] = []

    h, w = img_np.shape[:2]
    scale_factor = 1.0
    base_img = img_np

    # Upscale small images so micro-printed statutory text survives detection.
    if max(h, w) < 1400:
        scale_factor = 1400.0 / max(h, w)
        base_img = cv2.resize(
            img_np, (int(w * scale_factor), int(h * scale_factor)), interpolation=cv2.INTER_CUBIC
        )

    variants.append(("original", base_img, scale_factor))

    try:
        if len(base_img.shape) == 3 and base_img.shape[2] == 3:
            gray = cv2.cvtColor(base_img, cv2.COLOR_RGB2GRAY)
        else:
            gray = base_img

        # Unsharp mask - recovers edges on blurry / soft-focus captures.
        blurred = cv2.GaussianBlur(base_img, (0, 0), 2.5)
        variants.append(("unsharp_deblur", cv2.addWeighted(base_img, 1.8, blurred, -0.8, 0), scale_factor))

        # CLAHE at two strengths - uneven lighting, then glossy/shadowed packs.
        for name, clip, tile in (("clahe_medium", 2.5, (8, 8)), ("clahe_high", 4.0, (6, 6))):
            enhanced = cv2.createCLAHE(clipLimit=clip, tileGridSize=tile).apply(gray)
            variants.append((name, cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB), scale_factor))

        # Otsu binarisation - metallic and reflective backgrounds.
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.append(("otsu_binarized", cv2.cvtColor(otsu, cv2.COLOR_GRAY2RGB), scale_factor))

    except Exception as cv_err:
        logger.warning("Image preprocessing notice: %s", cv_err)

    return variants


def _box_centre_distance(box1: List[List[float]], box2: List[List[float]]) -> float:
    try:
        c1x = sum(p[0] for p in box1) / len(box1)
        c1y = sum(p[1] for p in box1) / len(box1)
        c2x = sum(p[0] for p in box2) / len(box2)
        c2y = sum(p[1] for p in box2) / len(box2)
        return ((c1x - c2x) ** 2 + (c1y - c2y) ** 2) ** 0.5
    except Exception:
        return 9999.0


def _normalise_ocr_output(raw: Any) -> List[Tuple[List[List[float]], str, float]]:
    """
    Flattens the differing shapes PaddleOCR and RapidOCR return into
    (box, text, confidence) triples.
    """
    lines: List[Tuple[List[List[float]], str, float]] = []
    if not raw:
        return lines

    # RapidOCR: [[box, text, score], ...]
    # PaddleOCR: [[[box, (text, score)], ...]]  (one entry per page)
    candidates = raw
    if isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], list) and raw[0] \
            and isinstance(raw[0][0], list) and len(raw[0][0]) == 2 \
            and isinstance(raw[0][0][1], (tuple, list)):
        candidates = raw[0]

    for line in candidates:
        try:
            box = line[0]
            payload = line[1]
            if isinstance(payload, (tuple, list)) and len(payload) == 2:
                text, conf = str(payload[0]), float(payload[1])
            else:
                text, conf = str(payload), float(line[2]) if len(line) > 2 else 0.0
            lines.append((box, text.strip(), conf))
        except (IndexError, TypeError, ValueError):
            continue
    return lines


def extract_segments_from_image(image_bytes: bytes) -> Tuple[List[Dict[str, Any]], Tuple[int, int]]:
    """
    Runs OCR across every preprocessing variant and fuses the results.

    Returns (segments, (height, width)). Each segment is {text, box, confidence}
    with box coordinates in the ORIGINAL image's pixel space.

    Raises ValueError if the bytes are not a decodable image.
    """
    try:
        pil_img = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes))).convert("RGB")
        img_w, img_h = pil_img.size
        img_np = np.array(pil_img)
    except Exception as img_err:
        raise ValueError("Uploaded file is not a decodable image: %s" % img_err) from img_err

    engine = get_ocr_engine()
    if engine is None:
        return [], (img_h, img_w)

    candidates: List[Dict[str, Any]] = []
    try:
        for variant_name, variant_img, scale in preprocess_image_for_ocr(img_np):
            try:
                result = engine(variant_img)
            except Exception as run_err:
                logger.warning("OCR variant %s failed: %s", variant_name, run_err)
                continue

            raw = result[0] if isinstance(result, tuple) else result
            for box, text, conf in _normalise_ocr_output(raw):
                if not text:
                    continue
                candidates.append({
                    "text": text,
                    "box": [[round(float(p[0]) / scale, 1), round(float(p[1]) / scale, 1)] for p in box],
                    "confidence": round(conf, 4),
                    "variant": variant_name,
                })
    except Exception as ocr_exc:
        logger.error("OCR pipeline exception: %s", ocr_exc)

    # Fuse: same text, or overlapping boxes where one transcription contains the
    # other. Keep whichever variant read it with more confidence or more detail.
    fused: List[Dict[str, Any]] = []
    for cand in candidates:
        cand_text = cand["text"].lower()
        matched = -1
        for idx, existing in enumerate(fused):
            ex_text = existing["text"].lower()
            if cand_text == ex_text or (
                _box_centre_distance(cand["box"], existing["box"]) < _DEDUPE_CENTRE_DISTANCE_PX
                and (cand_text in ex_text or ex_text in cand_text)
            ):
                matched = idx
                break
        if matched >= 0:
            if cand["confidence"] > fused[matched]["confidence"] or len(cand["text"]) > len(fused[matched]["text"]):
                fused[matched] = cand
        else:
            fused.append(cand)

    # Reading order: top to bottom, then left to right.
    fused.sort(key=lambda s: (min(p[1] for p in s["box"]), min(p[0] for p in s["box"])))

    segments = [{"text": s["text"], "box": s["box"], "confidence": s["confidence"]} for s in fused]
    return segments, (img_h, img_w)


def segments_from_plain_text(text: str, image_dimensions: Optional[Tuple[int, int]] = None) -> List[Dict[str, Any]]:
    """
    Turns pasted or client-OCR'd text into synthetic segments so the rule engine has
    one input shape. Boxes are evenly stacked placeholders - font-height checks
    downgrade themselves to advisory when the geometry is synthetic.
    """
    height, width = image_dimensions or (1000, 1000)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []

    row_h = max(1.0, height / max(len(lines), 1))
    segments = []
    for i, line in enumerate(lines):
        top = i * row_h
        segments.append({
            "text": line,
            "box": [[0.0, top], [float(width), top], [float(width), top + row_h], [0.0, top + row_h]],
            "confidence": 1.0,
            "synthetic_geometry": True,
        })
    return segments
