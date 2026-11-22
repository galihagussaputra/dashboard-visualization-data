# Architecture Decisions

**Status:** Phase 2, milestone M1.
**Scope:** Decisions made while implementing the foundation. These records distinguish implementation decisions from Phase 1 verified findings and unresolved assumptions.

---

## AD-001 — Preserve existing frameworks and entry points

**Decision:** Keep React 19 + Vite 7 + D3 7 in `frontend/` and FastAPI in `backend/`. `backend/main.py` remains a thin compatibility wrapper that imports `app.main:app`.

**Reason:** Mandatory Phase 2 constraint; Phase 1 demonstrated the scaffold is usable with targeted fixes.

**Consequence:** Existing `uvicorn main:app` workflows continue to work. No framework replacement occurred.

**Classification:** Implementation decision consistent with [Phase 1](analysis/phase-1-feasibility-report.md#5-phase-2-constraints).

---

## AD-002 — Layered backend package added incrementally

**Decision:** Add `backend/app/` with `core/`, `api/v1/`, and `ingestion/` packages while leaving application behavior additive in M0.

**Reason:** The single 119-line `main.py` cannot host persistence, parsing, validation, metrics, auth, and audit without becoming unmaintainable.

**Consequence:** Business logic will live in services; API handlers remain thin. No existing behavior was removed except the random demo endpoints, which are replaced by the v1 API.

**Classification:** Implementation decision; no architecture/framework replacement.

---

## AD-003 — No dependency added for routing in M0

**Decision:** Use a small hash-based router in `frontend/src/app/router.jsx` instead of adding `react-router-dom` during M0.

**Reason:** Host `node` is unavailable, so updating `package-lock.json` safely requires the container. A custom minimal router avoids stale lockfiles and keeps M0 dependency changes to the backend only.

**Consequence:** Navigation supports all nine modules and a legacy demo route. Revisit a routing library only if nested routes, loaders, or deep-link requirements justify the dependency.

**Classification:** Implementation decision; revisit in M4 if needed.

---

## AD-004 — Legacy demo retained but clearly labeled

**Decision:** Keep `frontend/src/components/Dashboard.jsx` at `#/legacy` with the verified D3/CSS defects fixed and misleading "FastAPI backend" wording removed.

**Reason:** Preserve existing user work while removing false claims about data provenance.

**Consequence:** The synthetic dashboard remains available for comparison but is not part of the product data flow.

**Classification:** Correctness fix required by Phase 1.

---

## AD-005 — Git cleanup limited to ignore rules

**Decision:** Add `.gitignore`, `.gitattributes`, and Docker ignore files; do not untrack or delete `backend/venv/`.

**Reason:** Removing 7,964 tracked files requires explicit approval per the mission rules. Ignore rules prevent new venv content from being added.

**Consequence:** Existing CRLF-modified entries remain in `git status` until an approved cleanup.

**Classification:** Approval required for untracking; safer alternative adopted now.

---

## AD-006 — Docker Compose topology

**Decision:** Four services: `db` (PostgreSQL 16, named volume `pgdata`), `api` (FastAPI with reload), `frontend` (Vite dev server), and `worker` (same backend image, `ingestion` profile). Named volume `raw_docs` stores original downloaded documents.

**Reason:** Matches the approved Phase 1 plan and keeps ingestion isolated from request handling.

**Consequence:** Database is not published to the host; use `docker compose exec db psql`. No existing volumes were present or modified.

**Classification:** Implementation decision from approved plan.

---

## AD-007 — Health semantics

**Decision:** `GET /api/v1/health` reports application status only. `GET /api/v1/ready` probes PostgreSQL via `SELECT 1` and returns a component-level status without secrets.

**Reason:** Liveness must not fail during a transient DB outage; readiness should reflect dependencies.

**Consequence:** Compose healthchecks use `/api/v1/health`; orchestrators can use `/api/v1/ready`.

**Classification:** Implementation decision.

---

## AD-008 — No publication or data writes in M0

**Decision:** M0 creates no migrations, no company rows, and no financial facts.

**Reason:** Data integrity gates require the model/parsers/validators from M1 and M2 before any value can be stored or displayed.

**Consequence:** All product modules currently show honest empty states.

**Classification:** Mandatory financial data integrity rule.

---

## AD-009 — Configurable frontend host port

**Decision:** Compose maps `${FRONTEND_PORT:-5173}:5173`, and the frontend health check probes `http://127.0.0.1:5173/` inside the container.

**Reason:** Host port 5173 was occupied by an unrelated running container. The frontend host port must be overridable without stopping user work, and `localhost` health probes failed while IPv4 probing succeeded.

**Consequence:** `FRONTEND_PORT=5174 docker compose up -d` is the supported fallback. The browser still uses the Vite `/api` proxy, so CORS origins do not change for this override.

**Classification:** Implementation decision.

---

## AD-010 — Bank-specific balance equation

**Decision:** `FACT-001` validates `Assets = Liabilities + TemporarySyirkahFunds + Equity` when the syirkah fact exists, and falls back to `Assets = Liabilities + Equity` when it does not.

**Reason:** BBCA FY2025 is a bank using the Financial and Sharia entry point. Its statement includes `TemporarySyirkahFunds` between liabilities and equity, so the generic equation does not balance.

**Consequence:** The 12 POC concepts remain the core reconciliation set; `TemporarySyirkahFunds` is a non-core validation concept displayed in the balance-sheet view.

**Classification:** Mandatory financial data integrity rule.

---

## AD-011 — Fixture-backed M1 ingestion

**Decision:** The M1 worker ingests the four local BBCA FY2025 POC files with size and SHA-256 checks, copies them into `raw_docs`, and records an `ingestion_jobs` row plus validation logs.

**Reason:** The POC files are verified Phase 1 evidence. Reusing them reproduces the 12-value baseline without new IDX traffic, high-volume polling, or credential use.

**Consequence:** The live IDX adapter is isolated in `backend/app/ingestion/sources/idx_id.py` and is not invoked by the default M1 runner.

**Classification:** Implementation decision.

---

## AD-012 — Additive M2 schema only

**Decision:** Introduce M2 structures through revision `d4e7b9c1a2f3` using new tables, new columns, and non-null defaults; preserve all M1 constraints and data.

**Reason:** Financial history and existing persisted fixture data must not be deleted or rewritten in place.

**Consequence:** Existing rows remain queryable; M2 backfill adds mapping and context metadata without changing financial values.

**Classification:** Mandatory financial data integrity rule.

---

## AD-013 — Deterministic account mapping with review states

**Decision:** Store versioned standard accounts and mapping rules in PostgreSQL; only exact taxonomy or reviewed rule evidence can be approved automatically.

**Reason:** Hardcoded parser concepts cannot support auditable multi-source, multi-industry normalization.

**Consequence:** Unknown or ambiguous mappings are persisted as `unmapped` or `review_required` and block publication until reviewed.

**Classification:** Implementation decision supporting data integrity.

---

## AD-014 — Guarded period derivation

**Decision:** Derive standalone quarters only from compatible YTD/full-year contexts with matching dimensions and formula version `m2-v1`; otherwise persist `unavailable` or `review_required`.

**Reason:** Cumulative YTD values must never be summed or compared across incompatible contexts.

**Consequence:** Derivation output includes input fact IDs, periods, document versions, warnings, and reasons.

**Classification:** Mandatory financial data integrity rule.

---

## AD-015 — Versioned metric engine with explicit unavailable states

**Decision:** Centralize ratios in `m2-v1` specs and persist inputs, formula definition, calculation status, unavailable reasons, and warnings.

**Reason:** Missing inputs must not become zero; distinct leverage definitions must not be conflated.

**Consequence:** Unavailable metrics remain visible with reasons and do not block publication; invalid calculations do block.

**Classification:** Mandatory calculation integrity rule.

---

## AD-016 — Server-side publication gate

**Decision:** Validation runs, warning acknowledgement, role-based publish permission, publication events, and published-only reads are enforced by the backend.

**Reason:** Client state cannot be trusted to prevent unvalidated or unauthorized publication.

**Consequence:** Draft reads remain available for local review; published reads require an active publication event.

**Classification:** Mandatory server-side trust rule.

---

## AD-017 — Hashed sessions and audited sensitive actions

**Decision:** Use PBKDF2 password hashes, hashed bearer tokens with expiry/revocation, role dependencies, and sanitized audit events.

**Reason:** Authentication must be added without exposing credentials or storing raw tokens.

**Consequence:** Login, review, approval, recalculation, derivation, and publication actions are auditable.

**Classification:** Implementation decision.

---

## Open items

- Untracking `backend/venv/` remains **awaiting explicit user approval**.
- Frontend test tooling is deferred; `package-lock.json` remains unchanged.
- Comparison analytics, sector aggregates, and broader multi-company publication workflows remain M3+ work.
