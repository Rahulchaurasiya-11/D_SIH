"""
Tests for the defects and gaps found in the post-build audit.

Each test names the failure it prevents, so a later change that reintroduces one
fails loudly rather than quietly.
"""

import pytest

from app.core.ratelimit import SlidingWindowLimiter
from app.db.store import literal_regex, matches
from app.models import CASE_TRANSITIONS, CaseStatus, validate_password_strength
from tests.conftest import COMPLIANT_LABEL


def scan_text(client, headers, lines, **extra):
    body = {"raw_text": "\n".join(lines), "filename": "label.txt", "source": "manual"}
    body.update(extra)
    return client.post("/api/v1/analyze-text", json=body, headers=headers)


# --------------------------------------------------------------------------- #
# Search: malformed regex and ReDoS
# --------------------------------------------------------------------------- #

def test_malformed_regex_does_not_crash_the_matcher():
    """A bare "[" is an invalid pattern; it used to raise re.error and 500."""
    doc = {"brand": "Acme"}
    assert matches(doc, {"brand": {"$regex": "["}}) is False
    assert matches(doc, {"brand": {"$regex": "(unclosed"}}) is False
    assert matches(doc, {"brand": {"$regex": "*bad"}}) is False


def test_literal_regex_escapes_metacharacters():
    assert literal_regex("a+b") != "a+b"
    doc = {"brand": "a+b Foods"}
    assert matches(doc, {"brand": {"$regex": literal_regex("a+b")}})
    # "a+b" as a pattern would match "aaab"; escaped, it must not.
    assert not matches({"brand": "aaab"}, {"brand": {"$regex": literal_regex("a+b")}})


def test_literal_regex_bounds_length():
    assert len(literal_regex("x" * 5000)) <= 240


@pytest.mark.parametrize("term", ["[", "(", "*", "a{999999}", "(a+)+$", "\\"])
def test_search_endpoint_survives_hostile_terms(client, inspector_headers, term):
    """Typing any of these into the search box must not 500 the repository."""
    response = client.get("/api/v1/inspections", params={"q": term}, headers=inspector_headers)
    assert response.status_code == 200, response.text


# --------------------------------------------------------------------------- #
# Rate limiting
# --------------------------------------------------------------------------- #

def test_sliding_window_allows_then_blocks():
    limiter = SlidingWindowLimiter(limit=3, window_seconds=60)
    assert all(limiter.check("k")[0] for _ in range(3))
    allowed, retry_after = limiter.check("k")
    assert allowed is False
    assert retry_after > 0


def test_sliding_window_reset_clears_budget():
    limiter = SlidingWindowLimiter(limit=2, window_seconds=60)
    limiter.check("k")
    limiter.check("k")
    assert limiter.check("k")[0] is False
    limiter.reset("k")
    assert limiter.check("k")[0] is True


def test_repeated_bad_passwords_are_rate_limited(client):
    """Without this, /auth/login is a password oracle at network speed."""
    body = {"email": "ratelimit-target@lm.gov.in", "password": "WrongPassword#1"}
    codes = [client.post("/api/v1/auth/login", json=body).status_code for _ in range(12)]
    assert 429 in codes, codes
    # The lockout must arrive before a realistic guessing budget is spent.
    assert codes.index(429) <= 9


def test_rate_limited_response_carries_retry_after(client):
    body = {"email": "retry-after@lm.gov.in", "password": "WrongPassword#1"}
    last = None
    for _ in range(12):
        last = client.post("/api/v1/auth/login", json=body)
        if last.status_code == 429:
            break
    assert last.status_code == 429
    assert int(last.headers["retry-after"]) > 0


# --------------------------------------------------------------------------- #
# Password strength
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("weak", [
    "password",            # the first thing anyone tries
    "Password",            # too short, two classes
    "password123",         # common
    "12345678901",         # one class
    "abcdefghijk",         # one class
])
def test_weak_passwords_are_rejected(weak):
    with pytest.raises(ValueError):
        validate_password_strength(weak)


