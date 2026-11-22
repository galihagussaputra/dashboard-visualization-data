import re
import zipfile
from datetime import date
from html import unescape
from pathlib import Path

from app.normalization.registry import CONCEPTS_BY_LOCAL_NAME
from app.parsers.models import ParsedFact, apply_scale, currency_for_unit, parse_decimal

TAG_PATTERN = re.compile(r"<ix:nonFraction\b([^>]*)>(.*?)</ix:nonFraction>", re.DOTALL | re.IGNORECASE)
ATTR_PATTERN = re.compile(r"([\w:-]+)\s*=\s*\"([^\"]*)\"")


def parse_inline_zip(path: str | Path, period=None) -> dict[str, ParsedFact]:
    facts: dict[str, ParsedFact] = {}
    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            if not member.endswith(".html"):
                continue
            content = archive.read(member).decode("utf-8", errors="replace")
            for match in TAG_PATTERN.finditer(content):
                attributes = dict(ATTR_PATTERN.findall(match.group(1)))
                local_name = attributes.get("name", "").split(":")[-1]
                spec = CONCEPTS_BY_LOCAL_NAME.get(local_name)
                if spec is None or attributes.get("contextRef") != spec.context_ref:
                    continue
                if spec.concept in facts:
                    continue
                raw_text = unescape(re.sub(r"<[^>]+>", "", match.group(2)))
                normalized_text = raw_text.replace("\u00a0", "").strip()
                negative_parentheses = normalized_text.startswith("(") and normalized_text.endswith(")")
                sign = attributes.get("sign") or ("-" if negative_parentheses else None)
                original = normalized_text.strip("() ").strip()
                scale = int(attributes.get("scale", "0"))
                unit = attributes.get("unitRef", spec.unit)
                facts[spec.concept] = ParsedFact(
                    concept=spec.concept,
                    statement_type=spec.statement_type,
                    source_fact_id=attributes.get("id", f"inline:{spec.concept}:{member}"),
                    source_context_ref=attributes["contextRef"],
                    value_original=original,
                    value_normalized=apply_scale(parse_decimal(original), scale, sign),
                    unit=unit,
                    source_scale=scale,
                    decimals=attributes.get("decimals"),
                    currency=currency_for_unit(unit),
                    context_start_date=_date(period, "start_date"),
                    context_end_date=_date(period, "end_date"),
                    context_instant_date=_date(period, "instant_date"),
                    source_file=member,
                )
    return facts


def _date(period, attribute: str) -> date | None:
    if period is None:
        return None
    value = getattr(period, attribute, None)
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    return None
