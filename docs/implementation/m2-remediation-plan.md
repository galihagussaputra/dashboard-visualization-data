# M2 Remediation Plan

**Status:** R1 gate passed; stopped before R2.  
**Milestone:** M2 — `CONDITIONAL PASS`  
**Execution rule:** remediate R1 → gate → stop; then R2 → gate → stop; then R3 → gate → stop; then R4 → gate → final report. Do not begin M3. Do not commit or push.

## 1. Mandatory inspection record

### 1.1 Git state

Inspected at start of remediation:

- Branch: `main`
- HEAD: `dbedd1200cf30376c773b5c2d8ae576b092c0fa4`
- Recent commits: `dbedd12`, `898ab39`, `b032031`, `66fdf04`, `8751c90`, `a8df56a`
- Working tree outside `backend/venv/`: only untracked `docs/analysis/m2-final-evidence-audit.md`
- `backend/venv/`: 3463 pre-existing tracked modifications; preserved untouched

No reset, clean, stash, checkout, rebase, commit, push, file deletion, or history rewrite has been performed.

### 1.2 Documents read

- `docs/analysis/m2-final-evidence-audit.md`
- `docs/implementation/phase-2-execution-plan.md`
- `docs/implementation/database-schema.md`
- `docs/implementation/financial-validation-rules.md`
- `docs/implementation/financial-data-pipeline.md`
- `docs/implementation/architecture-decisions.md`
- `docs/implementation/testing-and-qa.md`

### 1.3 Discrepancies between audit and repository

- The audit executive summary names three High findings, but its finding table and remediation scope identify four: `F-01`, `F-02`, `F-03`, and `F-04`. This plan treats all four as High.
- `docs/implementation/phase-2-execution-plan.md` section 9 records that the focused implementation docs did not exist at initial assessment; they now exist and were read from their current paths.
- The audit report states the API container was stopped after audit; baseline inspection confirmed only `db` was running. The API service was started non-destructively for baseline checks.
- Port `5173` was occupied by an unrelated process during the audit. Baseline frontend checks therefore used `docker compose run --rm frontend` rather than `docker compose exec frontend`.

No source-code discrepancy invalidated a current audit finding. All findings were re-verified against actual source before planning changes.

## 2. Reproducible baseline

### 2.1 Docker and database topology

- Compose services: `db`, `api`, `frontend`; `worker` is profile-gated under `ingestion`.
- Initial state: `db` healthy, `api` and `frontend` stopped.
- Database: PostgreSQL 16 in named volume `pgdata`, not published to host.
- API: FastAPI/Uvicorn on container port 8000, host port 8000.
- Frontend: Vite on container port 5173, configurable host port; port 5173 was already allocated externally.

### 2.2 Alembic and actual schema

- `alembic current`: `d4e7b9c1a2f3 (head)`
- `alembic history`: `a70b95fcb2e3 -> d4e7b9c1a2f3 (head)`, `<base> -> a70b95fcb2e3`
- Actual schema inspected through SQLAlchemy:
  - `financial_documents` includes `document_version`, `is_current`, `superseded_by`, `filing_date`, `reporting_basis`, `version_status`.
  - `financial_facts` includes `period_kind`, `duration_kind`, `accounting_definition_key`, `document_version`, `publication_status`, `mapping_id`, `is_derived`, `source_context_details`.
  - `financial_metrics` includes `reporting_basis`, `currency`, `calculation_status`, `unavailable_reason`, `validation_warnings`, `input_document_versions`, `formula_definition`, `publication_status`.
  - M2 tables `financial_metric_inputs`, `source_account_mappings`, `standard_accounts`, `account_mapping_rules`, `fact_revisions` are present.
- Baseline row counts:
  - `financial_documents`: 4
  - `financial_facts`: 13
  - `financial_metrics`: 33
  - `financial_metric_inputs`: 78
  - `source_account_mappings`: 15
  - `standard_accounts`: 26
  - `account_mapping_rules`: 13
  - `fact_revisions`: 0

### 2.3 Baseline regression

| Command | Baseline result |
| --- | --- |
| `docker compose exec api ruff check .` | PASS; no diagnostics |
| `docker compose exec api python -m pytest -q` | `53 passed, 5 warnings in 22.46s`; warnings are SWIG/Arelle deprecations |
| `docker compose run --rm frontend npm run lint` | PASS; stale `baseline-browser-mapping` advisory only |
| `docker compose run --rm frontend npm run build` | PASS; Vite `v7.2.4`, `2261 modules transformed`, JS `293.32 kB`, CSS `25.07 kB`, built in `10.21s` |
| `docker compose exec api alembic current` | `d4e7b9c1a2f3 (head)` |
| `docker compose exec api alembic history` | M1 `a70b95fcb2e3` → M2 `d4e7b9c1a2f3` |

