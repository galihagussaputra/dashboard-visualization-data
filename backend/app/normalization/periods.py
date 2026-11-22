from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

PERIOD_DERIVATION_FORMULA_VERSION = "m2-v1"


@dataclass(frozen=True)
class FactContext:
    fact_id: int | None
    company_id: int
    account_id: int
    statement_type: str
    period_id: int
    fiscal_year: int
    period_type: str
    period_sequence: int
    is_ytd: bool
    reporting_basis: str
    currency: str | None
    unit: str
    source_scale: int
    accounting_definition_key: str
    document_version: int
    document_id: int
    source_context_ref: str
    validation_status: str
    value: Decimal
    is_current: bool = True
    is_restated: bool = False


@dataclass(frozen=True)
class DerivationResult:
    status: str
    value: Decimal | None
    formula_code: str | None
    formula_version: str
    input_fact_ids: tuple[int, ...]
    input_periods: tuple[int, ...]
    input_document_versions: tuple[int, ...]
    derived_at: datetime
    validation_status: str
    warnings: tuple[str, ...]
    reason: str | None


def classify_context(
    instant_date: date | None,
    start_date: date | None,
    end_date: date | None,
) -> str:
    if instant_date is not None:
        if start_date is not None or end_date is not None:
            raise ValueError("instant context cannot also contain duration dates")
        return "instant"
    if start_date is None or end_date is None:
        raise ValueError("duration context requires start and end dates")
    if end_date < start_date:
        raise ValueError("duration end date precedes start date")
    return "duration"


def normalize_duration_kind(period_type: str, is_ytd: bool) -> str:
    if period_type == "FY":
        return "full_year"
    if period_type in {"Q1", "Q2", "Q3", "Q4"}:
        return "ytd" if is_ytd else "standalone"
    return "unknown"


def dimension_signature(context: FactContext) -> tuple[Any, ...]:
    return (
        context.company_id,
        context.account_id,
        context.statement_type,
        context.fiscal_year,
        context.reporting_basis,
        context.currency,
        context.unit,
        context.source_scale,
        context.accounting_definition_key,
        context.document_version,
    )


def derivation_roles(target_sequence: int) -> tuple[str, ...]:
    return {
        1: ("YTD_Q1",),
        2: ("YTD_Q1", "YTD_Q2"),
        3: ("YTD_Q2", "YTD_Q3"),
        4: ("YTD_Q3", "FY"),
    }.get(target_sequence, ())


def compatible_period_label(role: str) -> tuple[str, bool | None]:
    if role == "FY":
        return "FY", None
    sequence = int(role.split("_Q")[1])
    return f"Q{sequence}", True


def validate_derivation_inputs(
    target_sequence: int,
    inputs: dict[str, FactContext],
) -> tuple[str, ...]:
    roles = derivation_roles(target_sequence)
    if not roles:
        return ("UNSUPPORTED_TARGET_SEQUENCE",)
    missing = [role for role in roles if role not in inputs]
    if missing:
        return ("MISSING_" + "_".join(missing),)
    contexts = tuple(inputs[role] for role in roles)
    reasons: list[str] = []

    for context in contexts:
        if not context.is_current:
            reasons.append("NON_CURRENT_INPUT")
        if context.validation_status not in {"passed", "validated", "published", "overridden"}:
            reasons.append("INPUT_NOT_VALIDATED")
        expected_period, expected_ytd = compatible_period_label(context_period_role(inputs, context))
        if context.period_type != expected_period or (
            expected_ytd is not None and context.is_ytd != expected_ytd
        ):
            reasons.append("PERIOD_KIND_MISMATCH")

    signatures = {dimension_signature(context) for context in contexts}
    if len(signatures) > 1:
        reasons.extend(
            [
                "COMPANY_MISMATCH",
                "ACCOUNT_MISMATCH",
                "STATEMENT_MISMATCH",
                "FISCAL_YEAR_MISMATCH",
                "BASIS_MISMATCH",
                "CURRENCY_MISMATCH",
                "UNIT_MISMATCH",
                "SCALE_MISMATCH",
                "DEFINITION_MISMATCH",
                "DOCUMENT_VERSION_MISMATCH",
            ]
            if len(signatures) > 1
            else []
        )

    context_refs = [context.source_context_ref for context in contexts]
    if len(context_refs) != len(set(context_refs)):
        reasons.append("DUPLICATE_SOURCE_CONTEXT")
    if any(context.is_restated for context in contexts):
        versions = {context.document_version for context in contexts}
        if len(versions) > 1:
            reasons.append("RESTATEMENT_VERSION_MISMATCH")
    sequences = [context.period_sequence for context in contexts]
    if sequences != sorted(sequences):
        reasons.append("PERIOD_ORDER_MISMATCH")
    return tuple(dict.fromkeys(reasons))


def context_period_role(inputs: dict[str, FactContext], context: FactContext) -> str:
    for role, candidate in inputs.items():
        if candidate is context:
            return role
    return ""


def derive_standalone_quarter(
    target_sequence: int,
    inputs: dict[str, FactContext],
    *,
    derived_at: datetime | None = None,
) -> DerivationResult:
    now = derived_at or datetime.now(timezone.utc)
    reasons = validate_derivation_inputs(target_sequence, inputs)
    formula_code = f"STANDALONE_Q{target_sequence}"
    roles = derivation_roles(target_sequence)
    input_contexts = tuple(inputs[role] for role in roles if role in inputs)
    common = dict(
        formula_code=formula_code if not reasons else None,
        formula_version=PERIOD_DERIVATION_FORMULA_VERSION,
        input_fact_ids=tuple(context.fact_id for context in input_contexts if context.fact_id is not None),
        input_periods=tuple(context.period_id for context in input_contexts),
        input_document_versions=tuple(context.document_version for context in input_contexts),
        derived_at=now,
    )
    if reasons:
        status = "review_required" if "RESTATEMENT_VERSION_MISMATCH" in reasons else "unavailable"
        if any(reason.startswith("MISSING_") for reason in reasons):
            status = "unavailable"
        return DerivationResult(
            status=status,
            value=None,
            validation_status=status,
            warnings=(),
            reason=";".join(reasons),
            **common,
        )

    values = [inputs[role].value for role in roles]
    if len(values) == 1:
        value = values[0]
    elif target_sequence == 4:
        value = values[1] - values[0]
    else:
        value = values[1] - values[0]

    warnings: list[str] = []
    if value < 0 and inputs[roles[0]].statement_type != "cash_flow":
        warnings.append("NEGATIVE_DERIVED_VALUE")
    return DerivationResult(
        status="derived",
        value=value,
        validation_status="derived",
        warnings=tuple(warnings),
        reason=None,
        **common,
    )


def fact_context_from_models(fact: Any, account: Any, period: Any, document: Any) -> FactContext:
    return FactContext(
        fact_id=fact.id,
        company_id=fact.company_id,
        account_id=fact.account_id,
        statement_type=account.statement_type,
        period_id=fact.period_id,
        fiscal_year=period.fiscal_year,
        period_type=period.period_type,
        period_sequence=period.period_sequence,
        is_ytd=period.is_ytd,
        reporting_basis=fact.reporting_basis,
        currency=fact.currency,
        unit=fact.unit,
        source_scale=fact.source_scale,
        accounting_definition_key=fact.accounting_definition_key,
        document_version=fact.document_version,
        document_id=fact.document_id,
        source_context_ref=fact.source_context_ref,
        validation_status=fact.validation_status,
        value=fact.value_normalized,
        is_current=fact.is_current,
        is_restated=fact.is_restated,
    )
