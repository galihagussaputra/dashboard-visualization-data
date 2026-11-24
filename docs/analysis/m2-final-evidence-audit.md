# M2 Final Evidence Audit

**Date:** 2026-11-24  
**Branch:** `main`  
**HEAD:** `dbedd1200cf30376c773b5c2d8ae576b092c0fa4`  
**Audit mode:** read-only verification; only this report may be added.

## 1. Audit scope and method

- Objective: decide whether Phase 2 milestone M2 can be promoted from `CONDITIONAL PASS` to `PASS`.
- Scope: M2 metric engine, period derivation, restatement lifecycle, validation/publication trust controls, authentication/session behavior, frontend evidence surfaces, migration state, and regression suite.
- Method: static source/test inspection plus executable lint, test, build, and Alembic checks.
- Evidence labels:
  - `VERIFIED`: behavior is directly supported by code, tests, or command output.
  - `PARTIAL`: behavior exists but required lifecycle/test/provenance evidence is incomplete.
  - `NOT VERIFIED`: no direct executable or visual evidence was available.
  - `GAP`: implementation or evidence required for `PASS` is missing.
- Constraints observed:
  - No source, migration, dependency, existing test, or existing documentation changes.
  - No commit, push, reset, clean, stash, checkout, rebase, or history rewrite.
  - No `backend/venv` deletion/untracking; its 3463 tracked modifications were left untouched.
  - No Docker volume deletion, DB reset/truncation, destructive migration, downgrade, live IDX fetch, or publication of financial data.
  - The API container was started for regression checks; frontend commands were run in one-off containers because port `5173` was already allocated. No fixture data was published.

## 2. Verdict definitions and decision

- `PASS`: all required behavior is verified by executable evidence, migration state is current, and no unresolved High findings remain.
- `CONDITIONAL PASS`: core implementation and regression suite are green, but High or material Medium evidence gaps remain; not ready for production promotion.
- `FAIL`: required behavior is contradicted by code/tests or regression/migration checks fail.
- `NOT VERIFIED`: target could not be directly proven without unavailable tooling or prohibited/destructive actions.

**Decision: DO NOT PROMOTE. M2 remains `CONDITIONAL PASS`.**

Rationale: the regression suite, lint/build, and migration state are green, and M1 behavior is preserved. However, three unresolved High findings block `PASS`:

1. Runtime metric input collection omits several required instant balance-sheet inputs and taxonomy mappings, so most of the 11 metric definitions are not end-to-end exercisable from ingested data.
2. Restatement registration reuses the original document row instead of creating a distinct revised document version, leaving historic/as-of version evidence incomplete.
3. The publication/authorization API matrix lacks executable tests for the critical publisher, blocker/error, warning-acknowledgement, rollback, and audit-effect paths.

`FAIL` is not warranted because no required regression failed and the core flows are implemented. `PASS` is not warranted because High findings and several `NOT VERIFIED` areas remain.

## 3. Regression, migration, and preservation evidence

| Check | Command used | Result |
| --- | --- | --- |
| Backend lint | `docker compose exec api ruff check .` | PASS; no lint diagnostics. Environment warning only: `Cannot allocate memory (os error 12)`. |
| Backend tests | `docker compose exec api python -m pytest -q` | `53 passed, 5 warnings in 30.47s`. Warnings are SWIG/Arelle deprecation notices from `SwigPyPacked`, `SwigPyObject`, and `swigvarlink`. |
| Frontend lint | `docker compose run --rm frontend npm run lint` | PASS; only stale `baseline-browser-mapping` advisory. |
| Frontend build | `docker compose run --rm frontend npm run build` | PASS; Vite `v7.2.4`, `2261 modules transformed`, `dist/index.html 0.49 kB`, CSS `25.07 kB`, JS `293.32 kB`, built in `13.03s`. |
| Migration head | `docker compose exec api alembic current` | `d4e7b9c1a2f3 (head)`. |
| Migration history | `docker compose exec api alembic history` | `a70b95fcb2e3 -> d4e7b9c1a2f3 (head)`, `<base> -> a70b95fcb2e3, initial M1 schema`. |

Preservation evidence:

- Before this report was added, `git status --short --untracked-files=all -- . ':(exclude)backend/venv'` was empty.
- No live IDX request was issued during the audit.
- No publication event was created during the audit.
- No DB data, Docker volumes, or legacy tracked `backend/venv` files were modified by the audit.

