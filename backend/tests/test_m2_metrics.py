from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.metrics.calculator import INSTANT_INPUT_ROLES, MetricInput, calculate_metric
from app.metrics.definitions import FORMULA_VERSION


def _input(
    role: str,
    value: str,
    *,
    period_id: int = 1,
    period_kind: str | None = None,
    duration_kind: str | None = None,
    period_end: date | None = date(2025, 12, 31),
    basis: str = "consolidated",
    currency: str | None = "IDR",
    unit: str = "IDR",
    fact_id: int = 1,
    source_scale: int = 0,
) -> MetricInput:
    resolved_kind = period_kind or ("instant" if role in INSTANT_INPUT_ROLES else "duration")
    resolved_duration = duration_kind or ("not_applicable" if resolved_kind == "instant" else "full_year")
    return MetricInput(
        role=role,
        value=Decimal(value),
        company_id=1,
        period_id=period_id,
        fiscal_year=2025,
        period_start=date(2025, 1, 1) if resolved_kind == "duration" else None,
        period_end=period_end,
        period_kind=resolved_kind,
        duration_kind=resolved_duration,
        reporting_basis=basis,
        currency=currency,
        unit=unit,
        fact_id=fact_id,
        document_version=1,
        source_scale=source_scale,
    )


def _averaged(numerator: str, opening: str, closing: str) -> dict[str, MetricInput]:
    return {
        "NET_INCOME": _input("NET_INCOME", numerator, fact_id=1),
        "OPENING_TOTAL_ASSETS": _input(
            "OPENING_TOTAL_ASSETS", opening, period_id=2, period_end=date(2025, 1, 1), fact_id=2
        ),
        "CLOSING_TOTAL_ASSETS": _input(
            "CLOSING_TOTAL_ASSETS", closing, period_id=3, period_end=date(2025, 12, 31), fact_id=3
        ),
    }


def test_average_balance_formulas():
    inputs = _averaged("20", "100", "300")
    inputs["OPENING_EQUITY"] = _input(
        "OPENING_EQUITY", "80", period_id=4, period_end=date(2025, 1, 1), fact_id=4
    )
    inputs["CLOSING_EQUITY"] = _input(
        "CLOSING_EQUITY", "120", period_id=5, period_end=date(2025, 12, 31), fact_id=5
    )
    assert calculate_metric("ROA", inputs).value == Decimal("0.1")
    roe = calculate_metric("ROE", inputs)
    assert roe.value == Decimal("0.2")

    revenue_inputs = _averaged("100", "100", "300")
    revenue_inputs["REVENUE"] = _input("REVENUE", "100", fact_id=6)
    del revenue_inputs["NET_INCOME"]
    assert calculate_metric("ASSET_TURNOVER", revenue_inputs).value == Decimal("0.5")


@pytest.mark.parametrize(
    ("code", "values", "expected"),
    [
        ("NET_PROFIT_MARGIN", ("20", "100"), "0.2"),
        ("CURRENT_RATIO", ("200", "100"), "2"),
        ("QUICK_RATIO", ("100", "100"), "1"),
        ("DEBT_TO_EQUITY_TOTAL_DEBT", ("50", "100"), "0.5"),
        ("LIABILITIES_TO_EQUITY", ("200", "100"), "2"),
        ("DEBT_TO_ASSET", ("50", "200"), "0.25"),
    ],
)
def test_binary_ratio_formulas(code, values, expected):
    from app.metrics.definitions import METRICS_BY_CODE

    roles = METRICS_BY_CODE[code].inputs
    inputs = {
        roles[0]: _input(roles[0], values[0], fact_id=1),
        roles[1]: _input(roles[1], values[1], fact_id=2),
    }
    result = calculate_metric(code, inputs)
    assert result.status == "calculated"
    assert result.value == Decimal(expected)


def test_inventory_turnover_and_free_cash_flow():
    inventory = {
        "COST_OF_GOODS_SOLD": _input("COST_OF_GOODS_SOLD", "50", fact_id=1),
        "OPENING_INVENTORY": _input("OPENING_INVENTORY", "20", period_id=2, period_end=date(2025, 1, 1), fact_id=2),
        "CLOSING_INVENTORY": _input("CLOSING_INVENTORY", "30", period_id=3, period_end=date(2025, 12, 31), fact_id=3),
    }
    assert calculate_metric("INVENTORY_TURNOVER", inventory).value == Decimal("2")

    fcf_inputs = {
        "OPERATING_CASH_FLOW": _input("OPERATING_CASH_FLOW", "80", fact_id=4),
        "CAPITAL_EXPENDITURE": _input("CAPITAL_EXPENDITURE", "30", fact_id=5),
    }
    result = calculate_metric("FREE_CASH_FLOW", fcf_inputs)
    assert result.value == Decimal("50")
    assert result.unit == "IDR"


def test_zero_denominator_is_unavailable_not_zero():
    result = calculate_metric(
        "NET_PROFIT_MARGIN",
        {
            "NET_INCOME": _input("NET_INCOME", "20", fact_id=1),
            "REVENUE": _input("REVENUE", "0", fact_id=2),
        },
    )
    assert result.status == "unavailable"
    assert result.value is None
    assert result.reason == "ZERO_DENOMINATOR"


def test_missing_input_is_unavailable():
    result = calculate_metric("CURRENT_RATIO", {"CURRENT_ASSETS": _input("CURRENT_ASSETS", "200", fact_id=1)})
    assert result.status == "unavailable"
    assert "MISSING_INPUTS" in result.reason


