from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AccountMappingRule,
    FinancialAccount,
    FinancialFact,
    FinancialPeriod,
    SourceAccountMapping,
    StandardAccount,
)
from app.normalization.periods import classify_context, normalize_duration_kind

from .registry import ALL_CONCEPTS, ConceptSpec

MAPPING_STATUSES = ("unmapped", "suggested", "review_required", "approved", "rejected", "superseded")
APPROVED_CONFIDENCE = Decimal("1.0000")

STANDARD_ACCOUNT_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {"code": "CASH", "label": "Cash and cash equivalents", "statement_type": "balance_sheet", "definition": "Cash and balances with central banks at reporting date."},
    {"code": "TOTAL_ASSETS", "label": "Total assets", "statement_type": "balance_sheet", "definition": "Total assets at reporting date."},
    {"code": "TOTAL_LIABILITIES", "label": "Total liabilities", "statement_type": "balance_sheet", "definition": "Total liabilities at reporting date."},
    {"code": "TOTAL_EQUITY", "label": "Total equity", "statement_type": "balance_sheet", "definition": "Total equity at reporting date."},
    {"code": "TEMPORARY_SYIRKAH_FUNDS", "label": "Temporary syirkah funds", "statement_type": "balance_sheet", "definition": "Islamic banking temporary syirkah funds reported between liabilities and equity."},
    {"code": "REVENUE", "label": "Metric revenue", "statement_type": "income_statement", "definition": "Industry-specific revenue input used by margin and turnover ratios."},
    {"code": "OPERATING_PROFIT", "label": "Operating profit", "statement_type": "income_statement", "definition": "Profit from continuing operations before finance and tax where reported."},
    {"code": "PROFIT_LOSS_CONTINUING", "label": "Profit or loss from continuing operations", "statement_type": "income_statement", "definition": "Profit or loss from continuing operations before attribution."},
    {"code": "NET_INCOME", "label": "Net income attributable to parent", "statement_type": "income_statement", "definition": "Profit or loss attributable to the parent entity."},
    {"code": "EARNINGS_PER_SHARE", "label": "Basic earnings per share", "statement_type": "income_statement", "data_type": "per_share", "unit_hint": "IDRPerShares", "definition": "Basic earnings per share from continuing operations."},
    {"code": "OPERATING_CASH_FLOW", "label": "Operating cash flow", "statement_type": "cash_flow", "definition": "Net cash flows from operating activities."},
    {"code": "INVESTING_CASH_FLOW", "label": "Investing cash flow", "statement_type": "cash_flow", "definition": "Net cash flows from investing activities."},
    {"code": "FINANCING_CASH_FLOW", "label": "Financing cash flow", "statement_type": "cash_flow", "definition": "Net cash flows from financing activities."},
    {"code": "CURRENT_ASSETS", "label": "Current assets", "statement_type": "balance_sheet", "definition": "Assets expected to be realized within the normal operating cycle."},
    {"code": "CURRENT_LIABILITIES", "label": "Current liabilities", "statement_type": "balance_sheet", "definition": "Liabilities due within the normal operating cycle."},
    {"code": "QUICK_ASSETS", "label": "Quick assets", "statement_type": "balance_sheet", "definition": "Current assets excluding inventory and prepaid items."},
    {"code": "TOTAL_DEBT", "label": "Interest-bearing debt", "statement_type": "balance_sheet", "definition": "Interest-bearing borrowings; distinct from total liabilities."},
    {"code": "INVENTORY", "label": "Inventory", "statement_type": "balance_sheet", "definition": "Inventories at reporting date."},
    {"code": "COST_OF_GOODS_SOLD", "label": "Cost of goods sold", "statement_type": "income_statement", "definition": "Cost of inventory sold during the period."},
    {"code": "OPENING_TOTAL_ASSETS", "label": "Opening total assets", "statement_type": "balance_sheet", "definition": "Total assets at the beginning of the measurement period."},
    {"code": "CLOSING_TOTAL_ASSETS", "label": "Closing total assets", "statement_type": "balance_sheet", "definition": "Total assets at the end of the measurement period."},
    {"code": "OPENING_EQUITY", "label": "Opening equity", "statement_type": "balance_sheet", "definition": "Total equity at the beginning of the measurement period."},
    {"code": "CLOSING_EQUITY", "label": "Closing equity", "statement_type": "balance_sheet", "definition": "Total equity at the end of the measurement period."},
    {"code": "CAPITAL_EXPENDITURE", "label": "Capital expenditure", "statement_type": "cash_flow", "definition": "Cash outflow for purchases of property, plant and equipment, reported as a positive amount."},
    {"code": "OPENING_INVENTORY", "label": "Opening inventory", "statement_type": "balance_sheet", "definition": "Inventory at the beginning of the measurement period."},
    {"code": "CLOSING_INVENTORY", "label": "Closing inventory", "statement_type": "balance_sheet", "definition": "Inventory at the end of the measurement period."},
)

