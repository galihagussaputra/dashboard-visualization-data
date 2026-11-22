from dataclasses import dataclass


@dataclass(frozen=True)
class ConceptSpec:
    local_name: str
    statement_type: str
    context_ref: str
    unit: str
    xlsx_sheet: str
    xlsx_label: str
    pdf_label: str
    source_scale: int
    label_id: str
    label_en: str
    normal_sign: int = 1
    is_core: bool = True

    @property
    def concept(self) -> str:
        return f"idx-cor:{self.local_name}"


ALL_CONCEPTS: tuple[ConceptSpec, ...] = (
    ConceptSpec(
        "Cash", "balance_sheet", "CurrentYearInstant", "IDR",
        "4220000", "Cash", "Cash", 6, "Kas", "Cash",
    ),
    ConceptSpec(
        "Assets", "balance_sheet", "CurrentYearInstant", "IDR",
        "4220000", "Total assets", "Total assets", 6, "Jumlah aset", "Total assets",
    ),
    ConceptSpec(
        "Liabilities", "balance_sheet", "CurrentYearInstant", "IDR",
        "4220000", "Total liabilities", "Total liabilities", 6, "Jumlah liabilitas", "Total liabilities",
    ),
    ConceptSpec(
        "Equity", "balance_sheet", "CurrentYearInstant", "IDR",
        "4220000", "Total equity", "Total equity | Jumlah liabilitas, dana", 6, "Jumlah ekuitas", "Total equity",
    ),
    ConceptSpec(
        "InterestIncome", "income_statement", "CurrentYearDuration", "IDR",
        "4322000", "Interest income", "Interest income", 6, "Pendapatan bunga", "Interest income",
    ),
    ConceptSpec(
        "ProfitFromOperation", "income_statement", "CurrentYearDuration", "IDR",
        "4322000", "Total profit from operation", "Total profit from operation", 6,
        "Jumlah laba operasional", "Total profit from operation",
    ),
    ConceptSpec(
        "ProfitLoss", "income_statement", "CurrentYearDuration", "IDR",
        "4322000", "Total profit (loss) from continuing operations",
        "Total profit (loss) from", 6,
        "Jumlah laba (rugi) dari operasi yang dilanjutkan",
        "Total profit (loss) from continuing operations",
    ),
    ConceptSpec(
        "ProfitLossAttributableToParentEntity", "income_statement", "CurrentYearDuration", "IDR",
        "4322000", "Profit (loss) attributable to parent entity",
        "Profit (loss) attributable to | parent entity", 6,
        "Laba (rugi) yang dapat diatribusikan ke entitas induk",
        "Profit (loss) attributable to parent entity",
    ),
    ConceptSpec(
        "NetCashFlowsReceivedFromUsedInOperatingActivities", "cash_flow", "CurrentYearDuration", "IDR",
        "4510000", "Total net cash flows received from (used in) operating activities",
        "Total net cash flows | received from (used in) | operating activities", 6,
        "Jumlah arus kas bersih yang diperoleh dari (digunakan untuk) aktivitas operasi",
        "Total net cash flows received from (used in) operating activities",
    ),
    ConceptSpec(
        "NetCashFlowsReceivedFromUsedInInvestingActivities", "cash_flow", "CurrentYearDuration", "IDR",
        "4510000", "Total net cash flows received from (used in) investing activities",
        "Total net cash flows | received from (used in) | investing activities", 6,
        "Jumlah arus kas bersih yang diperoleh dari (digunakan untuk) aktivitas investasi",
        "Total net cash flows received from (used in) investing activities", -1,
    ),
    ConceptSpec(
        "NetCashFlowsReceivedFromUsedInFinancingActivities", "cash_flow", "CurrentYearDuration", "IDR",
        "4510000", "Total net cash flows received from (used in) financing activities",
        "Total net cash flows | received from (used in) | financing activities", 6,
        "Jumlah arus kas bersih yang diperoleh dari (digunakan untuk) aktivitas pendanaan",
        "Total net cash flows received from (used in) financing activities", -1,
    ),
    ConceptSpec(
        "BasicEarningsLossPerShareFromContinuingOperations", "income_statement", "CurrentYearDuration",
        "IDRPerShares", "4322000", "Basic earnings (loss) per share from continuing operations",
        "Basic earnings (loss) | per share from | continuing operations", 0,
        "Laba (rugi) per saham dasar dari operasi yang dilanjutkan",
        "Basic earnings (loss) per share from continuing operations",
    ),
    ConceptSpec(
        "TemporarySyirkahFunds", "balance_sheet", "CurrentYearInstant", "IDR",
        "4220000", "Total temporary syirkah funds",
        "Total temporary | syirkah funds", 6,
        "Jumlah dana syirkah temporer", "Total temporary syirkah funds",
        is_core=False,
    ),
)

CORE_CONCEPTS: tuple[ConceptSpec, ...] = tuple(spec for spec in ALL_CONCEPTS if spec.is_core)
CONCEPTS_BY_LOCAL_NAME = {spec.local_name: spec for spec in ALL_CONCEPTS}
