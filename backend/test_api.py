"""
Integration Test for FastAPI Endpoints
"""

import io
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_api_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ONLINE"
    print("  --> /api/v1/health: OK")

def test_api_samples():
    response = client.get("/api/v1/samples")
    assert response.status_code == 200
    data = response.json()
    assert len(data["samples"]) >= 4
    print(f"  --> /api/v1/samples: OK ({len(data['samples'])} demo scenarios available)")

def test_api_analyze_text_compliant():
    text_payload = {
        "text": (
            "SUPER CRUNCH BISCUITS\n"
            "Net Qty: 200 g\n"
            "MRP Rs. 40.00 (Inclusive of all taxes)\n"
            "Mfg Date: 02/2026\n"
            "Helpline: 1800-222-3344 | Email: care@crunch.in\n"
            "Country of Origin: India"
        )
    }
    response = client.post("/api/v1/analyze-text", json=text_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLIANT"
    assert data["overall_score"] >= 90
    print("  --> /api/v1/analyze-text (Compliant Case): OK")

def test_api_analyze_text_infringement():
    text_payload = {
        "text": (
            "SHINE SHAMPOO\n"
            "Net Vol: 12 fl oz\n"  # Illegal Imperial Unit
            "MRP Rs. 300\n"        # Missing tax suffix
            "Pkd: 01/2026\n"
            "Country of Origin: USA"
        )
    }
    response = client.post("/api/v1/analyze-text", json=text_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "NON_COMPLIANT"
    assert len(data["violations"]) >= 2
    print("  --> /api/v1/analyze-text (Infringement Case): OK")

def test_api_analyze_package_upload():
    # Create a synthetic image in memory
    img = Image.new("RGB", (600, 400), color=(240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    response = client.post(
        "/api/v1/analyze-package",
        files={"image": ("test_package.jpg", buf, "image/jpeg")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "status" in data
    assert "overall_score" in data
    print("  --> /api/v1/analyze-package (Multipart Upload): OK")

def test_api_analyze_package_multi_image_upload():
    # Create two synthetic images (e.g., front and back)
    img1 = Image.new("RGB", (600, 400), color=(240, 240, 240))
    buf1 = io.BytesIO()
    img1.save(buf1, format="JPEG")
    buf1.seek(0)

    img2 = Image.new("RGB", (600, 400), color=(245, 245, 245))
    buf2 = io.BytesIO()
    img2.save(buf2, format="JPEG")
    buf2.seek(0)

    response = client.post(
        "/api/v1/analyze-package",
        files=[
            ("images", ("front.jpg", buf1, "image/jpeg")),
            ("images", ("back.jpg", buf2, "image/jpeg")),
        ]
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["images_count"] == 2
    assert len(data["images_processed"]) == 2
    print("  --> /api/v1/analyze-package (Multi-Image 2 Angles Upload): OK")

def test_api_verify_and_re_audit():
    payload = {
        "segments": [
            {"text": "PREMIUM TEA", "box": [[10, 10], [200, 10], [200, 40], [10, 40]], "confidence": 0.99},
            {"text": "Net Qty: 250 g", "box": [[10, 50], [200, 50], [200, 80], [10, 80]], "confidence": 0.98},
            {"text": "Mfd: 01/2026", "box": [[10, 90], [200, 90], [200, 120], [10, 120]], "confidence": 0.98}
        ],
        "manual_overrides": {
            "brand_name": "PREMIUM TEA",
            "mrp": "120.00",
            "taxes_included": True,
            "consumer_care_email": "care@tea.in",
            "consumer_care_phone": "1800-333-2222",
            "country_of_origin": "India"
        }
    }
    response = client.post("/api/v1/verify-and-audit", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLIANT"
    assert data["overall_score"] == 100
    assert data["is_manually_verified"] is True
    assert "mrp" in data["manual_fields_applied"]
    print("  --> /api/v1/verify-and-audit (Hybrid AI + Manual Correction Re-Audit): OK")

def test_api_vlm_info():
    response = client.get("/api/v1/vlm-info")
    assert response.status_code == 200
    data = response.json()
    assert data["vlm_enabled"] is True
    assert "supported_models" in data
    print("  --> /api/v1/vlm-info (Vision-Language Models Info): OK")

if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING FASTAPI BACKEND INTEGRATION TESTS")
    print("=" * 60)
    test_api_health()
    test_api_vlm_info()
    test_api_samples()
    test_api_analyze_text_compliant()
    test_api_analyze_text_infringement()
    test_api_analyze_package_upload()
    test_api_analyze_package_multi_image_upload()
    test_api_verify_and_re_audit()
    print("=" * 60)
    print("ALL API INTEGRATION TESTS PASSED CLEANLY! [SUCCESS]")
    print("=" * 60)


