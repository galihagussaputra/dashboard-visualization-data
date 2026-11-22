from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.models import (
    FinancialAccount,
    FinancialDocument,
    FinancialFact,
    FinancialPeriod,
    FactRevision,
)


def restatement_summary(
    db: Session,
    *,
    company_id: int | None = None,
    period_id: int | None = None,
) -> list[dict[str, Any]]:
    statement = select(
        FactRevision,
        FinancialAccount.concept_code,
        FinancialPeriod.label,
        FinancialDocument.file_name,
    ).join(FinancialFact, FactRevision.predecessor_fact_id == FinancialFact.id)
    statement = statement.join(FinancialAccount, FinancialFact.account_id == FinancialAccount.id)
    statement = statement.join(FinancialPeriod, FactRevision.period_id == FinancialPeriod.id)
    statement = statement.join(FinancialDocument, FactRevision.document_id == FinancialDocument.id)
    if company_id is not None:
        statement = statement.where(FactRevision.company_id == company_id)
    if period_id is not None:
        statement = statement.where(FactRevision.period_id == period_id)
    rows = db.execute(statement.order_by(FactRevision.created_at.desc())).all()
    return [
        {
            "id": revision.id,
            "predecessor_fact_id": revision.predecessor_fact_id,
            "successor_fact_id": revision.successor_fact_id,
            "concept": concept,
            "period": label,
            "document": file_name,
            "document_version": revision.document_version,
            "reason": revision.revision_reason,
            "filing_date": revision.filing_date,
            "approval_status": revision.approval_status,
            "created_at": revision.created_at,
        }
        for revision, concept, label, file_name in rows
    ]


def approve_revision(
    db: Session,
    *,
    revision_id: int,
    actor_id: int,
    reason: str,
    context: dict[str, Any] | None = None,
) -> FactRevision:
    revision = db.get(FactRevision, revision_id)
    if revision is None:
        raise ValueError(f"revision {revision_id} not found")
    before = revision.approval_status
    revision.approval_status = "approved"
    revision.actor_id = actor_id
    revision.source_metadata = {
        **revision.source_metadata,
        "approval_reason": reason,
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }
    db.flush()
    record_audit(
        db,
        action="restatement.approve",
        entity_type="fact_revision",
        entity_id=str(revision.id),
        actor_id=actor_id,
        before_state={"approval_status": before},
        after_state={"approval_status": revision.approval_status},
        reason=reason,
        context=context,
    )
    return revision


def resolve_facts(
    db: Session,
    *,
    company_id: int,
    period_id: int,
    basis: str,
    as_of: date | None = None,
    published_only: bool = False,
) -> list[FinancialFact]:
    if as_of is None:
        statement = select(FinancialFact).where(
            FinancialFact.company_id == company_id,
            FinancialFact.period_id == period_id,
            FinancialFact.reporting_basis == basis,
            FinancialFact.is_current.is_(True),
        )
        if published_only:
            statement = statement.where(FinancialFact.publication_status == "published")
        return list(db.scalars(statement).all())

    documents = db.scalars(
        select(FinancialDocument).where(
            FinancialDocument.company_id == company_id,
            FinancialDocument.period_id == period_id,
        )
    ).all()
    eligible = [document for document in documents if _document_date(document) <= as_of]
    if not eligible:
        return []
    version = max(document.document_version for document in eligible)
    statement = select(FinancialFact).where(
        FinancialFact.company_id == company_id,
        FinancialFact.period_id == period_id,
        FinancialFact.reporting_basis == basis,
        FinancialFact.document_version == version,
    )
    if published_only:
        statement = statement.where(FinancialFact.publication_status == "published")
    return list(db.scalars(statement).all())


def _document_date(document: FinancialDocument) -> date:
    if document.filing_date is not None:
        return document.filing_date
    if isinstance(document.downloaded_at, datetime):
        return document.downloaded_at.date()
    return document.downloaded_at