CONCEPT_TO_STANDARD_ACCOUNT = {
    "Cash": "CASH",
    "Assets": "TOTAL_ASSETS",
    "Liabilities": "TOTAL_LIABILITIES",
    "Equity": "TOTAL_EQUITY",
    "TemporarySyirkahFunds": "TEMPORARY_SYIRKAH_FUNDS",
    "InterestIncome": "REVENUE",
    "ProfitFromOperation": "OPERATING_PROFIT",
    "ProfitLoss": "PROFIT_LOSS_CONTINUING",
    "ProfitLossAttributableToParentEntity": "NET_INCOME",
    "BasicEarningsLossPerShareFromContinuingOperations": "EARNINGS_PER_SHARE",
    "NetCashFlowsReceivedFromUsedInOperatingActivities": "OPERATING_CASH_FLOW",
    "NetCashFlowsReceivedFromUsedInInvestingActivities": "INVESTING_CASH_FLOW",
    "NetCashFlowsReceivedFromUsedInFinancingActivities": "FINANCING_CASH_FLOW",
}

CONCEPT_INDUSTRY = {
    "InterestIncome": "banking",
    "TemporarySyirkahFunds": "banking",
}

TAXONOMY_CODE = "idx-taxonomy-2020"
RULE_VERSION = "m2-v1"

NAME_RULE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {"rule_code": "ACC-NAME-TOTAL_REVENUE", "source_name": "Total revenue", "standard_code": "REVENUE", "statement_type": "income_statement", "confidence": APPROVED_CONFIDENCE, "status": "approved", "evidence": "Exact income-statement caption for metric revenue; industry-specific rules take precedence when present."},
    {"rule_code": "ACC-NAME-TOTAL_CURRENT_ASSETS", "source_name": "Total current assets", "standard_code": "CURRENT_ASSETS", "statement_type": "balance_sheet", "confidence": APPROVED_CONFIDENCE, "status": "approved", "evidence": "Exact balance-sheet caption for current assets."},
    {"rule_code": "ACC-NAME-TOTAL_CURRENT_LIABILITIES", "source_name": "Total current liabilities", "standard_code": "CURRENT_LIABILITIES", "statement_type": "balance_sheet", "confidence": APPROVED_CONFIDENCE, "status": "approved", "evidence": "Exact balance-sheet caption for current liabilities."},
    {"rule_code": "ACC-NAME-TOTAL_INVENTORIES", "source_name": "Total inventories", "standard_code": "INVENTORY", "statement_type": "balance_sheet", "confidence": APPROVED_CONFIDENCE, "status": "approved", "evidence": "Exact balance-sheet caption for inventories."},
    {"rule_code": "ACC-NAME-TOTAL_INTEREST_BEARING_DEBT", "source_name": "Total interest-bearing debt", "standard_code": "TOTAL_DEBT", "statement_type": "balance_sheet", "confidence": APPROVED_CONFIDENCE, "status": "approved", "evidence": "Exact caption for interest-bearing borrowings; distinct from total liabilities."},
    {"rule_code": "ACC-NAME-COST_OF_GOODS_SOLD", "source_name": "Cost of goods sold", "standard_code": "COST_OF_GOODS_SOLD", "statement_type": "income_statement", "confidence": APPROVED_CONFIDENCE, "status": "approved", "evidence": "Exact income-statement caption for cost of inventory sold."},
    {"rule_code": "ACC-NAME-CAPITAL_EXPENDITURE", "source_name": "Capital expenditure", "standard_code": "CAPITAL_EXPENDITURE", "statement_type": "cash_flow", "confidence": APPROVED_CONFIDENCE, "status": "approved", "evidence": "Exact caption for positive cash outflow used by m2-v1 free cash flow."},
    {"rule_code": "ACC-NAME-QUICK_ASSETS_DEFINED", "source_name": "Quick assets (current assets less inventory and prepaid items)", "standard_code": "QUICK_ASSETS", "statement_type": "balance_sheet", "confidence": APPROVED_CONFIDENCE, "status": "approved", "evidence": "Exact caption explicitly states the m2-v1 quick-assets exclusions."},
    {"rule_code": "ACC-NAME-QUICK_ASSETS", "source_name": "Quick assets", "standard_code": "QUICK_ASSETS", "statement_type": "balance_sheet", "confidence": Decimal("0.8500"), "status": "review_required", "evidence": "Quick-assets definition varies by filer; reviewer must confirm exclusions."},
    {"rule_code": "ACC-NAME-TOTAL_DEBT", "source_name": "Total debt", "standard_code": "TOTAL_DEBT", "statement_type": "balance_sheet", "confidence": Decimal("0.8000"), "status": "review_required", "evidence": "Caption may include non-interest-bearing obligations; reviewer must confirm scope."},
    {"rule_code": "ACC-NAME-PPE_PURCHASES", "source_name": "Purchases of property, plant and equipment", "standard_code": "CAPITAL_EXPENDITURE", "statement_type": "cash_flow", "confidence": Decimal("0.8000"), "status": "review_required", "evidence": "Cash-flow captions frequently use a negative sign; reviewer must confirm positive convention."},
)


