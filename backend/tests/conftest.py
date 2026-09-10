"""
Shared pytest fixtures.

Every test runs against an isolated JSON store in a temp directory, so the suite
never touches MongoDB, never needs credentials, and leaves no state behind.
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Must be set before app.config is imported anywhere.
os.environ["MONGODB_URI"] = ""
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET_KEY"] = "test-secret-not-used-outside-the-suite"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = ""


@pytest.fixture(scope="session", autouse=True)
def isolated_store():
    """Points the JSON document store at a throwaway directory for the whole session."""
    from app.db import store

    tmp = tempfile.mkdtemp(prefix="lm_test_store_")
    store._backend = store.JsonBackend(tmp)
    store._backend_name = "json"
    yield tmp


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def admin(client):
    """The first registered account is promoted to ADMIN automatically."""
    response = client.post("/api/v1/auth/register", json={
        "email": "admin@lm.gov.in", "password": "AdminPassphrase#2026",
        "full_name": "Ada Controller", "designation": "Controller",
        "jurisdiction": "Delhi",
    })
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture(scope="session")
def inspector(client, admin):
    response = client.post("/api/v1/auth/register", json={
        "email": "inspector@lm.gov.in", "password": "InspectorPass#2026",
        "full_name": "Ravi Inspector", "designation": "Inspector",
        "jurisdiction": "Delhi North",
    })
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def admin_headers(admin):
    return {"Authorization": "Bearer " + admin["access_token"]}


@pytest.fixture
def inspector_headers(inspector):
    return {"Authorization": "Bearer " + inspector["access_token"]}


# --------------------------------------------------------------------------- #
# Label fixtures used by the rule tests
# --------------------------------------------------------------------------- #

def as_segments(lines):
    """Turns label lines into OCR-shaped segments with plausible geometry."""
    segments = []
    for i, text in enumerate(lines):
        top = 10 + i * 40
        segments.append({
            "text": text,
            "box": [[10, top], [420, top], [420, top + 30], [10, top + 30]],
            "confidence": 0.98,
        })
    return segments


COMPLIANT_LABEL = [
    "PREMIUM ROASTED ALMONDS",
    "Marketed by: Almonds Fresh Pvt Ltd, Plot 14, Okhla Phase II, New Delhi - 110020",
    "Net Quantity: 500 g",
    "MRP Rs. 450.00 (Inclusive of all taxes)",
    "Mfg Date: 02/2026",
    "Customer Care Email: support@almondsfresh.com",
    "Helpline: 1800-111-2233",
    "Country of Origin: India",
]
