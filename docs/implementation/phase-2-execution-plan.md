# Phase 2 Execution Plan and Initial M0 Assessment

**Date:** 2026-11-22
**Status:** M1 regression preserved; M2 implementation complete with final quality gates recorded in section 10.
**Authority:** Phase 2 implementation authorized; destructive operations still require explicit approval.

---

## 1. Phase 1 baseline confirmed

All six Phase 1 documents were read in full. No required document is missing or unreadable. Terminology and classification from Phase 1 are retained:

- **[V]** verified by Phase 1 evidence.
- **[F]** implementation decision consistent with the approved plan.
- **[A]** unresolved assumption requiring validation.

Verified constraints carried forward:

- Preserve `frontend/` (React 19 + Vite 7 + D3 7) and `backend/` (FastAPI + Pydantic).
- IDX endpoints discovered in Phase 1 are the only permitted source access method; do not invent URLs or bypass controls.
- BBCA FY2025 is the first end-to-end dataset; the 12-value POC result is a reconciliation baseline, not universal proof.
- Undocumented endpoint, unknown rate limits, FY2024 Q1 gap, taxonomy diversity, and PDF quality remain open risks.
- No fabricated data, no zero-substituted missing values, no mixed reporting bases, no summed YTD quarters, no unvalidated publication.

---

## 2. Current repository state (inspected 2026-11-22)

| Area | Current state | Difference from Phase 1 |
|---|---|---|
| Git history | 7 commits, `HEAD = a970897 Main Python` | No change |
| Tracked files | 7,982 total; 7,964 under `backend/venv/`; 18 project files | No change |
| Working tree | 3,480 status entries: 3,463 `backend/venv/` modifications, 16 project-file modifications, 1 untracked `docs/` | `docs/analysis` is now present but untracked; Phase 2 implementation docs added here |
| Line endings | `core.autocrlf` unset; modified project files show equal line insert/delete counts | Matches Phase 1 CRLF/LF artifact |
| Docker | No `Dockerfile`, `docker-compose.yml`, or `.dockerignore` | No change |
| Database / migrations | No DB configuration, no Alembic, no `models/`, no schema files | No change |
| Tests | No application tests; only third-party tests inside committed venv | No change |
| Environment | No `.env`, `.env.example`, or settings module | No change |
| Backend | `backend/main.py` 119 lines, single module with the three verified defects intact | No change |
| Frontend | Vite scaffold with the verified Tailwind/D3/title/hardcoded-data defects intact | No change |
| Tooling | Python 3.14.4, npm 11.12.1, Docker 29.7.2, Compose v5.5.0; `node` absent; no host Python packages (`fastapi`, `sqlalchemy`, etc.) | Compose version now explicitly confirmed; otherwise matches Phase 1 |

Conclusion: the repository still matches the Phase 1 audit. No contradiction affects architecture or data integrity.

---

## 3. Cleanup candidates requiring approval

The following cleanup is **identified but NOT executed**.

### 3.1 Untrack committed Windows virtual environment

- **Exact operation:** `git rm -r --cached backend/venv`
- **Affected paths:** all 7,964 tracked files under `backend/venv/`.
- **Reason:** the venv is Windows CPython 3.11, unusable on Linux/containers, inflates the repository (~184 MB), and causes 3,463 false modified entries from line endings. Phase 1 and the implementation plan both defer this to an explicitly approved cleanup.
- **Risks / consequences:** after the next commit, collaborators who pull will have `backend/venv/` removed from version control; any workflow depending on the committed venv must use Docker or recreate it locally. Git history is not rewritten.
- **Backup:** none needed for the files themselves if `--cached` is used; they remain on disk. A Git bundle/branch backup is advisable before committing the cleanup if the team wants historical recovery.
- **Safer alternative adopted for now:** add root `.gitignore` and `backend/.dockerignore` entries so new work never adds venv content, while leaving all tracked files untouched. This does not reduce existing clone size but is fully reversible.

