from datetime import date
from pathlib import Path

import openpyxl

from app.normalization.registry import ALL_CONCEPTS
from app.parsers.models import ParsedFact, apply_scale, currency_for_unit, parse_decimal


def parse_xlsx(path: str | Path, period=None) -> dict[str, ParsedFact]:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    facts: dict[str, ParsedFact] = {}

    for spec in ALL_CONCEPTS:
        sheet = workbook[spec.xlsx_sheet]
        for row in range(1, sheet.max_row + 1):
            label = sheet.cell(row, 4).value
            if _normalize_label(label) != _normalize_label(spec.xlsx_label):
                continue
            value = sheet.cell(row, 2).value
            if value is None:
                break
            original = str(value)
            facts[spec.concept] = ParsedFact(
                concept=spec.concept,
                statement_type=spec.statement_type,
                source_fact_id=f"xlsx:{spec.xlsx_sheet}:{row}",
                source_context_ref=spec.context_ref,
                value_original=original,
                value_normalized=apply_scale(parse_decimal(original), spec.source_scale),
                unit=spec.unit,
                source_scale=spec.source_scale,
                currency=currency_for_unit(spec.unit),
                context_start_date=_date(period, "start_date"),
                context_end_date=_date(period, "end_date"),
                context_instant_date=_date(period, "instant_date"),
                source_file=Path(path).name,
            )
            break
    workbook.close()
    return facts


def _normalize_label(value) -> str:
    return " ".join(str(value or "").split())


def _date(period, attribute: str) -> date | None:
    if period is None:
        return None
    value = getattr(period, attribute, None)
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    return None
