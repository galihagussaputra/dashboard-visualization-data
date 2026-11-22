from dataclasses import dataclass

FORMULA_VERSION = "m2-v1"


@dataclass(frozen=True)
class MetricSpec:
    code: str
    name: str
    category: str
    unit: str
    operation: str
    inputs: tuple[str, ...]
    formula: str
    dependencies: tuple[str, ...] = ()

    @property
    def version(self) -> str:
        return FORMULA_VERSION


METRIC_SPECS: tuple[MetricSpec, ...] = (
    MetricSpec(
        "ROA",
        "Return on assets",
        "profitability",
        "ratio",
        "average_divide",
        ("NET_INCOME", "OPENING_TOTAL_ASSETS", "CLOSING_TOTAL_ASSETS"),
        "Net income / average total assets",
    ),
    MetricSpec(
        "ROE",
        "Return on equity",
        "profitability",
        "ratio",
        "average_divide",
        ("NET_INCOME", "OPENING_EQUITY", "CLOSING_EQUITY"),
        "Net income / average equity",
    ),
    MetricSpec(
        "NET_PROFIT_MARGIN",
        "Net profit margin",
        "profitability",
        "ratio",
        "divide",
        ("NET_INCOME", "REVENUE"),
        "Net income / metric revenue",
    ),
    MetricSpec(
        "CURRENT_RATIO",
        "Current ratio",
        "liquidity",
        "ratio",
        "divide",
        ("CURRENT_ASSETS", "CURRENT_LIABILITIES"),
        "Current assets / current liabilities",
    ),
    MetricSpec(
        "QUICK_RATIO",
        "Quick ratio",
        "liquidity",
        "ratio",
        "divide",
        ("QUICK_ASSETS", "CURRENT_LIABILITIES"),
        "Quick assets / current liabilities",
    ),
    MetricSpec(
        "DEBT_TO_EQUITY_TOTAL_DEBT",
        "Debt to equity (interest-bearing debt)",
        "leverage",
        "ratio",
        "divide",
        ("TOTAL_DEBT", "TOTAL_EQUITY"),
        "Interest-bearing total debt / total equity",
    ),
    MetricSpec(
        "LIABILITIES_TO_EQUITY",
        "Liabilities to equity",
        "leverage",
        "ratio",
        "divide",
        ("TOTAL_LIABILITIES", "TOTAL_EQUITY"),
        "Total liabilities / total equity; distinct from interest-bearing debt to equity",
    ),
    MetricSpec(
        "DEBT_TO_ASSET",
        "Debt to asset",
        "leverage",
        "ratio",
        "divide",
        ("TOTAL_DEBT", "TOTAL_ASSETS"),
        "Interest-bearing total debt / total assets",
    ),
    MetricSpec(
        "ASSET_TURNOVER",
        "Asset turnover",
        "efficiency",
        "ratio",
        "average_divide",
        ("REVENUE", "OPENING_TOTAL_ASSETS", "CLOSING_TOTAL_ASSETS"),
        "Metric revenue / average total assets",
    ),
    MetricSpec(
        "INVENTORY_TURNOVER",
        "Inventory turnover",
        "efficiency",
        "ratio",
        "average_divide",
        ("COST_OF_GOODS_SOLD", "OPENING_INVENTORY", "CLOSING_INVENTORY"),
        "Cost of goods sold / average inventory",
    ),
    MetricSpec(
        "FREE_CASH_FLOW",
        "Free cash flow",
        "cash_flow",
        "IDR",
        "subtract",
        ("OPERATING_CASH_FLOW", "CAPITAL_EXPENDITURE"),
        "Net operating cash flow minus positive capital expenditure",
    ),
)

METRICS_BY_CODE = {spec.code: spec for spec in METRIC_SPECS}
