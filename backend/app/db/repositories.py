"""
Repository layer: every read/write of application data goes through here.

Routers never touch the store directly, so swapping the backend (Mongo <-> JSON)
or adding caching stays a one-file change.
"""

import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.db.store import get_store, new_id

logger = logging.getLogger("legal_metrology_repo")

USERS = "users"
INSPECTIONS = "inspections"
AUDIT_LOG = "audit_log"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #

class UserRepository:
    def create(self, email: str, password_hash: str, full_name: str, role: str,
               designation: str = "", jurisdiction: str = "") -> Dict[str, Any]:
        doc = {
            "id": new_id("usr"),
            "email": email.lower().strip(),
            "password_hash": password_hash,
            "full_name": full_name.strip(),
            "role": role,
            "designation": designation.strip(),
            "jurisdiction": jurisdiction.strip(),
            "is_active": True,
            "created_at": utcnow_iso(),
        }
        get_store().insert(USERS, doc)
        return doc

    def by_email(self, email: str) -> Optional[Dict[str, Any]]:
        return get_store().find_one(USERS, {"email": email.lower().strip()})

    def by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return get_store().find_one(USERS, {"id": user_id})

    def list_all(self) -> List[Dict[str, Any]]:
        return get_store().find(USERS, {}, sort=[("created_at", -1)])

    def count(self) -> int:
        return get_store().count(USERS, {})

    def set_active(self, user_id: str, active: bool) -> bool:
        return get_store().update_one(USERS, {"id": user_id}, {"is_active": active})

    def set_role(self, user_id: str, role: str) -> bool:
        return get_store().update_one(USERS, {"id": user_id}, {"role": role})


# --------------------------------------------------------------------------- #
# Evidence (photographs / supporting material)
# --------------------------------------------------------------------------- #

class EvidenceRepository:
    """
    Stores package photographs. Images are downscaled before persisting: an Atlas
    free tier is 512 MB and a phone camera frame is ~4 MB, so storing originals
    would exhaust the cluster within roughly a hundred inspections.
    """

    def store_image(self, data: bytes, filename: str, angle: str = "") -> Dict[str, Any]:
        from PIL import Image, ImageOps

        from app.config import settings

        blob_id = new_id("evd")
        stored, width, height = data, 0, 0
        try:
            img = Image.open(io.BytesIO(data))
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.thumbnail(
                (settings.EVIDENCE_MAX_DIMENSION, settings.EVIDENCE_MAX_DIMENSION),
                Image.LANCZOS,
            )
            width, height = img.size
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=settings.EVIDENCE_JPEG_QUALITY, optimize=True)
            stored = buf.getvalue()
        except Exception as exc:
            # Keep the original rather than losing the evidence entirely.
            logger.warning("Could not re-encode evidence %s (%s); storing as uploaded.", filename, exc)

        get_store().put_blob(blob_id, stored)
        return {
            "evidence_id": blob_id,
            "filename": filename,
            "angle": angle,
            "bytes": len(stored),
            "width": width,
            "height": height,
            "captured_at": utcnow_iso(),
        }

    def load(self, evidence_id: str) -> Optional[bytes]:
        return get_store().get_blob(evidence_id)


# --------------------------------------------------------------------------- #
# Inspections
# --------------------------------------------------------------------------- #

