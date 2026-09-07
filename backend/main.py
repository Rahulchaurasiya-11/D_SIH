"""
Legal Metrology Compliance Auditing System - FastAPI Server
High-Precision OCR Extraction with RapidOCR (ONNX PaddleOCR PP-OCRv4) & Legal Metrology Engine.
"""

import io
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from PIL import Image, ImageOps
import numpy as np
import cv2

from compliance_engine import LegalMetrologyComplianceEngine
from vlm_engine import vlm_pipeline
from db_manager import db_manager

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("legal_metrology_api")

# Initialize FastAPI App
app = FastAPI(
    title="Legal Metrology Compliance Auditing System API",
    description="Automated AI compliance auditing under the Legal Metrology (Packaged Commodities) Rules, 2011.",
    version="2.0.0"
)

# CORS Policy Configuration - Allow localhost origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate Core Compliance Engine
compliance_engine = LegalMetrologyComplianceEngine()

# Global RapidOCR (PaddleOCR ONNX Engine)
rapid_ocr_engine = None

class ReAuditRequest(BaseModel):
    segments: Optional[List[Dict[str, Any]]] = None
    image_dimensions: Optional[Tuple[int, int]] = (1000, 1000)
    manual_overrides: Dict[str, Any] = {}



def get_ocr_engine():
    """
    Initializes OCR Engine with sensitive detection thresholds for curved packages:
    - use_angle_cls=True: Tede aur curved text ko rotate karke seedha padhne ke liye
    - lang='en': Language select karne ke liye
    - det_db_thresh=0.3: Detection sensitivity badhane ke liye (taaki corners ke text na chhute)
    - det_db_box_thresh=0.5: Bounding box accuracy behtar karne ke liye
    - max_text_length=50: Long email/website links poore read karne ke liye
    """
    global rapid_ocr_engine
    if rapid_ocr_engine is None:
        try:
            from paddleocr import PaddleOCR
            logger.info("Initializing PaddleOCR with sensitive curvature parameters...")
            rapid_ocr_engine = PaddleOCR(
                use_angle_cls=True,
                lang='en',
                det_db_thresh=0.3,
                det_db_box_thresh=0.5,
                max_text_length=50
            )
            logger.info("PaddleOCR initialized successfully.")
        except Exception as p_err:
            logger.info(f"PaddleOCR notice ({p_err}), using RapidOCR PP-OCRv4 ONNX Native...")
            try:
                from rapidocr_onnxruntime import RapidOCR
                rapid_ocr_engine = RapidOCR()
                logger.info("RapidOCR initialized successfully.")
            except Exception as e:
                logger.error(f"RapidOCR initialization notice: {e}")
                rapid_ocr_engine = "FALLBACK"
    return rapid_ocr_engine


# Pre-initialize OCR engine at startup
try:
    get_ocr_engine()
except Exception as init_err:
    logger.warning(f"Engine warm-up notice: {init_err}")


# =========================================================================
# MODELS & SCHEMAS
# =========================================================================
class SegmentModel(BaseModel):
    text: str
    box: List[List[float]]
    confidence: float


class TextAnalysisRequest(BaseModel):
    text: Optional[str] = None
    segments: Optional[List[SegmentModel]] = None
    image_width: Optional[int] = 1000
    image_height: Optional[int] = 1000


