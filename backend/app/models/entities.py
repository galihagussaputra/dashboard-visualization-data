from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Sector(Base):
    __tablename__ = "sectors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    sector: Mapped[str] = mapped_column(String(80), nullable=False)
    subsector: Mapped[str | None] = mapped_column(String(80))
    industry: Mapped[str | None] = mapped_column(String(80))
    subindustry: Mapped[str | None] = mapped_column(String(80))
    taxonomy_entry_point: Mapped[str | None] = mapped_column(String(80))


class Company(TimestampMixin, Base):
    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint(
            "reporting_basis_default IN ('consolidated', 'separate', 'unknown')",
            name="ck_companies_reporting_basis",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_company_id: Mapped[str | None] = mapped_column(String(40))
    data_source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), nullable=False)
    accounting_standard: Mapped[str | None] = mapped_column(String(30))
    reporting_basis_default: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown", server_default=text("'unknown'")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    company_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class CompanySector(Base):
    __tablename__ = "company_sectors"
    __table_args__ = (
        UniqueConstraint("company_id", "sector_id", "valid_from", name="uq_company_sector_valid_from"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    sector_id: Mapped[int] = mapped_column(ForeignKey("sectors.id"), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)


class FinancialPeriod(Base):
    __tablename__ = "financial_periods"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "fiscal_year", "period_type", "period_sequence",
            name="uq_financial_period_natural_key",
        ),
        CheckConstraint("period_type IN ('Q1', 'Q2', 'Q3', 'FY')", name="ck_financial_period_type"),
        CheckConstraint("period_sequence BETWEEN 1 AND 4", name="ck_financial_period_sequence"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    calendar_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)
    period_sequence: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_ytd: Mapped[bool] = mapped_column(Boolean, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    instant_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_period_code: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(40), nullable=False)


class TaxonomyVersion(Base):
    __tablename__ = "taxonomy_versions"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_taxonomy_code_version"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    namespace: Mapped[str] = mapped_column(Text, nullable=False)
    entry_points: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    source_url: Mapped[str | None] = mapped_column(Text)


class FinancialDocument(Base):
    __tablename__ = "financial_documents"
    __table_args__ = (
        UniqueConstraint(
            "data_source_id", "source_document_id", "file_type", "file_role",
            name="uq_financial_document_natural_key",
        ),
        CheckConstraint(
            "file_type IN ('.xlsx', '.pdf', '.zip', '.xbrl', '.html')",
            name="ck_financial_document_file_type",
        ),
        CheckConstraint(
            "file_role IN ('instance_xbrl', 'inline_xbrl', 'spreadsheet', 'pdf', 'annual_report', 'other')",
            name="ck_financial_document_file_role",
        ),
        CheckConstraint(
            "parse_status IN ('pending', 'parsed', 'warning', 'failed', 'skipped')",
            name="ck_financial_document_parse_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    data_source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), nullable=False)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    period_id: Mapped[int] = mapped_column(ForeignKey("financial_periods.id"), nullable=False)
    ingestion_job_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_jobs.id"))
    source_document_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_file_id: Mapped[str | None] = mapped_column(Text)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(String(12), nullable=False)
    file_role: Mapped[str] = mapped_column(String(20), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    raw_storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    source_file_size: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    parse_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default=text("'pending'")
    )
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    document_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    superseded_by: Mapped[int | None] = mapped_column(ForeignKey("financial_documents.id"))
    filing_date: Mapped[date | None] = mapped_column(Date)
    reporting_basis: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown", server_default=text("'unknown'"))
    version_status: Mapped[str] = mapped_column(String(20), nullable=False, default="current", server_default=text("'current'"))


class DocumentAttachment(Base):
    __tablename__ = "document_attachments"
    __table_args__ = (
        UniqueConstraint("financial_document_id", "source_file_id", name="uq_document_attachment"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    financial_document_id: Mapped[int] = mapped_column(ForeignKey("financial_documents.id"), nullable=False)
    source_file_id: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(String(12), nullable=False)
    extracted_path: Mapped[str | None] = mapped_column(Text)


class FinancialAccount(Base):
    __tablename__ = "financial_accounts"
    __table_args__ = (
        UniqueConstraint("taxonomy_version_id", "concept_code", name="uq_financial_account_concept"),
        CheckConstraint(
            "statement_type IN ('balance_sheet', 'income_statement', 'cash_flow', 'equity', "
            "'comprehensive_income', 'notes', 'dei', 'unknown')",
            name="ck_financial_account_statement",
        ),
        CheckConstraint("normal_sign IN (-1, 0, 1)", name="ck_financial_account_normal_sign"),
        CheckConstraint(
            "data_type IN ('monetary', 'shares', 'per_share', 'percentage', 'text', 'boolean')",
            name="ck_financial_account_data_type",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    taxonomy_version_id: Mapped[int] = mapped_column(ForeignKey("taxonomy_versions.id"), nullable=False)
    concept_code: Mapped[str] = mapped_column(String(120), nullable=False)
    concept_qname: Mapped[str] = mapped_column(String(180), nullable=False)
    namespace: Mapped[str] = mapped_column(Text, nullable=False)
    label_id: Mapped[str | None] = mapped_column(Text)
    label_en: Mapped[str | None] = mapped_column(Text)
    statement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    normal_sign: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, server_default=text("1"))
    data_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="monetary", server_default=text("'monetary'")
    )
    unit_hint: Mapped[str | None] = mapped_column(String(50))
    parent_account_id: Mapped[int | None] = mapped_column(ForeignKey("financial_accounts.id"))
    is_abstract: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))


class AccountAlias(Base):
    __tablename__ = "account_aliases"
    __table_args__ = (
        UniqueConstraint("account_id", "alias", "locale", "source", name="uq_account_alias"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("financial_accounts.id"), nullable=False)
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="id", server_default=text("'id'"))
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="idx", server_default=text("'idx'"))


class StandardAccount(Base):
    __tablename__ = "standard_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    statement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    data_type: Mapped[str] = mapped_column(String(20), nullable=False, default="monetary", server_default=text("'monetary'"))
    unit_hint: Mapped[str | None] = mapped_column(String(50))
    normal_sign: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, server_default=text("1"))
    industry_scope: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class AccountMappingRule(Base):
    __tablename__ = "account_mapping_rules"
    __table_args__ = (
        UniqueConstraint("rule_code", "version", name="uq_account_mapping_rule_version"),
        CheckConstraint(
            "status IN ('unmapped', 'suggested', 'review_required', 'approved', 'rejected', 'superseded')",
            name="ck_account_mapping_rule_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    rule_code: Mapped[str] = mapped_column(String(60), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    source_taxonomy_code: Mapped[str | None] = mapped_column(String(40))
    source_concept_qname: Mapped[str | None] = mapped_column(String(180))
    industry: Mapped[str | None] = mapped_column(String(50))
    statement_type: Mapped[str | None] = mapped_column(String(30))
    source_name: Mapped[str | None] = mapped_column(Text)
    standard_account_id: Mapped[int] = mapped_column(ForeignKey("standard_accounts.id"), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("1"), server_default=text("1.0000"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="suggested", server_default=text("'suggested'"))
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SourceAccountMapping(Base):
    __tablename__ = "source_account_mappings"
    __table_args__ = (
        Index("idx_source_account_mapping_lookup", "source_account_name", "industry", "is_current"),
        CheckConstraint(
            "status IN ('unmapped', 'suggested', 'review_required', 'approved', 'rejected', 'superseded')",
            name="ck_source_account_mapping_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"))
    taxonomy_version_id: Mapped[int | None] = mapped_column(ForeignKey("taxonomy_versions.id"))
    source_account_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_taxonomy_concept: Mapped[str | None] = mapped_column(String(180))
    industry: Mapped[str | None] = mapped_column(String(50))
    statement_type: Mapped[str | None] = mapped_column(String(30))
    standard_account_id: Mapped[int | None] = mapped_column(ForeignKey("standard_accounts.id"))
    rule_code: Mapped[str | None] = mapped_column(String(60))
    rule_version: Mapped[str | None] = mapped_column(String(20))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("1"), server_default=text("1.0000"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unmapped", server_default=text("'unmapped'"))
    evidence: Mapped[str | None] = mapped_column(Text)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    superseded_by: Mapped[int | None] = mapped_column(ForeignKey("source_account_mappings.id"))
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FinancialFact(Base):
    __tablename__ = "financial_facts"
    __table_args__ = (
        UniqueConstraint("document_id", "source_fact_id", "fact_version", name="uq_financial_fact_version"),
        CheckConstraint(
            "reporting_basis IN ('consolidated', 'separate', 'unknown')",
            name="ck_financial_fact_reporting_basis",
        ),
        CheckConstraint(
            "validation_status IN ('pending', 'passed', 'warning', 'failed', 'overridden')",
            name="ck_financial_fact_validation_status",
        ),
        Index(
            "idx_facts_current",
            "company_id",
            "period_id",
            "account_id",
            postgresql_where=text("is_current IS TRUE"),
        ),
        Index("idx_facts_document", "document_id"),
        Index("idx_facts_publication", "company_id", "period_id", "reporting_basis", "publication_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    period_id: Mapped[int] = mapped_column(ForeignKey("financial_periods.id"), nullable=False)
    document_id: Mapped[int] = mapped_column(ForeignKey("financial_documents.id"), nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("financial_accounts.id"), nullable=False)
    ingestion_job_id: Mapped[int] = mapped_column(ForeignKey("ingestion_jobs.id"), nullable=False)
    source_fact_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_context_ref: Mapped[str] = mapped_column(Text, nullable=False)
    context_start_date: Mapped[date | None] = mapped_column(Date)
    context_end_date: Mapped[date | None] = mapped_column(Date)
    context_instant_date: Mapped[date | None] = mapped_column(Date)
    value_original: Mapped[str] = mapped_column(Text, nullable=False)
    value_normalized: Mapped[Decimal] = mapped_column(Numeric(38, 10), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(3))
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    source_scale: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    source_decimals: Mapped[str | None] = mapped_column(String(10))
    reporting_basis: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown", server_default=text("'unknown'")
    )
    is_restated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    fact_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    superseded_by: Mapped[int | None] = mapped_column(ForeignKey("financial_facts.id"))
    validation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default=text("'pending'")
    )
    period_kind: Mapped[str] = mapped_column(String(12), nullable=False, default="duration", server_default=text("'duration'"))
    duration_kind: Mapped[str] = mapped_column(String(20), nullable=False, default="full_year", server_default=text("'full_year'"))
    accounting_definition_key: Mapped[str] = mapped_column(
        String(80), nullable=False, default="legacy", server_default=text("'legacy'")
    )
    document_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    publication_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default=text("'draft'")
    )
    mapping_id: Mapped[int | None] = mapped_column(ForeignKey("source_account_mappings.id"))
    is_derived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    source_context_details: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_metric_definition_version"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    formula: Mapped[dict] = mapped_column(JSONB, nullable=False)
    dependencies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    applicable_entry_points: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class FinancialMetric(Base):
    __tablename__ = "financial_metrics"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "period_id", "metric_definition_id", "is_current", "computed_at",
            name="uq_financial_metric_version",
        ),
        CheckConstraint(
            "status IN ('draft', 'validated', 'published', 'rejected')",
            name="ck_financial_metric_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    period_id: Mapped[int] = mapped_column(ForeignKey("financial_periods.id"), nullable=False)
    metric_definition_id: Mapped[int] = mapped_column(ForeignKey("metric_definitions.id"), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    source_fact_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    formula_version: Mapped[str] = mapped_column(String(20), nullable=False)
    is_derived_from_ytd: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default=text("'draft'"))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reporting_basis: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown", server_default=text("'unknown'"))
    currency: Mapped[str | None] = mapped_column(String(3))
    calculation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="calculated", server_default=text("'calculated'")
    )
    unavailable_reason: Mapped[str | None] = mapped_column(Text)
    validation_warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    input_document_versions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    formula_definition: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    publication_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default=text("'draft'")
    )


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'downloaded', 'parsed', 'validated', 'failed', 'cancelled')",
            name="ck_ingestion_job_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"))
    period_id: Mapped[int | None] = mapped_column(ForeignKey("financial_periods.id"))
    job_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default=text("'pending'"))
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ValidationLog(Base):
    __tablename__ = "validation_logs"
    __table_args__ = (
        CheckConstraint("severity IN ('error', 'warning', 'info')", name="ck_validation_log_severity"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    rule_code: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    expected_value: Mapped[str | None] = mapped_column(Text)
    actual_value: Mapped[str | None] = mapped_column(Text)
    override_reason: Mapped[str | None] = mapped_column(Text)
    log_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    severity_level: Mapped[str] = mapped_column(String(10), nullable=False, default="INFO", server_default=text("'INFO'"))
    rule_category: Mapped[str] = mapped_column(String(30), nullable=False, default="other", server_default=text("'other'"))
    is_blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    validation_run_id: Mapped[int | None] = mapped_column(ForeignKey("validation_runs.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", server_default=text("'open'"))
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_policy: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    before_state: Mapped[dict | None] = mapped_column(JSONB)
    after_state: Mapped[dict | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    request_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), primary_key=True)


class ValidationRun(Base):
    __tablename__ = "validation_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'validation_failed', 'review_required', 'validated', 'published', 'superseded')",
            name="ck_validation_run_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default=text("'pending'"))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DerivedValue(Base):
    __tablename__ = "derived_values"
    __table_args__ = (
        Index("idx_derived_values_scope", "company_id", "period_id", "reporting_basis"),
        CheckConstraint(
            "status IN ('derived', 'review_required', 'unavailable', 'invalid')",
            name="ck_derived_value_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    period_id: Mapped[int] = mapped_column(ForeignKey("financial_periods.id"), nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("financial_accounts.id"), nullable=False)
    reporting_basis: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(3))
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(38, 10))
    formula_code: Mapped[str] = mapped_column(String(60), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="derived", server_default=text("'derived'"))
    unavailable_reason: Mapped[str | None] = mapped_column(Text)
    validation_warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    source_context_details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DerivedValueInput(Base):
    __tablename__ = "derived_value_inputs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    derived_value_id: Mapped[int] = mapped_column(ForeignKey("derived_values.id"), nullable=False)
    input_fact_id: Mapped[int] = mapped_column(ForeignKey("financial_facts.id"), nullable=False)
    input_period_id: Mapped[int] = mapped_column(ForeignKey("financial_periods.id"), nullable=False)
    input_document_id: Mapped[int] = mapped_column(ForeignKey("financial_documents.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    sequence: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, server_default=text("1"))


class FinancialMetricInput(Base):
    __tablename__ = "financial_metric_inputs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    financial_metric_id: Mapped[int] = mapped_column(ForeignKey("financial_metrics.id"), nullable=False)
    input_fact_id: Mapped[int | None] = mapped_column(ForeignKey("financial_facts.id"))
    derived_value_id: Mapped[int | None] = mapped_column(ForeignKey("derived_values.id"))
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    sequence: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, server_default=text("1"))


class FactRevision(Base):
    __tablename__ = "fact_revisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    predecessor_fact_id: Mapped[int] = mapped_column(ForeignKey("financial_facts.id"), nullable=False)
    successor_fact_id: Mapped[int] = mapped_column(ForeignKey("financial_facts.id"), nullable=False)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    period_id: Mapped[int] = mapped_column(ForeignKey("financial_periods.id"), nullable=False)
    document_id: Mapped[int] = mapped_column(ForeignKey("financial_documents.id"), nullable=False)
    revision_reason: Mapped[str] = mapped_column(Text, nullable=False)
    filing_date: Mapped[date | None] = mapped_column(Date)
    document_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default=text("'pending'"))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PublicationEvent(Base):
    __tablename__ = "publication_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    period_id: Mapped[int] = mapped_column(ForeignKey("financial_periods.id"), nullable=False)
    reporting_basis: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="published", server_default=text("'published'"))
    validation_run_id: Mapped[int | None] = mapped_column(ForeignKey("validation_runs.id"))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    previous_event_id: Mapped[int | None] = mapped_column(ForeignKey("publication_events.id"))
    publication_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
