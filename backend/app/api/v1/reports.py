"""Report generation: PDF, editable DOCX, and bulk XLSX."""

import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.db import repositories as repo
from app.deps import can_view_inspection, get_current_user, require_role
from app.models import Role
from app.services.report_docx import render_docx
from app.services.report_pdf import render_pdf
from app.services.report_xlsx import render_xlsx

router = APIRouter(prefix="/reports", tags=["Reports"])

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _safe_filename(value: str, fallback: str = "report") -> str:
    """Strips anything that could break a Content-Disposition header or a filesystem."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (value or "").strip())[:60].strip("._")
    return cleaned or fallback


@router.get("/{inspection_id}")
def download_report(
    inspection_id: str,
    fmt: str = Query("pdf", pattern="^(pdf|docx)$", alias="format"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Downloads a single compliance report.

    `pdf`  - final, printable, real selectable text.
    `docx` - editable, for an officer to adapt before issuing a statutory notice.
    """
    inspection = repo.inspections.by_id(inspection_id)
    if not inspection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found.")
    if not can_view_inspection(user, inspection):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You do not have access to this inspection.")

    content = render_pdf(inspection) if fmt == "pdf" else render_docx(inspection)
    name = "%s_%s.%s" % (
        _safe_filename(inspection.get("product_name", ""), "compliance_report"),
        inspection_id, fmt,
    )
    repo.audit_log.record(user["id"], user.get("full_name", ""), "REPORT_EXPORTED",
                          inspection_id, "format=%s" % fmt)
    return Response(
        content=content,
        media_type=MEDIA_TYPES[fmt],
        headers={"Content-Disposition": 'attachment; filename="%s"' % name},
    )


@router.get("")
def bulk_export(
    q: str = "",
    status_filter: str = Query("", alias="status"),
    rule: str = "",
    officer_id: str = "",
    date_from: str = "",
    date_to: str = "",
    min_score: Optional[int] = Query(None, ge=0, le=100),
    max_score: Optional[int] = Query(None, ge=0, le=100),
    source: str = "",
    limit: int = Query(2000, ge=1, le=5000),
    user: Dict[str, Any] = Depends(require_role(Role.SENIOR_OFFICER)),
):
    """
    Exports every inspection matching the current repository filters as a workbook
    (inspections, violations, and a summary sheet). Senior officers and above.
    """
    query = repo.inspections.build_query(
        q=q, status=status_filter, rule=rule, officer_id=officer_id,
        date_from=date_from, date_to=date_to,
        min_score=min_score, max_score=max_score, source=source,
    )
    rows = repo.inspections.all_matching(query, limit=limit)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No inspections match these filters.")

    content = render_xlsx(rows, title="Legal Metrology compliance export")
    repo.audit_log.record(user["id"], user.get("full_name", ""), "BULK_EXPORTED",
                          detail="rows=%d" % len(rows))
    return Response(
        content=content,
        media_type=MEDIA_TYPES["xlsx"],
        headers={"Content-Disposition": 'attachment; filename="compliance_export.xlsx"'},
    )