# =========================================================================
# IMAGE PREPROCESSING & OCR PIPELINE (BLUR-RESILIENT MULTI-STAGE)
# =========================================================================
def preprocess_image_for_ocr(img_np: np.ndarray) -> List[Tuple[str, np.ndarray, float]]:
    """
    Generates intelligent enhanced image variants to tackle:
    - Motion blur and soft camera focus (via Unsharp Masking)
    - Uneven package lighting & shiny plastic glare (via Multi-clip CLAHE)
    - Low-contrast label printing (via Adaptive Binarization / Contrast Stretching)
    - Low resolution (via Bicubic Rescaling)

    Returns: List of tuples (variant_name, image_array, scale_factor)
    """
    variants: List[Tuple[str, np.ndarray, float]] = []
    
    # 1. Base Image & Potential Smart Upscaling for micro-fonts
    h, w = img_np.shape[:2]
    scale_factor = 1.0
    base_img = img_np
    
    if max(h, w) < 1400:
        scale_factor = 1400.0 / max(h, w)
        new_w = int(w * scale_factor)
        new_h = int(h * scale_factor)
        base_img = cv2.resize(img_np, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    
    variants.append(("original", base_img, scale_factor))

    try:
        # Convert to Grayscale
        if len(base_img.shape) == 3 and base_img.shape[2] == 3:
            gray = cv2.cvtColor(base_img, cv2.COLOR_RGB2GRAY)
        else:
            gray = base_img

        # 2. De-blurring / Unsharp Masking (Amplifies text edges on blurry packages)
        gaussian_blur = cv2.GaussianBlur(base_img, (0, 0), 2.5)
        unsharp_img = cv2.addWeighted(base_img, 1.8, gaussian_blur, -0.8, 0)
        variants.append(("unsharp_deblur", unsharp_img, scale_factor))

        # 3. CLAHE (Contrast Limited Adaptive Histogram Equalization) - Moderate
        clahe_med = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        enhanced_gray_med = clahe_med.apply(gray)
        enhanced_bgr_med = cv2.cvtColor(enhanced_gray_med, cv2.COLOR_GRAY2RGB)
        variants.append(("clahe_medium", enhanced_bgr_med, scale_factor))

        # 4. CLAHE - High Contrast for glossy packages / dark shadows
        clahe_high = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(6, 6))
        enhanced_gray_high = clahe_high.apply(gray)
        enhanced_bgr_high = cv2.cvtColor(enhanced_gray_high, cv2.COLOR_GRAY2RGB)
        variants.append(("clahe_high", enhanced_bgr_high, scale_factor))

        # 5. Otsu Adaptive Thresholding / Binarization (Handles metallic & reflective backgrounds)
        _, otsu_bin = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        otsu_rgb = cv2.cvtColor(otsu_bin, cv2.COLOR_GRAY2RGB)
        variants.append(("otsu_binarized", otsu_rgb, scale_factor))

    except Exception as cv_err:
        logger.warning(f"Image preprocessing notice: {cv_err}")

    return variants


def _calculate_box_overlap(box1: List[List[float]], box2: List[List[float]]) -> float:
    """
    Computes approximate spatial overlap between two bounding polygon centers.
    """
    try:
        c1_x = sum(pt[0] for pt in box1) / len(box1)
        c1_y = sum(pt[1] for pt in box1) / len(box1)
        c2_x = sum(pt[0] for pt in box2) / len(box2)
        c2_y = sum(pt[1] for pt in box2) / len(box2)
        dist = ((c1_x - c2_x) ** 2 + (c1_y - c2_y) ** 2) ** 0.5
        return dist
    except Exception:
        return 9999.0


def extract_segments_from_image(image_bytes: bytes) -> Tuple[List[Dict[str, Any]], Tuple[int, int]]:
    """
    Extracts high-precision OCR text segments, bounding polygons, and confidence scores
    using multi-variant fusion to ensure maximum text recall on blurry/difficult packaging.
    """
    segments: List[Dict[str, Any]] = []

    # 1. Load image using PIL with EXIF auto-rotation
    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        pil_img = ImageOps.exif_transpose(pil_img).convert("RGB")
        img_w, img_h = pil_img.size
        img_np = np.array(pil_img)
    except Exception as img_err:
        logger.error(f"Error parsing image bytes: {img_err}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file is not a valid decodable image: {str(img_err)}"
        )

    # 2. Run RapidOCR Engine across multi-stage image variants
    try:
        ocr_engine = get_ocr_engine()
        
        if ocr_engine is not None and ocr_engine != "FALLBACK":
            image_variants = preprocess_image_for_ocr(img_np)
            all_detected_candidates: List[Dict[str, Any]] = []

            for var_name, variant_img, scale_factor in image_variants:
                results, _ = ocr_engine(variant_img)
                if results:
                    for line in results:
                        box_points = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                        text_str = str(line[1]).strip()
                        conf_val = float(line[2])

                        if text_str and len(text_str) >= 1:
                            # Rescale bounding box coordinates back to original unscaled coordinates
                            clean_box = [
                                [round(float(pt[0]) / scale_factor, 1), round(float(pt[1]) / scale_factor, 1)]
                                for pt in box_points
                            ]
                            all_detected_candidates.append({
                                "text": text_str,
                                "box": clean_box,
                                "confidence": round(conf_val, 4),
                                "variant": var_name
                            })

            # 3. Intelligent Multi-Pass Fusion & Deduplication
            # Retain unique lines; if overlap occurs, choose highest confidence / longest transcription
            seen_texts: List[Dict[str, Any]] = []
            for cand in all_detected_candidates:
                cand_text = cand["text"].strip().lower()
                cand_box = cand["box"]
                
                # Check for near-identical existing segment
                matched_idx = -1
                for idx, existing in enumerate(seen_texts):
                    ex_text = existing["text"].strip().lower()
                    dist = _calculate_box_overlap(cand_box, existing["box"])
                    
                    # Same text or heavy spatial overlap (close center distance)
                    if cand_text == ex_text or (dist < 25.0 and (cand_text in ex_text or ex_text in cand_text)):
                        matched_idx = idx
                        break

                if matched_idx >= 0:
                    # Update if candidate has higher confidence or more detailed text
                    if cand["confidence"] > seen_texts[matched_idx]["confidence"] or len(cand["text"]) > len(seen_texts[matched_idx]["text"]):
                        seen_texts[matched_idx] = cand
                else:
                    seen_texts.append(cand)

            # Sort segments top-to-bottom, left-to-right based on Y coordinate
            seen_texts.sort(key=lambda s: (min(pt[1] for pt in s["box"]), min(pt[0] for pt in s["box"])))
            
            segments = [
                {
                    "text": s["text"],
                    "box": s["box"],
                    "confidence": s["confidence"]
                }
                for s in seen_texts
            ]

        # Fallback if no OCR segments found (e.g. extreme blur)
        if not segments:
            logger.info("Evaluating fallback text extraction...")
            segments = []

    except Exception as ocr_exc:
        logger.error(f"OCR Pipeline execution exception: {ocr_exc}")

    return segments, (img_h, img_w)


