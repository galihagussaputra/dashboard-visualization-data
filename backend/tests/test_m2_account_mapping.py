from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import AccountMappingRule, SourceAccountMapping, StandardAccount
from app.normalization.accounts import AccountNormalizer, ensure_reference_data


def _standard_id(db, code: str) -> int:
    ensure_reference_data(db)
    return db.scalars(select(StandardAccount).where(StandardAccount.code == code)).first().id


def test_known_taxonomy_mapping_is_approved_and_preserves_source_name():
    with SessionLocal() as db:
        result = AccountNormalizer(db).resolve(
            "Cash",
            source_taxonomy_code="idx-taxonomy-2020",
            source_taxonomy_concept="idx-cor:Cash",
            industry="banking",
            statement_type="balance_sheet",
        )
        assert result.status == "approved"
        assert result.standard_account_code == "CASH"
        mapping = db.get(SourceAccountMapping, result.mapping_id)
        assert mapping.source_account_name == "Cash"
        assert mapping.source_taxonomy_concept == "idx-cor:Cash"
        assert mapping.status == "approved"


def test_unknown_account_is_not_approved():
    with SessionLocal() as db:
        result = AccountNormalizer(db).resolve(
            f"Mystery account {uuid4()}", industry="manufacturing", statement_type="balance_sheet"
        )
        assert result.status == "unmapped"
        assert result.standard_account_code is None
        assert "cannot be approved automatically" in result.reason


def test_ambiguous_mapping_requires_review():
    with SessionLocal() as db:
        token = uuid4().hex[:8]
        assets_id = _standard_id(db, "TOTAL_ASSETS")
        liabilities_id = _standard_id(db, "TOTAL_LIABILITIES")
        source_name = f"Ambiguous {token}"
        for suffix, account_id in (("a", assets_id), ("b", liabilities_id)):
            db.add(
                AccountMappingRule(
                    rule_code=f"AMB-{token}-{suffix}",
                    version="m2-v1",
                    source_name=source_name,
                    industry="energy",
                    statement_type="balance_sheet",
                    standard_account_id=account_id,
                    confidence=Decimal("0.8000"),
                    status="approved",
                    evidence="fixture rule",
                )
            )
        db.flush()
        result = AccountNormalizer(db).resolve(source_name, industry="energy", statement_type="balance_sheet")
        assert result.status == "review_required"
        assert result.standard_account_code is None
        assert "ambiguous" in result.reason


def test_industry_specific_mapping_is_isolated():
    with SessionLocal() as db:
        token = uuid4().hex[:8]
        source_name = f"Industry revenue {token}"
        revenue_id = _standard_id(db, "REVENUE")
        db.add(
            AccountMappingRule(
                rule_code=f"IND-{token}",
                version="m2-v1",
                source_name=source_name,
                industry="energy",
                statement_type="income_statement",
                standard_account_id=revenue_id,
                confidence=Decimal("1.0000"),
                status="approved",
                evidence="energy industry reporting definition",
            )
        )
        db.flush()
        normalizer = AccountNormalizer(db)
        assert normalizer.resolve(source_name, industry="energy", statement_type="income_statement").status == "approved"
        assert normalizer.resolve(source_name, industry="telecommunications", statement_type="income_statement").status == "unmapped"


def test_taxonomy_specific_mapping_does_not_use_name_similarity():
    with SessionLocal() as db:
        token = uuid4().hex[:8]
        cash_id = _standard_id(db, "CASH")
        source_name = f"Taxonomy cash {token}"
        db.add(
            AccountMappingRule(
                rule_code=f"TAX-{token}",
                version="m2-v1",
                source_taxonomy_code="custom-taxonomy-2026",
                source_concept_qname="custom:CashEquivalent",
                industry=None,
                statement_type="balance_sheet",
                standard_account_id=cash_id,
                confidence=Decimal("1.0000"),
                status="approved",
                evidence="exact custom taxonomy concept",
            )
        )
        db.flush()
        normalizer = AccountNormalizer(db)
        good = normalizer.resolve(
            source_name,
            source_taxonomy_code="custom-taxonomy-2026",
            source_taxonomy_concept="custom:CashEquivalent",
            statement_type="balance_sheet",
        )
        bad = normalizer.resolve(
            source_name,
            source_taxonomy_code="other-taxonomy",
            source_taxonomy_concept="other:CashLike",
            statement_type="balance_sheet",
        )
        assert good.status == "approved"
        assert bad.status == "unmapped"


def test_mapping_version_change_supersedes_previous_mapping():
    with SessionLocal() as db:
        token = uuid4().hex[:8]
        source_name = f"Versioned account {token}"
        cash_id = _standard_id(db, "CASH")
        assets_id = _standard_id(db, "TOTAL_ASSETS")
        db.add(
            AccountMappingRule(
                rule_code=f"VER-{token}",
                version="m2-v1",
                source_name=source_name,
                standard_account_id=cash_id,
                confidence=Decimal("1.0000"),
                status="approved",
                evidence="v1 evidence",
            )
        )
        db.flush()
        first = AccountNormalizer(db).resolve(source_name)
        db.add(
            AccountMappingRule(
                rule_code=f"VER-{token}",
                version="m2-v2",
                source_name=source_name,
                standard_account_id=assets_id,
                confidence=Decimal("1.0000"),
                status="approved",
                evidence="v2 evidence",
            )
        )
        db.flush()
        second = AccountNormalizer(db).resolve(source_name)
        old_mapping = db.get(SourceAccountMapping, first.mapping_id)
        assert first.status == "approved"
        assert second.status == "approved"
        assert second.standard_account_code == "TOTAL_ASSETS"
        assert second.rule_version == "m2-v2"
        assert old_mapping.is_current is False
        assert old_mapping.status == "superseded"
        assert old_mapping.superseded_by == second.mapping_id


def test_rejected_rule_is_not_applied():
    with SessionLocal() as db:
        token = uuid4().hex[:8]
        source_name = f"Rejected account {token}"
        cash_id = _standard_id(db, "CASH")
        db.add(
            AccountMappingRule(
                rule_code=f"REJ-{token}",
                version="m2-v1",
                source_name=source_name,
                standard_account_id=cash_id,
                confidence=Decimal("1.0000"),
                status="rejected",
                evidence="explicitly rejected",
            )
        )
        db.flush()
        result = AccountNormalizer(db).resolve(source_name)
        assert result.status == "unmapped"
        assert result.standard_account_code is None
