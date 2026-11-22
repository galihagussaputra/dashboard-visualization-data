import re
from datetime import date
from pathlib import Path

import fitz

from app.normalization.registry import ALL_CONCEPTS
from app.parsers.models import ParsedFact, apply_scale, currency_for_unit, parse_decimal

NUMBER_PATTERN = re.compile(r"^-?[\d,]+(?:\.\d+)?$")


def parse_pdf(path: str | Path, period=None) -> dict[str, ParsedFact]:
    document = fitz.open(path)
    tokens = [
        line.strip()
        for page in document
        for line in page.get_text().splitlines()
        if line.strip()
    ]
    document.close()

    facts: dict[str, ParsedFact] = {}
    for spec in ALL_CONCEPTS:
        needle = spec.pdf_label.split(" | ")
        label_index = _find_sequence(tokens, needle)
        if label_index is None:
            continue
        numeric_indices = [
            index for index in range(label_index - 1, -1, -1)
            if NUMBER_PATTERN.fullmatch(tokens[index])
        ]
        if not numeric_indices:
            continue
        current_index = numeric_indices[1] if len(numeric_indices) > 1 else numeric_indices[0]
        original = tokens[current_index]
        negative_parentheses = (
            current_index >= 2
            and tokens[current_index - 2] == "("
            and tokens[current_index - 1] == ")"
        )
        sign = "-" if negative_parentheses or original.startswith("-") else None
        value = parse_decimal(original.lstrip("-"))
        facts[spec.concept] = ParsedFact(
            concept=spec.concept,
            statement_type=spec.statement_type,
            source_fact_id=f"pdf:{spec.concept}:{label_index}",
            source_context_ref=spec.context_ref,
            value_original=original,
            value_normalized=apply_scale(value, spec.source_scale, sign),
            unit=spec.unit,
            source_scale=spec.source_scale,
            currency=currency_for_unit(spec.unit),
            context_start_date=_date(period, "start_date"),
            context_end_date=_date(period, "end_date"),
            context_instant_date=_date(period, "instant_date"),
            source_file=Path(path).name,
        )
    return facts


def _find_sequence(tokens: list[str], needle: list[str]) -> int | None:
    width = len(needle)
    for index in range(len(tokens) - width + 1):
        if tokens[index:index + width] == needle:
            return index
    return None


def _date(period, attribute: str) -> date | None:
    if period is None:
        return None
    value = getattr(period, attribute, None)
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    return None