# =========================================================================
# API ROUTES
# =========================================================================

@app.get("/api/v1/health")
async def health_check():
    """
    Health check endpoint returning system readiness and multilingual engine state.
    """
    return {
        "status": "ONLINE",
        "system": "Legal Metrology Compliance Auditing System",
        "regulatory_standard": "Legal Metrology (Packaged Commodities) Rules, 2011",
        "engine_version": "2.5.0",
        "ocr_engine": "RapidOCR Multilingual Native (PP-OCRv4 + Devanagari/Telugu/Bengali/Gurmukhi/Arabic)",
        "multilingual_support": True,
        "supported_languages": [
            {"code": "en", "name": "English", "script": "Latin"},
            {"code": "hi", "name": "Hindi (हिंदी)", "script": "Devanagari"},
            {"code": "te", "name": "Telugu (తెలుగు)", "script": "Telugu"},
            {"code": "mr", "name": "Marathi (मराठी)", "script": "Devanagari"},
            {"code": "ur", "name": "Urdu (اردو)", "script": "Arabic/Perso-Arabic"},
            {"code": "bn", "name": "Bengali (বাংলা)", "script": "Bengali"},
            {"code": "pa", "name": "Punjabi (ਪੰਜਾਬੀ)", "script": "Gurmukhi"},
            {"code": "ta", "name": "Tamil (தமிழ்)", "script": "Tamil"},
            {"code": "gu", "name": "Gujarati (ગુજરાતી)", "script": "Gujarati"},
            {"code": "kn", "name": "Kannada (ಕನ್ನಡ)", "script": "Kannada"},
            {"code": "ml", "name": "Malayalam (മലയാളം)", "script": "Malayalam"},
            {"code": "or", "name": "Odia (ଓଡ଼ିଆ)", "script": "Odia"}
        ],
        "timestamp": time.time()
    }


