"""
PDF compliance report (ReportLab, server-side).

Replaces the previous html2canvas + jsPDF approach, which pasted a screenshot of
the dashboard into a PDF: the text could not be selected, searched or copied into
a notice, and a single page weighed several megabytes. This renders real text.
"""

import io
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.db import repositories as repo
from app.services.report_content import build_report_content

INK = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#64748B")
RULE = colors.HexColor("#CBD5E1")
PRIMARY = colors.HexColor("#1B4D89")
BAND = colors.HexColor("#F1F5F9")

SEVERITY_COLOURS = {
    "CRITICAL": colors.HexColor("#B42318"),
    "HIGH": colors.HexColor("#B42318"),
    "MEDIUM": colors.HexColor("#B45309"),
    "LOW": colors.HexColor("#B45309"),
    "ADVISORY": colors.HexColor("#64748B"),
}

STATUS_COLOURS = {
    "COMPLIANT": colors.HexColor("#0F7B4F"),
    "NON_COMPLIANT": colors.HexColor("#B42318"),
    "PARTIALLY_COMPLIANT": colors.HexColor("#B45309"),
}


def _styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontName="Helvetica-Bold",
                                fontSize=15, leading=19, textColor=INK, alignment=TA_CENTER),
        "subtitle": ParagraphStyle("st", parent=base["Normal"], fontSize=8.5, leading=12,
                                   textColor=MUTED, alignment=TA_CENTER),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold",
                             fontSize=10.5, leading=14, textColor=PRIMARY,
                             spaceBefore=12, spaceAfter=5),
        "body": ParagraphStyle("b", parent=base["Normal"], fontSize=8.5, leading=12, textColor=INK),
        "small": ParagraphStyle("s", parent=base["Normal"], fontSize=7.5, leading=10, textColor=MUTED),
        "cell": ParagraphStyle("c", parent=base["Normal"], fontSize=8, leading=11, textColor=INK),
        "cellb": ParagraphStyle("cb", parent=base["Normal"], fontName="Helvetica-Bold",
                                fontSize=8, leading=11, textColor=INK),
        "legal": ParagraphStyle("l", parent=base["Normal"], fontSize=7, leading=9.5,
                                textColor=MUTED, alignment=TA_JUSTIFY),
    }


