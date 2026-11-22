import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d4e7b9c1a2f3"
down_revision = "a70b95fcb2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "standard_accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("code", sa.String(80), nullable=False, unique=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("statement_type", sa.String(30), nullable=False),
        sa.Column("data_type", sa.String(20), nullable=False, server_default="monetary"),
        sa.Column("unit_hint", sa.String(50)),
        sa.Column("normal_sign", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("industry_scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "account_mapping_rules",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("rule_code", sa.String(60), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("source_taxonomy_code", sa.String(40)),
        sa.Column("source_concept_qname", sa.String(180)),
        sa.Column("industry", sa.String(50)),
        sa.Column("statement_type", sa.String(30)),
        sa.Column("source_name", sa.Text()),
        sa.Column("standard_account_id", sa.BigInteger(), sa.ForeignKey("standard_accounts.id"), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="1.0000"),
        sa.Column("status", sa.String(20), nullable=False, server_default="suggested"),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("rule_code", "version", name="uq_account_mapping_rule_version"),
        sa.CheckConstraint(
            "status IN ('unmapped', 'suggested', 'review_required', 'approved', 'rejected', 'superseded')",
            name="ck_account_mapping_rule_status",
        ),
    )

    op.create_table(
        "source_account_mappings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id")),
        sa.Column("taxonomy_version_id", sa.BigInteger(), sa.ForeignKey("taxonomy_versions.id")),
        sa.Column("source_account_name", sa.Text(), nullable=False),
        sa.Column("source_taxonomy_concept", sa.String(180)),
        sa.Column("industry", sa.String(50)),
        sa.Column("statement_type", sa.String(30)),
        sa.Column("standard_account_id", sa.BigInteger(), sa.ForeignKey("standard_accounts.id")),
        sa.Column("rule_code", sa.String(60)),
        sa.Column("rule_version", sa.String(20)),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="1.0000"),
        sa.Column("status", sa.String(20), nullable=False, server_default="unmapped"),
        sa.Column("evidence", sa.Text()),
        sa.Column("approved_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("superseded_by", sa.BigInteger(), sa.ForeignKey("source_account_mappings.id")),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('unmapped', 'suggested', 'review_required', 'approved', 'rejected', 'superseded')",
            name="ck_source_account_mapping_status",
        ),
    )
    op.create_index("idx_source_account_mapping_lookup", "source_account_mappings", ["source_account_name", "industry", "is_current"])

    op.create_table(
        "validation_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("scope_type", sa.String(40), nullable=False),
        sa.Column("scope_id", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("actor_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'validation_failed', 'review_required', 'validated', 'published', 'superseded')",
            name="ck_validation_run_status",
        ),
    )

    op.create_table(
        "derived_values",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("period_id", sa.BigInteger(), sa.ForeignKey("financial_periods.id"), nullable=False),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("financial_accounts.id"), nullable=False),
        sa.Column("reporting_basis", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(3)),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("value", sa.Numeric(38, 10)),
        sa.Column("formula_code", sa.String(60), nullable=False),
        sa.Column("formula_version", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="derived"),
        sa.Column("unavailable_reason", sa.Text()),
        sa.Column("validation_warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_context_details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('derived', 'review_required', 'unavailable', 'invalid')",
            name="ck_derived_value_status",
        ),
    )
    op.create_index("idx_derived_values_scope", "derived_values", ["company_id", "period_id", "reporting_basis"])

    op.create_table(
        "derived_value_inputs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("derived_value_id", sa.BigInteger(), sa.ForeignKey("derived_values.id"), nullable=False),
        sa.Column("input_fact_id", sa.BigInteger(), sa.ForeignKey("financial_facts.id"), nullable=False),
        sa.Column("input_period_id", sa.BigInteger(), sa.ForeignKey("financial_periods.id"), nullable=False),
        sa.Column("input_document_id", sa.BigInteger(), sa.ForeignKey("financial_documents.id"), nullable=False),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("sequence", sa.SmallInteger(), nullable=False, server_default="1"),
    )

    op.create_table(
        "financial_metric_inputs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("financial_metric_id", sa.BigInteger(), sa.ForeignKey("financial_metrics.id"), nullable=False),
        sa.Column("input_fact_id", sa.BigInteger(), sa.ForeignKey("financial_facts.id")),
        sa.Column("derived_value_id", sa.BigInteger(), sa.ForeignKey("derived_values.id")),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("sequence", sa.SmallInteger(), nullable=False, server_default="1"),
    )

    op.create_table(
        "fact_revisions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("predecessor_fact_id", sa.BigInteger(), sa.ForeignKey("financial_facts.id"), nullable=False),
        sa.Column("successor_fact_id", sa.BigInteger(), sa.ForeignKey("financial_facts.id"), nullable=False),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("period_id", sa.BigInteger(), sa.ForeignKey("financial_periods.id"), nullable=False),
        sa.Column("document_id", sa.BigInteger(), sa.ForeignKey("financial_documents.id"), nullable=False),
        sa.Column("revision_reason", sa.Text(), nullable=False),
        sa.Column("filing_date", sa.Date()),
        sa.Column("document_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("actor_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "publication_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("period_id", sa.BigInteger(), sa.ForeignKey("financial_periods.id"), nullable=False),
        sa.Column("reporting_basis", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="published"),
        sa.Column("validation_run_id", sa.BigInteger(), sa.ForeignKey("validation_runs.id")),
        sa.Column("actor_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("previous_event_id", sa.BigInteger(), sa.ForeignKey("publication_events.id")),
        sa.Column("publication_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("request_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_auth_sessions_user", "auth_sessions", ["user_id"])

    op.add_column("financial_documents", sa.Column("document_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("financial_documents", sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("financial_documents", sa.Column("superseded_by", sa.BigInteger(), sa.ForeignKey("financial_documents.id")))
    op.add_column("financial_documents", sa.Column("filing_date", sa.Date()))
    op.add_column("financial_documents", sa.Column("reporting_basis", sa.String(20), nullable=False, server_default="unknown"))
    op.add_column("financial_documents", sa.Column("version_status", sa.String(20), nullable=False, server_default="current"))

    op.add_column("financial_facts", sa.Column("period_kind", sa.String(12), nullable=False, server_default="duration"))
    op.add_column("financial_facts", sa.Column("duration_kind", sa.String(20), nullable=False, server_default="full_year"))
    op.add_column("financial_facts", sa.Column("accounting_definition_key", sa.String(80), nullable=False, server_default="legacy"))
    op.add_column("financial_facts", sa.Column("document_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("financial_facts", sa.Column("publication_status", sa.String(20), nullable=False, server_default="draft"))
    op.add_column("financial_facts", sa.Column("mapping_id", sa.BigInteger(), sa.ForeignKey("source_account_mappings.id")))
    op.add_column("financial_facts", sa.Column("is_derived", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("financial_facts", sa.Column("source_context_details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.create_index("idx_facts_publication", "financial_facts", ["company_id", "period_id", "reporting_basis", "publication_status"])

    op.alter_column("financial_metrics", "value", existing_type=sa.Numeric(38, 10), nullable=True)
    op.add_column("financial_metrics", sa.Column("reporting_basis", sa.String(20), nullable=False, server_default="unknown"))
    op.add_column("financial_metrics", sa.Column("currency", sa.String(3)))
    op.add_column("financial_metrics", sa.Column("calculation_status", sa.String(20), nullable=False, server_default="calculated"))
    op.add_column("financial_metrics", sa.Column("unavailable_reason", sa.Text()))
    op.add_column("financial_metrics", sa.Column("validation_warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("financial_metrics", sa.Column("input_document_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("financial_metrics", sa.Column("formula_definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("financial_metrics", sa.Column("publication_status", sa.String(20), nullable=False, server_default="draft"))

    op.add_column("validation_logs", sa.Column("severity_level", sa.String(10), nullable=False, server_default="INFO"))
    op.add_column("validation_logs", sa.Column("rule_category", sa.String(30), nullable=False, server_default="other"))
    op.add_column("validation_logs", sa.Column("is_blocking", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("validation_logs", sa.Column("validation_run_id", sa.BigInteger(), sa.ForeignKey("validation_runs.id")))
    op.add_column("validation_logs", sa.Column("status", sa.String(20), nullable=False, server_default="open"))
    op.add_column("validation_logs", sa.Column("resolved_by", sa.BigInteger(), sa.ForeignKey("users.id")))
    op.add_column("validation_logs", sa.Column("resolved_at", sa.DateTime(timezone=True)))
    op.add_column("validation_logs", sa.Column("review_policy", sa.Text()))

    op.add_column("audit_events", sa.Column("request_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))

    op.execute(
        sa.text(
            "INSERT INTO roles (name, description) VALUES "
            "('viewer', 'May view published and draft/internal data'), "
            "('analyst', 'May ingest data and calculate metrics'), "
            "('reviewer', 'May review mappings and validation issues'), "
            "('publisher', 'May publish validated data'), "
            "('admin', 'Full application administration') "
            "ON CONFLICT (name) DO NOTHING"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM roles WHERE name IN ('viewer', 'analyst', 'reviewer', 'publisher', 'admin')"))
    op.drop_column("audit_events", "request_context")
    op.drop_column("validation_logs", "review_policy")
    op.drop_column("validation_logs", "resolved_at")
    op.drop_column("validation_logs", "resolved_by")
    op.drop_column("validation_logs", "status")
    op.drop_column("validation_logs", "validation_run_id")
    op.drop_column("validation_logs", "is_blocking")
    op.drop_column("validation_logs", "rule_category")
    op.drop_column("validation_logs", "severity_level")
    op.drop_column("financial_metrics", "publication_status")
    op.drop_column("financial_metrics", "formula_definition")
    op.drop_column("financial_metrics", "input_document_versions")
    op.drop_column("financial_metrics", "validation_warnings")
    op.drop_column("financial_metrics", "unavailable_reason")
    op.drop_column("financial_metrics", "calculation_status")
    op.drop_column("financial_metrics", "currency")
    op.drop_column("financial_metrics", "reporting_basis")
    op.alter_column("financial_metrics", "value", existing_type=sa.Numeric(38, 10), nullable=False)
    op.drop_index("idx_facts_publication", table_name="financial_facts")
    op.drop_column("financial_facts", "source_context_details")
    op.drop_column("financial_facts", "is_derived")
    op.drop_column("financial_facts", "mapping_id")
    op.drop_column("financial_facts", "publication_status")
    op.drop_column("financial_facts", "document_version")
    op.drop_column("financial_facts", "accounting_definition_key")
    op.drop_column("financial_facts", "duration_kind")
    op.drop_column("financial_facts", "period_kind")
    op.drop_column("financial_documents", "version_status")
    op.drop_column("financial_documents", "reporting_basis")
    op.drop_column("financial_documents", "filing_date")
    op.drop_column("financial_documents", "superseded_by")
    op.drop_column("financial_documents", "is_current")
    op.drop_column("financial_documents", "document_version")
    op.drop_index("idx_auth_sessions_user", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("publication_events")
    op.drop_table("fact_revisions")
    op.drop_table("financial_metric_inputs")
    op.drop_table("derived_value_inputs")
    op.drop_index("idx_derived_values_scope", table_name="derived_values")
    op.drop_table("derived_values")
    op.drop_table("validation_runs")
    op.drop_index("idx_source_account_mapping_lookup", table_name="source_account_mappings")
    op.drop_table("source_account_mappings")
    op.drop_table("account_mapping_rules")
    op.drop_table("standard_accounts")
