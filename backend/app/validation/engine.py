from dataclasses import dataclass
from typing import Any

from app.parsers.arelle import ArelleResult
from app.parsers.models import ParsedFact
from app.parsers.reconcile import reconcile_balance_sheet, reconcile_sources


@dataclass(frozen=True)
class ValidationIssue:
    rule_code: str
    severity: str
    entity_type: str
    entity_id: str
    message: str
    expected_value: str | None = None
    actual_value: str | None = None
    log_metadata: dict[str, Any] | None = None
    rule_category: str = "extraction"


def build_validation_issues(
    sources: dict[str, dict[str, ParsedFact]],
    arelle_result: ArelleResult,
    document_checks: dict[str, tuple[bool, bool]],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    source_errors = reconcile_sources(sources)
    issues.append(
        ValidationIssue(
            "XFORM-001",
            "error" if source_errors else "info",
            "document_set",
            "bbca-fy2025-audit-fixture",
            "Cross-format values must match after scale normalization",
            expected_value="12/12 core facts match across four formats",
            actual_value="; ".join(source_errors) if source_errors else "12/12 core facts matched",
            log_metadata={"sources": sorted(sources)},
            rule_category="extraction",
        )
    )

    balance_errors = reconcile_balance_sheet(sources)
    issues.append(
        ValidationIssue(
            "FACT-001",
            "error" if balance_errors else "info",
            "document_set",
            "bbca-fy2025-audit-fixture",
            "Assets must equal liabilities plus temporary syirkah funds plus equity",
            expected_value="assets = liabilities + temporary syirkah funds + equity",
            actual_value="; ".join(balance_errors) if balance_errors else "balance equation matched in all sources",
            rule_category="accounting",
        )
    )

    document_errors = [
        f"{name}: size_match={size_match}, hash_match={hash_match}"
        for name, (size_match, hash_match) in document_checks.items()
        if not (size_match and hash_match)
    ]
    issues.append(
        ValidationIssue(
            "DOC-001",
            "error" if document_errors else "info",
            "document_set",
            "bbca-fy2025-audit-fixture",
            "Downloaded files must match source size and SHA-256",
            expected_value="4/4 files match source metadata",
            actual_value="; ".join(document_errors) if document_errors else "4/4 files matched",
            rule_category="document",
        )
    )

    arelle_severity = {"passed": "info", "warning": "warning", "failed": "error"}[arelle_result.status]
    issues.append(
        ValidationIssue(
            "ARELLE-001",
            arelle_severity,
            "document",
            "instance.xbrl",
            "Arelle offline XBRL validation status",
            expected_value="passed",
            actual_value=arelle_result.status,
            log_metadata={
                "return_code": arelle_result.return_code,
                "errors": list(arelle_result.errors),
                "warnings": list(arelle_result.warnings),
            },
            rule_category="document",
        )
    )
    return issues


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)
