from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.core.db import SessionLocal
from app.metrics.service import recalculate_metrics
from app.models import (
    Company,
    FinancialAccount,
    FinancialDocument,
    FinancialFact,
    FinancialMetric,
    FinancialMetricInput,
    FinancialPeriod,
    IngestionJob,
    TaxonomyVersion,
)
from app.normalization.accounts import AccountNormalizer, ensure_reference_data

ROLE_FIXTURES = (
    ("NET_INCOME", "Profit (loss) attributable to parent entity", "income_statement", "20", "duration"),
    ("REVENUE", "Total revenue", "income_statement", "100", "duration"),
    ("COST_OF_GOODS_SOLD", "Cost of goods sold", "income_statement", "50", "duration"),
    ("OPERATING_CASH_FLOW", "Total net cash flows received from (used in) operating activities", "cash_flow", "80", "duration"),
    ("CAPITAL_EXPENDITURE", "Capital expenditure", "cash_flow", "30", "duration"),
    ("TOTAL_ASSETS", "Total assets", "balance_sheet", "200", "instant"),
    ("TOTAL_EQUITY", "Total equity", "balance_sheet", "100", "instant"),
    ("CURRENT_ASSETS", "Total current assets", "balance_sheet", "200", "instant"),
    ("CURRENT_LIABILITIES", "Total current liabilities", "balance_sheet", "100", "instant"),
    ("QUICK_ASSETS", "Quick assets (current assets less inventory and prepaid items)", "balance_sheet", "100", "instant"),
    ("TOTAL_DEBT", "Total interest-bearing debt", "balance_sheet", "50", "instant"),
    ("TOTAL_LIABILITIES", "Total liabilities", "balance_sheet", "200", "instant"),
    ("INVENTORY", "Total inventories", "balance_sheet", "30", "instant"),
)

OPENING_FIXTURES = (
    ("TOTAL_ASSETS", "Total assets", "200"),
    ("TOTAL_EQUITY", "Total equity", "100"),
    ("INVENTORY", "Total inventories", "20"),
)

EXPECTED_VALUES = {
    "NET_PROFIT_MARGIN": Decimal("0.2"),
    "ROA": Decimal("0.1"),
    "ROE": Decimal("0.2"),
    "CURRENT_RATIO": Decimal("2"),
    "QUICK_RATIO": Decimal("1"),
    "DEBT_TO_EQUITY_TOTAL_DEBT": Decimal("0.5"),
    "LIABILITIES_TO_EQUITY": Decimal("2"),
    "DEBT_TO_ASSET": Decimal("0.25"),
    "ASSET_TURNOVER": Decimal("0.5"),
    "INVENTORY_TURNOVER": Decimal("2"),
    "FREE_CASH_FLOW": Decimal("50"),
}


