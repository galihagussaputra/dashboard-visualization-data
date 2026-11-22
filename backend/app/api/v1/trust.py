from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit, request_context
from app.core.db import get_db
from app.core.security import AuthenticatedUser, require_roles
from app.models import (
    AuditEvent,
    FinancialPeriod,
    PublicationEvent,
    SourceAccountMapping,
    StandardAccount,
    ValidationLog,
)
from app.metrics.service import current_metrics, recalculate_metrics
from app.normalization.accounts import approve_mapping
from app.normalization.derivations import derive_period_values, derived_values_for_scope
from app.normalization.restatement import approve_revision, restatement_summary
from app.publication import PublicationError, publish_scope
from app.validation.lifecycle import evaluate_scope, override_validation_log

from .schemas import (
    AcknowledgeRequest,
    ApproveRequest,
    AuditEventRead,
    DerivedValueRead,
    MappingRead,
    MetricRead,
    PublicationEventRead,
    PublicationRead,
    PublicationRequest,
    RestatementRead,
    ValidationLogRead,
    ValidationOutcomeRead,
    ValidationRunRead,
)
from .statements import _fiscal_year

router = APIRouter()

Analyst = require_roles("analyst", "reviewer", "publisher", "admin")
Reviewer = require_roles("reviewer", "admin")
Publisher = require_roles("publisher", "admin")
Viewer = require_roles("viewer", "analyst", "reviewer", "publisher", "admin")
ReportingBasis = Literal["consolidated", "separate"]


@router.get("/normalization/mappings", response_model=list[MappingRead])
def list_mappings(
    status_filter: str | None = Query(None, alias="status"),
    current: AuthenticatedUser = Depends(Viewer),
    db: Session = Depends(get_db),
) -> list[MappingRead]:
    del current
    statement = (
        select(SourceAccountMapping, StandardAccount.code)
        .outerjoin(StandardAccount, SourceAccountMapping.standard_account_id == StandardAccount.id)
        .order_by(SourceAccountMapping.created_at.desc())
    )
    if status_filter:
        statement = statement.where(SourceAccountMapping.status == status_filter)
    rows = db.execute(statement.limit(200)).all()
    return [
        MappingRead(
            id=mapping.id,
            source_account_name=mapping.source_account_name,
            source_taxonomy_concept=mapping.source_taxonomy_concept,
            standard_account_code=code,
            status=mapping.status,
            confidence=mapping.confidence,
            rule_code=mapping.rule_code,
            rule_version=mapping.rule_version,
            evidence=mapping.evidence,
            reason=(mapping.source_metadata or {}).get("reason"),
            is_current=mapping.is_current,
        )
        for mapping, code in rows
    ]


@router.post("/normalization/mappings/{mapping_id}/approve", response_model=MappingRead)
def approve_account_mapping(
    mapping_id: int,
    payload: ApproveRequest,
    request: Request,
    current: AuthenticatedUser = Depends(Reviewer),
    db: Session = Depends(get_db),
) -> MappingRead:
    mapping = approve_mapping(db, mapping_id, current.user_id, payload.reason)
    record_audit(
        db,
        action="mapping.approve",
        entity_type="source_account_mapping",
        entity_id=str(mapping.id),
        actor_id=current.user_id,
        after_state={"status": mapping.status},
        reason=payload.reason,
        context=request_context(request),
    )
    db.commit()
    code = db.get(StandardAccount, mapping.standard_account_id).code if mapping.standard_account_id else None
    return MappingRead(
        id=mapping.id,
        source_account_name=mapping.source_account_name,
        source_taxonomy_concept=mapping.source_taxonomy_concept,
        standard_account_code=code,
        status=mapping.status,
        confidence=mapping.confidence,
        rule_code=mapping.rule_code,
        rule_version=mapping.rule_version,
        evidence=mapping.evidence,
        reason=(mapping.source_metadata or {}).get("reason"),
        is_current=mapping.is_current,
    )


@router.post("/periods/derive")
def derive_periods(
    request: Request,
    ticker: str = Query(...),
    period: str = Query(...),
    basis: ReportingBasis = Query("consolidated"),
    current: AuthenticatedUser = Depends(Analyst),
    db: Session = Depends(get_db),
) -> dict:
    company, period_row = _resolve_scope(db, ticker, period)
    results = derive_period_values(
        db,
        company_id=company.id,
        fiscal_year=period_row.fiscal_year,
        basis=basis,
        created_by=current.user_id,
    )
    record_audit(
        db,
        action="period.derive",
        entity_type="company_period",
        entity_id=f"{company.ticker}:{period_row.label}:{basis}",
        actor_id=current.user_id,
        after_state={"derived_count": len(results)},
        context=request_context(request),
    )
    db.commit()
    return {"derived": results}