## 4. Metric engine evidence

### 4.1 Formula registry — VERIFIED

`FORMULA_VERSION = "m2-v1"` is defined at `backend/app/metrics/definitions.py:3`; formula definitions are seeded into `MetricDefinition.formula` at `backend/app/metrics/calculator.py:49-77`. Operations are implemented as:

- `divide`: inputs[0] / inputs[1], `backend/app/metrics/calculator.py:129-137`
- `average_divide`: inputs[0] / ((inputs[1] + inputs[2]) / 2), `backend/app/metrics/calculator.py:138-146`
- `subtract`: inputs[0] - inputs[1], `backend/app/metrics/calculator.py:147-151`

| Code | Inputs | Operation / unit | Definition ref |
| --- | --- | --- | --- |
| `ROA` | `NET_INCOME`, `OPENING_TOTAL_ASSETS`, `CLOSING_TOTAL_ASSETS` | `average_divide` / ratio | `definitions.py:23-31` |
| `ROE` | `NET_INCOME`, `OPENING_EQUITY`, `CLOSING_EQUITY` | `average_divide` / ratio | `definitions.py:32-40` |
| `NET_PROFIT_MARGIN` | `NET_INCOME`, `REVENUE` | `divide` / ratio | `definitions.py:41-49` |
| `CURRENT_RATIO` | `CURRENT_ASSETS`, `CURRENT_LIABILITIES` | `divide` / ratio | `definitions.py:50-58` |
| `QUICK_RATIO` | `QUICK_ASSETS`, `CURRENT_LIABILITIES` | `divide` / ratio | `definitions.py:59-67` |
| `DEBT_TO_EQUITY_TOTAL_DEBT` | `TOTAL_DEBT`, `TOTAL_EQUITY` | `divide` / ratio | `definitions.py:68-76` |
| `LIABILITIES_TO_EQUITY` | `TOTAL_LIABILITIES`, `TOTAL_EQUITY` | `divide` / ratio | `definitions.py:77-85` |
| `DEBT_TO_ASSET` | `TOTAL_DEBT`, `TOTAL_ASSETS` | `divide` / ratio | `definitions.py:86-94` |
| `ASSET_TURNOVER` | `REVENUE`, `OPENING_TOTAL_ASSETS`, `CLOSING_TOTAL_ASSETS` | `average_divide` / ratio | `definitions.py:95-103` |
| `INVENTORY_TURNOVER` | `COST_OF_GOODS_SOLD`, `OPENING_INVENTORY`, `CLOSING_INVENTORY` | `average_divide` / ratio | `definitions.py:104-112` |
| `FREE_CASH_FLOW` | `OPERATING_CASH_FLOW`, `CAPITAL_EXPENDITURE` | `subtract` / IDR | `definitions.py:113-121` |

### 4.2 Unit evidence — VERIFIED

`backend/tests/test_m2_metrics.py` covers:

- `test_average_balance_formulas:53-68`: ROA `0.1`, ROE `0.2`, ASSET_TURNOVER `0.5`.
- `test_binary_ratio_formulas:82-92`: NPM `0.2`, current `2`, quick `1`, debt/equity `0.5`, liabilities/equity `2`, debt/asset `0.25`.
- `test_inventory_turnover_and_free_cash_flow:95-109`: inventory turnover `2`, FCF `50` with unit IDR.
- `test_zero_denominator_is_unavailable_not_zero:112-122`: `unavailable`, `None`, `ZERO_DENOMINATOR`.
- `test_missing_input_is_unavailable:125-128`: `unavailable`, `MISSING_INPUTS`.
- `test_negative_values_are_calculated_with_warnings:131-151`: negative values preserved with warning codes.
- `test_incompatible_period_and_basis_and_unit_are_invalid:154-171`: explicit invalid reasons.
- `test_missing_average_balance_inputs_are_unavailable:174-177`.
- `test_formula_version_change_is_invalid:180-192`.
- `test_calculation_timestamp_is_recorded:195-205`.

### 4.3 Behavior and provenance — VERIFIED / PARTIAL

