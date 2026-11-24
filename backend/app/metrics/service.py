from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
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

DURATION_ROLES_BY_STANDARD = {
    "NET_INCOME": "NET_INCOME",
    "REVENUE": "REVENUE",
    "COST_OF_GOODS_SOLD": "COST_OF_GOODS_SOLD",
    "OPERATING_CASH_FLOW": "OPERATING_CASH_FLOW",
    "CAPITAL_EXPENDITURE": "CAPITAL_EXPENDITURE",
}

INSTANT_ROLES_BY_STANDARD = {
    "TOTAL_ASSETS": ("TOTAL_ASSETS", "CLOSING_TOTAL_ASSETS"),
    "TOTAL_EQUITY": ("TOTAL_EQUITY", "CLOSING_EQUITY"),
    "INVENTORY": ("INVENTORY", "CLOSING_INVENTORY"),
    "CURRENT_ASSETS": ("CURRENT_ASSETS",),
    "CURRENT_LIABILITIES": ("CURRENT_LIABILITIES",),
    "QUICK_ASSETS": ("QUICK_ASSETS",),
    "TOTAL_DEBT": ("TOTAL_DEBT",),
    "TOTAL_LIABILITIES": ("TOTAL_LIABILITIES",),
}

OPENING_ROLES_BY_STANDARD = {
    "TOTAL_ASSETS": "OPENING_TOTAL_ASSETS",
    "TOTAL_EQUITY": "OPENING_EQUITY",
    "INVENTORY": "OPENING_INVENTORY",
}


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
    period = db.get(FinancialPeriod, period_id)
    if period is None:
        return {}
    current_rows = _fact_rows(
        db,
        company_id=company_id,
        basis=basis,
        period_id=period_id,
    )
    all_rows = _fact_rows(db, company_id=company_id, basis=basis)
    inputs: dict[str, MetricInput] = {}

    for standard_code, role in DURATION_ROLES_BY_STANDARD.items():
        selected = _select_duration(current_rows, standard_code, period)
        if selected is not None:
            inputs[role] = replace(selected, role=role)

    closing_date = period.instant_date
    for standard_code, roles in INSTANT_ROLES_BY_STANDARD.items():
        selected = _select_instant(
            current_rows,
            standard_code,
            closing_date,
            lower_bound=period.start_date,
        )
        if selected is None:
            continue
        for role in roles:
            inputs[role] = replace(selected, role=role)

    excluded_ids = {
        value.fact_id
        for role, value in inputs.items()
        if role in {"CLOSING_TOTAL_ASSETS", "CLOSING_EQUITY", "CLOSING_INVENTORY"}
        and value.fact_id is not None
    }
    for standard_code, role in OPENING_ROLES_BY_STANDARD.items():
        selected = _select_instant(
            all_rows,
            standard_code,
            period.start_date,
            lower_bound=None,
            excluded_ids=excluded_ids,
        )
        if selected is not None:
            inputs[role] = replace(selected, role=role)
    return inputs


def _fact_rows(
    db: Session,
    *,
    company_id: int,
    basis: str,
    period_id: int | None = None,
) -> list[tuple[FinancialFact, FinancialPeriod, str]]:
    statement = (
        select(FinancialFact, FinancialPeriod, StandardAccount.code)
        .join(FinancialPeriod, FinancialFact.period_id == FinancialPeriod.id)
        .join(SourceAccountMapping, FinancialFact.mapping_id == SourceAccountMapping.id)
        .join(StandardAccount, SourceAccountMapping.standard_account_id == StandardAccount.id)
        .where(
            FinancialFact.company_id == company_id,
            FinancialFact.reporting_basis == basis,
            FinancialFact.is_current.is_(True),
            FinancialFact.mapping_id.is_not(None),
            SourceAccountMapping.status == "approved",
            SourceAccountMapping.is_current.is_(True),
        )
    )
    if period_id is not None:
        statement = statement.where(FinancialFact.period_id == period_id)
    return db.execute(statement).all()


def _select_duration(
    rows: list[tuple[FinancialFact, FinancialPeriod, str]],
    standard_code: str,
    period: FinancialPeriod,
) -> MetricInput | None:
    candidates = [
        (fact, fact_period)
        for fact, fact_period, code in rows
        if code == standard_code and fact.period_kind == "duration"
    ]
    if not candidates:
        return None
    selected = min(candidates, key=lambda row: _duration_rank(row[0], period))
    return _to_input(selected[0], selected[1])


def _select_instant(
    rows: list[tuple[FinancialFact, FinancialPeriod, str]],
    standard_code: str,
    target_date: date,
    *,
    lower_bound: date | None,
    excluded_ids: set[int] | None = None,
) -> MetricInput | None:
    candidates: list[tuple[FinancialFact, FinancialPeriod]] = []
    for fact, fact_period, code in rows:
        if code != standard_code or fact.period_kind != "instant":
            continue
        if excluded_ids and fact.id in excluded_ids:
            continue
        instant_date = _instant_date(fact, fact_period)
        if instant_date is None or instant_date > target_date:
            continue
        if lower_bound is not None and instant_date < lower_bound:
            continue
        candidates.append((fact, fact_period))
    if not candidates:
        return None
    selected = min(candidates, key=lambda row: _instant_rank(row[0], row[1], target_date))
    return _to_input(selected[0], selected[1])


def _duration_rank(fact: FinancialFact, period: FinancialPeriod) -> tuple[int, int, int, int]:
    exact = fact.context_start_date == period.start_date and fact.context_end_date == period.end_date
    return (
        0 if exact else 1,
        -fact.document_version,
        -fact.fact_version,
        -fact.id,
    )


def _instant_rank(fact: FinancialFact, period: FinancialPeriod, target_date: date) -> tuple[int, int, int, int]:
    instant_date = _instant_date(fact, period) or target_date
    distance = (target_date - instant_date).days
    return distance, -fact.document_version, -fact.fact_version, -fact.id


def _instant_date(fact: FinancialFact, period: FinancialPeriod) -> date | None:
    return fact.context_instant_date or period.instant_date


def _to_input(fact: FinancialFact, period: FinancialPeriod) -> MetricInput:
    if fact.period_kind == "instant":
        period_end = _instant_date(fact, period)
    else:
        period_end = fact.context_end_date or period.end_date
    return MetricInput(
        role="",
        value=Decimal(str(fact.value_normalized)),
        company_id=fact.company_id,
        period_id=fact.period_id,
        fiscal_year=period.fiscal_year,
        period_start=fact.context_start_date or period.start_date,
        period_end=period_end,
        period_kind=fact.period_kind,
        duration_kind=fact.duration_kind,
        reporting_basis=fact.reporting_basis,
        currency=fact.currency,
        unit=fact.unit,
        fact_id=fact.id,
        document_version=fact.document_version,
        validation_status=fact.validation_status,
        source_scale=fact.source_scale,
    )
