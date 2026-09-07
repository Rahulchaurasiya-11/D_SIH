"""
Unit and Integration Tests for Legal Metrology Compliance Engine
Standard Library + Pytest compatible.
"""

import sys
import io

# Ensure UTF-8 output encoding for Windows command line terminals
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from compliance_engine import LegalMetrologyComplianceEngine


def run_tests():
    engine = LegalMetrologyComplianceEngine()
    print("=" * 70)
    print("LEGAL METROLOGY COMPLIANCE ENGINE - VERIFICATION SUITE")
    print("=" * 70)

    # Test 1: Fully Compliant FMCG Package
    print("\n[TEST 1] Evaluating Fully Compliant Indian FMCG Package...")
    segments1 = [
        {
            "text": "PREMIUM ROASTED ALMONDS",
            "box": [[10, 10], [300, 10], [300, 40], [10, 40]],
            "confidence": 0.99,
        },
        {
            "text": "Net Quantity: 500 g",
            "box": [[10, 50], [250, 50], [250, 80], [10, 80]],
            "confidence": 0.98,
        },
        {
            "text": "MRP Rs. 450.00 (Inclusive of all taxes)",
            "box": [[10, 90], [400, 90], [400, 120], [10, 120]],
            "confidence": 0.99,
        },
        {
            "text": "Mfg Date: 02/2026",
            "box": [[10, 130], [200, 130], [200, 160], [10, 160]],
            "confidence": 0.97,
        },
        {
            "text": "Customer Care Email: support@almondsfresh.com",
            "box": [[10, 170], [450, 170], [450, 200], [10, 200]],
            "confidence": 0.98,
        },
        {
            "text": "Helpline: 1800-111-2233",
            "box": [[10, 210], [300, 210], [300, 240], [10, 240]],
            "confidence": 0.98,
        },
        {
            "text": "Country of Origin: India",
            "box": [[10, 250], [280, 250], [280, 280], [10, 280]],
            "confidence": 0.98,
        },
    ]
    res1 = engine.evaluate_compliance(segments1, (1000, 1000))
    assert res1["status"] == "COMPLIANT", f"Expected COMPLIANT, got {res1['status']}"
    assert res1["overall_score"] >= 90, (
        f"Expected score >= 90, got {res1['overall_score']}"
    )
    assert len(res1["violations"]) == 0, (
        f"Expected 0 violations, got {len(res1['violations'])}"
    )
    assert res1["rules_breakdown"]["rule_6_1_da_mrp"] is True
    assert res1["rules_breakdown"]["rule_11_12_net_quantity"] is True
    assert res1["rules_breakdown"]["rule_6_1_g_consumer_care"] is True
    assert res1["rules_breakdown"]["rule_6_1_c_mfg_date"] is True
    print(
        "  --> PASS: 100% Compliant Package correctly cleared with status:",
        res1["status"],
        "Score:",
        res1["overall_score"],
    )

    # Test 2: Prohibited Imperial Units (Rule 11/12)
    print("\n[TEST 2] Evaluating Package with Illegal Imperial Units (fl oz / oz)...")
    segments2 = [
        {
            "text": "IMPORTED LUXURY BODY WASH",
            "box": [[10, 10], [300, 10], [300, 40], [10, 40]],
            "confidence": 0.99,
        },
        {
            "text": "Net Contents: 16 fl oz (450 ml)",
            "box": [[10, 50], [350, 50], [350, 80], [10, 80]],
            "confidence": 0.98,
        },
        {
            "text": "MRP ₹ 799 (Inclusive of all taxes)",
            "box": [[10, 90], [380, 90], [380, 120], [10, 120]],
            "confidence": 0.98,
        },
        {
            "text": "Pkd: 01/2026",
            "box": [[10, 130], [150, 130], [150, 160], [10, 160]],
            "confidence": 0.98,
        },
        {
            "text": "Contact: care@luxwash.com | Phone: 9876543210",
            "box": [[10, 170], [450, 170], [450, 200], [10, 200]],
            "confidence": 0.98,
        },
    ]
    res2 = engine.evaluate_compliance(segments2, (1000, 1000))
    assert res2["status"] == "NON_COMPLIANT", (
        f"Expected NON_COMPLIANT, got {res2['status']}"
    )
    assert res2["rules_breakdown"]["rule_11_12_net_quantity"] is False
    assert any("RULE_11_12_PROHIBITED_UNIT" in v["rule_id"] for v in res2["violations"])
    print("  --> PASS: Prohibited Imperial Unit correctly flagged under Rule 11 & 12.")

    # Test 3: Missing Tax Suffix on MRP (Rule 6(1)(da))
    print("\n[TEST 3] Evaluating Missing 'Inclusive of all taxes' Suffix...")
    segments3 = [
        {
            "text": "CRUNCHY POTATO CHIPS",
            "box": [[10, 10], [300, 10], [300, 40], [10, 40]],
            "confidence": 0.99,
        },
        {
            "text": "Net Qty: 150 g",
            "box": [[10, 50], [200, 50], [200, 80], [10, 80]],
            "confidence": 0.98,
        },
        {
            "text": "MRP: Rs. 50.00",
            "box": [[10, 90], [220, 90], [220, 120], [10, 120]],
            "confidence": 0.98,
        },
        {
            "text": "Date of Pkg: 12/2025",
            "box": [[10, 130], [220, 130], [220, 160], [10, 160]],
            "confidence": 0.98,
        },
        {
            "text": "Helpline: 1800-444-5566 | Email: care@chips.in",
            "box": [[10, 170], [450, 170], [450, 200], [10, 200]],
            "confidence": 0.98,
        },
    ]
    res3 = engine.evaluate_compliance(segments3, (1000, 1000))
    assert res3["status"] == "NON_COMPLIANT", (
        f"Expected NON_COMPLIANT, got {res3['status']}"
    )
    assert res3["rules_breakdown"]["rule_6_1_da_mrp"] is False
    assert any(
        "RULE_6_1_DA_TAX_SUFFIX_MISSING" in v["rule_id"] for v in res3["violations"]
    )
    print("  --> PASS: Missing Tax Suffix correctly intercepted under Rule 6(1)(da).")

    # Test 4: Rule 6(1)(g) - Fuzzy & Resilient Consumer Care (care@ / helpline near manufacturing)
    print(
        "\n[TEST 4] Evaluating Consumer Care without strict 'Grievance Officer' keywords (care@ & Phone)..."
    )
    segments4 = [
        {
            "text": "AYURVEDIC HAIR OIL",
            "box": [[10, 10], [300, 10], [300, 40], [10, 40]],
            "confidence": 0.99,
        },
        {
            "text": "Net Vol: 200 ml",
            "box": [[10, 50], [200, 50], [200, 80], [10, 80]],
            "confidence": 0.98,
        },
        {
            "text": "MRP ₹ 180.00 (Incl. of all taxes)",
            "box": [[10, 90], [350, 90], [350, 120], [10, 120]],
            "confidence": 0.98,
        },
        {
            "text": "Mfd: 01/2026",
            "box": [[10, 130], [150, 130], [150, 160], [10, 160]],
            "confidence": 0.98,
        },
        {
            "text": "Manufactured by: Herbal Herbs Ltd, Vapi, Gujarat 396195",
            "box": [[10, 170], [450, 170], [450, 200], [10, 200]],
            "confidence": 0.98,
        },
        {
            "text": "care@herbalherbs.com | 9876543210",
            "box": [[10, 210], [350, 210], [350, 240], [10, 240]],
            "confidence": 0.98,
        },
    ]
    res4 = engine.evaluate_compliance(segments4, (1000, 1000))
    assert res4["status"] == "COMPLIANT", f"Expected COMPLIANT, got {res4['status']}"
    assert res4["rules_breakdown"]["rule_6_1_g_consumer_care"] is True
    print(
        "  --> PASS: care@ email & phone correctly cleared without false 'Consumer Care Missing' error! Status:",
        res4["status"],
    )

    # Test 5: Rule 6(10) - Country of Origin Inferred from Indian State & 6-Digit PIN Code
    print(
        "\n[TEST 5] Evaluating Country of Origin Inference from State ('Gujarat') & PIN Code ('396195')..."
    )
    segments5 = [
        {
            "text": "GLOW BODY LOTION",
            "box": [[10, 10], [300, 10], [300, 40], [10, 40]],
            "confidence": 0.99,
        },
        {
            "text": "Net Vol: 100 ml",
            "box": [[10, 50], [200, 50], [200, 80], [10, 80]],
            "confidence": 0.98,
        },
        {
            "text": "MRP Rs. 120 (Inclusive of all taxes)",
            "box": [[10, 90], [350, 90], [350, 120], [10, 120]],
            "confidence": 0.99,
        },
        {
            "text": "Mfg Date: 02/2026",
            "box": [[10, 130], [200, 130], [200, 160], [10, 160]],
            "confidence": 0.98,
        },
        {
            "text": "Manufactured by: Glow Cosmetics, Plot 14, GIDC Vapi, Gujarat - 396195",
            "box": [[10, 170], [500, 170], [500, 200], [10, 200]],
            "confidence": 0.98,
        },
        {
            "text": "For feedback: help@glow.com | Helpline: 1800-444-1122",
            "box": [[10, 210], [450, 210], [450, 240], [10, 240]],
            "confidence": 0.98,
        },
    ]
    res5 = engine.evaluate_compliance(segments5, (1000, 1000))
    assert res5["status"] == "COMPLIANT", f"Expected COMPLIANT, got {res5['status']}"
    assert "India" in res5["extracted_metadata"]["country_of_origin"]
    assert any("RULE_6_10_ORIGIN_ADVISORY" in w["rule_id"] for w in res5["warnings"])
    print(
        "  --> PASS: State ('Gujarat') & PIN Code ('396195') correctly inferred as India with Low Severity Advisory! Status: COMPLIANT"
    )

    # Test 6: Cylindrical Bottle Curvature & Partial Word Cut-Offs
    print(
        "\n[TEST 6] Evaluating Cylindrical Bottle with Curvature Cut-Offs ('incl of all ta', '200ml', 'mfd on 02/26')..."
    )
    segments6 = [
        {
            "text": "CITRUS ENERGY DRINK",
            "box": [[10, 10], [300, 10], [300, 40], [10, 40]],
            "confidence": 0.99,
        },
        {
            "text": "Net Vol: 200ml",
            "box": [[10, 50], [200, 50], [200, 80], [10, 80]],
            "confidence": 0.98,
        },
        {
            "text": "MRP Rs. 40.00 incl of all ta",
            "box": [[10, 90], [320, 90], [320, 120], [10, 120]],
            "confidence": 0.97,
        },
        {
            "text": "mfd on: 02/2026",
            "box": [[10, 130], [200, 130], [200, 160], [10, 160]],
            "confidence": 0.98,
        },
        {
            "text": "cust care: care@citrusdrink.co.in | 1800-999-8877",
            "box": [[10, 170], [450, 170], [450, 200], [10, 200]],
            "confidence": 0.98,
        },
        {
            "text": "Packed in Pune, MH - 411001",
            "box": [[10, 210], [300, 210], [300, 240], [10, 240]],
            "confidence": 0.98,
        },
    ]
    res6 = engine.evaluate_compliance(segments6, (1000, 1000))
    assert res6["status"] == "COMPLIANT", f"Expected COMPLIANT, got {res6['status']}"
    assert res6["rules_breakdown"]["rule_6_1_da_mrp"] is True
    assert res6["rules_breakdown"]["rule_11_12_net_quantity"] is True
    assert res6["rules_breakdown"]["rule_6_1_g_consumer_care"] is True
    assert res6["rules_breakdown"]["rule_6_1_c_mfg_date"] is True
    print(
        "  --> PASS: Bottle curvature partial words ('incl of all ta', '200ml', 'mfd on', 'cust care') pieced together and verified perfectly!"
    )

    # Test 7: Stationery Pen with ART NO. 3458 & Preposition Disambiguation
    print(
        "\n[TEST 7] Evaluating Stationery Pen with 'ART NO. 3458' and 'Made in India'..."
    )
    segments7 = [
        {
            "text": "PREMIUM GEL PEN - BLUE",
            "box": [[10, 10], [300, 10], [300, 40], [10, 40]],
            "confidence": 0.99,
        },
        {
            "text": "ART NO. 3458",
            "box": [[10, 50], [180, 50], [180, 80], [10, 80]],
            "confidence": 0.98,
        },
        {
            "text": "0.5 mm tip | Net Qty: 1 N",
            "box": [[10, 90], [280, 90], [280, 120], [10, 120]],
            "confidence": 0.99,
        },
        {
            "text": "MRP Rs. 50.00 (Inclusive of all taxes)",
            "box": [[10, 130], [420, 130], [420, 160], [10, 160]],
            "confidence": 0.99,
        },
        {
            "text": "Mfd: 03/2026 | Batch No: B-99",
            "box": [[10, 170], [320, 170], [320, 200], [10, 200]],
            "confidence": 0.98,
        },
        {
            "text": "Customer Care: care@gelpens.in | Helpline: 1800-222-3333",
            "box": [[10, 210], [550, 210], [550, 240], [10, 240]],
            "confidence": 0.98,
        },
        {
            "text": "Made in India by Pen Craft Industries, Gujarat",
            "box": [[10, 250], [450, 250], [450, 280], [10, 280]],
            "confidence": 0.98,
        },
    ]
    res7 = engine.evaluate_compliance(segments7, (1000, 1000))
    # Test 8: Regional Language - Telugu Compliant Label
    print("\n[TEST 8] Evaluating Regional Language - Telugu Compliant FMCG Label...")
    segments8 = [
        {"text": "హెర్బల్ హెయిర్ ఆయిల్", "box": [[10, 10], [300, 10], [300, 40], [10, 40]], "confidence": 0.99},
        {"text": "పరిమాణం: 200 ml", "box": [[10, 50], [250, 50], [250, 80], [10, 80]], "confidence": 0.98},
        {"text": "గరిష్ట రిటైల్ ధర ₹ 180.00 (అన్ని పన్నులతో కలిపి)", "box": [[10, 90], [450, 90], [450, 120], [10, 120]], "confidence": 0.99},
        {"text": "తయారీ తేదీ: 02/2026", "box": [[10, 130], [250, 130], [250, 160], [10, 160]], "confidence": 0.97},
        {"text": "వినియోగదారుల సంరక్షణ: care@teluguoil.in | హెల్ప్‌లైన్: 1800-425-0011", "box": [[10, 170], [500, 170], [500, 200], [10, 200]], "confidence": 0.98},
        {"text": "తయారీదారు: శ్రీ బాలాజీ ఇండస్ట్రీస్, హైదరాబాద్, తెలంగాణ", "box": [[10, 210], [450, 210], [450, 240], [10, 240]], "confidence": 0.98},
        {"text": "భారతదేశం లో తయారు చేయబడింది", "box": [[10, 250], [350, 250], [350, 280], [10, 280]], "confidence": 0.98}
    ]
    res8 = engine.evaluate_compliance(segments8, (1000, 1000))
    assert res8["status"] == "COMPLIANT", f"Expected COMPLIANT for Telugu label, got {res8['status']}"
    assert res8["extracted_metadata"]["detected_language"] == "te", f"Expected 'te', got {res8['extracted_metadata']['detected_language']}"
    assert res8["rules_breakdown"]["rule_6_1_da_mrp"] is True
    assert res8["rules_breakdown"]["rule_11_12_net_quantity"] is True
    assert res8["rules_breakdown"]["rule_6_1_g_consumer_care"] is True
    assert res8["rules_breakdown"]["rule_6_1_c_mfg_date"] is True
    print(f"  --> PASS: Telugu Regional Script Label accurately analyzed! Detected: {res8['extracted_metadata']['language_name']} | Status: {res8['status']}")

    # Test 9: Regional Language - Hindi Devanagari Compliant Label
    print("\n[TEST 9] Evaluating Regional Language - Hindi Devanagari Compliant Label...")
    segments9 = [
        {"text": "आयुर्वेदिक प्राकृतिक साबुन", "box": [[10, 10], [300, 10], [300, 40], [10, 40]], "confidence": 0.99},
        {"text": "शुद्ध मात्रा: 125 ग्राम", "box": [[10, 50], [250, 50], [250, 80], [10, 80]], "confidence": 0.98},
        {"text": "अधिकतम खुदरा मूल्य ₹ 65.00 (सभी करों सहित)", "box": [[10, 90], [450, 90], [450, 120], [10, 120]], "confidence": 0.99},
        {"text": "निर्माण तिथि: 01/2026 | बैच नं: H-12", "box": [[10, 130], [300, 130], [300, 160], [10, 160]], "confidence": 0.98},
        {"text": "ग्राहक सेवा: care@ayurved.in | 1800-222-1111", "box": [[10, 170], [450, 170], [450, 200], [10, 200]], "confidence": 0.98},
        {"text": "भारत में निर्मित | हरिद्वार, उत्तराखंड", "box": [[10, 210], [350, 210], [350, 240], [10, 240]], "confidence": 0.98}
    ]
    res9 = engine.evaluate_compliance(segments9, (1000, 1000))
    assert res9["status"] == "COMPLIANT", f"Expected COMPLIANT for Hindi label, got {res9['status']}"
    assert res9["extracted_metadata"]["detected_language"] == "hi", f"Expected 'hi', got {res9['extracted_metadata']['detected_language']}"
    assert res9["rules_breakdown"]["rule_6_1_da_mrp"] is True
    assert res9["rules_breakdown"]["rule_11_12_net_quantity"] is True
    # Test 10: Hybrid AI + Manual Verification Override (Eliminating False Positives)
    print("\n[TEST 10] Evaluating Hybrid AI + Manual Verification Override...")
    # Simulate a package image with blurry/missed MRP and tax suffix in OCR
    incomplete_segments = [
        {"text": "SUPER WHEAT FLOUR", "box": [[10, 10], [300, 10], [300, 40], [10, 40]], "confidence": 0.99},
        {"text": "Net Wt: 5 kg", "box": [[10, 50], [200, 50], [200, 80], [10, 80]], "confidence": 0.98},
        {"text": "Mfd: 02/2026", "box": [[10, 90], [200, 90], [200, 120], [10, 120]], "confidence": 0.98},
        {"text": "Customer Care: care@flour.in", "box": [[10, 130], [350, 130], [350, 160], [10, 160]], "confidence": 0.98},
        {"text": "Made in India", "box": [[10, 170], [200, 170], [200, 200], [10, 200]], "confidence": 0.98}
    ]
    # Initial scan without MRP should be NON_COMPLIANT
    initial_res = engine.evaluate_compliance(incomplete_segments, (1000, 1000))
    assert initial_res["status"] == "NON_COMPLIANT", "Expected initial scan to flag missing MRP"

    # Inspector manual verification override filling the missed MRP & taxes & helpline
    manual_overrides = {
        "brand_name": "SUPER WHEAT FLOUR",
        "mrp": "240.00",
        "taxes_included": True,
        "consumer_care_phone": "1800-444-5555"
    }
    corrected_res = engine.evaluate_compliance(incomplete_segments, (1000, 1000), manual_overrides=manual_overrides)
    assert corrected_res["status"] == "COMPLIANT", f"Expected COMPLIANT after manual correction, got {corrected_res['status']}"
    assert corrected_res["overall_score"] == 100, f"Expected 100 score, got {corrected_res['overall_score']}"
    assert corrected_res["is_manually_verified"] is True
    assert "mrp" in corrected_res["manual_fields_applied"]
    print("  --> PASS: Inspector manual input successfully cleared false missing MRP violation and brought score to 100/100 COMPLIANT!")

    print("\n" + "=" * 70)
    print("ALL COMPLIANCE PIPELINES PASSED VERIFICATION PERFECTLY! [SUCCESS]")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()


