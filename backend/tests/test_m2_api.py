from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.core.security import bootstrap_user
from app.main import app
from app.validation.lifecycle import VALIDATION_STATUSES

client = TestClient(app)
ADMIN_EMAIL = "api-admin@localhost.invalid"
ANALYST_EMAIL = "api-analyst@localhost.invalid"
PASSWORD = "local-m2-test-password"


def _seed_users() -> None:
    db = SessionLocal()
    try:
        bootstrap_user(
            db,
            email=ADMIN_EMAIL,
            password=PASSWORD,
            display_name="M2 API test admin",
            roles=("admin", "reviewer", "publisher", "analyst", "viewer"),
        )
        bootstrap_user(
            db,
            email=ANALYST_EMAIL,
            password=PASSWORD,
            display_name="M2 API test analyst",
            roles=("analyst", "viewer"),
        )
        db.commit()
    finally:
        db.close()


def _token(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_unauthenticated_metrics_requires_bearer_token():
    response = client.get("/api/v1/metrics", params={"ticker": "BBCA", "period": "2025"})
    assert response.status_code == 401


def test_login_and_current_user():
    _seed_users()
    token = _token(ADMIN_EMAIL)
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == ADMIN_EMAIL
    assert "admin" in response.json()["roles"]


def test_statement_api_exposes_m2_provenance():
    response = client.get(
        "/api/v1/statements/BBCA",
        params={"period": "2025", "statement": "balance_sheet", "basis": "consolidated"},
    )
    assert response.status_code == 200, response.text
    facts = response.json()["facts"]
    assert facts
    for fact in facts:
        assert "document_version" in fact
        assert "publication_status" in fact
        assert "period_kind" in fact
        assert "standard_account" in fact
        assert "source_context_details" in fact


def test_validation_run_uses_workflow_statuses():
    _seed_users()
    token = _token(ANALYST_EMAIL)
    response = client.post(
        "/api/v1/validation/run",
        params={"ticker": "BBCA", "period": "2025", "basis": "consolidated"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["run"]["status"] in VALIDATION_STATUSES
    assert isinstance(payload["issues"], list)
    assert all(issue["severity_level"] in {"INFO", "WARNING", "ERROR"} for issue in payload["issues"])


def test_publish_requires_publisher_role():
    _seed_users()
    token = _token(ANALYST_EMAIL)
    response = client.post(
        "/api/v1/publication/publish",
        json={"ticker": "BBCA", "period": "2025", "basis": "consolidated"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
