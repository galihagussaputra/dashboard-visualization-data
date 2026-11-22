from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class Period:
    start_date: date
    end_date: date
    instant_date: date


@dataclass(frozen=True)
class ParsedFact:
    concept: str
    statement_type: str
    source_fact_id: str
    source_context_ref: str
    value_original: str
    value_normalized: Decimal
    unit: str
    source_scale: int = 0
    decimals: str | None = None
    currency: str | None = None
    context_start_date: date | None = None
    context_end_date: date | None = None
    context_instant_date: date | None = None
    source_file: str | None = None

    @property
    def local_name(self) -> str:
        return self.concept.split(":", 1)[-1]


def parse_decimal(value: str) -> Decimal:
    cleaned = value.strip().replace(",", "").replace(" ", "")
    if not cleaned:
        raise InvalidOperation("empty value")
    return Decimal(cleaned)


def apply_scale(value: Decimal, scale: int, sign: str | None = None) -> Decimal:
    normalized = value * (Decimal(10) ** scale)
    if sign == "-":
        normalized = -normalized
    return normalized


def currency_for_unit(unit: str) -> str | None:
    return unit if len(unit) == 3 and unit.isalpha() else None
