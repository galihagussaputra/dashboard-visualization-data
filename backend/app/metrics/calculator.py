from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, DivisionByZero, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FinancialMetric, FinancialMetricInput, MetricDefinition

from .definitions import FORMULA_VERSION, METRIC_SPECS, METRICS_BY_CODE, MetricSpec


@dataclass(frozen=True)
class MetricInput:
    role: str
    value: Decimal | None
    company_id: int
    period_id: int
    fiscal_year: int
    period_start: date | None
    period_end: date | None
    period_kind: str
    duration_kind: str
    reporting_basis: str
    currency: str | None
    unit: str
    fact_id: int | None = None
    derived_value_id: int | None = None
    document_version: int | None = None
    validation_status: str = "passed"


@dataclass(frozen=True)
class MetricComputation:
    code: str
    status: str
    value: Decimal | None
    unit: str
    formula_version: str
    formula_definition: str
    input_roles: tuple[str, ...]
    input_fact_ids: tuple[int, ...]
    input_document_versions: tuple[int, ...]
    warnings: tuple[str, ...]
    reason: str | None
    calculated_at: datetime


def ensure_metric_definitions(db: Session) -> dict[str, int]:
    ids: dict[str, int] = {}
    for spec in METRIC_SPECS:
        definition = db.scalars(
            select(MetricDefinition).where(
                MetricDefinition.code == spec.code,
                MetricDefinition.version == spec.version,
            )
        ).first()
        if definition is None:
            definition = MetricDefinition(
                code=spec.code,
                name=spec.name,
                version=spec.version,
                category=spec.category,
                unit=spec.unit,
                formula={
                    "operation": spec.operation,
                    "expression": spec.formula,
                    "inputs": list(spec.inputs),
                },
                dependencies=list(spec.dependencies),
                applicable_entry_points=["ratios", "performance"],
                is_active=True,
            )
            db.add(definition)
            db.flush()
        ids[spec.code] = definition.id
    return ids


def calculate_metric(
    code: str,
    inputs: dict[str, MetricInput],
    *,
    formula_version: str | None = None,
    calculated_at: datetime | None = None,
    spec_override: MetricSpec | None = None,
) -> MetricComputation:
    spec = spec_override or METRICS_BY_CODE.get(code)
    now = calculated_at or datetime.now(timezone.utc)
    if spec is None:
        return _empty(code, "invalid", "UNKNOWN_METRIC", now)
    if formula_version is not None and formula_version != spec.version:
        return _empty(code, "invalid", "FORMULA_VERSION_MISMATCH", now, spec)

    missing = [
        role
        for role in spec.inputs
        if role not in inputs or inputs[role].value is None
    ]
    if missing:
        return _empty(
            code,
            "unavailable",
            "MISSING_INPUTS:" + ",".join(missing),
            now,
            spec,
            input_roles=tuple(spec.inputs),
        )

    selected = {role: inputs[role] for role in spec.inputs}
    compatibility_error = _compatibility_error(spec, selected)
    if compatibility_error:
        return _empty(
            code,
            "invalid",
            compatibility_error,
            now,
            spec,
            input_roles=tuple(spec.inputs),
            selected=selected,
        )

    warnings: list[str] = []
    numerator = selected[spec.inputs[0]].value
    if numerator is not None and numerator < 0:
        warnings.append("NEGATIVE_NUMERATOR")

    try:
        if spec.operation == "divide":
            denominator = selected[spec.inputs[1]].value
            if denominator == 0:
                return _empty(code, "unavailable", "ZERO_DENOMINATOR", now, spec, input_roles=tuple(spec.inputs), selected=selected)
            if denominator < 0:
                warnings.append("NEGATIVE_DENOMINATOR")
                if spec.inputs[1] in {"TOTAL_EQUITY", "CLOSING_EQUITY"}:
                    warnings.append("NEGATIVE_EQUITY")
            value = numerator / denominator
        elif spec.operation == "average_divide":
            opening = selected[spec.inputs[1]].value
            closing = selected[spec.inputs[2]].value
            average = (opening + closing) / Decimal(2)
            if average == 0:
                return _empty(code, "unavailable", "ZERO_AVERAGE_BALANCE", now, spec, input_roles=tuple(spec.inputs), selected=selected)
            if average < 0:
                warnings.append("NEGATIVE_AVERAGE_BALANCE")
            value = numerator / average
        elif spec.operation == "subtract":
            deduction = selected[spec.inputs[1]].value
            if deduction is not None and deduction < 0:
                warnings.append("NEGATIVE_CAPITAL_EXPENDITURE")
            value = numerator - deduction
        else:
            return _empty(code, "invalid", "UNSUPPORTED_OPERATION", now, spec, input_roles=tuple(spec.inputs), selected=selected)
    except (DivisionByZero, InvalidOperation, TypeError) as exc:
        return _empty(code, "invalid", f"CALCULATION_ERROR:{type(exc).__name__}", now, spec, input_roles=tuple(spec.inputs), selected=selected)

    fact_ids = tuple(
        item.fact_id for item in selected.values() if item.fact_id is not None
    )
    document_versions = tuple(
        item.document_version for item in selected.values() if item.document_version is not None
    )
    return MetricComputation(
        code=code,
        status="calculated",
        value=value,
        unit=spec.unit,
        formula_version=spec.version,
        formula_definition=spec.formula,
        input_roles=tuple(spec.inputs),
        input_fact_ids=fact_ids,
        input_document_versions=document_versions,
        warnings=tuple(dict.fromkeys(warnings)),
        reason=None,
        calculated_at=now,
    )


