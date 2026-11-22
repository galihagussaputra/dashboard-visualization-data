from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    DerivedValue,
    DerivedValueInput,
    FinancialAccount,
    FinancialDocument,
    FinancialFact,
    FinancialPeriod,
    SourceAccountMapping,
    StandardAccount,
)
from app.normalization.periods import (
    PERIOD_DERIVATION_FORMULA_VERSION,
    FactContext,
    derivation_roles,
    fact_context_from_models,
)

from .accounts import backfill_fact_mappings, ensure_reference_data
from .periods import derive_standalone_quarter


def derive_period_values(
    db: Session,
    *,
    company_id: int,
    fiscal_year: int,
    basis: str,
    created_by: int | None = None,
) -> list[dict[str, Any]]:
    ensure_reference_data(db)
    backfill_fact_mappings(db, company_id=company_id)
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
            FinancialFact.period_id == FinancialPeriod.id,
            FinancialPeriod.fiscal_year == fiscal_year,
            FinancialFact.reporting_basis == basis,
            FinancialFact.is_current.is_(True),
        )
    ).all()

    periods = db.scalars(
        select(FinancialPeriod).where(
            FinancialPeriod.company_id == company_id,
            FinancialPeriod.fiscal_year == fiscal_year,
        )
    ).all()
    period_lookup = {
        (row.period_type, row.period_sequence): row for row in periods
    }

    contexts: dict[tuple[str, str, int], FactContext] = {}
    first_models: dict[tuple[str, str, int], tuple[FinancialFact, FinancialAccount, FinancialDocument]] = {}
    for fact, account, period, document, standard_code in rows:
        key = (standard_code, period.period_type, period.period_sequence)
        contexts[key] = fact_context_from_models(fact, account, period, document)
        first_models[key] = (fact, account, document)

    results: list[dict[str, Any]] = []
    standard_codes = sorted({key[0] for key in contexts})
    for standard_code in standard_codes:
        for sequence in (1, 2, 3, 4):
            target = period_lookup.get((f"Q{sequence}", sequence))
            if target is None or target.is_ytd:
                continue
            roles = derivation_roles(sequence)
            inputs: dict[str, FactContext] = {}
            for role in roles:
                if role == "FY":
                    key = (standard_code, "FY", 4)
                else:
                    quarter = int(role.split("_Q")[1])
                    key = (standard_code, f"Q{quarter}", quarter)
                context = contexts.get(key)
                if context is not None:
                    inputs[role] = context
            result = derive_standalone_quarter(sequence, inputs)
            provenance = {
                "formula_code": result.formula_code,
                "formula_version": PERIOD_DERIVATION_FORMULA_VERSION,
                "input_periods": list(result.input_periods),
                "input_document_versions": list(result.input_document_versions),
                "reason": result.reason,
            }
            evidence = [first_models[(standard_code, _role_key(role))] for role in roles if _role_key(role) in first_models]
            if not evidence:
                continue
            source_fact, source_account, _ = evidence[0]
            derived = _persist_derived_value(
                db,
                company_id=company_id,
                period_id=target.id,
                account_id=source_account.id,
                basis=basis,
                currency=inputs[roles[0]].currency if roles and roles[0] in inputs else None,
                unit=inputs[roles[0]].unit if roles and roles[0] in inputs else source_fact.unit,
                value=result.value,
                formula_code=result.formula_code or f"STANDALONE_Q{sequence}",
                status=result.status,
                reason=result.reason,
                warnings=list(result.warnings),
                provenance=provenance,
                inputs=[(role, inputs[role]) for role in roles if role in inputs],
                created_by=created_by,
            )
            results.append(
                {
                    "standard_account": standard_code,
                    "period_id": target.id,
                    "derived_value_id": derived.id,
                    "status": derived.status,
                    "value": derived.value,
                    "formula_code": derived.formula_code,
                    "reason": derived.unavailable_reason,
                }
            )
    return results


def derived_values_for_scope(
    db: Session,
    *,
    company_id: int,
    period_id: int,
    basis: str,
) -> list[dict[str, Any]]:
    rows = db.execute(
        select(DerivedValue, FinancialAccount, FinancialPeriod)
        .join(FinancialAccount, DerivedValue.account_id == FinancialAccount.id)
        .join(FinancialPeriod, DerivedValue.period_id == FinancialPeriod.id)
        .where(
            DerivedValue.company_id == company_id,
            DerivedValue.reporting_basis == basis,
            FinancialPeriod.fiscal_year == _scope_fiscal_year(db, period_id),
        )
        .order_by(DerivedValue.created_at.desc())
    ).all()
    latest: dict[tuple[int, int, str], dict[str, Any]] = {}
    for derived, account, period in rows:
        key = (derived.account_id, derived.period_id, derived.formula_code)
        if key in latest:
            continue
        latest[key] = {
            "id": derived.id,
            "concept": account.concept_code,
            "period": period.label,
            "period_type": period.period_type,
            "value": derived.value,
            "status": derived.status,
            "formula_code": derived.formula_code,
            "formula_version": derived.formula_version,
            "unavailable_reason": derived.unavailable_reason,
            "validation_warnings": derived.validation_warnings,
            "source_context_details": derived.source_context_details,
        }
    return list(latest.values())


def _scope_fiscal_year(db: Session, period_id: int) -> int:
    period = db.get(FinancialPeriod, period_id)
    if period is None:
        raise ValueError(f"period {period_id} not found")
    return period.fiscal_year


def _role_key(role: str) -> tuple[str, str, int]:
    if role == "FY":
        return ("FY", "FY", 4)
    sequence = int(role.split("_Q")[1])
    return ("Q", f"Q{sequence}", sequence)


def _persist_derived_value(
    db: Session,
    *,
    company_id: int,
    period_id: int,
    account_id: int,
    basis: str,
    currency: str | None,
    unit: str,
    value: Decimal | None,
    formula_code: str,
    status: str,
    reason: str | None,
    warnings: list[str],
    provenance: dict[str, Any],
    inputs: list[tuple[str, FactContext]],
    created_by: int | None,
):
    current = db.scalars(
        select(DerivedValue)
        .where(
            DerivedValue.company_id == company_id,
            DerivedValue.period_id == period_id,
            DerivedValue.account_id == account_id,
            DerivedValue.reporting_basis == basis,
            DerivedValue.formula_code == formula_code,
            DerivedValue.formula_version == PERIOD_DERIVATION_FORMULA_VERSION,
            DerivedValue.status == status,
            DerivedValue.value == value,
            DerivedValue.unavailable_reason.is_(True) if reason is None else DerivedValue.unavailable_reason == reason,
        )
        .order_by(DerivedValue.created_at.desc())
        .limit(1)
    ).first()
    if current is not None and current.validation_warnings == warnings:
        return current

    derived = DerivedValue(
        company_id=company_id,
        period_id=period_id,
        account_id=account_id,
        reporting_basis=basis,
        currency=currency,
        unit=unit,
        value=value,
        formula_code=formula_code,
        formula_version=PERIOD_DERIVATION_FORMULA_VERSION,
        status=status,
        unavailable_reason=reason,
        validation_warnings=warnings,
        source_context_details=provenance,
        created_by=created_by,
    )
    db.add(derived)
    db.flush()
    for sequence, (role, context) in enumerate(inputs, start=1):
        db.add(
            DerivedValueInput(
                derived_value_id=derived.id,
                input_fact_id=context.fact_id,
                input_period_id=context.period_id,
                input_document_id=context.document_id,
                role=role,
                sequence=sequence,
            )
        )
    db.flush()
    return derived