- Missing role input or `None` value becomes `unavailable` at `calculator.py:95-108`.
- Zero denominator and zero average balance become `unavailable` with explicit reasons at `calculator.py:131-132` and `:142-143`.
- Negative numerator, denominator, equity, average balance, and capex generate warnings but preserve sign at `calculator.py:125-136`, `:144-145`, `:149-151`.
- Invalid metric states are explicit at `calculator.py:90-93`, `:111-121`, `:152-155`.
- Computation carries source fact IDs, document versions, warnings, reason, timestamp, formula text/version at `calculator.py:157-176` and `:279-305`.
- Supersession and persistence are implemented at `calculator.py:190-239`; one `FinancialMetricInput` row is written per role.
- Recalculation is audited and committed at `backend/app/api/v1/trust.py:168-194`.
- “Normalized to absolute IDR” means scale normalization to whole IDR (`value × 10^source_scale`) at `backend/app/parsers/models.py:42-46`; it does not mean mathematical `abs()`. Signs are preserved.

### 4.4 Metrics gaps

- **HIGH:** runtime collection keeps instant facts only for `TOTAL_ASSETS`, `TOTAL_EQUITY`, and `INVENTORY` at `backend/app/metrics/service.py:140-147`. Required instant inputs `CURRENT_ASSETS`, `CURRENT_LIABILITIES`, `QUICK_ASSETS`, `TOTAL_DEBT`, and instant `TOTAL_LIABILITIES` are generally dropped.
- **HIGH:** deterministic taxonomy rules do not cover the missing roles, COGS, inventory, or capex at `backend/app/normalization/accounts.py:52-66`; `CAPITAL_EXPENDITURE` is seeded at `accounts.py:47` but lacks a concept mapping.
- **MEDIUM:** no finite-value guard exists; `Decimal("NaN")` can fail at the unguarded `< 0` check before the calculation `try` block at `calculator.py:125-128`.
- **MEDIUM:** divide/subtract compatibility only checks `period_id` and `duration_kind` at `calculator.py:258-263`; there is no explicit `period_kind` or balance-type check.
- **MEDIUM:** `persist_metric` uses `baseline = next(iter(inputs.values()))` at `calculator.py:201`, making reporting basis/currency fallback order-dependent, and does not verify definition version against computation version.
- **MEDIUM:** negative capex is only warned but still subtracted at `calculator.py:149-151`, conflicting with the positive-capex assumption in `definitions.py:120`.

## 5. Period derivation evidence

### 5.1 Classification and formulas — VERIFIED

- `classify_context` returns `instant` when only an instant date is present and rejects mixed instant/duration contexts at `backend/app/normalization/periods.py:49-57`.
- `duration` requires start and end dates and rejects inverted ranges at `periods.py:58-62`.
- Ingestion and validation use the classifier at `backend/app/ingestion/service.py:438-447` and `backend/app/validation/lifecycle.py:345-372`.
- Standalone quarter roles are Q1 `YTD_Q1`, Q2 `YTD_Q1,YTD_Q2`, Q3 `YTD_Q2,YTD_Q3`, Q4 `YTD_Q3,FY` at `periods.py:88-94`.
- Derived formulas are Q1 `YTD_Q1`, Q2 `YTD_Q2 - YTD_Q1`, Q3 `YTD_Q3 - YTD_Q2`, Q4 `FY - YTD_Q3` at `periods.py:199-205`.
- Guards cover unsupported sequence, missing roles, non-current inputs, validation status, period kind/YTD compatibility, dimension signature, duplicate context, restatement version mismatch, period order, and negative values at `periods.py:104-157` and `:186-209`.
- Provenance is written as `formula_code`, `formula_version`, `input_fact_ids`, `input_periods`, `input_document_versions`, `derived_at`, and source context details at `periods.py:178-185`, `:220-243`, and `backend/app/normalization/derivations.py:96-102`, `:246-256`.

### 5.2 Tests — VERIFIED

`backend/tests/test_m2_periods.py` covers:

| Test | Evidence |
| --- | --- |
| `test_classify_context_distinguishes_instant_and_duration:62-68` | Instant/duration accepted; mixed/inverted raise `ValueError`. |
| `test_normalize_duration_kind:71-74` | FY, YTD, standalone mapping. |
| `test_supported_standalone_quarter_derivations:77-100` | Q1 `120`, Q2 `150`, Q3 `140`, Q4 `130`; IDs/timestamps recorded. |
| `test_missing_q1_is_unavailable_not_zero:103-107` | `unavailable`, `None`, `MISSING_YTD_Q1`. |
| `test_incompatible_reporting_basis_blocks_derivation:110-119` | `BASIS_MISMATCH`. |
| `test_incompatible_currency_unit_and_scale_block_derivation:122-132` | Currency/unit/scale guards. |
| `test_restated_previous_period_requires_review:135-144` | `review_required`, `RESTATEMENT_VERSION_MISMATCH`. |
| `test_duplicate_source_context_blocks_derivation:147-156` | `DUPLICATE_SOURCE_CONTEXT`. |
| `test_negative_derived_value_is_preserved_with_warning:159-169` | Value `-50`, warning preserved. |
| `test_fiscal_year_and_annual_context_mismatches_block_derivation:172-189` | `FISCAL_YEAR_MISMATCH`, `PERIOD_KIND_MISMATCH`. |