### 3.2 Existing CRLF/LF project-file modifications

- **Affected paths:** `README.md`, `backend/main.py`, `backend/requirements.txt`, and all 13 frontend project files.
- **Action proposed:** add `.gitattributes` with `* text=auto eol=lf` and ignore rules; do **not** normalize existing blobs or run `git add --renormalize .` without approval.
- **Risks / consequences:** future commits will normalize new content; existing working-tree noise remains until separately addressed.
- **Safer alternative adopted for now:** leave the pre-existing modifications in place and edit only the specific lines/sections required by each milestone.

No deletion, reset, force-push, commit, or push will be performed.

---

## 4. M0 definition for this implementation

M0 consists of safe, additive work only:

1. **Documentation baseline:** this execution plan plus architecture decisions and Docker guide.
2. **Git hygiene:** add `.gitignore`, `.gitattributes`, `backend/.dockerignore`, `frontend/.dockerignore`; do not untrack anything.
3. **Docker Compose:** add `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `.env.example`; no existing volumes exist to replace.
4. **Backend foundation:** keep `backend/main.py` as a compatibility wrapper; add `backend/app/` package with config, DB session, health/ready routes, structured logging, exception handling, API v1 router registration, and tests.
5. **Frontend foundation:** fix the verified F0 defects, add routing, API client, app shell, design tokens, and loading/error/empty states without replacing React/Vite/Tailwind/D3.
6. **Verification:** run available checks. Host Python lacks dependencies and `node` is absent, so containerized checks are required for true PASS results; host-side static checks will be reported as partial until Compose is executed.

---

## 5. M0 implementation file plan

### New root files

- `.gitignore`
- `.gitattributes`
- `.env.example`
- `docker-compose.yml`
- `README.md` update (corrects stale structure; additive edit)

### New backend files

- `backend/.dockerignore`
- `backend/Dockerfile`
- `backend/app/__init__.py`
- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/core/logging.py`
- `backend/app/core/db.py`
- `backend/app/core/errors.py`
- `backend/app/api/v1/router.py`
- `backend/app/api/v1/health.py`
- `backend/tests/test_health.py`
- `backend/pytest.ini`
- `backend/requirements.txt` update (add pinned compatible deps)

### Modified backend files

- `backend/main.py` — thin wrapper only; preserves existing entry point without architecture replacement.

### New frontend files

- `frontend/.dockerignore`
- `frontend/Dockerfile`
- `frontend/src/app/router.jsx`
- `frontend/src/app/AppShell.jsx`
- `frontend/src/lib/api.js`
- `frontend/src/lib/format.js`
- `frontend/src/styles/designTokens.css`
- `frontend/src/features/placeholder/PlaceholderPage.jsx`

### Modified frontend files

- `frontend/index.html` — correct title/lang.
- `frontend/src/index.css` — Tailwind v4 entrypoint.
- `frontend/src/App.jsx` — mount router/shell.
- `frontend/vite.config.js` — `/api` proxy.
- `frontend/package.json` — add router/test deps and scripts.
- `frontend/src/components/Dashboard.jsx` — F0 correctness fixes; retained as legacy demo route, not the product UI.

---

## 6. M0 quality gate evidence

| Check | Result |
|---|---|
| `docker compose config --quiet` | Pass |
| `docker compose build api frontend worker` | Pass |
| `docker compose up -d` | `db`, `api`, and `frontend` healthy |
| `GET /api/v1/health` | `200`, `status=ok` |
| `GET /api/v1/ready` | `200`, `database.status=ok` |
| Vite root and `/api` proxy | `200` on host port `5174` |
| Worker placeholder | `M0 placeholder: ingestion runner will be implemented in M1.` |
| `python -m pytest` | `3 passed` |
| `ruff check .` | Pass |
| `npm run lint` | Pass |
| `npm run build` | Pass |

