from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Company,
    FinancialDocument,
    FinancialFact,
    FinancialMetric,
    FinancialPeriod,
    PublicationEvent,
    SourceAccountMapping,
    StandardAccount,
    ValidationLog,
    ValidationRun,
)
from app.normalization.accounts import backfill_fact_mappings

BLOCKING_SEVERITIES = {"ERROR", "BLOCKER"}
VALIDATION_STATUSES = (
    "pending",
    "processing",
    "validation_failed",
    "review_required",
    "validated",
    "published",
    "superseded",
)
WARNING_REVIEW_POLICY = "reviewer_acknowledged_warning"


@dataclass(frozen=True)
class ValidationIssueRecord:
    rule_code: str
    severity: str
    category: str
    entity_type: str
    entity_id: str
    message: str
    expected_value: str | None = None
    actual_value: str | None = None
    metadata: dict[str, Any] | None = None
    review_policy: str | None = None

    @property
    def blocking(self) -> bool:
        return self.severity in BLOCKING_SEVERITIES


@dataclass(frozen=True)
class ValidationOutcome:
    run: ValidationRun
    issues: tuple[ValidationIssueRecord, ...]
    failures: tuple[ValidationIssueRecord, ...]
    warnings: tuple[ValidationIssueRecord, ...]

    @property
    def can_publish(self) -> bool:
        return not self.failures


def create_validation_run(
    db: Session,
    *,
    scope_type: str,
    scope_id: str,
    actor_id: int | None = None,
) -> ValidationRun:
    run = ValidationRun(
        scope_type=scope_type,
        scope_id=scope_id,
        status="pending",
        actor_id=actor_id,
        summary={},
    )
    db.add(run)
    db.flush()
    run.status = "processing"
    db.flush()
    return run


def complete_validation_run(db: Session, outcome: ValidationOutcome) -> ValidationRun:
    run = outcome.run
    if outcome.failures:
        run.status = "validation_failed"
    elif outcome.warnings:
        run.status = "review_required"
    else:
        run.status = "validated"
    run.summary = {
        "issue_count": len(outcome.issues),
        "failure_count": len(outcome.failures),
        "warning_count": len(outcome.warnings),
        "can_publish": outcome.can_publish,
    }
    run.finished_at = datetime.now(timezone.utc)
    db.flush()
    return run


def record_issue(
    db: Session,
    *,
    run_id: int,
    issue: ValidationIssueRecord,
    ingestion_job_id: int | None = None,
) -> ValidationLog:
    metadata = dict(issue.metadata or {})
    if ingestion_job_id is not None:
        metadata["ingestion_job_id"] = ingestion_job_id
    log = ValidationLog(
        rule_code=issue.rule_code,
        severity=issue.severity.lower() if issue.severity != "BLOCKER" else "error",
        entity_type=issue.entity_type,
        entity_id=issue.entity_id,
        message=issue.message,
        expected_value=issue.expected_value,
        actual_value=issue.actual_value,
        severity_level="ERROR" if issue.severity == "BLOCKER" else issue.severity,
        rule_category=issue.category,
        is_blocking=issue.blocking,
        validation_run_id=run_id,
        status="open",
        review_policy=issue.review_policy,
        log_metadata=metadata,
    )
    db.add(log)
    db.flush()
    return log


def evaluate_scope(
    db: Session,
    *,
    company_id: int,
    period_id: int,
    basis: str,
    actor_id: int | None = None,
) -> ValidationOutcome:
    company = db.get(Company, company_id)
    period = db.get(FinancialPeriod, period_id)
    backfill_fact_mappings(db, company_id=company_id, period_id=period_id)
    run = create_validation_run(
        db,
        scope_type="publication_scope",
        scope_id=f"{company.ticker if company else company_id}:{period.label if period else period_id}:{basis}",
        actor_id=actor_id,
    )
    issues = _evaluate_documents(db, company_id, period_id)
    issues.extend(_evaluate_facts(db, company_id, period_id, basis))
    issues.extend(_evaluate_mappings(db, company_id, period_id, basis))
    issues.extend(_evaluate_metrics(db, company_id, period_id, basis))
    issues.extend(_evaluate_publication_history(db, company_id, period_id, basis))

    for issue in issues:
        record_issue(db, run_id=run.id, issue=issue)
    failures = tuple(issue for issue in issues if issue.blocking)
    warnings = tuple(
        issue for issue in issues if issue.severity == "WARNING" and issue.review_policy is None
    )
    outcome = ValidationOutcome(run=run, issues=tuple(issues), failures=failures, warnings=warnings)
    complete_validation_run(db, outcome)
    return outcome