### 5.3 Period gaps

- **MEDIUM:** derivation deduplication excludes document version and reason, so a changed restatement provenance with the same value can reuse a stale row at `derivations.py:209-226`.
- **MEDIUM:** derivation tests use synthetic `FactContext` inputs; no end-to-end API test proves real ingested context flow through Q2/Q3/Q4 derivation.
- **LOW:** dimension mismatch emits all reason codes indiscriminately at `periods.py:128-145`; duplicate fact ID is not checked.

## 6. Restatement lifecycle evidence

| Required step | Evidence | Status |
| --- | --- | --- |
| Original document registration | New `FinancialDocument` with v1/current defaults at `ingestion/service.py:337-365`; defaults at `models/entities.py:166-171`. | VERIFIED |
| Revised document registration | Existing row is updated in place at `ingestion/service.py:366-375`; no `document_version` increment, `is_current=False`, `superseded_by`, `filing_date`, or `version_status` transition. | GAP — HIGH |
| Predecessor fact retention | `is_current=False`, `superseded_by=successor.id`, prior validation preserved at `ingestion/service.py:504-507`. | VERIFIED |
| Successor fact creation | New fact with `fact_version=existing+1`, `is_restated=True`, `is_current=True` at `ingestion/service.py:471-503`. | VERIFIED |
| Revision record and approval | `FactRevision` created at `ingestion/service.py:508-521`; approval at `normalization/restatement.py:55-86` and `api/v1/trust.py:319-339`. | PARTIAL |
| Approval enforcement | No gate ties `FactRevision.approval_status` to fact usage, publication, validation, or metric recalculation at `restatement.py:98-127` and `publication.py:62-69`. | GAP — MEDIUM |
| Creation-time audit/recompute | Restatement creation writes no audit event and does not re-run validation/metrics at `ingestion/service.py:471-523`. | GAP — MEDIUM |
| As-of resolution | Highest eligible document version selected by filing/download date at `restatement.py:89-135`; exposed through `api/v1/statements.py:47` and `:76-83`. | PARTIAL |
| Distinct historic version in API | `document_version` appears in statement/restatement responses, but catalog `DocumentRead` omits version fields at `api/v1/catalog.py:35-53` and `api/v1/schemas.py:30-39`; no distinct v2 is reachable because revised documents are never registered. | GAP — HIGH |
| No dashboard rewrite / no fixture publication | Legacy dashboard isolated at `frontend/src/App.jsx:9-19`, `:32-46`; published read without event returned `404`; statement additions are additive at `api/v1/schemas.py:42-64`. | VERIFIED |

## 7. Validation and publication evidence

Role dependencies are `Analyst`, `Reviewer`, `Publisher`, and `Viewer` at `backend/app/api/v1/trust.py:44-47`; missing/invalid bearer yields `401` and insufficient role yields `403` at `backend/app/core/security.py:130-165`.

| Scenario | Implemented behavior | Executable test evidence |
| --- | --- | --- |
| Unauthenticated publish | `401` via bearer dependency at `security.py:135-139`; publish requires `Publisher` at `trust.py:346`. | NOT VERIFIED; no API test. |
| Analyst publish | `403`; `Analyst` set excludes publisher and `Publisher` dependency rejects it at `trust.py:44-47`, `:346`. | VERIFIED: `backend/tests/test_m2_api.py:87-95`. |
| Reviewer publish | `403`; `Reviewer` set excludes publisher at `trust.py:45-47`. | NOT VERIFIED; no API test. |
| Publisher, no blockers | `200 PublicationRead` at `trust.py:365-373`; facts/metrics marked published, prior event superseded, audit written at `publication.py:62-140`. | NOT VERIFIED; intentionally not executed to avoid publishing fixture data. |
| BLOCKER or ERROR | Both blocking at `validation/lifecycle.py:23`, `:49-51`; gate raises `422` at `publication.py:50-60`, endpoint rolls back at `trust.py:359-364`. | NOT VERIFIED; no API test. |
| Unacknowledged WARNING | Gate rejects at `publication.py:51-60`; acknowledgement requires Reviewer at `trust.py:266-289`. | NOT VERIFIED; no API test. |
| Publisher can_publish mismatch | `can_publish` ignores warnings with review policy at `lifecycle.py:62-63`, while publish rejects them at `publication.py:51-60`. | VERIFIED as code GAP — MEDIUM. |
| Published statement without active publication | `404` at `api/v1/statements.py:66-68`. | VERIFIED by prior manual QA; no dedicated M2 API test. |
| Validation run with findings | `200` with run/issues at `trust.py:217-253`; blockers do not cause validation endpoint failure. | VERIFIED broadly at `test_m2_api.py:72-84`. |

