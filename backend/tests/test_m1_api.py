import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.ingestion.service import FixtureIngestionService
from app.main import app
from app.models import Company


@pytest.fixture(scope="module")
def client():
    with SessionLocal() as db:
        existing = db.scalars(select(Company).where(Company.ticker == "BBCA")).first()
        if existing is None:
            FixtureIngestionService(db).run()
    with TestClient(app) as test_client:
        yield test_client


def test_catalog_endpoints(client):
    companies = client.get("/api/v1/companies").json()
    assert any(company["ticker"] == "BBCA" for company in companies)

    periods = client.get("/api/v1/periods", params={"ticker": "BBCA"}).json()
    assert any(period["label"] == "FY2025" for period in periods)

    documents = client.get(
        "/api/v1/documents", params={"ticker": "BBCA", "year": 2025, "period": "audit"}
    ).json()
    assert {document["file_role"] for document in documents} == {
        "instance_xbrl",
        "inline_xbrl",
        "spreadsheet",
        "pdf",
    }


def test_statement_endpoint_returns_values_and_provenance(client):
    response = client.get(
        "/api/v1/statements/BBCA",
        params={"period": "FY2025", "statement": "balance_sheet", "basis": "consolidated"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "BBCA"
    assert len(payload["facts"]) == 5

    values = {
        fact["concept"].split(":")[-1]: fact["value_display"] for fact in payload["facts"]
    }
    assert values == {
        "Cash": "25,305,031",
        "Assets": "1,586,828,536",
        "Liabilities": "1,294,508,286",
        "Equity": "281,687,555",
        "TemporarySyirkahFunds": "10,632,695",
    }
    for fact in payload["facts"]:
        assert fact["source_fact_id"]
        assert fact["source_context_ref"]
        assert fact["source_file"]
        assert fact["source_url"].startswith("https://www.idx.id")
        assert fact["validation_status"] == "passed"


def test_income_statement_and_cash_flow_counts(client):
    income = client.get(
        "/api/v1/statements/BBCA",
        params={"period": "FY2025", "statement": "income_statement", "basis": "consolidated"},
    ).json()
    cash_flow = client.get(
        "/api/v1/statements/BBCA",
        params={"period": "FY2025", "statement": "cash_flow", "basis": "consolidated"},
    ).json()
    assert len(income["facts"]) == 5
    assert len(cash_flow["facts"]) == 3