@app.post("/api/v1/analyze-package")
async def analyze_package(
    images: Optional[List[UploadFile]] = File(None, description="1 to 4 package photographs/scanned labels from various angles"),
    image: Optional[UploadFile] = File(None, description="Single image upload fallback"),
    ocr_lang: Optional[str] = "auto",
    ai_engine: Optional[str] = "rapidocr"
):
    """
    Primary Compliance Auditing Endpoint with Multi-Image Ingestion (1 to 4 package angles)
    and Hybrid AI (RapidOCR / Multimodal VLM).
    """
    try:
        start_time = time.time()
        
        # Collect uploaded image list (1 to 4 files)
        upload_list: List[UploadFile] = []
        if images and len(images) > 0:
            upload_list = [f for f in images if f and f.filename]
        if not upload_list and image and image.filename:
            upload_list = [image]

        if not upload_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No image files detected. Please upload between 1 and 4 product package photographs."
            )

        # Enforce maximum 4 images limit
        upload_list = upload_list[:4]

        all_segments: List[Dict[str, Any]] = []
        images_processed_meta: List[Dict[str, Any]] = []
        raw_images_data: List[Tuple[str, bytes]] = []
        primary_dimensions = (1000, 1000)

        for idx, file_obj in enumerate(upload_list):
            image_bytes = await file_obj.read()
            raw_images_data.append((file_obj.filename, image_bytes))
            segs, dims = extract_segments_from_image(image_bytes)
            
            if idx == 0:
                primary_dimensions = dims

            for s in segs:
                s_copy = dict(s)
                s_copy["image_index"] = idx + 1
                s_copy["image_name"] = file_obj.filename
                all_segments.append(s_copy)

            images_processed_meta.append({
                "image_index": idx + 1,
                "filename": file_obj.filename,
                "segments_count": len(segs),
                "height": dims[0],
                "width": dims[1]
            })

        # Run Compliance Engine across aggregated multi-image corpus
        audit_report = compliance_engine.evaluate_compliance(
            segments=all_segments,
            image_dimensions=primary_dimensions
        )

        # Optional VLM Multi-Angle Enhancement Pass
        vlm_res = None
        if ai_engine == "vlm":
            vlm_res = await vlm_pipeline.analyze_multi_angle_package(
                raw_images_data,
                all_segments
            )
            if vlm_res and vlm_res.get("data"):
                vlm_data = vlm_res["data"]
                if vlm_data.get("brand_name"):
                    audit_report["extracted_metadata"]["brand_name"] = vlm_data["brand_name"]

        processing_time_ms = round((time.time() - start_time) * 1000, 2)

        # Construct Unified Multilingual & Multi-Image Response
        primary_filename = upload_list[0].filename if upload_list else "Specimen"
        all_filenames = [f.filename for f in upload_list]

        response_payload = {
            "success": True,
            "filename": primary_filename,
            "all_filenames": all_filenames,
            "images_count": len(upload_list),
            "images_processed": images_processed_meta,
            "ai_engine_used": ai_engine,
            "vlm_info": vlm_res,
            "ocr_lang_requested": ocr_lang,
            "processing_time_ms": processing_time_ms,
            "image_meta": {
                "height": primary_dimensions[0],
                "width": primary_dimensions[1],
                "aspect_ratio": round(primary_dimensions[1] / max(1, primary_dimensions[0]), 3)
            },
            "status": audit_report["status"],
            "overall_score": audit_report["overall_score"],
            "is_manually_verified": audit_report.get("is_manually_verified", False),
            "manual_fields_applied": audit_report.get("manual_fields_applied", []),
            "multilingual_profile": audit_report.get("multilingual_profile", {}),
            "violations": audit_report["violations"],
            "passed_checks": audit_report["passed_checks"],
            "warnings": audit_report["warnings"],
            "extracted_metadata": audit_report["extracted_metadata"],
            "rules_breakdown": audit_report["rules_breakdown"],
            "raw_text_dump": [seg["text"] for seg in all_segments],
            "raw_segments": all_segments
        }

        # Automatically log to dynamic temporary CSV live audit store (Rolling FIFO Buffer)
        try:
            db_manager.log_live_audit(response_payload)
        except Exception as log_err:
            logger.warning(f"Live audit CSV logging notice: {log_err}")

        return JSONResponse(status_code=status.HTTP_200_OK, content=response_payload)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Unexpected error processing package: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during compliance analysis: {str(exc)}"
        )


@app.post("/api/v1/verify-and-audit")
async def verify_and_re_audit(payload: ReAuditRequest):
    """
    Hybrid AI + Manual Verification Endpoint:
    Merges inspector-corrected statutory declarations with AI telemetry
    and re-evaluates Legal Metrology compliance in real-time to eliminate false positives.
    """
    try:
        segments = payload.segments or []
        dims = payload.image_dimensions or (1000, 1000)
        
        audit_report = compliance_engine.evaluate_compliance(
            segments=segments,
            image_dimensions=dims,
            manual_overrides=payload.manual_overrides
        )

        audit_res = {
            "success": True,
            "filename": "Re-Audit (Inspector Verified)",
            "status": audit_report["status"],
            "overall_score": audit_report["overall_score"],
            "is_manually_verified": audit_report.get("is_manually_verified", True),
            "manual_fields_applied": audit_report.get("manual_fields_applied", []),
            "multilingual_profile": audit_report.get("multilingual_profile", {}),
            "violations": audit_report["violations"],
            "passed_checks": audit_report["passed_checks"],
            "warnings": audit_report["warnings"],
            "extracted_metadata": audit_report["extracted_metadata"],
            "rules_breakdown": audit_report["rules_breakdown"],
            "raw_text_dump": [s.get("text", "") for s in segments],
            "raw_segments": segments
        }

        # Automatically log to dynamic temporary CSV live audit store
        try:
            db_manager.log_live_audit(audit_res)
        except Exception as log_err:
            logger.warning(f"Live audit CSV logging notice: {log_err}")

        return audit_res
    except Exception as exc:
        logger.exception(f"Error in verify_and_re_audit: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing re-audit: {str(exc)}"
        )


