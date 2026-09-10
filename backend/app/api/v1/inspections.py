"""
Scanning and the inspection repository.

Every route here is authenticated. Inspectors see their own inspections; senior
officers and admins see everything (enforced in `deps.can_view_inspection`).
"""

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

from app.config import settings
from app.core.ocr import engine_name, extract_segments_from_image, segments_from_plain_text
from app.db import repositories as repo
from app.deps import can_view_inspection, get_current_user, require_role
from app.engine.compliance_engine import LegalMetrologyComplianceEngine
from app.models import (
    InspectionSummary,
    ListingAnalysisRequest,
    PaginatedInspections,
    ReAuditRequest,
    Role,
    TextAnalysisRequest,
)
from app.services.listing_parser import parse_listing

logger = logging.getLogger("legal_metrology_api")
router = APIRouter(tags=["Inspections"])

engine = LegalMetrologyComplianceEngine()

ANGLE_LABELS = ["Front", "Back", "Side", "Top"]


def _summarise(doc: Dict[str, Any]) -> InspectionSummary:
    return InspectionSummary(
        id=doc.get("id", ""),
        created_at=doc.get("created_at", ""),
        status=doc.get("status", "UNKNOWN"),
        overall_score=doc.get("overall_score", 0),
        product_name=doc.get("product_name", ""),
        brand=doc.get("brand", ""),
        violations_count=doc.get("violations_count", 0),
        violation_rule_ids=doc.get("violation_rule_ids", []),
        officer_id=doc.get("officer_id", ""),
        officer_name=doc.get("officer_name", ""),
        source=doc.get("source", "image"),
        evidence_ids=doc.get("evidence_ids", []),
        is_manually_verified=doc.get("is_manually_verified", False),
    )