@router.get("/periods/derived", response_model=list[DerivedValueRead])
def list_derived_values(
    ticker: str = Query(...),
    period: str = Query(...),
    basis: ReportingBasis = Query("consolidated"),
    current: AuthenticatedUser = Depends(Viewer),
    db: Session = Depends(get_db),
) -> list[DerivedValueRead]:
    del current
    company, period_row = _resolve_scope(db, ticker, period)
    return [DerivedValueRead(**item) for item in derived_values_for_scope(
        db,
        company_id=company.id,
        period_id=period_row.id,
        basis=basis,
    )]


@router.post("/metrics/recalculate")
def recalculate(
    request: Request,
    ticker: str = Query(...),
    period: str = Query(...),
    basis: ReportingBasis = Query("consolidated"),
    current: AuthenticatedUser = Depends(Analyst),
    db: Session = Depends(get_db),
) -> dict:
    company, period_row = _resolve_scope(db, ticker, period)
    results = recalculate_metrics(
        db,
        company_id=company.id,
        period_id=period_row.id,
        basis=basis,
    )
    record_audit(
        db,
        action="metrics.recalculate",
        entity_type="company_period",
        entity_id=f"{company.ticker}:{period_row.label}:{basis}",
        actor_id=current.user_id,
        after_state={"metric_count": len(results)},
        context=request_context(request),
    )
    db.commit()
    return {"metrics": results}


@router.get("/metrics", response_model=list[MetricRead])
def list_metrics(
    ticker: str = Query(...),
    period: str = Query(...),
    basis: ReportingBasis = Query("consolidated"),
    published_only: bool = Query(False),
    current: AuthenticatedUser = Depends(Viewer),
    db: Session = Depends(get_db),
) -> list[MetricRead]:
    del current
    company, period_row = _resolve_scope(db, ticker, period)
    return [MetricRead(**item) for item in current_metrics(
        db,
        company_id=company.id,
        period_id=period_row.id,
        basis=basis,
        published_only=published_only,
    )]


@router.post("/validation/run", response_model=ValidationOutcomeRead)
def run_validation(
    request: Request,
    ticker: str = Query(...),
    period: str = Query(...),
    basis: ReportingBasis = Query("consolidated"),
    current: AuthenticatedUser = Depends(Analyst),
    db: Session = Depends(get_db),
) -> ValidationOutcomeRead:
    company, period_row = _resolve_scope(db, ticker, period)
    outcome = evaluate_scope(
        db,
        company_id=company.id,
        period_id=period_row.id,
        basis=basis,
        actor_id=current.user_id,
    )
    record_audit(
        db,
        action="validation.run",
        entity_type="validation_run",
        entity_id=str(outcome.run.id),
        actor_id=current.user_id,
        after_state=outcome.run.summary,
        context=request_context(request),
    )
    db.commit()
    logs = db.scalars(
        select(ValidationLog).where(ValidationLog.validation_run_id == outcome.run.id)
    ).all()
    return ValidationOutcomeRead(
        run=ValidationRunRead(**_model_dict(outcome.run)),
        issues=[ValidationLogRead(**_model_dict(log)) for log in logs],
        can_publish=outcome.can_publish,
        failures=[f"{issue.rule_code}: {issue.message}" for issue in outcome.failures],
        warnings=[f"{issue.rule_code}: {issue.message}" for issue in outcome.warnings],
    )


@router.get("/validation/logs", response_model=list[ValidationLogRead])
def list_validation_logs(
    current: AuthenticatedUser = Depends(Viewer),
    db: Session = Depends(get_db),
) -> list[ValidationLogRead]:
    del current
    logs = db.scalars(select(ValidationLog).order_by(ValidationLog.created_at.desc()).limit(200)).all()
    return [ValidationLogRead(**_model_dict(log)) for log in logs]