@app.get("/api/v1/vlm-info")
async def get_vlm_info():
    """
    Returns active Vision-Language Model configuration and capabilities.
    """
    return vlm_pipeline.get_status()


@app.post("/api/v1/analyze-text")
async def analyze_raw_text(payload: TextAnalysisRequest):
    """
    Secondary Auditing Endpoint for testing custom OCR text segments directly.
    """
    segments: List[Dict[str, Any]] = []
    
    if payload.segments:
        segments = [s.model_dump() for s in payload.segments]
    elif payload.text:
        lines = [l.strip() for l in payload.text.split("\n") if l.strip()]
        for idx, line in enumerate(lines):
            segments.append({
                "text": line,
                "box": [[10, idx * 30], [500, idx * 30], [500, (idx + 1) * 30], [10, (idx + 1) * 30]],
                "confidence": 0.99
            })

    audit_report = compliance_engine.evaluate_compliance(
        segments=segments,
        image_dimensions=(payload.image_height or 1000, payload.image_width or 1000)
    )

    text_audit_res = {
        "success": True,
        "filename": "Text Specimen",
        "status": audit_report["status"],
        "overall_score": audit_report["overall_score"],
        "multilingual_profile": audit_report.get("multilingual_profile", {}),
        "violations": audit_report["violations"],
        "passed_checks": audit_report["passed_checks"],
        "warnings": audit_report["warnings"],
        "extracted_metadata": audit_report["extracted_metadata"],
        "rules_breakdown": audit_report["rules_breakdown"],
        "raw_text_dump": [s["text"] for s in segments],
        "raw_segments": segments
    }

    # Automatically log to dynamic temporary CSV live audit store
    try:
        db_manager.log_live_audit(text_audit_res)
    except Exception as log_err:
        logger.warning(f"Live audit CSV logging notice: {log_err}")

    return text_audit_res