def can_publish(issues: list[ValidationIssueRecord] | tuple[ValidationIssueRecord, ...]) -> tuple[bool, list[str]]:
    failures = [
        f"{issue.rule_code}: {issue.message}"
        for issue in issues
        if issue.blocking
    ]
    return not failures, failures


def override_validation_log(db: Session, log_id: int, actor_id: int, reason: str) -> ValidationLog:
    log = db.get(ValidationLog, log_id)
    if log is None:
        raise ValueError(f"validation log {log_id} not found")
    if log.severity_level not in {"WARNING"}:
        raise ValueError("only warning findings can be manually acknowledged")
    log.status = "overridden"
    log.resolved_by = actor_id
    log.resolved_at = datetime.now(timezone.utc)
    log.review_policy = WARNING_REVIEW_POLICY
    log.override_reason = reason
    db.flush()
    return log


def _evaluate_documents(db: Session, company_id: int, period_id: int) -> list[ValidationIssueRecord]:
    documents = db.scalars(
        select(FinancialDocument).where(
            FinancialDocument.company_id == company_id,
            FinancialDocument.period_id == period_id,
        )
    ).all()
    issues: list[ValidationIssueRecord] = []
    if not documents:
        issues.append(
            ValidationIssueRecord(
                "DOC-003", "BLOCKER", "document", "company_period", f"{company_id}:{period_id}",
                "No source documents found for publication scope",
                expected_value="at least one parsed document",
            )
        )
        return issues

    seen: set[tuple[str, str]] = set()
    for document in documents:
        if document.company_id != company_id or document.period_id != period_id:
            issues.append(
                ValidationIssueRecord(
                    "DOC-003", "BLOCKER", "document", "document", str(document.id),
                    "Document identity or period does not match publication scope",
                )
            )
        key = (document.source_document_id, document.file_role)
        if key in seen:
            issues.append(
                ValidationIssueRecord(
                    "DOC-002", "BLOCKER", "document", "document", str(document.id),
                    "Duplicate source document and file role detected",
                    actual_value=f"{document.source_document_id}:{document.file_role}",
                )
            )
        seen.add(key)
        if document.parse_status != "parsed":
            issues.append(
                ValidationIssueRecord(
                    "DOC-001", "ERROR", "document", "document", str(document.id),
                    "Document has not completed parsing",
                    expected_value="parsed",
                    actual_value=document.parse_status,
                )
            )
        if not document.sha256 or (document.file_size_bytes or 0) <= 0:
            issues.append(
                ValidationIssueRecord(
                    "DOC-001", "ERROR", "document", "document", str(document.id),
                    "Document checksum or size is missing",
                )
            )
    return issues