@pytest.mark.parametrize("strong", [
    "Inspector#2026Delhi",
    "correct-horse-Battery9",
    "Xy7$qwertyuiop",
])
def test_strong_passwords_are_accepted(strong):
    assert validate_password_strength(strong) == strong


def test_registration_rejects_a_weak_password(client, admin):
    response = client.post("/api/v1/auth/register", json={
        "email": "weakpass@lm.gov.in", "password": "password", "full_name": "Weak Pass",
    })
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Upload limits
# --------------------------------------------------------------------------- #

def test_oversized_upload_is_rejected(client, inspector_headers):
    """Uploads are held in memory for OCR, so an unbounded file exhausts the process."""
    from app.config import settings

    oversized = b"\xff\xd8\xff" + b"0" * (settings.MAX_IMAGE_BYTES + 1024)
    response = client.post(
        "/api/v1/analyze-package",
        headers=inspector_headers,
        files={"images": ("huge.jpg", oversized, "image/jpeg")},
    )
    assert response.status_code == 413
    assert "limit" in response.json()["detail"].lower()


# --------------------------------------------------------------------------- #
# Inspection context: where the package was found
# --------------------------------------------------------------------------- #

NON_COMPLIANT = [ln.replace(" (Inclusive of all taxes)", "") for ln in COMPLIANT_LABEL]

CONTEXT = {
    "premises_name": "Sharma General Store",
    "premises_address": "12 Nehru Market, Karol Bagh, New Delhi - 110005",
    "premises_type": "RETAIL",
    "premises_licence": "DL-LM-2026-4417",
    "latitude": 28.6519,
    "longitude": 77.1909,
    "location_accuracy_m": 8.0,
    "remarks": "Pack taken from the front shelf.",
}


@pytest.fixture
def stub_ocr(monkeypatch):
    """
    Replaces the OCR pass with a deterministic reading of NON_COMPLIANT.

    These tests are about the context, case and report plumbing, not about
    recognition. Running the real engine here cost roughly fifteen seconds per
    upload and turned a fast suite into a multi-minute one, which is how suites
    stop being run. The genuine OCR pipeline is covered separately by
    `test_real_ocr_pipeline_reads_a_label`.
    """
    from app.api.v1 import inspections as module
    from tests.conftest import as_segments

    def fake(_data):
        return as_segments(NON_COMPLIANT), (800, 600)

    monkeypatch.setattr(module, "extract_segments_from_image", fake)
    return fake


def _scan_with_context(client, headers, lines=None, context=CONTEXT):
    import json

    return client.post(
        "/api/v1/analyze-package",
        headers=headers,
        files={"images": ("front.jpg", _tiny_label(lines or NON_COMPLIANT), "image/jpeg")},
        data={"context": json.dumps(context)},
    )