def persist_metric(
    db: Session,
    *,
    company_id: int,
    period_id: int,
    definition_id: int,
    computation: MetricComputation,
    inputs: dict[str, MetricInput],
    reporting_basis: str | None = None,
    currency: str | None = None,
) -> FinancialMetric:
    previous = db.scalars(
        select(FinancialMetric).where(
            FinancialMetric.company_id == company_id,
            FinancialMetric.period_id == period_id,
            FinancialMetric.metric_definition_id == definition_id,
            FinancialMetric.is_current.is_(True),
        )
    ).all()
    for row in previous:
        row.is_current = False

    baseline = next(iter(inputs.values()), None)
    metric = FinancialMetric(
        company_id=company_id,
        period_id=period_id,
        metric_definition_id=definition_id,
        value=computation.value,
        unit=computation.unit,
        source_fact_ids=list(computation.input_fact_ids),
        formula_version=computation.formula_version,
        is_derived_from_ytd=False,
        status="draft",
        is_current=True,
        computed_at=computation.calculated_at,
        reporting_basis=reporting_basis or (baseline.reporting_basis if baseline else "unknown"),
        currency=currency or (baseline.currency if baseline else None),
        calculation_status=computation.status,
        unavailable_reason=computation.reason,
        validation_warnings=list(computation.warnings),
        input_document_versions=list(computation.input_document_versions),
        formula_definition={
            "expression": computation.formula_definition,
            "version": computation.formula_version,
            "roles": list(computation.input_roles),
        },
        publication_status="draft",
    )
    db.add(metric)
    db.flush()
    for sequence, role in enumerate(computation.input_roles, start=1):
        source = inputs.get(role)
        db.add(
            FinancialMetricInput(
                financial_metric_id=metric.id,
                input_fact_id=source.fact_id if source else None,
                derived_value_id=source.derived_value_id if source else None,
                role=role,
                sequence=sequence,
            )
        )
    db.flush()
    return metric


def _compatibility_error(spec: MetricSpec, inputs: dict[str, MetricInput]) -> str | None:
    if len({item.company_id for item in inputs.values()}) > 1:
        return "COMPANY_MISMATCH"
    if len({item.reporting_basis for item in inputs.values()}) > 1:
        return "REPORTING_BASIS_MISMATCH"
    if len({item.currency for item in inputs.values()}) > 1:
        return "CURRENCY_MISMATCH"
    if len({item.unit for item in inputs.values()}) > 1:
        return "UNIT_MISMATCH"
    if len({item.fiscal_year for item in inputs.values()}) > 1:
        return "FISCAL_YEAR_MISMATCH"
    if any(item.validation_status in {"failed", "pending"} for item in inputs.values()):
        return "INPUT_NOT_VALIDATED"

    if spec.operation in {"divide", "subtract"}:
        if len({item.period_id for item in inputs.values()}) > 1:
            return "INCOMPATIBLE_PERIOD"
        if len({item.duration_kind for item in inputs.values()}) > 1:
            return "INCOMPATIBLE_DURATION_KIND"
        return None

    numerator = inputs[spec.inputs[0]]
    opening = inputs[spec.inputs[1]]
    closing = inputs[spec.inputs[2]]
    if numerator.period_kind != "duration":
        return "NUMERATOR_PERIOD_MISMATCH"
    if opening.period_kind != "instant" or closing.period_kind != "instant":
        return "AVERAGE_BALANCE_PERIOD_MISMATCH"
    if opening.period_end is None or closing.period_end is None:
        return "MISSING_AVERAGE_BALANCE_DATES"
    if opening.period_end >= closing.period_end:
        return "INVALID_AVERAGE_BALANCE_ORDER"
    return None


def _empty(
    code: str,
    status: str,
    reason: str,
    calculated_at: datetime,
    spec: MetricSpec | None = None,
    *,
    input_roles: tuple[str, ...] = (),
    selected: dict[str, MetricInput] | None = None,
) -> MetricComputation:
    items = tuple(selected.values()) if selected else ()
    return MetricComputation(
        code=code,
        status=status,
        value=None,
        unit=spec.unit if spec else "ratio",
        formula_version=spec.version if spec else FORMULA_VERSION,
        formula_definition=spec.formula if spec else "",
        input_roles=input_roles,
        input_fact_ids=tuple(item.fact_id for item in items if item.fact_id is not None),
        input_document_versions=tuple(
            item.document_version for item in items if item.document_version is not None
        ),
        warnings=(),
        reason=reason,
        calculated_at=calculated_at,
    )