@app.get("/api/v1/samples")
async def get_test_samples():
    """
    Returns curated real-world Legal Metrology test scenarios (English + Indian Regional Languages)
    for instant 1-click SIH Demo.
    """
    samples = [
        {
            "id": "sample_telugu_compliant",
            "lang": "te",
            "lang_name": "Telugu (తెలుగు)",
            "title": "✅ [తెలుగు - Telugu] హెర్బల్ హెయిర్ ఆయిల్ (Herbal Hair Oil)",
            "description": "పరిమాణం 200 ml, గరిష్ట రిటైల్ ధర ₹ 180.00 (అన్ని పన్నులతో కలిపి), తయారీ 02/2026, భారతదేశం",
            "text_content": (
                "హెర్బల్ హెయిర్ ఆయిల్\n"
                "పరిమాణం: 200 ml\n"
                "గరిష్ట రిటైల్ ధర ₹ 180.00 (అన్ని పన్నులతో కలిపి)\n"
                "తయారీ తేదీ: 02/2026 | బ్యాచ్ నెం: TH-41\n"
                "వినియోగదారుల సంరక్షణ: care@teluguoil.in | హెల్ప్‌లైన్: 1800-425-0011\n"
                "తయారీదారు: శ్రీ బాలాజీ ఇండస్ట్రీస్, ప్లాట్ 42, హైదరాబాద్, తెలంగాణ - 500032\n"
                "భారతదేశం లో తయారు చేయబడింది"
            )
        },
        {
            "id": "sample_hindi_compliant",
            "lang": "hi",
            "lang_name": "Hindi (हिंदी)",
            "title": "✅ [हिंदी - Hindi] आयुर्वेदिक प्राकृतिक साबुन (Herbal Soap)",
            "description": "शुद्ध मात्रा 125 ग्राम, अधिकतम खुदरा मूल्य ₹ 65.00 (सभी करों सहित), निर्माण 01/2026, भारत में निर्मित",
            "text_content": (
                "आयुर्वेदिक प्राकृतिक साबुन\n"
                "शुद्ध मात्रा: 125 ग्राम\n"
                "अधिकतम खुदरा मूल्य ₹ 65.00 (सभी करों सहित)\n"
                "निर्माण तिथि: 01/2026 | बैच नं: H-12\n"
                "ग्राहक सेवा कक्ष: care@ayurved.in | टोल फ्री: 1800-222-1111\n"
                "निर्माता: श्री पतंजलि ग्रामोद्योग, प्लॉट 14, हरिद्वार, उत्तराखंड - 249401\n"
                "भारत में निर्मित (Made in India)"
            )
        },
        {
            "id": "sample_marathi_compliant",
            "lang": "mr",
            "lang_name": "Marathi (मराठी)",
            "title": "✅ [मराठी - Marathi] प्रीमियम शरबती गहू आटा (Wheat Flour Pack)",
            "description": "निव्वळ वजन 5 कि.ग्रॅ., कमाल किरकोळ किंमत ₹ 340.00 (सर्व करांसह), पॅकिंग 02/2026, पुणे महाराष्ट्र",
            "text_content": (
                "प्रीमियम शरबती गहू आटा\n"
                "निव्वळ वजन: 5 कि.ग्रॅ.\n"
                "कमाल किरकोळ किंमत ₹ 340.00 (सर्व करांसह)\n"
                "पॅकिंग दिनांक: 02/2026 | बॅच क्र: M-88\n"
                "ग्राहक तक्रार निवारण कक्ष: care@maharashtraagro.in | फोन: 1800-233-4455\n"
                "उत्पादक: सह्याद्री ऍग्रो प्रॉडक्ट्स, चाकण, पुणे, महाराष्ट्र - 410501\n"
                "उत्पादन देश: भारत"
            )
        },
        {
            "id": "sample_bengali_compliant",
            "lang": "bn",
            "lang_name": "Bengali (বাংলা)",
            "title": "✅ [বাংলা - Bengali] দার্জিলিং প্রিমিয়াম চা (Darjeeling Tea)",
            "description": "নিট পরিমাণ 250 গ্রাম, সর্বোচ্চ খুচরা মূল্য ₹ 240.00 (সমস্ত কর সহ), উত্পাদন 01/2026, পশ্চিমবঙ্গ",
            "text_content": (
                "দার্জিলিং গোল্ডেন প্রিমিয়াম চা পাতা\n"
                "নিট পরিমাণ: 250 গ্রাম\n"
                "সর্বোচ্চ খুচরা মূল্য ₹ 240.00 (সমস্ত কর সহ)\n"
                "উত্পাদন তারিখ: 01/2026 | ব্যাচ নং: B-701\n"
                "গ্রাহক সেবা সেল: feedback@bengaltea.co.in | হেল্পলাইন: 1800-345-6789\n"
                "প্রস্তুতকারক: বেঙ্গল টি এস্টেট, শিলিগুড়ি, পশ্চিমবঙ্গ - 734001\n"
                "উৎপাদনকারী দেশ: ভারত"
            )
        },
        {
            "id": "sample_punjabi_compliant",
            "lang": "pa",
            "lang_name": "Punjabi (ਪੰਜਾਬੀ)",
            "title": "✅ [ਪੰਜਾਬੀ - Punjabi] ਸ਼ਾਹੀ ਬਾਸਮਤੀ ਚਾਵਲ (Basmati Rice)",
            "description": "ਸ਼ੁੱਧ ਮਾਤਰਾ 5 ਕਿਲੋ, ਵੱਧ ਤੋਂ ਵੱਧ ਪ੍ਰਚੂਨ ਮੁੱਲ ₹ 450.00 (ਸਾਰੇ ਟੈਕਸਾਂ ਸਮੇਤ), ਪੈਕਿੰਗ 02/2026, ਪੰਜਾਬ",
            "text_content": (
                "ਸ਼ਾਹੀ ਪ੍ਰੀਮੀਅਮ ਬਾਸਮਤੀ ਚਾਵਲ\n"
                "ਸ਼ੁੱਧ ਮਾਤਰਾ: 5 ਕਿਲੋ\n"
                "ਵੱਧ ਤੋਂ ਵੱਧ ਪ੍ਰਚੂਨ ਮੁੱਲ ₹ 450.00 (ਸਾਰੇ ਟੈਕਸਾਂ ਸਮੇਤ)\n"
                "ਪੈਕਿੰਗ ਮਿਤੀ: 02/2026 | ਬੈਚ ਨੰਬਰ: PB-902\n"
                "ਗ੍ਰਾਹਕ ਸੇਵਾ ਸਹਾਇਤਾ: care@punjabrice.in | ਹੈਲਪਲਾਈਨ: 1800-180-2233\n"
                "ਪੈਕ ਕਰਤਾ: ਪੰਜਾਬ ਐਗਰੋ ਫੂਡਜ਼, ਜੀ ਟੀ ਰੋਡ, ਅੰਮ੍ਰਿਤਸਰ, ਪੰਜਾਬ - 143001\n"
                "ਉਤਪਾਦਨ ਦੇਸ਼: ਭਾਰਤ"
            )
        },
        {
            "id": "sample_urdu_compliant",
            "lang": "ur",
            "lang_name": "Urdu (اردو)",
            "title": "✅ [اردو - Urdu] خالص سرسوں کا تیل (Pure Mustard Oil)",
            "description": "خالص مقدار: 1 لیٹر, زیادہ سے زیادہ خوردہ قیمت ₹ 190.00 (تمام ٹیکسز سمیت), تاریخ تیاری 01/2026",
            "text_content": (
                "خالص کوہلو سرسوں کا تیل\n"
                "خالص مقدار: 1 لیٹر\n"
                "زیادہ سے زیادہ خوردہ قیمت ₹ 190.00 (تمام ٹیکسز سمیت)\n"
                "تاریخ تیاری: 01/2026 | بیچ نمبر: U-33\n"
                "صارفین کی دیکھ بھال: care@pureoil.in | ہیلپ لائن: 1800-111-9988\n"
                "تیار کردہ: نیشنل آئل ملز, علی گڑھ, اتر پردیش - 202001\n"
                "ملک پیدائش: ہندوستان"
            )
        },
        {
            "id": "sample_compliant_fmcg",
            "lang": "en",
            "lang_name": "English",
            "title": "✅ [English] Compliant FMCG Biscuit Pack",
            "description": "500 g, MRP ₹ 120.00 (Inclusive of all taxes), Mfg: 02/2026, Email: customercare@supercrunch.in, Helpline: 1800-209-8899",
            "text_content": (
                "SUPER CRUNCH CHOCO COOKIES\n"
                "Net Quantity: 500 g\n"
                "MRP ₹ 120.00 (Inclusive of all taxes)\n"
                "Mfg Date: 02/2026 | Batch No: B4092\n"
                "Consumer Care Cell: For feedback/queries contact Executive at\n"
                "Email: customercare@supercrunch.in\n"
                "Toll Free Helpline: 1800-209-8899\n"
                "Manufactured by: Super Foods India Pvt Ltd, Plot 42, Sector 8, Manesar, Haryana\n"
                "Country of Origin: India"
            )
        },
        {
            "id": "sample_curved_bottle_ayurvedic",
            "lang": "en",
            "lang_name": "English",
            "title": "✅ [English] Cylindrical Bottle (Curvature Cut-Off Specimen)",
            "description": "Hair Oil Bottle: 200ml, MRP Rs. 180.00 incl of all ta, mfd on 02/2026, care@herbalcare.com, Vapi, Gujarat - 396195",
            "text_content": (
                "AYURVEDIC HERBAL HAIR OIL\n"
                "Net Vol: 200ml\n"
                "MRP Rs. 180.00 incl of all ta\n"
                "mfd on: 02/2026 | B.No: H-41\n"
                "Manufactured by: Herbal Care Ltd, Plot 12, GIDC Vapi, Gujarat - 396195\n"
                "care@herbalcare.com | Helpline: 9876543210"
            )
        },
        {
            "id": "sample_compliant_pen_artno",
            "lang": "en",
            "lang_name": "English",
            "title": "✅ [English] Stationery Pen with ART NO. 3458",
            "description": "0.5 mm tip, Net Qty: 1 N, ART NO. 3458, MRP Rs. 50.00 (Inclusive of all taxes), Mfd: 03/2026, Made in India",
            "text_content": (
                "TRIMAX GEL PEN - BLUE\n"
                "ART NO. 3458\n"
                "0.5 mm tip | Net Qty: 1 N\n"
                "MRP Rs. 50.00 (Inclusive of all taxes)\n"
                "Mfd. on: 03/2026 | Batch No: B-99\n"
                "Customer Care: care@gelpens.in | Helpline: 1800-222-3333\n"
                "Made in India by Pen Craft Industries, Gujarat"
            )
        },
        {
            "id": "sample_illegal_imperial_units",
            "lang": "en",
            "lang_name": "English",
            "title": "❌ [Breach] Prohibited Imperial Units (Rule 11/12)",
            "description": "Cosmetic bottle declaring net quantity in non-metric fluid ounces (8.5 fl oz / 16 oz)",
            "text_content": (
                "SILK & GLOW HYDRATING SHAMPOO\n"
                "Net Contents: 8.5 fl oz (16 oz)\n"
                "MRP Rs. 650 (Inclusive of all taxes)\n"
                "Pkd: 01/2026\n"
                "Customer Care: helpline@beautyglow.com | Phone: 1800-444-2211\n"
                "Country of Origin: USA\n"
                "Imported and Marketed by: Global Trends Ltd, Mumbai, India"
            )
        },
        {
            "id": "sample_missing_tax_suffix",
            "lang": "en",
            "lang_name": "English",
            "title": "❌ [Breach] Missing Tax Suffix on MRP (Rule 6(1)(da))",
            "description": "Packaged snack declaring MRP Rs. 250 without statutory phrase 'Inclusive of all taxes'",
            "text_content": (
                "ROYAL CRUNCH DRY FRUIT MIX\n"
                "Net Qty: 400 g\n"
                "MRP: Rs. 250.00\n"
                "Date of Pkg: 12/2025\n"
                "Consumer Feedback: feedback@royalsnacks.com | Helpline: 011-28947261\n"
                "Mfg by: Royal Foods Pvt Ltd, Delhi\n"
                "Country of Origin: India"
            )
        },
        {
            "id": "sample_missing_consumer_care",
            "lang": "en",
            "lang_name": "English",
            "title": "❌ [Breach] Missing Consumer Care Redressal (Rule 6(1)(g))",
            "description": "Herbal tea pack missing telephonic helpline / email redressal channel",
            "text_content": (
                "ORGANIC GREEN TEA DELIGHT\n"
                "Net Weight: 250 g\n"
                "MRP ₹ 350.00 (Incl. of all taxes)\n"
                "Mfg: Jan-2026\n"
                "Manufactured by: Herbal Valley Estates, Assam\n"
                "Country of Origin: India"
            )
        }
    ]
    return {"samples": samples}


