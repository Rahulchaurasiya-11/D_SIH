"""
Golden-case tests for the compliance engine.

These pin the behaviour the original `test_engine.py` verified, so the restructure
(and any later rule edit) cannot silently change a verdict. Each case names the
statutory provision it exercises.
"""

import pytest

from app.engine.compliance_engine import LegalMetrologyComplianceEngine
from tests.conftest import COMPLIANT_LABEL, as_segments

engine = LegalMetrologyComplianceEngine()
DIMS = (400, 450)


def evaluate(lines, **kwargs):
    return engine.evaluate_compliance(segments=as_segments(lines), image_dimensions=DIMS, **kwargs)


def rule_ids(report):
    return {v.get("rule_id", "") for v in report["violations"]}


def violated(report, fragment):
    return any(fragment in rid for rid in rule_ids(report))


# --------------------------------------------------------------------------- #

def test_fully_compliant_label_passes():
    report = evaluate(COMPLIANT_LABEL)
    assert report["status"] == "COMPLIANT", rule_ids(report)
    assert report["overall_score"] >= 90
    assert report["violations"] == []
    assert report["passed_checks"]


def test_prohibited_imperial_units_flagged():
    """Rule 11/12 - imperial units are not permitted on an Indian retail package."""
    lines = [ln for ln in COMPLIANT_LABEL if not ln.startswith("Net Quantity")]
    lines.insert(2, "Net Contents: 16 fl oz")
    report = evaluate(lines)
    assert report["status"] != "COMPLIANT"
    assert any("NET_QTY" in rid or "UNIT" in rid or "11" in rid for rid in rule_ids(report)), rule_ids(report)


def test_missing_tax_suffix_flagged():
    """Rule 6(1)(da) - MRP must carry the 'inclusive of all taxes' clause."""
    lines = [ln.replace(" (Inclusive of all taxes)", "") for ln in COMPLIANT_LABEL]
    report = evaluate(lines)
    assert violated(report, "TAX_SUFFIX"), rule_ids(report)


def test_missing_mrp_entirely_flagged():
    lines = [ln for ln in COMPLIANT_LABEL if "MRP" not in ln]
    report = evaluate(lines)
    assert any("6_1_DA" in rid for rid in rule_ids(report)), rule_ids(report)


def test_missing_consumer_helpline_flagged():
    """Rule 6(1)(g) - both an email and a telephone contact are required."""
    lines = [ln for ln in COMPLIANT_LABEL if not ln.startswith("Helpline")]
    report = evaluate(lines)
    assert report["status"] != "COMPLIANT"
    assert any("CONSUMER" in rid or "6_1_G" in rid for rid in rule_ids(report)), rule_ids(report)


def test_missing_manufacture_date_flagged():
    """Rule 6(1)(c) - month and year of manufacture or packing."""
    lines = [ln for ln in COMPLIANT_LABEL if not ln.startswith("Mfg Date")]
    report = evaluate(lines)
    assert any("MFG" in rid or "6_1_C" in rid for rid in rule_ids(report)), rule_ids(report)


def test_empty_label_is_not_compliant():
    report = evaluate([])
    assert report["status"] != "COMPLIANT"
    assert report["overall_score"] < 50


def test_manual_override_clears_false_positive():
    """
    An inspector correcting an OCR misread must be able to clear the violation it
    caused - otherwise a bad scan becomes a wrongful enforcement notice.
    """
    lines = [ln.replace(" (Inclusive of all taxes)", "") for ln in COMPLIANT_LABEL]
    before = evaluate(lines)
    assert violated(before, "TAX_SUFFIX")

    after = engine.evaluate_compliance(
        segments=as_segments(lines),
        image_dimensions=DIMS,
        manual_overrides={"mrp": "450.00", "taxes_included": True},
    )
    assert not violated(after, "TAX_SUFFIX"), rule_ids(after)
    assert after["overall_score"] >= before["overall_score"]


def test_report_shape_is_stable():
    """Downstream renderers and the frontend depend on these keys existing."""
    report = evaluate(COMPLIANT_LABEL)
    for key in ("status", "overall_score", "violations", "passed_checks",
                "warnings", "extracted_metadata", "rules_breakdown"):
        assert key in report, "missing key: " + key


def test_metadata_extraction_finds_declarations():
    meta = evaluate(COMPLIANT_LABEL)["extracted_metadata"]
    assert meta.get("mrp")
    assert meta.get("taxes_included") is True
    assert meta.get("net_quantity")
    assert meta.get("consumer_care_email")


@pytest.mark.parametrize("unit", ["fl oz", "oz", "lbs", "gallon"])
def test_each_prohibited_unit_is_detected(unit):
    report = evaluate(["Net Contents: 12 " + unit, "MRP Rs. 99 (Inclusive of all taxes)"])
    assert report["status"] != "COMPLIANT"