@dataclass(frozen=True)
class MappingResolution:
    status: str
    source_account_name: str
    source_taxonomy_concept: str | None
    standard_account_code: str | None
    mapping_id: int | None
    rule_code: str | None
    rule_version: str | None
    confidence: Decimal
    reason: str
    candidates: tuple[str, ...]


def ensure_reference_data(db: Session) -> dict[str, int]:
    standard_ids = {
        row.code: row.id for row in db.scalars(select(StandardAccount)).all()
    }
    for definition in STANDARD_ACCOUNT_DEFINITIONS:
        existing = db.scalars(select(StandardAccount).where(StandardAccount.code == definition["code"])).first()
        if existing is None:
            existing = StandardAccount(
                code=definition["code"],
                label=definition["label"],
                statement_type=definition["statement_type"],
                data_type=definition.get("data_type", "monetary"),
                unit_hint=definition.get("unit_hint"),
                definition=definition["definition"],
                industry_scope=definition.get("industry_scope", []),
            )
            db.add(existing)
            db.flush()
        standard_ids[definition["code"]] = existing.id

    for spec in ALL_CONCEPTS:
        standard_code = CONCEPT_TO_STANDARD_ACCOUNT.get(spec.local_name)
        if standard_code is None:
            continue
        rule_code = f"ACC-{spec.local_name}"
        exists = db.scalars(
            select(AccountMappingRule).where(
                AccountMappingRule.rule_code == rule_code,
                AccountMappingRule.version == RULE_VERSION,
            )
        ).first()
        if exists is not None:
            continue
        db.add(
            AccountMappingRule(
                rule_code=rule_code,
                version=RULE_VERSION,
                source_taxonomy_code=TAXONOMY_CODE,
                source_concept_qname=spec.concept,
                industry=CONCEPT_INDUSTRY.get(spec.local_name),
                statement_type=spec.statement_type,
                source_name=spec.label_en,
                standard_account_id=standard_ids[standard_code],
                confidence=APPROVED_CONFIDENCE,
                status="approved",
                evidence=f"Exact IDX taxonomy concept {spec.concept} in {spec.statement_type}",
                approved_at=None,
                is_active=True,
            )
        )
    for definition in NAME_RULE_DEFINITIONS:
        exists = db.scalars(
            select(AccountMappingRule).where(
                AccountMappingRule.rule_code == definition["rule_code"],
                AccountMappingRule.version == RULE_VERSION,
            )
        ).first()
        if exists is not None:
            continue
        db.add(
            AccountMappingRule(
                rule_code=definition["rule_code"],
                version=RULE_VERSION,
                source_taxonomy_code=TAXONOMY_CODE,
                source_concept_qname=None,
                industry=None,
                statement_type=definition["statement_type"],
                source_name=definition["source_name"],
                standard_account_id=standard_ids[definition["standard_code"]],
                confidence=definition["confidence"],
                status=definition["status"],
                evidence=definition["evidence"],
                approved_at=None,
                is_active=True,
            )
        )
    db.flush()
    return standard_ids


