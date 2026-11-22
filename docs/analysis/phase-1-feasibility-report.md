# Phase 1 Feasibility Report

**Date:** 2026-11-22
**Subject:** IDX Financial Intelligence — repository audit, data-source feasibility, extraction POC, data model, Docker/UI/implementation planning
**Evidence classification:** **[V]** verified during Phase 1; **[F]** feasible design decision; **[A]** assumption requiring Phase 2 validation.
**Cross-references:** [Repository audit](repository-technical-audit.md), [IDX feasibility](idx-data-source-feasibility.md), [Extraction POC](financial-data-extraction-poc.md), [Data model](financial-data-model.md), [Implementation plan](technical-implementation-plan.md).

---

## Go / Conditional Go / No-Go

**Decision: CONDITIONAL GO.**

Phase 2 should proceed on the existing React/Vite + FastAPI structure, using IDX as the primary public source and the normalized model in [Financial data model](financial-data-model.md). The conditions below must be satisfied before any data is published to dashboards:

1. Apply the correctness fixes in [Repository audit](repository-technical-audit.md#4-backend-architecture-and-specific-defects) and [Implementation plan](technical-implementation-plan.md#3-backend-work-packages) (`allow_methods`, month label, Tailwind v4 CSS, D3 ref/append, typos) **[V defects]** .
2. Add real parser libraries (`openpyxl`, `PyMuPDF`/`pdfplumber`, `Arelle`) and reproduce the 12/12 POC matches automatically **[V POC]** .
3. Implement the validation and role-gated publication workflow; dashboards must read only `status='published'` metrics **[V requirement]** .
4. Enforce YTD rules: never sum cumulative quarters; derive standalone quarters only through validated differences **[V requirement]** .
5. Keep IDX access conservative and isolated in one adapter; validate rate/header behavior in the container before scaling ingestion **[V/A]** .
6. Keep Docker, `.env`, and secret handling per [Implementation plan](technical-implementation-plan.md#4-docker-desktop--local-development); no committed credentials or production DB changes **[V requirement]** .

**Not a full Go** because the endpoint is undocumented, rate limits are unknown, one confirmed period gap exists, and only one company/period was parsed end-to-end **[V/A]** .
**Not a No-Go** because all core feasibility questions were answered positively with direct evidence: official documents are public, four formats parse, 12 values match exactly across formats, and the current stack is salvageable **[V]** .

---

## 1. Mandate recap

Phase 1 was limited to:

- Read-only audit of the repository; documentation creation allowed; no source rewrite, deletion, or Git commit/push.
- Preserve React frontend and FastAPI backend; no framework replacement.
- Investigate official IDX/OJK/XBRL data sources; no third-party data provider.
- Run a limited extraction POC without publishing results.
- Design a normalized financial data model with full source traceability.
- Assess Docker Desktop on Windows and original UI/UX deliverability.
- Produce six cross-referenced docs under `docs/analysis/`.
- Separate verified findings from assumptions; no fabricated data or unverified claims.

All mandate items were addressed; no application code was modified **[V]** .

---

## 2. Verdict summary

| Area | Verdict | Evidence |
|---|---|---|
| Existing repo as base | **Usable with fixes** | 16 tracked project files; FastAPI + React/Vite + D3 present; 9 confirmed defects; no tests/DB/Docker **[V]** |
| Official data availability | **Yes** | IDX listing API and helper endpoint work without credentials; 5 sample tickers × 5 years × 4 periods queried **[V]** |
| Historical coverage | **Mostly complete, one gap** | FY2024 Q1 absent for BBCA, BBRI, TLKM, ASII; present for ICBP; cause unknown **[V/A]** |
| Document formats | **Yes** | XLSX, PDF, XBRL instance ZIP, inline-XBRL ZIP downloaded for BBCA FY2025 **[V]** |
| Extraction to required structure | **Yes, conditional** | 12/12 selected values exact across all four formats; POC used stdlib only **[V]** |
| Data model feasibility | **Yes** | Proposed PostgreSQL schema covers provenance, versioning, missing vs zero, consolidated basis, YTD rules, validation/publication **[F]** |
| Docker Desktop feasibility | **Yes** | Docker CLI/daemon 29.7.2 available; Compose design avoids missing host Node/pip and committed Windows venv **[V/F]** |
| Original UI/UX feasibility | **Yes** | Existing stack supports editorial research-sheet direction; no redesign performed in Phase 1 **[F]** |
| Main blocker to Phase 2 | **Operational trust** | Undocumented endpoint, unknown rate limits, taxonomy diversity, publication controls **[V/A]** |
| Overall | **Conditional Go** | §Go / Conditional Go / No-Go |

---

## 3. Answers to the 10 assessment questions

### 3.1 Is the current repository technically usable as a base?

**Yes, with targeted fixes.** The split into `frontend/` and `backend/` and the dependency choices (React 19, Vite 7, D3 7, FastAPI 0.104.1, Pydantic 2.5, Pandas 2.1) are retained. However, the backend raises `TypeError` on the first request because of `allow_method=["*"]` (`backend/main.py:15`), the month list contains `'JunJul'`, and the frontend does not call the API at all. The committed Windows venv and CRLF noise are hygiene issues, not architectural blockers. See [Repository audit](repository-technical-audit.md) **[V]** .

### 3.2 Are official data sources accessible without credentials?

**Yes.** `GET https://www.idx.id/primary/ListedCompany/GetFinancialReport` and `GET https://www.idx.id/primary/Helper/GetEmiten?emitenType=s` returned HTTP 200 without credentials. No API key, CAPTCHA, or auth challenge was encountered. The URLs were discovered from IDX's own Nuxt bundle, not invented. No access control was bypassed. `www.idx.co.id` returned 403; use `www.idx.id` **[V]** .

### 3.3 Is there enough historical coverage?

**Yes for annual data; mostly for quarterly.** FY2021–FY2025 metadata was verified for `BBCA`, `BBRI`, `TLKM`, `ASII`, `ICBP`. All five have annual filings every year. FY2024 Q1 is missing for four of five; ICBP has it. FY2026 Q1 filings were visible on the listing page. Earlier than FY2021 was not tested **[V/A]** . See [IDX feasibility](idx-data-source-feasibility.md#4-initial-company-availability-matrix).

### 3.4 Are document formats machine-readable?

**Yes.** The BBCA FY2025 annual filing provided `.xlsx` (47 sheets), `instance.xbrl` + `Taxonomy.xsd`, 23 inline-XBRL HTML files, and a text-bearing PDF. Standard-library parsing succeeded for XML/ZIP/XLSX/PDF-text enough to prove the concept; production requires real libraries for validation and robust PDF extraction **[V]** .

### 3.5 Does normalization to the required fact structure work?

**Yes.** Each POC fact was assembled with company identifier, reporting period (duration + instant), statement type, account code (e.g. `idx-cor:Assets`), original account name, normalized category, value, currency, unit, scale, reporting basis, and source document reference (`File_ID`, filename, XBRL `id`, context). Values from four formats matched exactly after scale normalization (12/12) **[V]** .

### 3.6 Can the proposed data model support all product requirements?

**Yes, conditionally.** The model in [Financial data model](financial-data-model.md) covers master data, documents, concepts/aliases, versioned facts, metrics, jobs, validation, audit, and roles. It explicitly handles missing vs zero, consolidated vs separate, restatements, source hashes, and YTD derivation. It must be implemented with Alembic and `NUMERIC`, with publication gated by validation **[F]** .

### 3.7 Can Docker Desktop on Windows deliver the local environment?

**Yes.** Docker CLI/daemon 29.7.2 is available in the audit environment, and Compose can run `db` (Postgres 16), `api` (Python 3.11), `frontend` (Node 20), and an optional `worker` profile for ingestion. This avoids the unusable committed Windows venv and the missing host `node`/`pip`. Named volumes preserve data across restarts; `.env.example` contains no real secrets **[V/F]** .

### 3.8 Can the original UI/UX direction be achieved on the existing stack?

**Yes.** React 19 + D3 7 + Tailwind 4 can support the proposed editorial research-sheet design: left navigation, global filters, evidence rail, financial statement tables with explicit negative/missing/zero semantics, and purpose-built slope/dumbbell/rank/waterfall/DuPont visuals. No design or code changes were made during Phase 1; this is a feasibility conclusion **[F]** .

### 3.9 What are the main risks and mitigations?

See [§6 Risk assessment](#6-risk-assessment). The highest are undocumented endpoint instability, unknown rate limits, YTD misinterpretation, taxonomy differences between banks and general issuers, PDF extraction quality, and publication without validation **[V/A]** .

### 3.10 Should Phase 2 proceed, and under what conditions?

**Conditional Go** under the six conditions at the top of this report. Recommended sequence is M0 foundations → M1 one end-to-end company (BBCA FY2025) → M2 normalization/trust → M3 analytics → M4 hardening **[V/F]** .

---

## 4. Verified findings vs assumptions

### Verified in Phase 1

- Repository contains only the demo scaffold; no DB, tests, Docker, ingestion, parsers, validation, auth, or CI **[V]** .
- Both existing runtime entry points have concrete defects (backend CORS/date; frontend D3/Tailwind/hardcoded data) **[V]** .
- IDX metadata API, ticker helper, and document downloads work without credentials on `www.idx.id` **[V]** .
- Five-year annual metadata exists for all five sample companies; FY2024 Q1 gap confirmed for four **[V]** .
- Four BBCA FY2025 documents downloaded over HTTPS with HTTP 200 and known byte sizes **[V]** .
- XBRL instance uses absolute IDR with `decimals="-6"` and no `scale`; inline XBRL/XLSX/PDF display millions with scale 6 **[V]** .
- 12 selected values match across XBRL instance, XLSX, inline XBRL, and PDF **[V]** .
- BBCA FY2025 is consolidated/group, PSAK, `G. Financials` / `G1. Banks` **[V]** .
- OJK POJK 14/POJK.04/2022 explains the XBRL + PDF combination; IDX is the practical download source **[V]** .
- Docker CLI/daemon available; host `node`, `pip`, and installed `node_modules` absent **[V]** .

### Assumptions requiring Phase 2 validation

- The undocumented IDX endpoint will remain reachable with similar parameters **[A]** .
- Acceptable automated request rate; none is published **[A]** .
- Cause of the FY2024 Q1 gap for four companies **[A]** .
- Quarterly IDX periods are YTD for all issuers (standard practice; annual BBCA structure verified, quarterly not parsed in POC) **[A]** .
- Non-bank entry points can be mapped with the same concept/alias approach tested on BBCA **[A]** .
- `File_Size: 0` annual attachments are either stale metadata or unavailable files; not fetched in POC **[A]** .
- `httpx` in Linux containers behaves like `curl` rather than the Python 403 observed with `urllib` **[A]** .
- Arelle validation will pass the sample filing; Arelle was not installed during Phase 1 **[A]** .

---

## 5. Phase 2 constraints

- Keep React/Vite frontend and FastAPI backend; no framework swap **[V]** .
- No source deletion or large refactor; add layers incrementally **[V]** .
- No secrets in repo; `.env` is local only **[V]** .
- No production DB modification; local Compose DB only **[V]** .
- No fabricated financial data or unverified publication **[V]** .
- No bypass of WAF/CAPTCHA/auth if introduced later **[V]** .
- No Git commit/push unless explicitly requested **[V]** .

---

## 6. Risk assessment

| Risk | Likelihood / impact | Evidence | Mitigation | Phase |
|---|---|---|---|---|
| Undocumented IDX endpoint changes | Medium / High | First-party JS endpoint, not a public API **[V]** | Isolate in `idx_id.py`, config-driven base URL, monitor 404/param changes, cache metadata **[F]** | B2 |
| Rate limiting / WAF behavior | Medium / High | No published limits; `urllib` 403 vs `curl` 200 **[V/A]** | `IDX_REQUEST_DELAY_SECONDS`, backoff, honest user agent, no parallel bursts, container validation **[F]** | B2, M4 |
| Missing periods (FY2024 Q1) | Confirmed / Medium | 4/5 sample companies **[V]** | Query standard periods, log `PER-001`, show `—`, never estimate **[F]** | B2, F2 |
| Taxonomy differences (banks vs general) | High / Medium | BBCA Financial/Sharia entry point **[V]** ; others unparsed **[A]** | Concept-code keys, aliases, `applicable_entry_points`, metric definitions per entry point **[F]** | B3, B4 |
| YTD summed incorrectly | High / High | Flow statements are YTD; annual = FY **[V/A]** | `normalization/periods.py`, `financial_metrics.is_derived_from_ytd`, explicit tests **[F]** | B4, F3 |
| PDF extraction quality | Medium / Medium | Naive extractor split numbers and signs **[V]** | Use PyMuPDF/pdfplumber, cross-format `XFORM-001`, never publish PDF-only unverified values **[F]** | B3 |
| Zero-size attachments | Medium / Low | Several annual attachments have `File_Size: 0` **[V]** | `DOC-003` warning, fetch/hash before use, keep raw metadata **[F]** | B2 |
| Committed Windows venv / CRLF noise | High / Low | 7,964 venv files, ~184 MB; all diffs line endings **[V]** | `.dockerignore`, later approved untrack, `.gitattributes` **[F]** | M0, separate cleanup |
| Missing host Node/pip | Confirmed / Low | `node` and `pip` absent **[V]** | Use Compose containers for build/test **[F]** | M0 |
| Publication without validation | Medium / High | No auth/validation exists today **[V]** | `PUB-001`/`PUB-002`, roles, audit events, dashboards read published only **[F]** | B4, B5, F4 |
| Unverified source values shown as facts | Medium / High | Current UI footer claims FastAPI data but is hardcoded **[V]** | Remove hardcoded `rawData`, evidence rail, source footnotes **[F]** | F1, F2 |

---

## 7. Conditions to upgrade to full Go

| Condition | Verification method | Owner milestone |
|---|---|---|
| One more company (e.g. `TLKM`, General entry point) parsed with 12 comparable core facts | Golden test + evidence doc update | M1 |
| All four BBCA quarterly periods parsed and YTD derivation tested | `pytest` period tests, no summed YTD | M2 |
| Containerized ingestion respects conservative delay and normal headers | `docker compose --profile ingestion run --rm worker ...` | M2 |
| Arelle validates BBCA FY2025 instance without fatal errors | Validation run logged | M2 |
| Publication gate rejects a draft metric with a failed error-severity rule | Negative test + 403 role test | M2 |
| Lint/build/test green in Compose | `ruff check`, `pytest`, `npm run lint`, `npm run build` | M4 |

Until these pass, keep rollout limited to the BBCA FY2025 annual sample and internal/draft views **[F]** .

---

## 8. Recommended Phase 2 sequence

| Milestone | Scope from [Implementation plan](technical-implementation-plan.md#9-delivery-sequence) |
|---|---|
| **M0 — Foundations** | B0 correctness, F0 frontend fixes, Compose files, `.env.example`, health checks |
| **M1 — One end-to-end company** | DB migration, IDX adapter, four-file download, parsers, BBCA FY2025 statement view |
| **M2 — Normalization & trust** | Validation engine, YTD derivation, role-gated publication, data-management/validation UI |
| **M3 — Analytics** | Ratios, comparison (max 5 tickers), sector/peer views, evidence rail across modules |
| **M4 — Hardening** | Tests, lint, build, CI, documentation updates, no secrets |

---

## 9. Phase 1 deliverables and repository state

Produced under `docs/analysis/`:

1. [repository-technical-audit.md](repository-technical-audit.md)
2. [idx-data-source-feasibility.md](idx-data-source-feasibility.md)
3. [financial-data-extraction-poc.md](financial-data-extraction-poc.md)
4. [financial-data-model.md](financial-data-model.md)
5. [technical-implementation-plan.md](technical-implementation-plan.md)
6. [phase-1-feasibility-report.md](phase-1-feasibility-report.md)

State **[V]**:

- Only `docs/analysis/` was added to the repository.
- No application source, dependency file, config, or Git state was changed.
- No commit, push, or dependency installation was performed.
- POC files and scripts remain in `/tmp/opencode/` and were not copied into the repo.
- No financial data was published to any database or dashboard.