class InspectionRepository:
    def create(self, payload: Dict[str, Any], officer: Dict[str, Any],
               evidence: Optional[List[Dict[str, Any]]] = None,
               source: str = "image") -> Dict[str, Any]:
        meta = payload.get("extracted_metadata") or {}
        violations = payload.get("violations") or []
        doc = {
            "id": new_id("insp"),
            "created_at": utcnow_iso(),
            "officer_id": officer.get("id", ""),
            "officer_name": officer.get("full_name", ""),
            "jurisdiction": officer.get("jurisdiction", ""),
            "source": source,
            "status": payload.get("status", "UNKNOWN"),
            "overall_score": int(payload.get("overall_score", 0) or 0),
            "product_name": str(meta.get("brand_name") or payload.get("filename") or "Unnamed product"),
            "brand": str(meta.get("brand_name") or ""),
            "violations_count": len(violations),
            "violation_rule_ids": [v.get("rule_id", "") for v in violations if v.get("rule_id")],
            "is_manually_verified": bool(payload.get("is_manually_verified", False)),
            "evidence": evidence or [],
            "evidence_ids": [e["evidence_id"] for e in (evidence or [])],
            "report": payload,
        }
        get_store().insert(INSPECTIONS, doc)
        return doc

    def by_id(self, inspection_id: str) -> Optional[Dict[str, Any]]:
        return get_store().find_one(INSPECTIONS, {"id": inspection_id})

    def update_report(self, inspection_id: str, payload: Dict[str, Any]) -> bool:
        violations = payload.get("violations") or []
        return get_store().update_one(
            INSPECTIONS,
            {"id": inspection_id},
            {
                "report": payload,
                "status": payload.get("status", "UNKNOWN"),
                "overall_score": int(payload.get("overall_score", 0) or 0),
                "violations_count": len(violations),
                "violation_rule_ids": [v.get("rule_id", "") for v in violations if v.get("rule_id")],
                "is_manually_verified": bool(payload.get("is_manually_verified", False)),
                "updated_at": utcnow_iso(),
            },
        )

    # -- search ------------------------------------------------------------- #

    @staticmethod
    def build_query(q: str = "", status: str = "", rule: str = "", officer_id: str = "",
                    date_from: str = "", date_to: str = "", min_score: Optional[int] = None,
                    max_score: Optional[int] = None, source: str = "") -> Dict[str, Any]:
        query: Dict[str, Any] = {}
        if status:
            query["status"] = status
        if rule:
            query["violation_rule_ids"] = {"$in": [rule]}
        if officer_id:
            query["officer_id"] = officer_id
        if source:
            query["source"] = source

        created: Dict[str, Any] = {}
        if date_from:
            created["$gte"] = date_from
        if date_to:
            # Inclusive end-of-day: a bare "2026-09-10" would otherwise exclude
            # everything recorded during that day.
            created["$lte"] = date_to if len(date_to) > 10 else date_to + "T23:59:59.999999+00:00"
        if created:
            query["created_at"] = created

        score: Dict[str, Any] = {}
        if min_score is not None:
            score["$gte"] = min_score
        if max_score is not None:
            score["$lte"] = max_score
        if score:
            query["overall_score"] = score

        if q:
            term = q.strip()
            query["$or"] = [
                {"product_name": {"$regex": term}},
                {"brand": {"$regex": term}},
                {"id": {"$regex": term}},
                {"officer_name": {"$regex": term}},
            ]
        return query

    def search(self, query: Dict[str, Any], page: int = 1, page_size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        store = get_store()
        total = store.count(INSPECTIONS, query)
        items = store.find(
            INSPECTIONS, query,
            sort=[("created_at", -1)],
            skip=max(0, (page - 1) * page_size),
            limit=page_size,
        )
        return items, total

    def all_matching(self, query: Dict[str, Any], limit: int = 5000) -> List[Dict[str, Any]]:
        return get_store().find(INSPECTIONS, query, sort=[("created_at", -1)], limit=limit)

    # -- dashboard aggregation ---------------------------------------------- #

    def dashboard_stats(self, days: int = 30, officer_id: str = "") -> Dict[str, Any]:
        """
        Aggregates for the enforcement dashboard.

        Computed in Python over a bounded window rather than as a Mongo pipeline so
        the JSON and Mongo backends return byte-identical numbers. The date filter
        is still pushed into the query, so the `created_at` index does the heavy work.
        """
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        base: Dict[str, Any] = {"created_at": {"$gte": since}}
        if officer_id:
            base["officer_id"] = officer_id

        rows = get_store().find(INSPECTIONS, base, sort=[("created_at", -1)], limit=20000)

        today = datetime.now(timezone.utc).date().isoformat()
        week_start = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        total = len(rows)
        compliant = sum(1 for r in rows if r.get("status") == "COMPLIANT")
        non_compliant = sum(1 for r in rows if r.get("status") == "NON_COMPLIANT")
        scores = [r.get("overall_score", 0) for r in rows]

        by_rule: Dict[str, int] = {}
        for r in rows:
            for rid in r.get("violation_rule_ids", []):
                by_rule[rid] = by_rule.get(rid, 0) + 1

        by_brand: Dict[str, Dict[str, int]] = {}
        for r in rows:
            brand = (r.get("brand") or "").strip() or "Unidentified"
            slot = by_brand.setdefault(brand, {"total": 0, "violations": 0})
            slot["total"] += 1
            slot["violations"] += r.get("violations_count", 0)

        trend: Dict[str, Dict[str, int]] = {}
        for i in range(days - 1, -1, -1):
            day = (datetime.now(timezone.utc) - timedelta(days=i)).date().isoformat()
            trend[day] = {"date": day, "total": 0, "compliant": 0, "non_compliant": 0}
        for r in rows:
            day = str(r.get("created_at", ""))[:10]
            if day in trend:
                trend[day]["total"] += 1
                if r.get("status") == "COMPLIANT":
                    trend[day]["compliant"] += 1
                else:
                    trend[day]["non_compliant"] += 1

        severity = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for r in rows:
            for v in (r.get("report") or {}).get("violations", []):
                sev = str(v.get("severity", "MEDIUM")).upper()
                severity[sev] = severity.get(sev, 0) + 1

        top_brands = sorted(
            [{"brand": b, **v} for b, v in by_brand.items()],
            key=lambda x: (-x["violations"], -x["total"]),
        )[:8]

        return {
            "window_days": days,
            "total_inspections": total,
            "inspections_today": sum(1 for r in rows if str(r.get("created_at", ""))[:10] == today),
            "inspections_this_week": sum(1 for r in rows if str(r.get("created_at", "")) >= week_start),
            "compliant": compliant,
            "non_compliant": non_compliant,
            "compliance_rate": round((compliant / total) * 100, 1) if total else 0.0,
            "average_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
            "total_violations": sum(r.get("violations_count", 0) for r in rows),
            "violations_by_rule": sorted(
                [{"rule_id": k, "count": v} for k, v in by_rule.items()],
                key=lambda x: -x["count"],
            ),
            "severity_split": [{"severity": k, "count": v} for k, v in severity.items()],
            "trend": list(trend.values()),
            "top_offending_brands": top_brands,
            "recent": [
                {
                    "id": r.get("id"), "created_at": r.get("created_at"),
                    "product_name": r.get("product_name"), "brand": r.get("brand"),
                    "status": r.get("status"), "overall_score": r.get("overall_score"),
                    "violations_count": r.get("violations_count"),
                    "officer_name": r.get("officer_name"),
                }
                for r in rows[:10]
            ],
        }


# --------------------------------------------------------------------------- #
# Audit trail
# --------------------------------------------------------------------------- #

class AuditLogRepository:
    def record(self, actor_id: str, actor_name: str, action: str,
               target: str = "", detail: str = "") -> None:
        try:
            get_store().insert(AUDIT_LOG, {
                "id": new_id("log"),
                "created_at": utcnow_iso(),
                "actor_id": actor_id,
                "actor_name": actor_name,
                "action": action,
                "target": target,
                "detail": detail,
            })
        except Exception as exc:
            # An audit-trail failure must never break the user's actual request.
            logger.warning("Audit log write failed for action %s: %s", action, exc)

    def recent(self, limit: int = 100, target: str = "") -> List[Dict[str, Any]]:
        query = {"target": target} if target else {}
        return get_store().find(AUDIT_LOG, query, sort=[("created_at", -1)], limit=limit)


users = UserRepository()
inspections = InspectionRepository()
evidence = EvidenceRepository()
audit_log = AuditLogRepository()