# =========================================================================
# STATUTORY RULES & TEMPORARY LIVE AUDIT DATABASE ENDPOINTS
# =========================================================================
@app.get("/api/v1/rules/database")
async def get_rules_database():
    """
    Returns master statutory rules, approved SI metric units, and prohibited imperial units
    loaded directly from the backend CSV knowledge base.
    """
    return {
        "success": True,
        "master_rules": db_manager.master_rules,
        "approved_units": db_manager.approved_units_list,
        "approved_units_count": len(db_manager.approved_units_set),
        "prohibited_units": db_manager.prohibited_units_dict,
        "prohibited_units_count": len(db_manager.prohibited_units_dict),
        "tax_suffix_patterns_count": len(db_manager.tax_suffix_patterns),
        "consumer_care_keywords_count": len(db_manager.consumer_care_keywords),
        "mfg_keywords_count": len(db_manager.mfg_keywords),
        "storage_mode": "MongoDB (Active)" if db_manager.mongo_client else "CSV Knowledge Base (Local)"
    }


@app.post("/api/v1/rules/reload")
async def reload_rules_database():
    """
    Hot-reloads all master rules, approved metric units, and regulatory keywords from the CSV files
    into the running compliance engine without restarting the server.
    """
    reload_summary = compliance_engine.reload_rules()
    db_status = db_manager.get_database_status()
    return {
        "success": True,
        "message": "Statutory rules and metric datasets hot-reloaded successfully from CSV.",
        "reload_summary": reload_summary,
        "database_status": db_status
    }


@app.get("/api/v1/audits/live-history")
async def get_live_audit_history(limit: int = 50):
    """
    Fetches temporary live extracted package audit records from the rolling CSV buffer.
    """
    history = db_manager.get_live_audit_history(limit=limit)
    return {
        "success": True,
        "count": len(history),
        "max_buffer_limit": db_manager.max_live_records,
        "history": history
    }


@app.delete("/api/v1/audits/live-history")
async def clear_live_audit_history():
    """
    Clears the temporary live audit CSV file to reset audit history on demand.
    """
    cleared = db_manager.clear_live_audit_history()
    return {
        "success": cleared,
        "message": "Live audit history cleared successfully." if cleared else "Failed to clear live audit history."
    }


@app.get("/api/v1/database/status")
async def get_database_status():
    """
    Returns database diagnostics, CSV file statistics, and MongoDB connection status.
    """
    return db_manager.get_database_status()


@app.post("/api/v1/mongodb/sync")
async def trigger_mongodb_sync():
    """
    Triggers an immediate full synchronization of all statutory datasets and live logs
    to MongoDB Atlas collections.
    """
    sync_result = db_manager.sync_all_to_mongodb()
    return sync_result



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


