import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from app.normalization.registry import CONCEPTS_BY_LOCAL_NAME
from app.parsers.models import ParsedFact, apply_scale, currency_for_unit, parse_decimal


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_contexts(root: ET.Element) -> dict[str, dict[str, str]]:
    contexts: dict[str, dict[str, str]] = {}
    for element in root.iter():
        if _local_name(element.tag) != "context":
            continue
        context_id = element.attrib.get("id")
        if not context_id:
            continue
        values: dict[str, str] = {}
        for child in element.iter():
            name = _local_name(child.tag)
            if name in {"instant", "startDate", "endDate"} and child.text:
                values[name] = child.text.strip()
        contexts[context_id] = values
    return contexts


def parse_instance_zip(path: str | Path, period=None) -> dict[str, ParsedFact]:
    with zipfile.ZipFile(path) as archive:
        member = next(name for name in archive.namelist() if name.endswith("instance.xbrl"))
        root = ET.fromstring(archive.read(member))

    contexts = _parse_contexts(root)
    facts: dict[str, ParsedFact] = {}

    for element in root.iter():
        local_name = _local_name(element.tag)
        spec = CONCEPTS_BY_LOCAL_NAME.get(local_name)
        if spec is None:
            continue
        context_ref = element.attrib.get("contextRef")
        if context_ref != spec.context_ref:
            continue
        original = (element.text or "").strip()
        if not original:
            continue
        scale = int(element.attrib.get("scale", "0"))
        context = contexts.get(context_ref, {})
        unit_ref = element.attrib.get("unitRef", spec.unit)
        facts[spec.concept] = ParsedFact(
            concept=spec.concept,
            statement_type=spec.statement_type,
            source_fact_id=element.attrib.get("id", f"instance:{spec.concept}:{context_ref}"),
            source_context_ref=context_ref,
            value_original=original,
            value_normalized=apply_scale(parse_decimal(original), scale, element.attrib.get("sign")),
            unit=unit_ref,
            source_scale=scale,
            decimals=element.attrib.get("decimals"),
            currency=currency_for_unit(unit_ref),
            context_start_date=_to_date(context.get("startDate")),
            context_end_date=_to_date(context.get("endDate")),
            context_instant_date=_to_date(context.get("instant")),
            source_file=member,
        )
    return facts


def _to_date(value: str | None):
    if not value:
        return None
    return date.fromisoformat(value)
