# Database Schema

**Status:** Phase 2, milestone M2.
**Scope:** M1 baseline plus additive M2 normalization, trust, calculation, and publication structures.

## Migration baseline

- M1 head: `a70b95fcb2e3`.
- M2 head: `d4e7b9c1a2f3`, revision file `backend/migrations/versions/d4e7b9c1a2f3_m2_normalization_trust.py`.
- Upgrade only. No M2 table is dropped, truncated, or rewritten in place.
- Existing M1 rows remain valid through additive columns with non-null defaults.

## M1 core tables

- `data_sources`, `companies`, `sectors`, `company_sectors`, `financial_periods`.
- `taxonomy_versions`, `financial_accounts`, `account_aliases`.
- `financial_documents`, `document_attachments`.
- `financial_facts` with source fact/context identifiers, context dates, original and normalized values, currency, unit, scale, decimals, reporting basis, fact version, current/superseded flags, and validation status.
- `metric_definitions`, `financial_metrics`.
- `ingestion_jobs`, `validation_logs`, `audit_events`.
- `roles`, `users`, `user_roles`.

## M2 tables

| Table | Purpose |
| --- | --- |
| `standard_accounts` | Stable internal account catalog with statement type, data type, normal sign, industry scope, definition, and active flag. |
| `account_mapping_rules` | Versioned source-to-standard rules with taxonomy, concept, industry, statement, source name, confidence, status, evidence, and approval metadata. |
| `source_account_mappings` | Per-source/company mapping decisions with confidence, status, current/superseded chain, approver, and evidence. |
| `validation_runs` | Grouped validation execution with scope, status, actor, summary, started time, and finished time. |
| `derived_values` | Derived period values with formula code/version, value, unavailable reason, warnings, context provenance, and creator. |
| `derived_value_inputs` | Role-ordered source facts, periods, and documents feeding each derived value. |
| `financial_metric_inputs` | Role-ordered facts or derived values feeding each metric computation. |
| `fact_revisions` | Predecessor/successor fact chain with reason, filing date, document version, approval status, actor, and metadata. |
| `publication_events` | Published scope snapshots with validation run, actor, previous event, status, and metadata. |
| `auth_sessions` | Hashed bearer tokens with expiry, revocation, request context, and creation time. |

## M2 columns added to existing tables

- `financial_documents`: `document_version`, `is_current`, `superseded_by`, `filing_date`, `reporting_basis`, `version_status`.
- `financial_facts`: `period_kind`, `duration_kind`, `accounting_definition_key`, `document_version`, `publication_status`, `mapping_id`, `is_derived`, `source_context_details`; index `idx_facts_publication`.
- `financial_metrics`: `reporting_basis`, `currency`, `calculation_status`, `unavailable_reason`, `validation_warnings`, `input_document_versions`, `formula_definition`, `publication_status`; `value` is nullable.
- `validation_logs`: `severity_level`, `rule_category`, `is_blocking`, `validation_run_id`, `status`, `resolved_by`, `resolved_at`, `review_policy`.
- `audit_events`: `request_context`.

## Roles

Seeded idempotently: `viewer`, `analyst`, `reviewer`, `publisher`, `admin`.

## Integrity rules

- Existing natural keys and check constraints are preserved.
- New facts are created as successors; prior facts are marked `is_current=false` and linked through `superseded_by` instead of being overwritten.
- Derived values and metrics store formula versions and input references.
- Publication status is stored per fact and metric and linked to a `publication_event`.
- Passwords are PBKDF2-SHA256 hashes; bearer tokens are stored only as SHA-256 hashes.