Publication DB effects are present in code: validation run/log creation at `validation/lifecycle.py:106-168`; fact and metric publication at `publication.py:62-91`; event supersession and metadata at `publication.py:93-123`; audit `publication.publish` at `publication.py:125-140`. These effects were not exercised by an executable success-path test in this audit.

## 8. Authentication and session evidence

| Control | Evidence | Status |
| --- | --- | --- |
| Password hashing | PBKDF2-SHA256, 16-byte salt, `120_000` iterations, constant-time verify at `security.py:17`, `:29-49`. | VERIFIED |
| Bootstrap rehash | Existing user password rehashed when changed at `security.py:103-105`. | VERIFIED |
| Token generation/storage | `secrets.token_urlsafe(32)` raw token; only SHA-256 hash stored at `security.py:52-53`, `:65-76`; model fields at `models/entities.py:630-639`. | VERIFIED |
| Expiry | `session_ttl_minutes` default `480` at `config.py:24`; lookup rejects revoked/expired sessions at `security.py:140-148`. | VERIFIED |
| Logout/revocation | `revoke_session` at `security.py:79-82`; logout endpoint at `api/v1/auth.py:47-63`; frontend clears token in `finally` at `frontend/src/lib/authApi.js:31-38`. | VERIFIED |
| Role checks | `require_roles` at `security.py:161-165`; role sets at `trust.py:44-47`. | VERIFIED |
| Generic login errors | Unknown, inactive, and bad-password users all return the same `401` at `auth.py:20-35` and `security.py:56-62`. | VERIFIED |
| Audit sanitization | Request context stores only path, method, client host, and 200-char user agent at `backend/app/audit.py:9-21`. | VERIFIED |

Auth gaps:

- **HIGH:** no login rate limiting, lockout, or failed-login audit at `backend/app/main.py:20-29`, `config.py:6-24`, and `backend/requirements.txt:1-18`.
- **HIGH:** no TLS/HSTS enforcement in application; Compose exposes plaintext HTTP at `docker-compose.yml:42-43` and `:67-68`. Deployment must assume HTTPS termination.
- **MEDIUM:** bearer token stored in browser `localStorage` at `frontend/src/lib/authApi.js:3-12`, exposing it to XSS.
- **MEDIUM:** no password policy in `api/v1/schemas.py:89-91`; seed only requires non-empty values at `backend/app/cli/seed_users.py:8-11`; no password change/reset endpoint in `api/v1/auth.py:20-63`.
- **MEDIUM:** no revoke-all, refresh rotation, idle timeout, expired-session cleanup, MFA, or algorithm-upgrade policy.
- **MEDIUM:** user-supplied reason strings are stored verbatim in audit/log state at `trust.py:100`, `:278-287`, `:327-334`.
- **MEDIUM:** unknown users skip PBKDF2 verification at `security.py:56-62`, leaving a timing distinction.
- **EVIDENCE GAP:** no negative auth tests for bad password, inactive user, logout/revocation, expiry, or role denial on validation/ack/audit.

## 9. Frontend and visual evidence

### 9.1 Functionality — VERIFIED / PARTIAL

- Statement page defaults to Draft and sends `visibility` to the API at `frontend/src/features/statements/StatementPage.jsx:25`, `:27-36`, `:123-132`.
- Statement errors and empty states are rendered at `StatementPage.jsx:70-92`, `:136-140`.
- Evidence rail shows source fact, context, period kind, document version, publication, and validation status at `StatementPage.jsx:180-207`.
- Source documents are listed with source links at `StatementPage.jsx:212-222`.
- Trust page supports login, validation, recalculation, publish, and display of validation findings, metrics, mappings, publication events, restatements, and audit events at `frontend/src/features/trust/TrustPage.jsx:37-53`, `:69-131`, `:167-181`, `:184-278`.
- Frontend build and lint pass, as recorded in section 3.