@router.post("/validation/warnings/{log_id}/acknowledge", response_model=ValidationLogRead)
def acknowledge_warning(
    log_id: int,
    payload: AcknowledgeRequest,
    request: Request,
    current: AuthenticatedUser = Depends(Reviewer),
    db: Session = Depends(get_db),
) -> ValidationLogRead:
    try:
        log = override_validation_log(db, log_id, current.user_id, payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    record_audit(
        db,
        action="validation.warning_acknowledge",
        entity_type="validation_log",
        entity_id=str(log.id),
        actor_id=current.user_id,
        after_state={"status": log.status, "review_policy": log.review_policy},
        reason=payload.reason,
        context=request_context(request),
    )
    db.commit()
    return ValidationLogRead(**_model_dict(log))


@router.get("/restatements", response_model=list[RestatementRead])
def list_restatements(
    ticker: str | None = Query(None),
    period: str | None = Query(None),
    current: AuthenticatedUser = Depends(Viewer),
    db: Session = Depends(get_db),
) -> list[RestatementRead]:
    del current
    company_id = None
    period_id = None
    if ticker:
        from app.models import Company

        company = db.scalars(select(Company).where(Company.ticker == ticker.upper())).first()
        if company is None:
            raise HTTPException(status_code=404, detail=f"company {ticker} not found")
        company_id = company.id
    if period:
        _, period_row = _resolve_scope(db, ticker or "", period)
        period_id = period_row.id
    return [RestatementRead(**item) for item in restatement_summary(
        db,
        company_id=company_id,
        period_id=period_id,
    )]


@router.post("/restatements/{revision_id}/approve", response_model=RestatementRead)
def approve_fact_revision(
    revision_id: int,
    payload: ApproveRequest,
    request: Request,
    current: AuthenticatedUser = Depends(Reviewer),
    db: Session = Depends(get_db),
) -> RestatementRead:
    try:
        revision = approve_revision(
            db,
            revision_id=revision_id,
            actor_id=current.user_id,
            reason=payload.reason,
            context=request_context(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    item = next(item for item in restatement_summary(db) if item["id"] == revision.id)
    return RestatementRead(**item)


@router.post("/publication/publish", response_model=PublicationRead)
def publish(
    payload: PublicationRequest,
    request: Request,
    current: AuthenticatedUser = Depends(Publisher),
    db: Session = Depends(get_db),
) -> PublicationRead:
    company, period_row = _resolve_scope(db, payload.ticker, payload.period)
    try:
        result = publish_scope(
            db,
            company_id=company.id,
            period_id=period_row.id,
            basis=payload.basis,
            actor_id=current.user_id,
            context=request_context(request),
        )
    except PublicationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(exc), "issues": exc.issues},
        ) from exc
    db.commit()
    return PublicationRead(
        id=result.event.id,
        status=result.event.status,
        validation_run_id=result.event.validation_run_id,
        facts_published=result.facts_published,
        metrics_published=result.metrics_published,
        created_at=result.event.created_at,
    )


@router.get("/publication/events", response_model=list[PublicationEventRead])
def list_publication_events(
    current: AuthenticatedUser = Depends(Viewer),
    db: Session = Depends(get_db),
) -> list[PublicationEventRead]:
    del current
    events = db.scalars(
        select(PublicationEvent).order_by(PublicationEvent.created_at.desc()).limit(100)
    ).all()
    return [PublicationEventRead(**_model_dict(event)) for event in events]


@router.get("/audit/events", response_model=list[AuditEventRead])
def list_audit_events(
    current: AuthenticatedUser = Depends(Reviewer),
    db: Session = Depends(get_db),
) -> list[AuditEventRead]:
    del current
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(200)).all()
    return [AuditEventRead(**_model_dict(event)) for event in events]


def _resolve_scope(db: Session, ticker: str, period: str):
    from app.models import Company

    fiscal_year = _fiscal_year(period)
    if ticker:
        company = db.scalars(select(Company).where(Company.ticker == ticker.upper())).first()
        if company is None:
            raise HTTPException(status_code=404, detail=f"company {ticker} not found")
    else:
        company = db.scalars(select(Company).order_by(Company.id).limit(1)).first()
        if company is None:
            raise HTTPException(status_code=404, detail="no company available")
    period_row = db.scalars(
        select(FinancialPeriod).where(
            FinancialPeriod.company_id == company.id,
            FinancialPeriod.fiscal_year == fiscal_year,
        )
    ).first()
    if period_row is None:
        raise HTTPException(status_code=404, detail=f"period {period} not found for {company.ticker}")
    return company, period_row


def _model_dict(model) -> dict:
    return {
        column.name: getattr(model, column.name)
        for column in model.__table__.columns
    }