class AccountNormalizer:
    def __init__(self, db: Session):
        self.db = db

    def resolve(
        self,
        source_account_name: str,
        *,
        company_id: int | None = None,
        taxonomy_version_id: int | None = None,
        source_taxonomy_code: str | None = None,
        source_taxonomy_concept: str | None = None,
        industry: str | None = None,
        statement_type: str | None = None,
    ) -> MappingResolution:
        ensure_reference_data(self.db)
        rules = self.db.scalars(
            select(AccountMappingRule).where(AccountMappingRule.is_active.is_(True))
        ).all()
        matches = [
            rule
            for rule in rules
            if rule.status not in {"rejected", "superseded", "unmapped"}
            and self._matches(
                rule,
                source_account_name,
                source_taxonomy_code,
                source_taxonomy_concept,
                industry,
                statement_type,
            )
        ]
        if not matches:
            return self._record_unmapped(
                source_account_name,
                source_taxonomy_concept,
                company_id,
                taxonomy_version_id,
                industry,
                statement_type,
            )

        latest: dict[str, AccountMappingRule] = {}
        for rule in matches:
            current = latest.get(rule.rule_code)
            if current is None or _version_key(rule.version) > _version_key(current.version):
                latest[rule.rule_code] = rule
        candidates = list(latest.values())
        confidence = max(rule.confidence for rule in candidates)
        finalists = [rule for rule in candidates if rule.confidence == confidence]
        distinct_accounts = {rule.standard_account_id for rule in finalists}
        if len(distinct_accounts) > 1:
            return MappingResolution(
                status="review_required",
                source_account_name=source_account_name,
                source_taxonomy_concept=source_taxonomy_concept,
                standard_account_code=None,
                mapping_id=None,
                rule_code=None,
                rule_version=None,
                confidence=confidence,
                reason="ambiguous mapping: multiple standard accounts match with equal confidence",
                candidates=tuple(sorted(rule.rule_code for rule in finalists)),
            )

        rule = finalists[0]
        approved = (
            rule.status == "approved"
            and confidence == APPROVED_CONFIDENCE
            and bool(rule.evidence)
        )
        status = "approved" if approved else "review_required"
        standard = self.db.get(StandardAccount, rule.standard_account_id)
        reason = (
            "deterministic approved rule with taxonomy and statement evidence"
            if approved
            else "rule requires reviewer approval before publication"
        )
        mapping = self._persist_mapping(
            rule=rule,
            status=status,
            source_account_name=source_account_name,
            source_taxonomy_concept=source_taxonomy_concept,
            company_id=company_id,
            taxonomy_version_id=taxonomy_version_id,
            industry=industry,
            statement_type=statement_type,
            reason=reason,
        )
        return MappingResolution(
            status=status,
            source_account_name=source_account_name,
            source_taxonomy_concept=source_taxonomy_concept,
            standard_account_code=standard.code if standard else None,
            mapping_id=mapping.id,
            rule_code=rule.rule_code,
            rule_version=rule.version,
            confidence=confidence,
            reason=reason,
            candidates=tuple(sorted(rule.rule_code for rule in finalists)),
        )

    def _matches(
        self,
        rule: AccountMappingRule,
        source_account_name: str,
        source_taxonomy_code: str | None,
        source_taxonomy_concept: str | None,
        industry: str | None,
        statement_type: str | None,
    ) -> bool:
        if rule.industry is not None and rule.industry != industry:
            return False
        if rule.statement_type is not None and rule.statement_type != statement_type:
            return False
        taxonomy_match = bool(
            source_taxonomy_code
            and rule.source_taxonomy_code == source_taxonomy_code
            and source_taxonomy_concept
            and rule.source_concept_qname == source_taxonomy_concept
        )
        exact_name_match = bool(rule.source_name and rule.source_name == source_account_name)
        return taxonomy_match or exact_name_match

    def _record_unmapped(
        self,
        source_account_name: str,
        source_taxonomy_concept: str | None,
        company_id: int | None,
        taxonomy_version_id: int | None,
        industry: str | None,
        statement_type: str | None,
    ) -> MappingResolution:
        current = self.db.scalars(
            select(SourceAccountMapping).where(
                SourceAccountMapping.source_account_name == source_account_name,
                SourceAccountMapping.is_current.is_(True),
            )
        ).first()
        if current is not None and current.status == "unmapped":
            mapping = current
        else:
            mapping = SourceAccountMapping(
                company_id=company_id,
                taxonomy_version_id=taxonomy_version_id,
                source_account_name=source_account_name,
                source_taxonomy_concept=source_taxonomy_concept,
                industry=industry,
                statement_type=statement_type,
                status="unmapped",
                confidence=Decimal("0"),
                source_metadata={"reason": "no exact taxonomy or reviewed rule matched"},
            )
            self.db.add(mapping)
            self.db.flush()
            if current is not None:
                current.is_current = False
                current.status = "superseded"
                current.superseded_by = mapping.id
        return MappingResolution(
            status="unmapped",
            source_account_name=source_account_name,
            source_taxonomy_concept=source_taxonomy_concept,
            standard_account_code=None,
            mapping_id=mapping.id,
            rule_code=None,
            rule_version=None,
            confidence=Decimal("0"),
            reason="no exact taxonomy or reviewed rule matched; unknown account cannot be approved automatically",
            candidates=(),
        )

    def _persist_mapping(
        self,
        *,
        rule: AccountMappingRule,
        status: str,
        source_account_name: str,
        source_taxonomy_concept: str | None,
        company_id: int | None,
        taxonomy_version_id: int | None,
        industry: str | None,
        statement_type: str | None,
        reason: str,
    ) -> SourceAccountMapping:
        current = self.db.scalars(
            select(SourceAccountMapping).where(
                SourceAccountMapping.source_account_name == source_account_name,
                SourceAccountMapping.is_current.is_(True),
            )
        ).first()
        if (
            current is not None
            and current.status == status
            and current.rule_code == rule.rule_code
            and current.rule_version == rule.version
            and current.standard_account_id == rule.standard_account_id
        ):
            return current

        mapping = SourceAccountMapping(
            company_id=company_id,
            taxonomy_version_id=taxonomy_version_id,
            source_account_name=source_account_name,
            source_taxonomy_concept=source_taxonomy_concept,
            industry=industry,
            statement_type=statement_type,
            standard_account_id=rule.standard_account_id,
            rule_code=rule.rule_code,
            rule_version=rule.version,
            confidence=rule.confidence,
            status=status,
            evidence=rule.evidence,
            approved_by=rule.approved_by,
            approved_at=rule.approved_at,
            source_metadata={"reason": reason},
        )
        self.db.add(mapping)
        self.db.flush()
        if current is not None:
            current.is_current = False
            current.status = "superseded"
            current.superseded_by = mapping.id
        self.db.flush()
        return mapping