### 9.2 Frontend gaps

- **MEDIUM:** global chrome always displays `Draft · internal review only` even when Published view is selected at `frontend/src/app/AppShell.jsx:109`.
- **MEDIUM:** `unavailable_reason` and validation warnings are exposed by the API at `backend/app/api/v1/schemas.py:107-119`, but the metrics table shows only value/status/formula at `TrustPage.jsx:206-222`, hiding why a metric is unavailable.
- **MEDIUM:** trust UI has no warning acknowledgement, mapping approval, or restatement approval controls despite backend endpoints at `trust.py:84-117`, `:266-339`.
- **MEDIUM:** validation/recalculation buttons are enabled for any signed-in user at `TrustPage.jsx:169-173`, so lower roles receive server-side `403`.
- **MEDIUM:** non-reviewers silently see an empty audit list because rejected `Promise.allSettled` results are ignored at `TrustPage.jsx:37-53`.
- **NOT VERIFIED:** visual QA. `frontend/package.json:6-31` has no test, screenshot, Storybook, Playwright, Cypress, or visual-regression tooling. Lint/build are not visual proof.

## 10. Findings, severity, and promotion conditions

| ID | Severity | Finding | Required action before `PASS` |
| --- | --- | --- | --- |
| F-01 | HIGH | Metric input collection and taxonomy mappings omit required instant balance-sheet and capex roles (`metrics/service.py:140-147`, `normalization/accounts.py:52-66`). | Add mappings and instant input collection; add end-to-end tests proving each required metric is calculated or unavailable with a truthful reason. |
| F-02 | HIGH | Revised document registration does not create a distinct document version (`ingestion/service.py:366-375`). | Implement version increment, supersession, filing date/status, as-of selection, and API/history tests proving predecessor and successor are distinct. |
| F-03 | HIGH | Publication/authorization success and rejection matrix is not executable-tested (`test_m2_api.py:42-95`). | Add isolated-fixture API tests for unauth, analyst, reviewer, publisher success, blocker/error, unacknowledged warning, acknowledgement, rollback, DB effects, and audit events. |
| F-04 | HIGH | Security hardening absent: rate limiting, failed-login audit, TLS/HSTS enforcement, and safe token storage (`main.py:20-29`, `config.py:6-24`, `docker-compose.yml:42-43`, `authApi.js:3-12`). | Implement or document a verified deployment-boundary control with evidence. |
| F-05 | MEDIUM | `can_publish` can be true while publish rejects unacknowledged warnings (`lifecycle.py:62-63`, `publication.py:51-60`). | Align validation outcome with publication gate and expose pending acknowledgement state. |
| F-06 | MEDIUM | Metric engine lacks finite-value guard, balance-type check, version consistency check, deterministic basis/currency source, and correct negative-capex handling (`calculator.py:125-128`, `:201`, `:258-275`). | Add guards and targeted tests. |
| F-07 | MEDIUM | Period derivation has stale-dedup risk and only synthetic end-to-end evidence (`derivations.py:209-226`, `test_m2_periods.py`). | Include document version/reason in dedup key and add API-level derivation tests. |
| F-08 | MEDIUM | Frontend hides unavailable reasons, has stale Draft chrome, lacks approval controls, and has no visual QA evidence (`TrustPage.jsx:206-222`, `AppShell.jsx:109`, `package.json:6-31`). | Surface reasons/status, gate controls by role, add manual screenshot evidence or component tests. |
| F-09 | LOW | Document API omits version fields; audit reasons are unredacted; minor deterministic/cosmetic issues remain (`catalog.py:35-53`, `schemas.py:30-39`, `trust.py:100`). | Expose version metadata, sanitize free-text reasons, clean minor code issues. |

**Promotion conditions:** M2 may be reconsidered for `PASS` only after F-01 through F-04 are closed with executable evidence, F-05 through F-08 are either closed or formally accepted by the project owner with rationale, and a fresh regression run remains green with Alembic at `d4e7b9c1a2f3 (head)`.

**Final recommendation:** keep M2 at `CONDITIONAL PASS`; do not begin M3 or production promotion until the conditions above are explicitly approved and verified.