## 3. Re-verified findings and root causes

| Finding | Verdict | Root cause |
| --- | --- | --- |
| `F-01` High | VERIFIED | `_collect_inputs` keeps instant facts only for assets/equity/inventory and only approved mappings; deterministic taxonomy rules cover only the original 12/13 POC concepts. Current assets, current liabilities, quick assets, total debt, liabilities, COGS, inventory, capex, and opening/closing roles lack a complete runtime path. |
| `F-02` High | VERIFIED | Re-ingestion matches the existing document natural key and updates that row in place; version fields exist but are not used to append a revised filing. Approval is recorded but not enforced downstream. |
| `F-03` High | VERIFIED | Authorization and publication gate exist in code, but only unauth metrics, login/current-user, validation shape, and analyst publish `403` are executable-tested. No isolated success/rejection/rollback/audit matrix. |
| `F-04` High | VERIFIED | PBKDF2, hashed sessions, expiry, revocation, roles, and sanitized request context exist. No login abuse protection, failed-login audit, TLS/HSTS deployment evidence, password policy/account lifecycle, or safe browser token storage. |
| `F-05` Medium | VERIFIED | `can_publish` ignores warnings while publication rejects unacknowledged warnings; review-policy warnings are omitted from `warnings`, allowing contradictory `validated/can_publish=true` state. |
| `F-06` Medium | VERIFIED | Calculator lacks finite-value guard, balance-type check, deterministic basis/currency selection, definition-version consistency check, and explicit negative-capex convention. |
| `F-07` Medium | VERIFIED | Derivation dedup uses an output signature and excludes provenance/document version; no API-level derivation test exists. |
| `F-08` Medium | VERIFIED | Frontend hides unavailable reasons, shows stale Draft chrome, lacks approval/acknowledgement controls and clear denial states, and has no visual QA tooling. |
| `F-09` Low | VERIFIED | Document catalog omits version metadata; free-text audit reasons are stored verbatim; minor determinism issues remain in calculator fallback and derivation dedup. |

## 4. Planned remediation by gate

### R1 — financial input completeness and metric integrity

Intended files:

- `backend/app/metrics/service.py`
- `backend/app/metrics/calculator.py`
- `backend/app/metrics/definitions.py` if a semantic version change is proven necessary
- `backend/app/normalization/accounts.py`
- `backend/app/normalization/registry.py` only for source-concept evidence, not fabricated mappings
- `backend/tests/test_m2_metrics.py`
- New focused tests under `backend/tests/` for runtime collection and end-to-end metric inputs

Planned changes:

1. Replace role allow-listing with role-aware instant balance selection based on standard account code, reporting date, period boundaries, basis, currency, unit, scale, and document version.
2. Add explicit opening/closing boundary selection from prior and current period instant facts, with no zero substitution.
3. Add deterministic, evidence-backed mappings only where accounting meaning is unambiguous. Ambiguous or unsupported concepts remain `review_required`/`unmapped`.
4. Preserve source taxonomy and original concept names in all mapping provenance.
5. Add finite-value rejection, period-kind/balance-type checks, formula-version consistency, deterministic basis/currency selection, and an explicit positive-capex convention with an auditable unavailable reason for incompatible signs.
6. Add isolated end-to-end tests from normalized facts through input collection to calculation for all 11 metrics, including truthful unavailable outcomes.

Gate evidence required: targeted tests, full backend test suite, lint, migration state unchanged, Git diff review, and a recorded R1 result in this plan.

### R2 — document versioning and restatement lifecycle

Intended files:

- `backend/app/ingestion/service.py`
- `backend/app/normalization/restatement.py`
- `backend/app/normalization/derivations.py`
- `backend/app/api/v1/catalog.py`, `schemas.py`, `trust.py`, `statements.py`
- Possibly one additive Alembic migration if a document predecessor field needs strengthening

Planned changes:

1. Append a distinct revised document row instead of mutating the original.
2. Set predecessor/current/superseded state, filing date, version, basis, and restatement status.
3. Link successor facts to predecessors and preserve original facts and metric provenance.
4. Enforce approval before a revision enters current selection, validation, metrics, or publication.
5. Correct as-of resolution and expose document version metadata through catalog/statements.
6. Include provenance in derivation dedup and add synthetic lifecycle tests.

### R3 — publication, authorization, and API test coverage

Intended files:

- `backend/app/publication.py`
- `backend/app/validation/lifecycle.py`
- `backend/app/api/v1/trust.py`, `schemas.py`
- New isolated API test fixtures and matrix tests

Planned changes:

1. Single authoritative publishability policy shared by validation response and publication service.
2. Explicit pending-warning acknowledgement state, required role, and unresolved conditions.
3. Executable matrix for unauth, analyst, reviewer, publisher, viewer, success, blocker, error, warning, acknowledgement, rollback, audit, and published-statement gate.
4. Isolated publication success and failure tests with no shared BBCA publication.