def _build_payload(report: Dict[str, Any], *, filename: str, segments: List[Dict[str, Any]],
                   extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = {
        "success": True,
        "filename": filename,
        "status": report["status"],
        "overall_score": report["overall_score"],
        "is_manually_verified": report.get("is_manually_verified", False),
        "manual_fields_applied": report.get("manual_fields_applied", []),
        "multilingual_profile": report.get("multilingual_profile", {}),
        "violations": report["violations"],
        "passed_checks": report["passed_checks"],
        "warnings": report["warnings"],
        "extracted_metadata": report["extracted_metadata"],
        "rules_breakdown": report["rules_breakdown"],
        "raw_text_dump": [s.get("text", "") for s in segments],
        "raw_segments": segments,
    }
    if extra:
        payload.update(extra)
    return payload


# --------------------------------------------------------------------------- #
# Scanning
# --------------------------------------------------------------------------- #

@router.post("/analyze-package", status_code=status.HTTP_201_CREATED)
async def analyze_package(
    images: Optional[List[UploadFile]] = File(None, description="1-4 package photographs"),
    image: Optional[UploadFile] = File(None, description="Single-image fallback"),
    ocr_lang: str = "auto",
    ai_engine: str = "rapidocr",
    persist: bool = True,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Primary scanning endpoint. Accepts up to four package angles, runs OCR over each,
    evaluates the aggregated text against the Legal Metrology rule engine, stores the
    photographs as evidence and persists the inspection.
    """
    start = time.time()

    uploads: List[UploadFile] = [f for f in (images or []) if f and f.filename]
    if not uploads and image and image.filename:
        uploads = [image]
    if not uploads:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No image supplied. Upload between 1 and %d package photographs."
                   % settings.MAX_IMAGES_PER_SCAN,
        )
    uploads = uploads[: settings.MAX_IMAGES_PER_SCAN]

    all_segments: List[Dict[str, Any]] = []
    images_meta: List[Dict[str, Any]] = []
    evidence_records: List[Dict[str, Any]] = []
    raw_images: List[tuple] = []
    primary_dims = (1000, 1000)

    for idx, upload in enumerate(uploads):
        data = await upload.read()
        if not data:
            continue
        raw_images.append((upload.filename, data))
        angle = ANGLE_LABELS[idx] if idx < len(ANGLE_LABELS) else "Angle %d" % (idx + 1)

        try:
            segs, dims = extract_segments_from_image(data)
        except ValueError as bad_image:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(bad_image))

        if idx == 0:
            primary_dims = dims

        for seg in segs:
            enriched = dict(seg)
            enriched["image_index"] = idx + 1
            enriched["image_name"] = upload.filename
            enriched["angle"] = angle
            all_segments.append(enriched)

        images_meta.append({
            "image_index": idx + 1, "filename": upload.filename, "angle": angle,
            "segments_count": len(segs), "height": dims[0], "width": dims[1],
        })

        if persist:
            try:
                evidence_records.append(repo.evidence.store_image(data, upload.filename, angle))
            except Exception as exc:
                logger.warning("Evidence storage failed for %s: %s", upload.filename, exc)

    report = engine.evaluate_compliance(segments=all_segments, image_dimensions=primary_dims)

    vlm_result = None
    if ai_engine == "vlm":
        try:
            from app.engine.vlm_engine import vlm_pipeline

            vlm_result = await vlm_pipeline.analyze_multi_angle_package(raw_images, all_segments)
            if vlm_result and vlm_result.get("data", {}).get("brand_name"):
                report["extracted_metadata"]["brand_name"] = vlm_result["data"]["brand_name"]
        except Exception as exc:
            logger.warning("VLM pass failed, continuing with OCR result only: %s", exc)
            vlm_result = {"error": str(exc)}

    payload = _build_payload(
        report,
        filename=uploads[0].filename,
        segments=all_segments,
        extra={
            "all_filenames": [u.filename for u in uploads],
            "images_count": len(uploads),
            "images_processed": images_meta,
            "ai_engine_used": ai_engine,
            "ocr_engine": engine_name(),
            "vlm_info": vlm_result,
            "ocr_lang_requested": ocr_lang,
            "processing_time_ms": round((time.time() - start) * 1000, 2),
            "image_meta": {
                "height": primary_dims[0],
                "width": primary_dims[1],
                "aspect_ratio": round(primary_dims[1] / max(1, primary_dims[0]), 3),
            },
            "evidence": evidence_records,
        },
    )

    if persist:
        doc = repo.inspections.create(payload, user, evidence_records, source="image")
        payload["inspection_id"] = doc["id"]
        repo.audit_log.record(user["id"], user.get("full_name", ""), "SCAN_CREATED", doc["id"],
                              "status=%s score=%s" % (payload["status"], payload["overall_score"]))
    return payload


@router.post("/analyze-text", status_code=status.HTTP_201_CREATED)
def analyze_text(payload: TextAnalysisRequest, user: Dict[str, Any] = Depends(get_current_user)):
    """
    Rules a body of text that was extracted elsewhere - the browser-side Tesseract
    fallback, or an inspector typing a label out by hand.

    This is the ONLY compliance path besides `/analyze-package`: the browser never
    decides compliance itself, so a phone and the server always agree.
    """
    dims = tuple(payload.image_dimensions) if payload.image_dimensions else (1000, 1000)
    segments = payload.segments or segments_from_plain_text(payload.raw_text, dims)
    if not segments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No text supplied. Provide `raw_text` or pre-extracted `segments`.",
        )

    report = engine.evaluate_compliance(segments=segments, image_dimensions=dims)
    result = _build_payload(report, filename=payload.filename, segments=segments,
                            extra={"source": payload.source})

    if payload.persist:
        doc = repo.inspections.create(result, user, [], source=payload.source or "text")
        result["inspection_id"] = doc["id"]
    return result


@router.post("/analyze-listing", status_code=status.HTTP_201_CREATED)
def analyze_listing(payload: ListingAnalysisRequest, user: Dict[str, Any] = Depends(get_current_user)):
    """
    Checks an e-commerce product listing (Rule 6 applies to online listings too).

    Accepts pasted listing text or copied page HTML. It deliberately does not fetch
    `source_url` server-side: fetching arbitrary user-supplied URLs is a server-side
    request forgery hole, and marketplace pages are JavaScript-rendered anyway. The
    URL is kept as provenance only.
    """
    text = parse_listing(payload.listing_text, payload.listing_html)
    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Listing is empty. Paste the listing text or the copied page HTML.",
        )

    segments = segments_from_plain_text(text, (1000, 1000))
    report = engine.evaluate_compliance(segments=segments, image_dimensions=(1000, 1000))

    title = payload.product_title or "E-commerce listing"
    if not report["extracted_metadata"].get("product_name"):
        report["extracted_metadata"]["product_name"] = title

    result = _build_payload(report, filename=title, segments=segments, extra={
        "source": "listing",
        "source_url": payload.source_url,
        "platform": payload.platform,
        "listing_characters": len(text),
    })

    if payload.persist:
        doc = repo.inspections.create(result, user, [], source="listing")
        result["inspection_id"] = doc["id"]
    return result


@router.post("/verify-and-audit")
def verify_and_audit(payload: ReAuditRequest, user: Dict[str, Any] = Depends(get_current_user)):
    """
    Inspector correction pass: re-runs the rules with human-verified values so an OCR
    misread does not become a false violation on an enforcement notice.
    """
    segments = payload.segments or []
    dims = tuple(payload.image_dimensions) if payload.image_dimensions else (1000, 1000)
    existing = None

    if payload.inspection_id:
        existing = repo.inspections.by_id(payload.inspection_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found.")
        if not can_view_inspection(user, existing):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="You may only revise your own inspections.")
        if not segments:
            segments = (existing.get("report") or {}).get("raw_segments", [])

    report = engine.evaluate_compliance(
        segments=segments, image_dimensions=dims, manual_overrides=payload.manual_overrides
    )
    result = _build_payload(report, filename="Re-audit (inspector verified)", segments=segments)
    result["is_manually_verified"] = True

    if existing:
        result["evidence"] = existing.get("evidence", [])
        result["inspection_id"] = existing["id"]
        repo.inspections.update_report(existing["id"], result)
        repo.audit_log.record(
            user["id"], user.get("full_name", ""), "INSPECTION_REVISED", existing["id"],
            "fields=%s" % ",".join(report.get("manual_fields_applied", [])),
        )
    return result


# --------------------------------------------------------------------------- #
# Repository: search, retrieval, evidence
# --------------------------------------------------------------------------- #

@router.get("/inspections", response_model=PaginatedInspections)
def search_inspections(
    q: str = Query("", description="Free text over product, brand, inspection id, officer"),
    status_filter: str = Query("", alias="status"),
    rule: str = "",
    officer_id: str = "",
    date_from: str = "",
    date_to: str = "",
    min_score: Optional[int] = Query(None, ge=0, le=100),
    max_score: Optional[int] = Query(None, ge=0, le=100),
    source: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Search and retrieval over previously scanned products."""
    # An inspector is pinned to their own records regardless of what they ask for.
    if user.get("role") == Role.INSPECTOR.value:
        officer_id = user["id"]

    query = repo.inspections.build_query(
        q=q, status=status_filter, rule=rule, officer_id=officer_id,
        date_from=date_from, date_to=date_to,
        min_score=min_score, max_score=max_score, source=source,
    )
    items, total = repo.inspections.search(query, page=page, page_size=page_size)
    return PaginatedInspections(
        items=[_summarise(d) for d in items],
        total=total, page=page, page_size=page_size,
        pages=max(1, -(-total // page_size)),
    )


@router.get("/inspections/{inspection_id}")
def get_inspection(inspection_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    doc = repo.inspections.by_id(inspection_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found.")
    if not can_view_inspection(user, doc):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You do not have access to this inspection.")
    doc["audit_trail"] = repo.audit_log.recent(limit=50, target=inspection_id)
    return doc


@router.get("/evidence/{evidence_id}")
def get_evidence(evidence_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """Serves a stored package photograph. Authenticated: evidence backs legal notices."""
    data = repo.evidence.load(evidence_id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found.")
    return Response(content=data, media_type="image/jpeg",
                    headers={"Cache-Control": "private, max-age=3600"})


@router.get("/dashboard/stats")
def dashboard_stats(
    days: int = Query(30, ge=1, le=365),
    user: Dict[str, Any] = Depends(require_role(Role.INSPECTOR)),
):
    """
    Enforcement dashboard aggregates. An inspector sees their own activity; senior
    officers and admins see the whole jurisdiction.
    """
    officer_id = user["id"] if user.get("role") == Role.INSPECTOR.value else ""
    stats = repo.inspections.dashboard_stats(days=days, officer_id=officer_id)
    stats["scope"] = "own" if officer_id else "all"
    return stats