def _header_footer(canvas, doc):
    canvas.saveState()
    w, h = A4

    canvas.setFillColor(PRIMARY)
    canvas.rect(0, h - 12 * mm, w, 12 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 8.5)
    canvas.drawString(15 * mm, h - 8 * mm, "GOVERNMENT OF INDIA  |  DEPARTMENT OF CONSUMER AFFAIRS")
    canvas.setFont("Helvetica", 7.5)
    canvas.drawRightString(w - 15 * mm, h - 8 * mm, "Legal Metrology (Packaged Commodities) Rules, 2011")

    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(15 * mm, 13 * mm, w - 15 * mm, 13 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(15 * mm, 9 * mm, "Computer-generated compliance report - valid without signature for internal record.")
    canvas.drawRightString(w - 15 * mm, 9 * mm, "Page %d" % doc.page)
    canvas.restoreState()


def _kv_table(rows: List[List[Any]], widths: List[float]) -> Table:
    table = Table(rows, colWidths=widths, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), BAND),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def render_pdf(inspection: Dict[str, Any]) -> bytes:
    c = build_report_content(inspection)
    s = _styles()
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title="Compliance Report %s" % c["inspection_id"],
        author="Legal Metrology Compliance Auditing System",
        subject="Legal Metrology (Packaged Commodities) Rules, 2011",
    )

    story: List[Any] = [
        Paragraph("STATUTORY COMPLIANCE INSPECTION REPORT", s["title"]),
        Paragraph("Issued under the Legal Metrology Act, 2009 and the Legal Metrology "
                  "(Packaged Commodities) Rules, 2011", s["subtitle"]),
        Spacer(1, 8),
    ]

    # --- Verdict band -------------------------------------------------------
    verdict_colour = STATUS_COLOURS.get(c["status"], MUTED)
    verdict = Table(
        [[Paragraph('<font color="white" size="13"><b>%s</b></font>' % c["status_label"],
                    ParagraphStyle("v", alignment=TA_CENTER, fontSize=13, leading=16)),
          Paragraph('<font color="white" size="13"><b>%d / 100</b></font><br/>'
                    '<font color="white" size="7">COMPLIANCE SCORE</font>' % c["overall_score"],
                    ParagraphStyle("vs", alignment=TA_CENTER, fontSize=13, leading=15))]],
        colWidths=[110 * mm, 70 * mm],
    )
    verdict.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), verdict_colour),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story += [verdict, Spacer(1, 12)]

    # --- Inspection particulars --------------------------------------------
    story.append(Paragraph("1. INSPECTION PARTICULARS", s["h2"]))
    story.append(_kv_table([
        [Paragraph("Inspection ID", s["cellb"]), Paragraph(c["inspection_id"], s["cell"]),
         Paragraph("Date of inspection", s["cellb"]), Paragraph(c["created_at"], s["cell"])],
        [Paragraph("Product", s["cellb"]), Paragraph(c["product_name"], s["cell"]),
         Paragraph("Brand", s["cellb"]), Paragraph(c["brand"], s["cell"])],
        [Paragraph("Inspecting officer", s["cellb"]), Paragraph(c["officer_name"], s["cell"]),
         Paragraph("Jurisdiction", s["cellb"]), Paragraph(c["jurisdiction"], s["cell"])],
        [Paragraph("Evidence source", s["cellb"]), Paragraph(c["source"].title(), s["cell"]),
         Paragraph("Label language", s["cellb"]), Paragraph(str(c["language_profile"]), s["cell"])],
    ], [32 * mm, 58 * mm, 32 * mm, 58 * mm]))

    if c["is_manually_verified"]:
        story += [Spacer(1, 4), Paragraph(
            "Fields verified/corrected by the inspecting officer: <b>%s</b>"
            % (", ".join(c["manual_fields_applied"]) or "yes"), s["small"])]

    # --- Declarations -------------------------------------------------------
    story.append(Paragraph("2. MANDATORY DECLARATIONS DETECTED", s["h2"]))
    decl_rows = [[Paragraph("Declaration required", s["cellb"]),
                  Paragraph("Value found on package", s["cellb"]),
                  Paragraph("Rule", s["cellb"])]]
    for label, value, rule in c["declarations"]:
        missing = value == "Not detected"
        decl_rows.append([
            Paragraph(label, s["cell"]),
            Paragraph('<font color="%s">%s</font>' % ("#B42318" if missing else "#0F172A", value), s["cell"]),
            Paragraph(rule, s["cell"]),
        ])
    decl = Table(decl_rows, colWidths=[68 * mm, 82 * mm, 30 * mm], repeatRows=1, hAlign="LEFT")
    decl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BAND),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(decl)

    # --- Violations ---------------------------------------------------------
    story.append(Paragraph("3. CONTRAVENTIONS IDENTIFIED (%d)" % len(c["violations"]), s["h2"]))
    if not c["violations"]:
        story.append(Paragraph(
            "No contravention was identified. All mandatory declarations verified by the "
            "system were found to be present and in the prescribed form.", s["body"]))
    else:
        for i, v in enumerate(c["violations"], 1):
            sev = str(v.get("severity", "MEDIUM")).upper()
            block = [
                Table([[
                    Paragraph('<b>%d. %s</b>' % (i, v.get("rule_name", v.get("rule_id", "Violation"))), s["cell"]),
                    Paragraph('<font color="white"><b>%s</b></font>' % sev,
                              ParagraphStyle("sev", fontSize=7.5, leading=10, alignment=TA_CENTER)),
                ]], colWidths=[152 * mm, 28 * mm], hAlign="LEFT", style=TableStyle([
                    ("BACKGROUND", (1, 0), (1, 0), SEVERITY_COLOURS.get(sev, MUTED)),
                    ("BACKGROUND", (0, 0), (0, 0), BAND),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("GRID", (0, 0), (-1, -1), 0.4, RULE),
                ])),
                _kv_table([
                    [Paragraph("Legal reference", s["cellb"]),
                     Paragraph(str(v.get("legal_reference", "-")), s["cell"])],
                    [Paragraph("Finding", s["cellb"]),
                     Paragraph(str(v.get("description", "-")), s["cell"])],
                    [Paragraph("Evidence", s["cellb"]),
                     Paragraph(str(v.get("found_text", "-")), s["cell"])],
                    [Paragraph("Required action", s["cellb"]),
                     Paragraph(str(v.get("remediation", "-")), s["cell"])],
                    [Paragraph("Penalty band", s["cellb"]),
                     Paragraph(str(v.get("penalty_band", "-")), s["cell"])],
                ], [32 * mm, 148 * mm]),
                Spacer(1, 8),
            ]
            story.append(KeepTogether(block))

    # --- Verified checks ----------------------------------------------------
    if c["passed_checks"]:
        story.append(Paragraph("4. DECLARATIONS VERIFIED AS COMPLIANT (%d)" % len(c["passed_checks"]), s["h2"]))
        rows = [[Paragraph("Rule", s["cellb"]), Paragraph("Verification", s["cellb"])]]
        for chk in c["passed_checks"]:
            rows.append([
                Paragraph(str(chk.get("rule_name", chk.get("rule_id", "-"))), s["cell"]),
                Paragraph(str(chk.get("evidence", chk.get("description", "-"))), s["cell"]),
            ])
        passed = Table(rows, colWidths=[70 * mm, 110 * mm], repeatRows=1, hAlign="LEFT")
        passed.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BAND),
            ("GRID", (0, 0), (-1, -1), 0.4, RULE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(passed)

    # --- Evidence photographs ----------------------------------------------
    thumbs = _evidence_flowables(c["evidence"])
    if thumbs:
        story += [PageBreak(), Paragraph("5. PHOTOGRAPHIC EVIDENCE", s["h2"]), thumbs]

    # --- Declaration & signature -------------------------------------------
    story += [
        Spacer(1, 14),
        Paragraph("DECLARATION", s["h2"]),
        Paragraph(c["disclaimer"], s["legal"]),
        Spacer(1, 20),
        Table([[
            Paragraph("_______________________________<br/><b>%s</b><br/>"
                      "<font size='7'>Inspecting Officer, Legal Metrology</font>" % c["officer_name"], s["small"]),
            Paragraph("_______________________________<br/><b>Controller / Authorised Officer</b><br/>"
                      "<font size='7'>Countersignature</font>", s["small"]),
        ]], colWidths=[90 * mm, 90 * mm], hAlign="LEFT"),
        Spacer(1, 8),
        Paragraph("Report generated on %s  |  Reference: %s" % (c["generated_at"], c["inspection_id"]), s["small"]),
    ]

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


def _evidence_flowables(evidence: List[Dict[str, Any]]):
    """Lays the stored package photographs out two per row, scaled to fit."""
    cells: List[Any] = []
    for item in evidence[:4]:
        data = repo.evidence.load(item.get("evidence_id", ""))
        if not data:
            continue
        try:
            img = Image(io.BytesIO(data))
            ratio = img.imageHeight / float(img.imageWidth or 1)
            img.drawWidth = 85 * mm
            img.drawHeight = min(85 * mm * ratio, 95 * mm)
            caption = ParagraphStyle("cap", fontSize=7, leading=9, textColor=MUTED, alignment=TA_CENTER)
            cells.append([img, Paragraph("%s - %s" % (item.get("angle", "Angle"),
                                                      item.get("filename", "")), caption)])
        except Exception:
            continue

    if not cells:
        return None

    rows = []
    for i in range(0, len(cells), 2):
        pair = cells[i:i + 2]
        rows.append([pair[0][0], pair[1][0] if len(pair) > 1 else ""])
        rows.append([pair[0][1], pair[1][1] if len(pair) > 1 else ""])

    table = Table(rows, colWidths=[90 * mm, 90 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table
