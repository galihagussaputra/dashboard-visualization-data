from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.normalization.periods import (
    FactContext,
    classify_context,
    derive_standalone_quarter,
    normalize_duration_kind,
)


def _context(
    value: str,
    period_type: str,
    sequence: int,
    is_ytd: bool,
    *,
    fact_id: int = 1,
    basis: str = "consolidated",
    currency: str | None = "IDR",
    unit: str = "IDR",
    scale: int = 6,
    fiscal_year: int = 2025,
    definition: str = "idx-cor:Revenue",
    document_version: int = 1,
    context_ref: str | None = None,
    restated: bool = False,
    status: str = "passed",
) -> FactContext:
    return FactContext(
        fact_id=fact_id,
        company_id=1,
        account_id=10,
        statement_type="income_statement",
        period_id=sequence,
        fiscal_year=fiscal_year,
        period_type=period_type,
        period_sequence=sequence,
        is_ytd=is_ytd,
        reporting_basis=basis,
        currency=currency,
        unit=unit,
        source_scale=scale,
        accounting_definition_key=definition,
        document_version=document_version,
        document_id=100,
        source_context_ref=context_ref or f"ctx-Q{sequence}",
        validation_status=status,
        value=Decimal(value),
        is_current=True,
        is_restated=restated,
    )


def _inputs(*items: FactContext) -> dict:
    roles = {1: "YTD_Q1", 2: "YTD_Q2", 3: "YTD_Q3", 4: "FY"}
    return {roles[item.period_sequence]: item for item in items}


def test_classify_context_distinguishes_instant_and_duration():
    assert classify_context(date(2025, 12, 31), None, None) == "instant"
    assert classify_context(None, date(2025, 1, 1), date(2025, 12, 31)) == "duration"
    with pytest.raises(ValueError):
        classify_context(date(2025, 12, 31), date(2025, 1, 1), None)
    with pytest.raises(ValueError):
        classify_context(None, date(2025, 12, 31), date(2025, 1, 1))


def test_normalize_duration_kind():
    assert normalize_duration_kind("FY", True) == "full_year"
    assert normalize_duration_kind("Q2", True) == "ytd"
    assert normalize_duration_kind("Q2", False) == "standalone"


@pytest.mark.parametrize(
    ("sequence", "values", "expected"),
    [
        (1, ("120",), "120"),
        (2, ("100", "250"), "150"),
        (3, ("250", "390"), "140"),
        (4, ("390", "520"), "130"),
    ],
)
def test_supported_standalone_quarter_derivations(sequence, values, expected):
    at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    if sequence == 1:
        items = [_context(values[0], "Q1", 1, True)]
    elif sequence == 2:
        items = [_context(values[0], "Q1", 1, True), _context(values[1], "Q2", 2, True)]
    elif sequence == 3:
        items = [_context(values[0], "Q2", 2, True), _context(values[1], "Q3", 3, True)]
    else:
        items = [_context(values[0], "Q3", 3, True), _context(values[1], "FY", 4, True)]
    result = derive_standalone_quarter(sequence, _inputs(*items), derived_at=at)
    assert result.status == "derived"
    assert result.value == Decimal(expected)
    assert result.derived_at == at
    assert result.input_fact_ids == tuple(item.fact_id for item in items)


def test_missing_q1_is_unavailable_not_zero():
    result = derive_standalone_quarter(2, {"YTD_Q2": _context("250", "Q2", 2, True)})
    assert result.status == "unavailable"
    assert result.value is None
    assert "MISSING_YTD_Q1" in result.reason


def test_incompatible_reporting_basis_blocks_derivation():
    result = derive_standalone_quarter(
        2,
        _inputs(
            _context("100", "Q1", 1, True, basis="consolidated"),
            _context("250", "Q2", 2, True, basis="separate"),
        ),
    )
    assert result.status == "unavailable"
    assert "BASIS_MISMATCH" in result.reason


def test_incompatible_currency_unit_and_scale_block_derivation():
    for kwargs in ({"currency": "USD"}, {"unit": "USD"}, {"scale": 3}):
        result = derive_standalone_quarter(
            2,
            _inputs(
                _context("100", "Q1", 1, True),
                _context("250", "Q2", 2, True, **kwargs),
            ),
        )
        assert result.status == "unavailable"
        assert result.value is None


def test_restated_previous_period_requires_review():
    result = derive_standalone_quarter(
        2,
        _inputs(
            _context("100", "Q1", 1, True, restated=True, document_version=2),
            _context("250", "Q2", 2, True),
        ),
    )
    assert result.status == "review_required"
    assert "RESTATEMENT_VERSION_MISMATCH" in result.reason


def test_duplicate_source_context_blocks_derivation():
    result = derive_standalone_quarter(
        2,
        _inputs(
            _context("100", "Q1", 1, True, context_ref="same"),
            _context("250", "Q2", 2, True, context_ref="same"),
        ),
    )
    assert result.status == "unavailable"
    assert "DUPLICATE_SOURCE_CONTEXT" in result.reason


def test_negative_derived_value_is_preserved_with_warning():
    result = derive_standalone_quarter(
        2,
        _inputs(
            _context("100", "Q1", 1, True),
            _context("50", "Q2", 2, True),
        ),
    )
    assert result.status == "derived"
    assert result.value == Decimal("-50")
    assert "NEGATIVE_DERIVED_VALUE" in result.warnings


def test_fiscal_year_and_annual_context_mismatches_block_derivation():
    wrong_year = derive_standalone_quarter(
        2,
        _inputs(
            _context("100", "Q1", 1, True),
            _context("250", "Q2", 2, True, fiscal_year=2024),
        ),
    )
    assert "FISCAL_YEAR_MISMATCH" in wrong_year.reason

    wrong_annual = derive_standalone_quarter(
        4,
        _inputs(
            _context("390", "Q3", 3, True),
            _context("520", "Q4", 4, False),
        ),
    )
    assert "PERIOD_KIND_MISMATCH" in wrong_annual.reason