def test_all_metrics_have_runtime_input_path_from_normalized_facts():
    with SessionLocal() as db:
        savepoint = db.begin_nested()
        try:
            company = db.scalars(select(Company).limit(1)).first()
            taxonomy = db.scalars(select(TaxonomyVersion).limit(1)).first()
            assert company is not None and taxonomy is not None
            company_id = company.id
            taxonomy_version_id = taxonomy.id
            document = db.scalars(select(FinancialDocument).limit(1)).first()
            job = db.scalars(select(IngestionJob).limit(1)).first()
            assert document is not None and job is not None

            current = FinancialPeriod(
                company_id=company_id,
                fiscal_year=2099,
                calendar_year=2099,
                period_type="FY",
                period_sequence=4,
                is_ytd=True,
                start_date=date(2099, 1, 1),
                end_date=date(2099, 12, 31),
                instant_date=date(2099, 12, 31),
                source_period_code="TEST-FY2099",
                label="Test FY2099",
            )
            prior = FinancialPeriod(
                company_id=company_id,
                fiscal_year=2098,
                calendar_year=2098,
                period_type="FY",
                period_sequence=4,
                is_ytd=True,
                start_date=date(2098, 1, 1),
                end_date=date(2098, 12, 31),
                instant_date=date(2098, 12, 31),
                source_period_code="TEST-FY2098",
                label="Test FY2098",
            )
            db.add_all((current, prior))
            db.flush()
            ensure_reference_data(db)
            normalizer = AccountNormalizer(db)
            token = uuid4().hex[:8]

            def add_fact(
                *,
                role: str,
                source_name: str,
                statement_type: str,
                value: str,
                period: FinancialPeriod,
                period_kind: str,
            ) -> None:
                account = FinancialAccount(
                    taxonomy_version_id=taxonomy_version_id,
                    concept_code=f"idx-cor:Test{token}{role}{period.fiscal_year}",
                    concept_qname=f"idx-cor:Test{token}{role}{period.fiscal_year}",
                    namespace="http://example.invalid/test",
                    label_en=source_name,
                    statement_type=statement_type,
                )
                db.add(account)
                db.flush()
                if period_kind == "instant":
                    start_date = None
                    end_date = None
                    instant_date = period.instant_date
                    duration_kind = "not_applicable"
                else:
                    start_date = period.start_date
                    end_date = period.end_date
                    instant_date = None
                    duration_kind = "full_year"
                fact = FinancialFact(
                    company_id=company_id,
                    period_id=period.id,
                    document_id=document.id,
                    account_id=account.id,
                    ingestion_job_id=job.id,
                    source_fact_id=f"test-{token}-{role}-{period.fiscal_year}",
                    source_context_ref=f"test-context-{token}-{role}-{period.fiscal_year}",
                    context_start_date=start_date,
                    context_end_date=end_date,
                    context_instant_date=instant_date,
                    value_original=value,
                    value_normalized=Decimal(value),
                    currency="IDR",
                    unit="IDR",
                    source_scale=0,
                    reporting_basis="consolidated",
                    validation_status="passed",
                    period_kind=period_kind,
                    duration_kind=duration_kind,
                    accounting_definition_key="m2-v1",
                    document_version=1,
                    publication_status="draft",
                )
                db.add(fact)
                db.flush()
                resolution = normalizer.resolve(
                    source_name,
                    company_id=company_id,
                    taxonomy_version_id=taxonomy_version_id,
                    statement_type=statement_type,
                )
                assert resolution.status == "approved", (source_name, resolution.status, resolution.reason)
                fact.mapping_id = resolution.mapping_id
                db.flush()

            for role, source_name, statement_type, value, period_kind in ROLE_FIXTURES:
                add_fact(
                    role=role,
                    source_name=source_name,
                    statement_type=statement_type,
                    value=value,
                    period=current,
                    period_kind=period_kind,
                )
            for role, source_name, value in OPENING_FIXTURES:
                add_fact(
                    role=f"OPENING_{role}",
                    source_name=source_name,
                    statement_type="balance_sheet",
                    value=value,
                    period=prior,
                    period_kind="instant",
                )

            results = recalculate_metrics(
                db,
                company_id=company_id,
                period_id=current.id,
                basis="consolidated",
            )
            by_code = {row["code"]: row for row in results}
            assert set(by_code) == set(EXPECTED_VALUES)
            for code, expected in EXPECTED_VALUES.items():
                row = by_code[code]
                assert row["calculation_status"] == "calculated", (code, row["unavailable_reason"])
                assert row["value"] == expected, (code, row["value"], expected)
                assert row["formula_version"] == "m2-v1"
                assert row["currency"] if "currency" in row else True
                metric = db.get(FinancialMetric, row["id"])
                assert metric.currency == "IDR"
                assert metric.input_document_versions == [1] * len(metric.input_document_versions)
                assert len(metric.input_document_versions) > 0

            for row in results:
                metric = db.get(FinancialMetric, row["id"])
                inputs = db.scalars(
                    select(FinancialMetricInput).where(
                        FinancialMetricInput.financial_metric_id == metric.id
                    )
                ).all()
                assert len(inputs) == len(metric.formula_definition["roles"])
                assert all(item.input_fact_id is not None for item in inputs)
        finally:
            savepoint.rollback()