Host port `5173` was already allocated by an unrelated container. It was left untouched; `FRONTEND_PORT=5174` was used for verification. No commits, pushes, DB volume deletion, IDX downloads, or financial data publication occurred.

---

## 7. Approval status

| Item | Status |
|---|---|
| Untrack/delete `backend/venv/` | **Awaiting explicit user approval; not executed** |
| Overwrite `.env` | Local ignored `.env` created from `.env.example`; no real secrets; `.env.example` committed |
| Delete tracked files | Not requested; will not occur |
| Drop/recreate DB volumes | Not executed; volumes created and preserved |
| Replace frameworks | Not requested; will not occur |
| Publish financial data | M1 view is draft/internal only; no publication occurred |
| High-volume IDX requests | No new IDX requests; M1 used local Phase 1 POC fixtures |

M0 and M1 are complete. M2 proceeds sequentially from this gate under the existing Phase 2 authorization.

---

## 8. M1 quality gate evidence

| Check | Result |
|---|---|
| `alembic current` | `a70b95fcb2e3 (head)` |
| `alembic downgrade base && alembic upgrade head` | Passed on empty schema before fixture ingestion |
| `docker compose --profile ingestion run --rm worker python -m app.ingestion.runner --ticker BBCA --year 2025 --period audit --source fixture` | `job=2 status=validated documents=4 facts=13 logs=4` |
| Fixture integrity | 4/4 files matched source size and SHA-256 |
| XBRL instance, inline XBRL, XLSX, PDF parsing | 12/12 POC values reproduced in each format |
| `XFORM-001` | `12/12 core facts matched` |
| `FACT-001` | `balance equation matched in all sources` using liabilities + temporary syirkah funds + equity |
| `ARELLE-001` | `passed` with offline Arelle validation |
| Postgres state | 4 documents, 13 current facts, 4 validation logs, latest job `validated` |
| `GET /api/v1/companies` | BBCA present |
| `GET /api/v1/periods?ticker=BBCA` | FY2025 present |
| `GET /api/v1/documents?ticker=BBCA&year=2025&period=audit` | 4 source documents present |
| `GET /api/v1/statements/BBCA?period=FY2025&statement=balance_sheet&basis=consolidated` | 5 facts with concept, context, source file, source URL and validation status |
| Income statement / cash flow endpoints | 5 facts / 3 facts |
| `GET /api/v1/ingestion/jobs/2` | `validated` |
| Frontend `/performance` | Statement table, global filters, selected-fact evidence rail and source document rail |
| `python -m pytest` | 13 passed |
| `ruff check .` | Pass |
| `npm run lint` | Pass |
| `npm run build` | Pass |
| Vite API proxy | `200` for `/api/v1/statements/BBCA` |

---

## 9. M2 initial assessment (2026-11-22)

### 9.1 Baseline verification

- `git branch --show-current`: `main`; `git log --oneline -10` head `a970897 Main Python`. No Git history was modified.
- `git status --short -- . ':(exclude)backend/venv'`: 26 project paths changed or untracked. `git status --short --untracked-files=no | wc -l`: 3,471, overwhelmingly legacy `backend/venv/` modifications.
- Required implementation docs found: `docs/implementation/phase-2-execution-plan.md` and `docs/implementation/architecture-decisions.md`.
- Requested names `database-schema.md`, `financial-data-pipeline.md`, `financial-validation-rules.md`, and `testing-and-qa.md` do not exist. Existing substitutes read: `docs/analysis/financial-data-model.md`, `docs/analysis/technical-implementation-plan.md`, `docs/implementation/docker-development-guide.md`, and M1 gate evidence in this plan. Focused M2 docs will be added under the existing `docs/implementation/` folder without duplicating Phase 1 analysis.
- Alembic current: `a70b95fcb2e3 (head)`; history: `<base> -> a70b95fcb2e3`.
- Baseline `docker compose exec api python -m pytest -q`: `13 passed, 5 warnings in 16.47s`.

