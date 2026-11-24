# Financial Data Pipeline

**Status:** Phase 2, milestone M2.
**Scope:** Controlled path from local source documents to published, source-backed financial views.

## Pipeline stages

1. **Source registration**
   - Local BBCA FY2025 fixture files are verified by size and SHA-256.
   - Live IDX access remains disabled in the default runner; no new IDX request is issued by M2.
   - `financial_documents` stores source identifiers, file role, checksum, file size, source URL, parse status, document version, and reporting basis.

2. **Parsing and extraction**
   - XBRL instance, inline XBRL, XLSX, and PDF parsers produce the same 12/12 POC fact set.
   - Original values, scale, decimals, currency, unit, source fact ID, context ID, and context dates are preserved.
   - Values are normalized to absolute IDR; EPS remains `IDRPerShares` with no currency.

3. **Account normalization**
   - `ensure_reference_data` seeds standard accounts, approved taxonomy rules, and reviewed source-name rules for unambiguous captions.
   - `AccountNormalizer.resolve` prefers exact taxonomy/concept evidence, then reviewed rule name/industry/statement evidence; ambiguous captions such as generic quick assets or total debt remain `review_required`.
   - Unknown or ambiguous accounts receive `unmapped` or `review_required` and cannot publish automatically.
   - Source account names are preserved on every mapping row.
   - Current facts created before M2 are idempotently backfilled with mapping references, period kind, duration kind, and context details without changing values.

4. **Period and context interpretation**
   - Fact contexts are classified as `instant` or `duration`.
   - Duration facts carry `duration_kind` (`full_year`, `ytd`, `standalone`, or `unknown`).
   - Standalone quarters are derived only from compatible YTD/full-year inputs with the same company, account, basis, currency, unit, scale, accounting definition, and document version.
   - Unsupported or incompatible derivations become `unavailable` or `review_required` with explicit reasons.

5. **Reporting-basis integrity**
   - Every fact carries `consolidated`, `separate`, or `unknown`.
   - Statement reads and validation scopes require an explicit basis.
   - Mixed-basis or unknown-basis fact populations block publication.

6. **Restatement handling**
   - Re-ingestion creates successor facts and `fact_revisions` when values change.
   - Prior facts remain queryable as historical versions.
   - `resolve_facts` selects current facts by default or the highest document version at `as_of`.

7. **Metric calculation**
   - `metric_definitions` are seeded from versioned `m2-v1` specs.
   - Input collection selects duration and instant facts by standard role, reporting date, opening/closing boundary, basis, and approved mapping; duplicated candidates are resolved deterministically by period alignment, document version, fact version, and fact ID.
   - The calculator records inputs, formula definition, formula version, warnings, calculation status, and unavailable reasons.
   - Non-finite values, scale/role-kind mismatches, zero denominators, missing inputs, negative balances, incompatible periods, mixed basis, and mixed units are explicit outcomes.
   - Free cash flow uses positive capital expenditure; negative-source sign conventions require an auditable normalization or return `NEGATIVE_CAPITAL_EXPENDITURE_UNSUPPORTED_SIGN`.
   - Distinct leverage definitions prevent interest-bearing debt from being conflated with total liabilities.

8. **Validation and review**
   - `evaluate_scope` creates a `validation_run`, writes severity/category-aware `validation_logs`, and returns a publish decision.
   - Reviewers may acknowledge warning findings; errors and blockers cannot be overridden.
   - Restatement approvals and mapping approvals write audit events.

9. **Publication**
   - `publish_scope` re-runs validation immediately before publication.
   - Publication marks current facts and metrics as published and creates a `publication_event`.
   - Republishing supersedes the previous event without mutating historical facts.
   - Statement reads with `visibility=published` require an active publication event and filter to published facts.

## API entry points

- `GET /api/v1/statements/{ticker}` with `visibility=draft|published` and optional `as_of`.
- `GET/POST /api/v1/normalization/mappings`, `/periods/derive`, `/metrics`, `/metrics/recalculate`.
- `POST /api/v1/validation/run`, `GET /api/v1/validation/logs`.
- `GET /api/v1/restatements`, `POST /api/v1/restatements/{id}/approve`.
- `POST /api/v1/publication/publish`, `GET /api/v1/publication/events`.
- `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`.
- `GET /api/v1/audit/events`.

## Local user seeding

```bash
M2_ADMIN_PASSWORD='local-admin-password' \
M2_ANALYST_PASSWORD='local-analyst-password' \
docker compose exec -e M2_ADMIN_PASSWORD -e M2_ANALYST_PASSWORD api \
python -m app.cli.seed_users
```
