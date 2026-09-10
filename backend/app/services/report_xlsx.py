"""
Bulk spreadsheet export (openpyxl).

Enforcement reporting works on aggregates - "every non-compliant pack in this
district last month" - so the repository exports a workbook an officer can pivot,
sort and forward, not a stack of individual PDFs.
"""

import io
from typing import Any, Dict, List

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.services.report_content import build_report_content

HEADER_FILL = PatternFill("solid", fgColor="1B4D89")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=10)
TITLE_FONT = Font(bold=True, size=13, color="0F172A")
THIN = Side(style="thin", color="CBD5E1")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

STATUS_FILL = {
    "COMPLIANT": PatternFill("solid", fgColor="DCFCE7"),
    "NON_COMPLIANT": PatternFill("solid", fgColor="FEE2E2"),
    "PARTIALLY_COMPLIANT": PatternFill("solid", fgColor="FEF3C7"),
}


def _write_header(ws, headers: List[str], row: int = 1) -> None:
    for col, name in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=name)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cell.border = BORDER
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def _autosize(ws, widths: List[int]) -> None:
    for i, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width


def render_xlsx(inspections: List[Dict[str, Any]], title: str = "Compliance export") -> bytes:
    wb = Workbook()

    # --- Sheet 1: one row per inspection -----------------------------------
    ws = wb.active
    ws.title = "Inspections"
    ws["A1"] = title
    ws["A1"].font = TITLE_FONT
    ws["A2"] = "Legal Metrology (Packaged Commodities) Rules, 2011  -  %d record(s)" % len(inspections)
    ws["A2"].font = Font(size=9, color="64748B")

    headers = ["Inspection ID", "Date", "Product", "Brand", "Status", "Score",
               "Violations", "Rules contravened", "Officer", "Jurisdiction",
               "Source", "MRP", "Net quantity", "Mfg / packing date",
               "Consumer care", "Country of origin", "Officer verified"]
    _write_header(ws, headers, row=4)

    for r, inspection in enumerate(inspections, start=5):
        c = build_report_content(inspection)
        decl = {label: value for label, value, _ in c["declarations"]}
        values = [
            c["inspection_id"], c["created_at"], c["product_name"], c["brand"],
            c["status_label"], c["overall_score"], len(c["violations"]),
            ", ".join(v.get("rule_id", "") for v in c["violations"]),
            c["officer_name"], c["jurisdiction"], c["source"].title(),
            decl.get("Maximum Retail Price (inclusive of all taxes)", "-"),
            decl.get("Net quantity", "-"),
            decl.get("Month & year of manufacture / packing", "-"),
            decl.get("Consumer care details", "-"),
            decl.get("Country of origin", "-"),
            "Yes" if c["is_manually_verified"] else "No",
        ]
        for col, value in enumerate(values, 1):
            cell = ws.cell(row=r, column=col, value=value)
            cell.border = BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=col in (3, 8, 15))
            if col == 5:
                cell.fill = STATUS_FILL.get(c["status"], PatternFill())
                cell.font = Font(bold=True, size=10)

    _autosize(ws, [22, 22, 30, 18, 18, 8, 10, 34, 20, 18, 12, 26, 18, 20, 30, 16, 14])
    ws.auto_filter.ref = "A4:%s%d" % (get_column_letter(len(headers)), max(5, 4 + len(inspections)))

    # --- Sheet 2: one row per violation ------------------------------------
    vs = wb.create_sheet("Violations")
    v_headers = ["Inspection ID", "Product", "Brand", "Rule ID", "Rule",
                 "Severity", "Legal reference", "Finding", "Evidence",
                 "Required action", "Penalty band", "Officer", "Date"]
    _write_header(vs, v_headers)

    row = 2
    for inspection in inspections:
        c = build_report_content(inspection)
        for v in c["violations"]:
            values = [
                c["inspection_id"], c["product_name"], c["brand"],
                v.get("rule_id", ""), v.get("rule_name", ""),
                str(v.get("severity", "")).upper(), v.get("legal_reference", ""),
                v.get("description", ""), v.get("found_text", ""),
                v.get("remediation", ""), v.get("penalty_band", ""),
                c["officer_name"], c["created_at"],
            ]
            for col, value in enumerate(values, 1):
                cell = vs.cell(row=row, column=col, value=value)
                cell.border = BORDER
                cell.alignment = Alignment(vertical="top", wrap_text=col in (5, 7, 8, 9, 10))
            row += 1

    _autosize(vs, [22, 26, 16, 26, 32, 12, 34, 40, 30, 40, 22, 20, 22])
    vs.auto_filter.ref = "A1:%s%d" % (get_column_letter(len(v_headers)), max(2, row - 1))

    # --- Sheet 3: summary ---------------------------------------------------
    summary = wb.create_sheet("Summary")
    summary["A1"] = "Compliance summary"
    summary["A1"].font = TITLE_FONT

    total = len(inspections)
    compliant = sum(1 for i in inspections if (i.get("status") or "") == "COMPLIANT")
    scores = [i.get("overall_score", 0) for i in inspections]

    by_rule: Dict[str, int] = {}
    for i in inspections:
        for rid in i.get("violation_rule_ids", []):
            by_rule[rid] = by_rule.get(rid, 0) + 1

    rows = [
        ("Total inspections", total),
        ("Compliant", compliant),
        ("Non-compliant", total - compliant),
        ("Compliance rate", "%.1f%%" % ((compliant / total * 100) if total else 0)),
        ("Average score", round(sum(scores) / len(scores), 1) if scores else 0),
        ("Total contraventions", sum(i.get("violations_count", 0) for i in inspections)),
    ]
    for r, (label, value) in enumerate(rows, start=3):
        summary.cell(row=r, column=1, value=label).font = Font(bold=True, size=10)
        summary.cell(row=r, column=2, value=value)

    summary.cell(row=len(rows) + 5, column=1, value="Contraventions by rule").font = TITLE_FONT
    _write_header(summary, ["Rule ID", "Count"], row=len(rows) + 6)
    for r, (rule_id, count) in enumerate(sorted(by_rule.items(), key=lambda kv: -kv[1]),
                                         start=len(rows) + 7):
        summary.cell(row=r, column=1, value=rule_id).border = BORDER
        summary.cell(row=r, column=2, value=count).border = BORDER

    _autosize(summary, [38, 18])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