### 9.2 Existing implementation facts

- **Financial fact schema:** `financial_facts` stores company, period, document, account, ingestion job, verbatim source fact/context IDs, context start/end/instant dates, original and normalized values, currency, unit, scale, decimals, reporting basis, fact version, current/superseded flags, validation status, and creation time. It has no normalized period kind, YTD/standalone flag, derived-value provenance, account-mapping reference, or publication status.
- **Account mapping capability:** ingestion materializes 13 hardcoded `ConceptSpec` rows into `financial_accounts`; parsers match by local concept name or format-specific labels. `account_aliases` exists but is unused. There is no DB-driven mapping registry, mapping version, confidence, review workflow, industry scope, approved-by metadata, or unknown/ambiguous detection.
- **Period/context representation:** `financial_periods` stores fiscal year, `period_type`, sequence, `is_ytd`, period start/end and instant dates, and source period code. Facts preserve `source_context_ref` and context dates. M1 writes only one FY2025 `audit` period with `is_ytd=True`; no YTD derivation or standalone-quarter representation exists.
- **Consolidated/separate representation:** `companies.reporting_basis_default` and `financial_facts.reporting_basis` exist with an allowed-value check. The value is copied from fixture metadata to every fact; the statement API filters by explicit `basis`, but there is no document-level detection, mixed-basis validation, or no-silent-fallback guard.
- **Metric calculation implementation:** none. `metric_definitions` and `financial_metrics` tables exist but have no seeded rows, calculator, API, input references, validation warnings, or publication flow.
- **Document versioning:** `financial_documents` has source IDs, checksums, parse status, and metadata but no version number, filing date, current/superseded chain, or duplicate-version detection. Re-ingestion updates the existing document row in place; fact values are versioned but `superseded_by` and `is_restated` are not set.
- **Validation and publication workflow:** M1 emits four internal validation rules (`XFORM-001`, `FACT-001`, `DOC-001`, `ARELLE-001`) and blocks ingestion on `error`. `ValidationLog` has only `error/warning/info`; there is no BLOCKER severity, validation run grouping, review state, override audit, publication endpoint, or published-only read path. `ValidationGateError` is defined but unused.
- **Authentication and permissions:** roles/users/user_roles tables exist but no password hashing, login, session/token, current-user dependency, role checker, user seeding, protected endpoint, or audit-event writer exists. CORS uses explicit origins with credentials enabled, but no credential mechanism exists yet.
- **Fixtures vs actual IDX source:** the four BBCA FY2025 binaries are local copies of real Phase 1 IDX downloads. Identifiers such as `bbca-fy2025-audit-fixture` are local fixture IDs, jobs are tagged `local_fixture`, live IDX access is disabled in the runner, and no new IDX request is planned for M2.

### 9.3 M2 gaps

1. No controlled source-account-to-standard-account mapping service or review workflow.
2. No derivation of standalone quarters from compatible YTD contexts and no explicit unavailable/review-required result.
3. No database-level enforcement that derived values, metrics, and comparisons inherit and preserve reporting basis.
4. No centralized versioned ratio engine; no input fact links, calculation status, or missing-input behavior.
5. No restatement chain linking revised facts/documents to predecessors with audit records and metric recomputation.
6. No severity-based validation lifecycle (`PENDING` through `SUPERSEDED`) or backend publication gate.
7. No server-side authentication, role enforcement, login, permission matrix, or audit of sensitive actions.
8. Frontend shows provenance for selected facts but not per-value period kind/YTD state, derived/reported distinction, restatement state, validation warnings, unavailable reasons, source file links, or authorized review/publish actions.

### 9.4 Proposed implementation sequence

