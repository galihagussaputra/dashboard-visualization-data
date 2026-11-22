import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.normalization.registry import CORE_CONCEPTS
from app.parsers.inline_xbrl import parse_inline_zip
from app.parsers.instance_xbrl import parse_instance_zip
from app.parsers.models import Period
from app.parsers.pdf import parse_pdf
from app.parsers.reconcile import reconcile_balance_sheet, reconcile_sources
from app.parsers.xlsx import parse_xlsx

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "bbca-2025"
PERIOD = Period(date(2025, 1, 1), date(2025, 12, 31), date(2025, 12, 31))

EXPECTED_VALUES = {
    "Cash": Decimal("25305031000000"),
    "Assets": Decimal("1586828536000000"),
    "Liabilities": Decimal("1294508286000000"),
    "Equity": Decimal("281687555000000"),
    "InterestIncome": Decimal("98912652000000"),
    "ProfitFromOperation": Decimal("71260876000000"),
    "ProfitLoss": Decimal("57563093000000"),
    "ProfitLossAttributableToParentEntity": Decimal("57537287000000"),
    "NetCashFlowsReceivedFromUsedInOperatingActivities": Decimal("77508785000000"),
    "NetCashFlowsReceivedFromUsedInInvestingActivities": Decimal("-33690926000000"),
    "NetCashFlowsReceivedFromUsedInFinancingActivities": Decimal("-41708637000000"),
    "BasicEarningsLossPerShareFromContinuingOperations": Decimal("467"),
}

SOURCES = {
    "instance_xbrl": ("instance.zip", parse_instance_zip),
    "inline_xbrl": ("inlineXBRL.zip", parse_inline_zip),
    "xlsx": ("FinancialStatement-2025-Tahunan-BBCA.xlsx", parse_xlsx),
    "pdf": ("FinancialStatement-2025-Tahunan-BBCA.pdf", parse_pdf),
}


@pytest.fixture(scope="module")
def parsed_sources():
    return {
        source_name: parser(FIXTURE_DIR / file_name, PERIOD)
        for source_name, (file_name, parser) in SOURCES.items()
    }


@pytest.mark.parametrize("source_name", sorted(SOURCES))
def test_source_reproduces_all_12_values(source_name, parsed_sources):
    facts = parsed_sources[source_name]
    assert len(CORE_CONCEPTS) == 12
    assert len(facts) >= len(EXPECTED_VALUES)
    for spec in CORE_CONCEPTS:
        assert facts[spec.concept].value_normalized == EXPECTED_VALUES[spec.local_name], (
            f"{source_name}:{spec.local_name}"
        )


def test_cross_source_reconciliation(parsed_sources):
    assert reconcile_sources(parsed_sources) == []


def test_balance_sheet_identity(parsed_sources):
    assert reconcile_balance_sheet(parsed_sources) == []


def test_fixture_metadata_matches_files():
    metadata = json.loads((FIXTURE_DIR / "metadata.json").read_text(encoding="utf-8"))
    assert len(metadata["attachments"]) == 4
    for attachment in metadata["attachments"]:
        path = FIXTURE_DIR / attachment["file_name"]
        assert path.stat().st_size == attachment["file_size"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == attachment["sha256"]