def test_negative_values_are_calculated_with_warnings():
    negative_income = calculate_metric(
        "NET_PROFIT_MARGIN",
        {
            "NET_INCOME": _input("NET_INCOME", "-20", fact_id=1),
            "REVENUE": _input("REVENUE", "100", fact_id=2),
        },
    )
    assert negative_income.value == Decimal("-0.2")
    assert "NEGATIVE_NUMERATOR" in negative_income.warnings

    negative_equity = calculate_metric(
        "LIABILITIES_TO_EQUITY",
        {
            "TOTAL_LIABILITIES": _input("TOTAL_LIABILITIES", "200", fact_id=1),
            "TOTAL_EQUITY": _input("TOTAL_EQUITY", "-100", fact_id=2),
        },
    )
    assert negative_equity.value == Decimal("-2")
    assert "NEGATIVE_DENOMINATOR" in negative_equity.warnings
    assert "NEGATIVE_EQUITY" in negative_equity.warnings


def test_incompatible_period_and_basis_and_unit_are_invalid():
    period_inputs = {
        "NET_INCOME": _input("NET_INCOME", "20", period_id=1, fact_id=1),
        "REVENUE": _input("REVENUE", "100", period_id=2, fact_id=2),
    }
    assert calculate_metric("NET_PROFIT_MARGIN", period_inputs).reason == "INCOMPATIBLE_PERIOD"

    basis_inputs = {
        "NET_INCOME": _input("NET_INCOME", "20", fact_id=1),
        "REVENUE": _input("REVENUE", "100", basis="separate", fact_id=2),
    }
    assert calculate_metric("NET_PROFIT_MARGIN", basis_inputs).reason == "REPORTING_BASIS_MISMATCH"

    unit_inputs = {
        "NET_INCOME": _input("NET_INCOME", "20", fact_id=1),
        "REVENUE": _input("REVENUE", "100", unit="USD", fact_id=2),
    }
    assert calculate_metric("NET_PROFIT_MARGIN", unit_inputs).reason == "UNIT_MISMATCH"


def test_missing_average_balance_inputs_are_unavailable():
    result = calculate_metric("ROA", {"NET_INCOME": _input("NET_INCOME", "20", fact_id=1)})
    assert result.status == "unavailable"
    assert "MISSING_INPUTS" in result.reason


def test_formula_version_change_is_invalid():
    result = calculate_metric(
        "NET_PROFIT_MARGIN",
        {
            "NET_INCOME": _input("NET_INCOME", "20", fact_id=1),
            "REVENUE": _input("REVENUE", "100", fact_id=2),
        },
        formula_version="m0-v1",
    )
    assert result.status == "invalid"
    assert result.reason == "FORMULA_VERSION_MISMATCH"
    assert result.value is None
    assert FORMULA_VERSION == "m2-v1"


def test_calculation_timestamp_is_recorded():
    at = datetime(2026, 2, 1, tzinfo=timezone.utc)
    result = calculate_metric(
        "FREE_CASH_FLOW",
        {
            "OPERATING_CASH_FLOW": _input("OPERATING_CASH_FLOW", "80", fact_id=1),
            "CAPITAL_EXPENDITURE": _input("CAPITAL_EXPENDITURE", "30", fact_id=2),
        },
        calculated_at=at,
    )
    assert result.calculated_at == at


def test_non_finite_input_is_rejected():
    result = calculate_metric(
        "NET_PROFIT_MARGIN",
        {
            "NET_INCOME": _input("NET_INCOME", "NaN", fact_id=1),
            "REVENUE": _input("REVENUE", "100", fact_id=2),
        },
    )
    assert result.status == "invalid"
    assert result.reason == "NON_FINITE_INPUT:NET_INCOME"
    assert result.value is None


def test_source_scale_mismatch_is_invalid():
    result = calculate_metric(
        "NET_PROFIT_MARGIN",
        {
            "NET_INCOME": _input("NET_INCOME", "20", fact_id=1, source_scale=0),
            "REVENUE": _input("REVENUE", "100", fact_id=2, source_scale=3),
        },
    )
    assert result.status == "invalid"
    assert result.reason == "SOURCE_SCALE_MISMATCH"


def test_role_period_kind_mismatch_is_invalid():
    result = calculate_metric(
        "CURRENT_RATIO",
        {
            "CURRENT_ASSETS": _input("CURRENT_ASSETS", "200", period_kind="duration", fact_id=1),
            "CURRENT_LIABILITIES": _input("CURRENT_LIABILITIES", "100", fact_id=2),
        },
    )
    assert result.status == "invalid"
    assert result.reason == "ROLE_PERIOD_KIND_MISMATCH"


def test_negative_capex_uses_explicit_positive_sign_convention():
    result = calculate_metric(
        "FREE_CASH_FLOW",
        {
            "OPERATING_CASH_FLOW": _input("OPERATING_CASH_FLOW", "80", fact_id=1),
            "CAPITAL_EXPENDITURE": _input("CAPITAL_EXPENDITURE", "-30", fact_id=2),
        },
    )
    assert result.status == "unavailable"
    assert result.reason == "NEGATIVE_CAPITAL_EXPENDITURE_UNSUPPORTED_SIGN"
    assert result.value is None


def test_average_window_mismatch_is_invalid():
    inputs = _averaged("20", "100", "300")
    inputs["OPENING_TOTAL_ASSETS"] = _input(
        "OPENING_TOTAL_ASSETS", "100", period_id=2, period_end=date(2025, 2, 1), fact_id=2
    )
    result = calculate_metric("ROA", inputs)
    assert result.status == "invalid"
    assert result.reason == "INVALID_OPENING_WINDOW"
