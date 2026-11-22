from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import (
    Company,
    FinancialAccount,
    FinancialDocument,
    FinancialFact,
    FinancialPeriod,
    SourceAccountMapping,
    StandardAccount,
)
from app.normalization.registry import ALL_CONCEPTS
from app.normalization.restatement import resolve_facts
from app.publication import published_scope_exists

from .schemas import StatementFactRead, StatementRead

router = APIRouter()

StatementName = Literal[
    "balance_sheet",
    "income_statement",
    "cash_flow",
    "equity",
    "comprehensive_income",
]
ReportingBasis = Literal["consolidated", "separate", "unknown"]
Visibility = Literal["draft", "published"]

CONCEPT_ORDER = {spec.concept: index for index, spec in enumerate(ALL_CONCEPTS)}


@router.get("/statements/{ticker}", response_model=StatementRead)
def get_statement(
    ticker: str,
    period: str = Query(..., description="FY2025 or 2025"),
    statement: StatementName = Query("balance_sheet"),
    basis: ReportingBasis = Query("consolidated"),
    visibility: Visibility = Query("draft"),
    as_of: date | None = Query(None),
    db: Session = Depends(get_db),
) -> StatementRead:
    ticker = ticker.upper()
    fiscal_year = _fiscal_year(period)

    company = db.scalars(select(Company).where(Company.ticker == ticker)).first()
    if company is None:
        raise HTTPException(status_code=404, detail=f"company {ticker} not found")

    period_row = db.scalars(
        select(FinancialPeriod).where(
            FinancialPeriod.company_id == company.id,
            FinancialPeriod.fiscal_year == fiscal_year,
        )
    ).first()
    if period_row is None:
        raise HTTPException(status_code=404, detail=f"period {period} not found for {ticker}")

    published_only = visibility == "published"
    if published_only and not published_scope_exists(db, company.id, period_row.id, basis):
        raise HTTPException(status_code=404, detail=f"no published {basis} snapshot for {ticker} {period}")

    allowed_concepts = [
        spec.concept
        for spec in ALL_CONCEPTS
        if spec.statement_type == statement
        and (spec.is_core or spec.local_name == "TemporarySyirkahFunds")
    ]
    facts = resolve_facts(
        db,
        company_id=company.id,
        period_id=period_row.id,
        basis=basis,
        as_of=as_of,
        published_only=published_only,
    )
    fact_ids = {fact.id for fact in facts}
    rows = []
    if fact_ids:
        rows = db.execute(
            select(
                FinancialFact,
                FinancialAccount,
                FinancialDocument,
                StandardAccount.code,
                SourceAccountMapping.status,
            )
            .join(FinancialAccount, FinancialFact.account_id == FinancialAccount.id)
            .join(FinancialDocument, FinancialFact.document_id == FinancialDocument.id)
            .outerjoin(SourceAccountMapping, FinancialFact.mapping_id == SourceAccountMapping.id)
            .outerjoin(StandardAccount, SourceAccountMapping.standard_account_id == StandardAccount.id)
            .where(
                FinancialFact.id.in_(fact_ids),
                FinancialAccount.statement_type == statement,
                FinancialAccount.concept_code.in_(allowed_concepts),
            )
        ).all()

    facts_out = [
        _to_fact_schema(fact, account, document, standard_code, mapping_status)
        for fact, account, document, standard_code, mapping_status in rows
    ]
    facts_out.sort(key=lambda item: CONCEPT_ORDER.get(item.concept, 999))

    return StatementRead(
        ticker=company.ticker,
        company_name=company.name,
        period=period_row.label,
        period_label=period_row.label,
        basis=basis,
        statement=statement,
        facts=facts_out,
    )


def _fiscal_year(period: str) -> int:
    value = period.strip().upper()
    if value.startswith("FY"):
        value = value[2:]
    try:
        return int(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="period must be FY2025 or 2025") from exc


def _to_fact_schema(
    fact: FinancialFact,
    account: FinancialAccount,
    document: FinancialDocument,
    standard_code: str | None,
    mapping_status: str | None,
) -> StatementFactRead:
    if account.data_type == "per_share":
        display_scale = 0
        displayed = f"{fact.value_normalized:,.0f}"
    else:
        display_scale = 6
        displayed = f"{fact.value_normalized / Decimal(10**display_scale):,.0f}"
    return StatementFactRead(
        concept=account.concept_code,
        label_id=account.label_id,
        label_en=account.label_en,
        statement_type=account.statement_type,
        value_normalized=fact.value_normalized,
        value_display=displayed,
        display_scale=display_scale,
        currency=fact.currency,
        unit=fact.unit,
        source_scale=fact.source_scale,
        source_fact_id=fact.source_fact_id,
        source_context_ref=fact.source_context_ref,
        source_file=document.file_name,
        source_url=document.source_url,
        validation_status=fact.validation_status,
        document_version=fact.document_version,
        publication_status=fact.publication_status,
        period_kind=fact.period_kind,
        duration_kind=fact.duration_kind,
        standard_account=standard_code,
        mapping_status=mapping_status,
        source_context_details=fact.source_context_details or {},
    )
