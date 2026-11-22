from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Company, FinancialDocument, FinancialPeriod

from .schemas import CompanyRead, DocumentRead, PeriodRead

router = APIRouter()


@router.get("/companies", response_model=list[CompanyRead])
def list_companies(db: Session = Depends(get_db)) -> list[CompanyRead]:
    companies = db.scalars(
        select(Company).where(Company.is_active.is_(True)).order_by(Company.ticker)
    ).all()
    return list(companies)


@router.get("/periods", response_model=list[PeriodRead])
def list_periods(
    ticker: str = Query(..., description="Issuer ticker, e.g. BBCA"),
    db: Session = Depends(get_db),
) -> list[PeriodRead]:
    periods = db.scalars(
        select(FinancialPeriod)
        .join(Company, FinancialPeriod.company_id == Company.id)
        .where(Company.ticker == ticker.upper())
        .order_by(FinancialPeriod.fiscal_year.desc(), FinancialPeriod.period_sequence.desc())
    ).all()
    return list(periods)


@router.get("/documents", response_model=list[DocumentRead])
def list_documents(
    ticker: str | None = Query(None),
    year: int | None = Query(None),
    period: str | None = Query(None, description="audit, tw1, tw2, or tw3"),
    db: Session = Depends(get_db),
) -> list[DocumentRead]:
    query = (
        select(FinancialDocument)
        .join(Company, FinancialDocument.company_id == Company.id)
        .join(FinancialPeriod, FinancialDocument.period_id == FinancialPeriod.id)
    )
    if ticker:
        query = query.where(Company.ticker == ticker.upper())
    if year is not None:
        query = query.where(FinancialPeriod.fiscal_year == year)
    if period:
        query = query.where(FinancialPeriod.source_period_code == period.lower())
    documents = db.scalars(query.order_by(FinancialDocument.file_role, FinancialDocument.file_name)).all()
    return list(documents)