def _tiny_label(lines):
    """A small JPEG carrying the label text, so the real engine can also read it."""
    import io

    from PIL import Image, ImageDraw

    img = Image.new("RGB", (600, 800), "white")
    draw = ImageDraw.Draw(img)
    for i, text in enumerate(lines):
        draw.text((10, 20 + i * 30), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_scan_records_the_premises(client, inspector_headers, stub_ocr):
    """A finding with no record of where the pack was found cannot support a notice."""
    response = _scan_with_context(client, inspector_headers)
    assert response.status_code == 201, response.text

    inspection_id = response.json()["inspection_id"]
    stored = client.get("/api/v1/inspections/" + inspection_id, headers=inspector_headers).json()

    assert stored["premises_name"] == "Sharma General Store"
    assert stored["premises_licence"] == "DL-LM-2026-4417"
    assert stored["latitude"] == pytest.approx(28.6519)
    assert stored["remarks"].startswith("Pack taken")


def test_invalid_context_is_rejected_not_silently_dropped(client, inspector_headers, stub_ocr):
    """The officer must be told the premises did not save, not left assuming it did."""
    response = client.post(
        "/api/v1/analyze-package",
        headers=inspector_headers,
        files={"images": ("front.jpg", _tiny_label(NON_COMPLIANT), "image/jpeg")},
        data={"context": '{"latitude": 999}'},
    )
    assert response.status_code == 422


def test_premises_is_searchable(client, inspector_headers, stub_ocr):
    _scan_with_context(client, inspector_headers)
    response = client.get("/api/v1/inspections", params={"premises": "Sharma General"},
                          headers=inspector_headers)
    assert response.status_code == 200
    assert response.json()["total"] >= 1


# --------------------------------------------------------------------------- #
# Enforcement case lifecycle
# --------------------------------------------------------------------------- #

def test_non_compliant_scan_opens_a_numbered_case(client, inspector_headers, stub_ocr):
    body = _scan_with_context(client, inspector_headers).json()
    assert body["case_status"] == "OPEN"
    assert body["case_number"].startswith("LM/")
    assert body["case_number"].count("/") == 3


def test_compliant_scan_opens_no_case(client, inspector_headers):
    """A clean pack is recorded and searchable, but there is nothing to enforce."""
    body = scan_text(client, inspector_headers, COMPLIANT_LABEL).json()
    stored = client.get("/api/v1/inspections/" + body["inspection_id"],
                        headers=inspector_headers).json()
    assert stored["case_status"] == ""
    assert stored["case_number"] == ""


def test_case_numbers_are_unique(client, inspector_headers, stub_ocr):
    numbers = {_scan_with_context(client, inspector_headers).json()["case_number"] for _ in range(3)}
    assert len(numbers) == 3


def test_inspector_cannot_advance_a_case(client, inspector_headers, stub_ocr):
    """Issuing a notice is an enforcement decision, not a data-entry step."""
    inspection_id = _scan_with_context(client, inspector_headers).json()["inspection_id"]
    response = client.patch("/api/v1/inspections/%s/case" % inspection_id,
                            json={"case_status": "NOTICE_ISSUED"}, headers=inspector_headers)
    assert response.status_code == 403


def test_senior_officer_can_advance_a_case(client, admin_headers, stub_ocr):
    inspection_id = _scan_with_context(client, admin_headers).json()["inspection_id"]
    response = client.patch(
        "/api/v1/inspections/%s/case" % inspection_id,
        json={"case_status": "NOTICE_ISSUED", "note": "Notice served on the packer.",
              "notice_reference": "LM/NOT/2026/88"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["case_status"] == "NOTICE_ISSUED"
    assert body["notice_reference"] == "LM/NOT/2026/88"
    assert body["case_history"][-1]["from"] == "OPEN"
    assert body["case_history"][-1]["note"].startswith("Notice served")


def test_illegal_transition_is_refused(client, admin_headers, stub_ocr):
    """A case must not jump to COMPLIED without a notice having been issued."""
    inspection_id = _scan_with_context(client, admin_headers).json()["inspection_id"]
    response = client.patch("/api/v1/inspections/%s/case" % inspection_id,
                            json={"case_status": "COMPLIED"}, headers=admin_headers)
    assert response.status_code == 409
    assert "Cannot move" in response.json()["detail"]


def test_closed_case_cannot_be_reopened(client, admin_headers, stub_ocr):
    inspection_id = _scan_with_context(client, admin_headers).json()["inspection_id"]
    client.patch("/api/v1/inspections/%s/case" % inspection_id,
                 json={"case_status": "CLOSED"}, headers=admin_headers)
    response = client.patch("/api/v1/inspections/%s/case" % inspection_id,
                            json={"case_status": "NOTICE_ISSUED"}, headers=admin_headers)
    assert response.status_code == 409


def test_case_on_a_compliant_inspection_is_refused(client, admin_headers):
    body = scan_text(client, admin_headers, COMPLIANT_LABEL).json()
    response = client.patch("/api/v1/inspections/%s/case" % body["inspection_id"],
                            json={"case_status": "NOTICE_ISSUED"}, headers=admin_headers)
    assert response.status_code == 409


def test_transition_table_has_no_dead_ends_except_closed():
    for state, allowed in CASE_TRANSITIONS.items():
        if state == CaseStatus.CLOSED.value:
            assert allowed == []
        else:
            assert allowed, "%s has no way forward" % state
        assert all(a in CASE_TRANSITIONS for a in allowed)


def test_case_status_is_filterable(client, admin_headers):
    response = client.get("/api/v1/inspections", params={"case_status": "OPEN"},
                          headers=admin_headers)
    assert response.status_code == 200
    assert all(row["case_status"] == "OPEN" for row in response.json()["items"])


# --------------------------------------------------------------------------- #
# Dashboard: enforcement activity, not just detection
# --------------------------------------------------------------------------- #

def test_dashboard_reports_case_activity(client, admin_headers):
    stats = client.get("/api/v1/dashboard/stats", headers=admin_headers).json()
    for key in ("cases_by_status", "open_cases", "concluded_cases",
                "compliance_recovery_rate", "premises_covered"):
        assert key in stats, "missing key: " + key


def test_repeat_offenders_requires_senior_officer(client, inspector_headers):
    assert client.get("/api/v1/repeat-offenders", headers=inspector_headers).status_code == 403


def test_repeat_offenders_groups_by_brand(client, admin_headers):
    response = client.get("/api/v1/repeat-offenders", params={"minimum": 2}, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert "offenders" in body
    for row in body["offenders"]:
        assert row["inspections"] >= 2
        assert "top_rules" in row and "distinct_premises" in row


# --------------------------------------------------------------------------- #
# Reports must carry the case and the premises
# --------------------------------------------------------------------------- #

def test_report_includes_case_number_and_premises(client, admin_headers, stub_ocr):
    import io
    import zipfile

    inspection_id = _scan_with_context(client, admin_headers).json()["inspection_id"]
    docx = client.get("/api/v1/reports/%s?format=docx" % inspection_id,
                      headers=admin_headers).content

    with zipfile.ZipFile(io.BytesIO(docx)) as zf:
        document = zf.read("word/document.xml").decode("utf-8")

    assert "PREMISES WHERE THE PACKAGE WAS FOUND" in document
    assert "Sharma General Store" in document
    assert "Karol Bagh" in document
    assert "LM/" in document


def test_report_warns_when_premises_was_not_recorded(client, admin_headers):
    """Silence here would let an officer issue a notice with no place of seizure."""
    import io
    import zipfile

    body = scan_text(client, admin_headers, NON_COMPLIANT).json()
    docx = client.get("/api/v1/reports/%s?format=docx" % body["inspection_id"],
                      headers=admin_headers).content

    with zipfile.ZipFile(io.BytesIO(docx)) as zf:
        document = zf.read("word/document.xml").decode("utf-8")

    assert "premises details were not recorded" in document


# --------------------------------------------------------------------------- #
# The real OCR pipeline
# --------------------------------------------------------------------------- #

@pytest.mark.slow
def test_real_ocr_pipeline_reads_a_label(client, admin_headers):
    """
    Exercises the genuine recognition path end to end, once.

    Every other upload test stubs OCR to stay fast; this one does not, so a break
    in preprocessing, engine selection or segment fusion is still caught. Skipped
    automatically when no OCR engine is installed, because that is a deployment
    choice rather than a defect.
    """
    from app.core.ocr import engine_name

    if engine_name() == "none":
        pytest.skip("no server-side OCR engine installed")

    response = client.post(
        "/api/v1/analyze-package",
        headers=admin_headers,
        files={"images": ("front.jpg", _tiny_label(COMPLIANT_LABEL), "image/jpeg")},
    )
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["raw_segments"], "OCR returned no segments from a legible label"
    assert body["ocr_engine"] != "none"
    # Boxes must be in the original image's pixel space for the overlay to line up.
    for segment in body["raw_segments"]:
        for x, y in segment["box"]:
            assert 0 <= x <= 700 and 0 <= y <= 900, (x, y)