def backfill_fact_mappings(db: Session, *, company_id: int | None = None, period_id: int | None = None) -> int:
    ensure_reference_data(db)
    normalizer = AccountNormalizer(db)
    statement = select(FinancialFact).where(
        FinancialFact.is_current.is_(True),
    )
    if company_id is not None:
        statement = statement.where(FinancialFact.company_id == company_id)
    if period_id is not None:
        statement = statement.where(FinancialFact.period_id == period_id)
    facts = db.scalars(statement).all()
    updated = 0
    for fact in facts:
        account = db.get(FinancialAccount, fact.account_id)
        if account is None:
            continue
        local_name = account.concept_code.split(":")[-1]
        resolution = normalizer.resolve(
            account.label_en or account.label_id or local_name,
            company_id=fact.company_id,
            taxonomy_version_id=account.taxonomy_version_id,
            source_taxonomy_code=TAXONOMY_CODE,
            source_taxonomy_concept=account.concept_qname,
            industry=CONCEPT_INDUSTRY.get(local_name),
            statement_type=account.statement_type,
        )
        if resolution.status == "approved" and resolution.mapping_id is not None:
            fact.mapping_id = resolution.mapping_id
            updated += 1

        try:
            fact.period_kind = classify_context(
                fact.context_instant_date,
                fact.context_start_date,
                fact.context_end_date,
            )
        except ValueError:
            fact.period_kind = "duration"
        period = db.get(FinancialPeriod, fact.period_id)
        fact.duration_kind = (
            "not_applicable"
            if fact.period_kind == "instant"
            else normalize_duration_kind(period.period_type, period.is_ytd)
            if period is not None
            else "unknown"
        )
        if not fact.source_context_details:
            fact.source_context_details = {
                "source_context_ref": fact.source_context_ref,
                "context_start_date": fact.context_start_date.isoformat() if fact.context_start_date else None,
                "context_end_date": fact.context_end_date.isoformat() if fact.context_end_date else None,
                "context_instant_date": fact.context_instant_date.isoformat() if fact.context_instant_date else None,
                "taxonomy_code": TAXONOMY_CODE,
                "taxonomy_concept": account.concept_qname,
                "source_scale": fact.source_scale,
                "source_period_code": period.source_period_code if period else None,
            }
    db.flush()
    return updated


def approve_mapping(db: Session, mapping_id: int, actor_id: int, reason: str) -> SourceAccountMapping:
    mapping = db.get(SourceAccountMapping, mapping_id)
    if mapping is None:
        raise ValueError(f"mapping {mapping_id} not found")
    from datetime import datetime, timezone

    mapping.status = "approved"
    mapping.approved_by = actor_id
    mapping.approved_at = datetime.now(timezone.utc)
    mapping.source_metadata = {**mapping.source_metadata, "review_reason": reason}
    db.flush()
    return mapping


def _version_key(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in version.replace("v", ".").split("."):
        if piece.isdigit():
            parts.append(int(piece))
    return tuple(parts) or (0,)


def concept_spec(local_name: str) -> ConceptSpec | None:
    return next((spec for spec in ALL_CONCEPTS if spec.local_name == local_name), None)