### R4 — security and frontend trust

Intended files:

- `backend/app/core/security.py`, `config.py`, `main.py`
- `backend/app/api/v1/auth.py`, `schemas.py`
- `backend/app/audit.py`
- `frontend/src/lib/authApi.js`, `frontend/src/app/AppShell.jsx`, `frontend/src/features/trust/TrustPage.jsx`, related API clients
- Documentation for deployment boundary assumptions

Planned changes:

1. Project-native failed-login throttling with generic responses and sanitized audit events.
2. Evaluate cookie-based session transport; if it needs explicit approval or deployment changes, stop and document rather than silently invalidate sessions.
3. Document TLS/HSTS boundary as a deployment blocker if no approved proxy configuration exists.
4. Add password policy and negative auth tests where safe.
5. Surface metric reasons, validation/warning state, reported vs derived facts, revisions, role-aware actions, and clear denial states in the frontend.
6. Perform visual QA if tooling exists; otherwise report `NOT VERIFIED`.

## 5. Safety controls

- Preserve all tracked/untracked work, including `backend/venv/`.
- No destructive DB operation, data rewrite, volume deletion, migration downgrade, historical fact rewrite, live IDX fetch, or publication of fixture/real data.
- No commit, push, reset, clean, stash, checkout, rebase, or history rewrite.
- Additive/backward-compatible migrations only, with explicit approval sought if any data transformation appears necessary.
- Stop at each gate if the gate fails or if a required operation falls into an explicit-confirmation category.

## 6. R1 gate record

### 6.1 Changes made

- `backend/app/metrics/service.py`
  - Replaced role allow-listing with role-aware duration and instant input collection.
  - Added explicit closing-boundary selection and prior/current-period opening-boundary selection.
  - Added deterministic candidate ranking by period alignment, document version, fact version, and fact ID.
  - Added approved-mapping filtering and source-scale propagation.
- `backend/app/metrics/calculator.py`
  - Added role-to-period-kind checks, finite-value rejection, scale consistency, average-balance window checks, and average-balance fiscal-year compatibility.
  - Enforced positive capital expenditure with `NEGATIVE_CAPITAL_EXPENDITURE_UNSUPPORTED_SIGN`.
  - Enforced metric definition/version consistency before persistence.
  - Made persisted currency selection deterministic.
- `backend/app/normalization/accounts.py`
  - Added reviewed source-name rules for unambiguous captions: total revenue, current assets, current liabilities, inventories, interest-bearing debt, cost of goods sold, capital expenditure, and explicitly defined quick assets.
  - Kept generic quick assets, generic total debt, and negative-sign PPE purchases as `review_required`.
- `backend/tests/test_m2_metrics.py`
  - Updated role-aware test inputs and added non-finite, scale, role-kind, capex-sign, and window-mismatch tests.
- `backend/tests/test_m2_metric_runtime.py`
  - Added isolated transactional end-to-end coverage for all 11 `m2-v1` metrics.
- `docs/implementation/financial-data-pipeline.md` and `docs/implementation/testing-and-qa.md`
  - Updated only where R1 behavior changed.

No Alembic migration was added. Alembic remains at `d4e7b9c1a2f3 (head)`.

### 6.2 Gate evidence

| Check | Result |
| --- | --- |
| `docker compose exec api ruff check .` | PASS |
| Targeted `pytest tests/test_m2_metrics.py tests/test_m2_account_mapping.py tests/test_m2_metric_runtime.py` | `28 passed in 8.83s` |
| Full `docker compose exec api python -m pytest -q` | `59 passed, 5 warnings in 31.86s` |
| `docker compose exec api alembic current` | `d4e7b9c1a2f3 (head)` |
| `docker compose run --rm frontend npm run lint` | PASS; stale `baseline-browser-mapping` advisory only |
| `docker compose run --rm frontend npm run build` | PASS; Vite `v7.2.4`, `2261 modules transformed`, built in `10.88s` |

### 6.3 Finding status after R1

- `F-01`: code remediation and executable end-to-end evidence complete. The isolated test exercises all 11 metrics from approved normalized facts through role-aware input collection and calculation.
- `F-06`: code remediation and executable evidence complete. Non-finite values, role/period/scale mismatches, average windows, formula versions, currency selection, and capex sign convention are enforced.
- `F-09` determinism sub-issues addressed where they overlapped R1: instant/duration selection, currency selection, and derivation-adjacent input ordering. Remaining F-09 catalog/audit text concerns stay open for later gates.
- `F-02`, `F-03`, `F-04`, `F-05`, `F-07`, `F-08`, and remaining `F-09` concerns are not changed in R1.

R1 gate result: PASS. R2 has not started.
