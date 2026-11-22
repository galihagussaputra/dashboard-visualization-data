from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.models import FinancialFact, FinancialMetric, PublicationEvent, ValidationLog
from app.validation.lifecycle import ValidationIssueRecord, ValidationOutcome, evaluate_scope

from .normalization.basis import publication_basis_is_explicit

WARNING_REVIEW_POLICY = "reviewer_acknowledged_warning"


class PublicationError(Exception):
    def __init__(self, message: str, issues: list[str]):
        super().__init__(message)
        self.issues = issues


@dataclass(frozen=True)
class PublicationResult:
    event: PublicationEvent
    outcome: ValidationOutcome
    facts_published: int
    metrics_published: int


def publish_scope(
    db: Session,
    *,
    company_id: int,
    period_id: int,
    basis: str,
    actor_id: int,
    context: dict[str, Any] | None = None,
) -> PublicationResult:
    if not publication_basis_is_explicit(basis):
        raise PublicationError("reporting basis must be explicit", ["BASIS-001: unknown reporting basis"])

    outcome = evaluate_scope(
        db,
        company_id=company_id,
        period_id=period_id,
        basis=basis,
        actor_id=actor_id,
    )
    blockers = [f"{issue.rule_code}: {issue.message}" for issue in outcome.issues if issue.blocking]
    unacknowledged = [
        f"{issue.rule_code}: {issue.message}"
        for issue in outcome.issues
        if issue.severity == "WARNING" and not _warning_acknowledged(db, issue)
    ]
    if blockers or unacknowledged:
        raise PublicationError(
            "publication gate rejected this scope",
            blockers + unacknowledged,
        )

    facts = db.scalars(
        select(FinancialFact).where(
            FinancialFact.company_id == company_id,
            FinancialFact.period_id == period_id,
            FinancialFact.reporting_basis == basis,
            FinancialFact.is_current.is_(True),
        )
    ).all()
    for fact in facts:
        fact.publication_status = "published"

    metrics = db.scalars(
        select(FinancialMetric).where(
            FinancialMetric.company_id == company_id,
            FinancialMetric.period_id == period_id,
            FinancialMetric.reporting_basis == basis,
            FinancialMetric.is_current.is_(True),
        )
    ).all()
    now = datetime.now(timezone.utc)
    for metric in metrics:
        if metric.calculation_status == "invalid":
            raise PublicationError(
                "publication gate rejected this scope",
                [f"MET-001: metric {metric.id} is invalid: {metric.unavailable_reason}"],
            )
        metric.publication_status = "published"
        metric.status = "published"
        metric.published_at = now
        metric.published_by = actor_id

    previous = db.scalars(
        select(PublicationEvent)
        .where(
            PublicationEvent.company_id == company_id,
            PublicationEvent.period_id == period_id,
            PublicationEvent.reporting_basis == basis,
            PublicationEvent.status == "published",
        )
        .order_by(PublicationEvent.created_at.desc())
    ).first()
    if previous is not None:
        previous.status = "superseded"

    event = PublicationEvent(
        company_id=company_id,
        period_id=period_id,
        reporting_basis=basis,
        status="published",
        validation_run_id=outcome.run.id,
        actor_id=actor_id,
        previous_event_id=previous.id if previous else None,
        publication_metadata={
            "facts_published": len(facts),
            "metrics_published": len(metrics),
            "validation_failure_count": len(blockers),
        },
    )
    db.add(event)
    outcome.run.status = "published"
    outcome.run.finished_at = now
    db.flush()

    record_audit(
        db,
        action="publication.publish",
        entity_type="publication_event",
        entity_id=str(event.id),
        actor_id=actor_id,
        after_state={
            "company_id": company_id,
            "period_id": period_id,
            "reporting_basis": basis,
            "facts_published": len(facts),
            "metrics_published": len(metrics),
        },
        reason="publisher gate passed",
        context=context,
    )
    return PublicationResult(
        event=event,
        outcome=outcome,
        facts_published=len(facts),
        metrics_published=len(metrics),
    )


def published_scope_exists(db: Session, company_id: int, period_id: int, basis: str) -> bool:
    return (
        db.scalars(
            select(PublicationEvent.id).where(
                PublicationEvent.company_id == company_id,
                PublicationEvent.period_id == period_id,
                PublicationEvent.reporting_basis == basis,
                PublicationEvent.status == "published",
            )
        ).first()
        is not None
    )


def _warning_acknowledged(db: Session, issue: ValidationIssueRecord) -> bool:
    if issue.severity != "WARNING":
        return True
    if issue.review_policy is None:
        return False
    return (
        db.scalars(
            select(ValidationLog.id)
            .where(
                ValidationLog.rule_code == issue.rule_code,
                ValidationLog.entity_type == issue.entity_type,
                ValidationLog.entity_id == issue.entity_id,
                ValidationLog.status == "overridden",
                ValidationLog.review_policy == issue.review_policy,
            )
            .limit(1)
        ).first()
        is not None
    )