def _evaluate_facts(
    db: Session,
    company_id: int,
    period_id: int,
    basis: str,
) -> list[ValidationIssueRecord]:
    facts = db.scalars(
        select(FinancialFact).where(
            FinancialFact.company_id == company_id,
            FinancialFact.period_id == period_id,
            FinancialFact.is_current.is_(True),
        )
    ).all()
    issues: list[ValidationIssueRecord] = []
    if not facts:
        issues.append(
            ValidationIssueRecord(
                "FACT-004", "BLOCKER", "extraction", "company_period", f"{company_id}:{period_id}",
                "No current financial facts found for publication scope",
            )
        )
        return issues

    if any(fact.reporting_basis != basis for fact in facts):
        issues.append(
            ValidationIssueRecord(
                "BASIS-001", "BLOCKER", "reporting_basis", "company_period", f"{company_id}:{period_id}",
                "Reporting basis mismatch detected in current facts",
                expected_value=basis,
                actual_value=",".join(sorted({fact.reporting_basis for fact in facts})),
            )
        )
    if basis not in {"consolidated", "separate"}:
        issues.append(
            ValidationIssueRecord(
                "BASIS-001", "BLOCKER", "reporting_basis", "company_period", f"{company_id}:{period_id}",
                "Publication requires an explicit consolidated or separate basis",
                actual_value=basis,
            )
        )

    seen: set[tuple[str, int, str]] = set()
    context_signatures: dict[str, tuple] = {}
    by_concept: dict[str, Decimal] = {}
    for fact in facts:
        key = (fact.source_fact_id, fact.period_id, fact.reporting_basis)
        if key in seen:
            issues.append(
                ValidationIssueRecord(
                    "FACT-002", "BLOCKER", "extraction", "fact", str(fact.id),
                    "Duplicate source fact detected in current population",
                )
            )
        seen.add(key)

        context_signature = (
            fact.context_start_date,
            fact.context_end_date,
            fact.context_instant_date,
            fact.reporting_basis,
            fact.period_kind,
        )
        previous_signature = context_signatures.get(fact.source_context_ref)
        if previous_signature is not None and previous_signature != context_signature:
            issues.append(
                ValidationIssueRecord(
                    "PER-001", "ERROR", "period", "fact", str(fact.id),
                    "Source context reused with inconsistent period or basis dimensions",
                    actual_value=fact.source_context_ref,
                )
            )
        context_signatures[fact.source_context_ref] = context_signature

        if fact.value_normalized is None or not Decimal(str(fact.value_normalized)).is_finite():
            issues.append(
                ValidationIssueRecord(
                    "FACT-003", "BLOCKER", "extraction", "fact", str(fact.id),
                    "Financial fact value is not numerically valid",
                )
            )
        if not fact.unit or (fact.unit != "IDRPerShares" and not fact.currency):
            issues.append(
                ValidationIssueRecord(
                    "FACT-003", "ERROR", "extraction", "fact", str(fact.id),
                    "Financial fact unit or currency is missing",
                )
            )
        if not fact.source_context_ref:
            issues.append(
                ValidationIssueRecord(
                    "FACT-003", "ERROR", "extraction", "fact", str(fact.id),
                    "Financial fact source context is missing",
                )
            )
        if fact.period_kind not in {"instant", "duration"}:
            issues.append(
                ValidationIssueRecord(
                    "PER-001", "ERROR", "period", "fact", str(fact.id),
                    "Financial fact period kind is not normalized",
                    actual_value=fact.period_kind,
                )
            )
        if fact.period_kind == "instant" and (
            fact.context_instant_date is None or fact.context_start_date is not None
        ):
            issues.append(
                ValidationIssueRecord(
                    "PER-001", "ERROR", "period", "fact", str(fact.id),
                    "Instant fact does not have a valid instant context",
                )
            )
        if fact.period_kind == "duration" and (
            fact.context_start_date is None
            or fact.context_end_date is None
            or fact.context_end_date < fact.context_start_date
        ):
            issues.append(
                ValidationIssueRecord(
                    "PER-001", "ERROR", "period", "fact", str(fact.id),
                    "Duration fact does not have a valid date range",
                )
            )
        if fact.validation_status in {"failed", "pending"}:
            issues.append(
                ValidationIssueRecord(
                    "FACT-003", "ERROR", "extraction", "fact", str(fact.id),
                    "Financial fact has not passed validation",
                    actual_value=fact.validation_status,
                )
            )
        by_concept[fact.accounting_definition_key] = fact.value_normalized

    assets = by_concept.get("idx-cor:Assets")
    liabilities = by_concept.get("idx-cor:Liabilities")
    equity = by_concept.get("idx-cor:Equity")
    syirkah = by_concept.get("idx-cor:TemporarySyirkahFunds", Decimal("0"))
    if assets is not None and liabilities is not None and equity is not None:
        expected = liabilities + syirkah + equity
        if assets != expected:
            issues.append(
                ValidationIssueRecord(
                    "FACT-001", "ERROR", "accounting", "company_period", f"{company_id}:{period_id}",
                    "Bank balance equation does not reconcile",
                    expected_value=str(expected),
                    actual_value=str(assets),
                )
            )
    return issues