1. Additive M2 schema migration and focused docs.
2. Account normalization catalog, deterministic/taxonomy-aware/industry-aware mapping rules, and tests.
3. Reporting-context helpers, period normalization, guarded quarter derivation, and reporting-basis integrity.
4. Versioned metric definitions/engine with explicit statuses and relational input references.
5. Restatement/version selection service, validation runs, publication gate, auth/session/roles, and audit events.
6. API endpoints and frontend trust/review experience.
7. Full M1/M2 regression, lint, build, migration, and endpoint checks.

### 9.5 Migration risks and controls

- Existing tables must not be dropped, truncated, recreated, or rewritten in place.
- Existing `CHECK` constraints will be preserved; new M2 states will use new columns or new tables rather than replacing legacy constraints.
- The existing `financial_documents` natural-key constraint prevents storing two rows with the same source document ID and role; revised filings must use explicit versioned source document IDs rather than changing that constraint.
- Additive columns will use non-null defaults so existing BBCA rows remain valid.
- No publication state will be granted automatically to existing M1 facts; M2 tests will publish only synthetic/fixture-scoped records after the backend gate passes.
- No `backend/venv/` cleanup, Git reset, commit, push, volume deletion, historical rewrite, live IDX fetch, or destructive migration will be performed.

---

## 10. M2 implementation summary

### 10.1 Delivered scope

- Additive Alembic migration `d4e7b9c1a2f3` with normalization, derivation, metric input, revision, validation run, publication, and session tables.
- DB-driven account normalization with versioned rules, review states, industry/statement/taxonomy evidence, and idempotent backfill of current M1 facts.
- Reporting-context classification and guarded standalone-quarter derivation with explicit provenance and unavailable/review-required results.
- Centralized `m2-v1` metric engine with 11 versioned definitions, input references, warnings, and explicit unavailable reasons.
- Restatement version selection, pending/approved revision workflow, and audited approvals.
- Validation runs with BLOCKER/ERROR/WARNING/INFO severities, rule categories, status workflow, and warning acknowledgement limited to reviewers.
- Server-side publication gate, publication events, supersession without historical rewrites, and published-only statement reads.
- PBKDF2 password hashing, hashed bearer sessions, expiry/revocation, role dependencies, protected endpoints, and sanitized audit events.
- Frontend provenance columns, published/draft view toggle, and validation/publication/audit trust pages.

### 10.2 Focused M2 documents

- `docs/implementation/database-schema.md`
- `docs/implementation/financial-data-pipeline.md`
- `docs/implementation/financial-validation-rules.md`
- `docs/implementation/testing-and-qa.md`

### 10.3 Final quality gate

| Criterion | Status | Evidence |
| --- | --- | --- |
| Additive migration applied | PASS | `alembic current` = `d4e7b9c1a2f3 (head)` |
| M1 regression preserved | PASS | M1 reconciliation/API tests pass in the 53-test suite |
| Account normalization | PASS | Mapping unit tests plus statement `standard_account=CASH` evidence |
| Period interpretation | PASS | Derivation tests plus shard context `period_kind=instant` evidence |
| Basis integrity | PASS | Basis helpers, explicit basis filters, `BASIS-001` blocker |
| Metric integrity | PASS | 11 metrics persisted; `NET_PROFIT_MARGIN` calculated; others unavailable with reasons |
| Restatement handling | PASS | `fact_revisions` model/service and approval endpoint; no historical values rewritten |
| Validation workflow | PASS | `POST /validation/run` returned `validated`, 0 issues, `can_publish=true` |
| Publication controls | PASS | Published read returned `404` without a publication event; no fixture data published |
| Auth and permissions | PASS | Unauthenticated request `401`; publisher role required for publish |
| Audit trail | PASS | Login, validation, recalculation, approval, and publication actions write audit events |
| Frontend | PASS | Trust/provenance UI built; lint and production build pass |
| Backend lint/tests | PASS | `ruff check .`; `53 passed, 5 warnings` |
| Destructive operations | PASS | None performed; no commit, push, venv cleanup, volume deletion, data deletion, or live IDX fetch |
