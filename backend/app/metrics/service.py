from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    FinancialAccount,
    FinancialDocument,
    FinancialFact,
    FinancialMetric,
    FinancialPeriod,
    MetricDefinition,
    SourceAccountMapping,
    StandardAccount,
)

from app.normalization.accounts import backfill_fact_mappings

from .calculator import MetricInput, calculate_metric, ensure_metric_definitions, persist_metric
from .definitions import METRIC_SPECS


def recalculate_metrics(
    db: Session,
    *,
    company_id: int,
    period_id: int,
    basis: str,
    calculated_at: datetime | None = None,
) -> list[dict[str, Any]]:
    definitions = ensure_metric_definitions(db)
    backfill_fact_mappings(db, company_id=company_id, period_id=period_id)
    inputs = _collect_inputs(db, company_id=company_id, period_id=period_id, basis=basis)
    now = calculated_at or datetime.now(timezone.utc)
    results: list[dict[str, Any]] = []
    for spec in METRIC_SPECS:
        selected = {role: inputs[role] for role in spec.inputs if role in inputs}
        computation = calculate_metric(
            spec.code,
            selected,
            formula_version=spec.version,
            calculated_at=now,
        )
        metric = persist_metric(
            db,
            company_id=company_id,
            period_id=period_id,
            definition_id=definitions[spec.code],
            computation=computation,
            inputs=selected,
            reporting_basis=basis,
        )
        results.append(
            {
                "id": metric.id,
                "code": spec.code,
                "name": spec.name,
                "value": metric.value,
                "unit": metric.unit,
                "calculation_status": metric.calculation_status,
                "unavailable_reason": metric.unavailable_reason,
                "validation_warnings": metric.validation_warnings,
                "formula_version": metric.formula_version,
                "formula_definition": metric.formula_definition,
                "input_document_versions": metric.input_document_versions,
            }
        )
    return results


def current_metrics(
    db: Session,
    *,
    company_id: int,
    period_id: int,
    basis: str,
    published_only: bool = False,
) -> list[dict[str, Any]]:
    statement = (
        select(FinancialMetric, MetricDefinition)
        .join(MetricDefinition, FinancialMetric.metric_definition_id == MetricDefinition.id)
        .where(
            FinancialMetric.company_id == company_id,
            FinancialMetric.period_id == period_id,
            FinancialMetric.reporting_basis == basis,
            FinancialMetric.is_current.is_(True),
        )
    )
    if published_only:
        statement = statement.where(FinancialMetric.publication_status == "published")
    rows = db.execute(statement.order_by(MetricDefinition.code)).all()
    return [
        {
            "id": metric.id,
            "code": definition.code,
            "name": definition.name,
            "value": metric.value,
            "unit": metric.unit,
            "calculation_status": metric.calculation_status,
            "unavailable_reason": metric.unavailable_reason,
            "validation_warnings": metric.validation_warnings,
            "formula_version": metric.formula_version,
            "formula_definition": metric.formula_definition,
            "input_document_versions": metric.input_document_versions,
            "publication_status": metric.publication_status,
        }
        for metric, definition in rows
    ]


def _collect_inputs(db: Session, *, company_id: int, period_id: int, basis: str) -> dict[str, MetricInput]:
    rows = db.execute(
        select(
            FinancialFact,
            FinancialAccount,
            FinancialPeriod,
            FinancialDocument,
            StandardAccount.code,
        )
        .join(FinancialAccount, FinancialFact.account_id == FinancialAccount.id)
        .join(FinancialPeriod, FinancialFact.period_id == FinancialPeriod.id)
        .join(FinancialDocument, FinancialFact.document_id == FinancialDocument.id)
        .join(SourceAccountMapping, FinancialFact.mapping_id == SourceAccountMapping.id)
        .join(StandardAccount, SourceAccountMapping.standard_account_id == StandardAccount.id)
        .where(
            FinancialFact.company_id == company_id,
            FinancialFact.period_id == period_id,
            FinancialFact.reporting_basis == basis,
            FinancialFact.is_current.is_(True),
        )
    ).all()

    inputs: dict[str, MetricInput] = {}
    for fact, account, period, document, standard_code in rows:
        metric = _to_input(fact, period)
        if fact.period_kind == "duration":
            inputs.setdefault(standard_code, metric)
        elif standard_code in {"TOTAL_ASSETS", "TOTAL_EQUITY", "INVENTORY"}:
            suffix = {
                "TOTAL_ASSETS": "TOTAL_ASSETS",
                "TOTAL_EQUITY": "EQUITY",
                "INVENTORY": "INVENTORY",
            }[standard_code]
            inputs.setdefault(standard_code, metric)
            inputs.setdefault("CLOSING_TOTAL_ASSETS" if standard_code == "TOTAL_ASSETS" else f"CLOSING_{suffix}", metric)
        del account, document

    prior_opening = {
        "TOTAL_ASSETS": "OPENING_TOTAL_ASSETS",
        "TOTAL_EQUITY": "OPENING_EQUITY",
        "INVENTORY": "OPENING_INVENTORY",
    }
    for standard_code, role in prior_opening.items():
        opening = _prior_period_input(db, company_id, period_id, basis, standard_code)
        if opening is not None:
            inputs[role] = opening
    return inputs


def _to_input(fact: FinancialFact, period: FinancialPeriod) -> MetricInput:
    return MetricInput(
        role="",
        value=Decimal(str(fact.value_normalized)),
        company_id=fact.company_id,
        period_id=fact.period_id,
        fiscal_year=period.fiscal_year,
        period_start=fact.context_start_date or period.start_date,
        period_end=fact.context_end_date or fact.context_instant_date or period.end_date,
        period_kind=fact.period_kind,
        duration_kind=fact.duration_kind,
        reporting_basis=fact.reporting_basis,
        currency=fact.currency,
        unit=fact.unit,
        fact_id=fact.id,
        document_version=fact.document_version,
        validation_status=fact.validation_status,
    )


def _prior_period_input(
    db: Session,
    company_id: int,
    period_id: int,
    basis: str,
    standard_code: str,
) -> MetricInput | None:
    period = db.get(FinancialPeriod, period_id)
    if period is None:
        return None
    previous = db.scalars(
        select(FinancialPeriod).where(
            FinancialPeriod.company_id == company_id,
            FinancialPeriod.fiscal_year == period.fiscal_year - 1,
        )
    ).first()
    if previous is None:
        return None
    fact = db.scalars(
        select(FinancialFact)
        .join(SourceAccountMapping, FinancialFact.mapping_id == SourceAccountMapping.id)
        .join(StandardAccount, SourceAccountMapping.standard_account_id == StandardAccount.id)
        .where(
            FinancialFact.company_id == company_id,
            FinancialFact.period_id == previous.id,
            FinancialFact.reporting_basis == basis,
            FinancialFact.is_current.is_(True),
            FinancialFact.period_kind == "instant",
            StandardAccount.code == standard_code,
        )
    ).first()
    if fact is None:
        return None
    return _to_input(fact, previous)