def _evaluate_mappings(
    db: Session,
    company_id: int,
    period_id: int,
    basis: str,
) -> list[ValidationIssueRecord]:
    facts = db.scalars(
        select(FinancialFact).where(
            FinancialFact.company_id == company_id,
            FinancialFact.period_id == period_id,
            FinancialFact.is_current.is_(True),
            FinancialFact.reporting_basis == basis,
        )
    ).all()
    issues: list[ValidationIssueRecord] = []
    for fact in facts:
        mapping = db.get(SourceAccountMapping, fact.mapping_id) if fact.mapping_id else None
        if mapping is None:
            issues.append(
                ValidationIssueRecord(
                    "MAP-001", "BLOCKER", "mapping", "fact", str(fact.id),
                    "Financial fact has no reviewed source account mapping",
                )
            )
            continue
        if mapping.status != "approved":
            issues.append(
                ValidationIssueRecord(
                    "MAP-001", "BLOCKER", "mapping", "fact", str(fact.id),
                    "Source account mapping is not approved",
                    expected_value="approved",
                    actual_value=mapping.status,
                )
            )
            continue
        if mapping.standard_account_id is None:
            issues.append(
                ValidationIssueRecord(
                    "MAP-001", "BLOCKER", "mapping", "mapping", str(mapping.id),
                    "Approved mapping has no standard account",
                )
            )
        else:
            standard = db.get(StandardAccount, mapping.standard_account_id)
            if standard is None or not standard.is_active:
                issues.append(
                    ValidationIssueRecord(
                        "MAP-001", "BLOCKER", "mapping", "mapping", str(mapping.id),
                        "Approved mapping references an inactive standard account",
                    )
                )
    return issues


def _evaluate_metrics(
    db: Session,
    company_id: int,
    period_id: int,
    basis: str,
) -> list[ValidationIssueRecord]:
    metrics = db.scalars(
        select(FinancialMetric).where(
            FinancialMetric.company_id == company_id,
            FinancialMetric.period_id == period_id,
            FinancialMetric.is_current.is_(True),
            FinancialMetric.reporting_basis == basis,
        )
    ).all()
    issues: list[ValidationIssueRecord] = []
    for metric in metrics:
        if metric.calculation_status == "invalid":
            issues.append(
                ValidationIssueRecord(
                    "MET-001", "BLOCKER", "metric", "metric", str(metric.id),
                    "Metric cannot be published with an invalid calculation",
                    actual_value=f"{metric.calculation_status}:{metric.unavailable_reason}",
                )
            )
        if metric.formula_version != "m2-v1":
            issues.append(
                ValidationIssueRecord(
                    "MET-001", "BLOCKER", "metric", "metric", str(metric.id),
                    "Metric uses an unsupported formula version",
                    actual_value=metric.formula_version,
                )
            )
    return issues


def _evaluate_publication_history(
    db: Session,
    company_id: int,
    period_id: int,
    basis: str,
) -> list[ValidationIssueRecord]:
    events = db.scalars(
        select(PublicationEvent).where(
            PublicationEvent.company_id == company_id,
            PublicationEvent.period_id == period_id,
            PublicationEvent.reporting_basis == basis,
        )
    ).all()
    if not events:
        return []
    return [
        ValidationIssueRecord(
            "PUB-001",
            "WARNING",
            "publication",
            "publication_event",
            str(events[-1].id),
            "Scope was previously published; republishing will supersede the prior event",
            review_policy=WARNING_REVIEW_POLICY,
        )
    ]
