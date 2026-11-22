from app.normalization.registry import CORE_CONCEPTS
from app.parsers.models import ParsedFact

SOURCE_NAMES = ("instance_xbrl", "inline_xbrl", "xlsx", "pdf")


def reconcile_sources(sources: dict[str, dict[str, ParsedFact]]) -> list[str]:
    errors: list[str] = []
    for spec in CORE_CONCEPTS:
        values: dict[str, object] = {}
        for source_name in SOURCE_NAMES:
            fact = sources.get(source_name, {}).get(spec.concept)
            if fact is None:
                errors.append(f"{spec.local_name}: missing in {source_name}")
                continue
            if fact.statement_type != spec.statement_type:
                errors.append(f"{spec.local_name}: statement type mismatch in {source_name}")
            if fact.unit != spec.unit:
                errors.append(f"{spec.local_name}: unit mismatch in {source_name}")
            values[source_name] = fact.value_normalized
        if len(set(values.values())) > 1:
            rendered = ", ".join(f"{name}={value}" for name, value in values.items())
            errors.append(f"{spec.local_name}: cross-source value mismatch ({rendered})")
    return errors


def reconcile_balance_sheet(sources: dict[str, dict[str, ParsedFact]]) -> list[str]:
    errors: list[str] = []
    for source_name, facts in sources.items():
        try:
            assets = facts["idx-cor:Assets"].value_normalized
            liabilities = facts["idx-cor:Liabilities"].value_normalized
            equity = facts["idx-cor:Equity"].value_normalized
        except KeyError:
            errors.append(f"{source_name}: balance sheet facts missing")
            continue
        syirkah_fact = facts.get("idx-cor:TemporarySyirkahFunds")
        syirkah = syirkah_fact.value_normalized if syirkah_fact is not None else 0
        if assets != liabilities + syirkah + equity:
            errors.append(
                f"{source_name}: assets {assets} != liabilities {liabilities} "
                f"+ temporary syirkah funds {syirkah} + equity {equity}"
            )
    return errors
