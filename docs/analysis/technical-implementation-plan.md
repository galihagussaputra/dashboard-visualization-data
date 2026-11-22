# Technical Implementation Plan

**Date:** 2026-11-22
**Scope:** Phase 2 implementation plan derived from the Phase 1 audit. This is a plan, not completed implementation.
**Cross-references:** [Repository audit](repository-technical-audit.md), [IDX feasibility](idx-data-source-feasibility.md), [Extraction POC](financial-data-extraction-poc.md), [Data model](financial-data-model.md), [Feasibility report](phase-1-feasibility-report.md).

---

## 1. Guiding constraints

1. **Preserve the existing architecture:** `frontend/` stays React 19 + Vite 7 + D3 7; `backend/` stays FastAPI + Pydantic. No framework replacement, no deletion, no large refactor **[V constraint from brief]** .
2. **Incremental replacement:** the current demo UI/API are disposable, but changes land as new modules behind stable interfaces, not as a big-bang rewrite.
3. **Docker Desktop on Windows** is the local runtime target; Compose must work with WSL2 integration **[V requirement]** .
4. **Original UI/UX direction** is mandatory; no generic template dashboard, gradients, neon, glassmorphism, or decorative charts **[V requirement]** .
5. **No secrets, no production data modification, no unvalidated publication** **[V requirement]** .
6. **No fabricated financial values.** Use verified source extracts for fixtures (the BBCA FY2025 sample in the [Extraction POC](financial-data-extraction-poc.md) is suitable) **[V]** .
7. **Phase 1 remains read-only for source code**; only `docs/analysis/` was created **[V]** .

---

## 2. Target architecture

```text
Docker Desktop (Windows + WSL2)
└── docker-compose.yml
    ├── frontend  (node:20-alpine, Vite dev server)  ──HTTP /api──▶ api
    ├── api       (python:3.11-slim, FastAPI)        ──SQL────────▶ db
    ├── db        (postgres:16-alpine, named volume pgdata)
    └── worker    (same image as api, profile "ingestion")
                  ├── HTTPS ─▶ www.idx.id (metadata + documents)
                  ├── writes ─▶ named volume raw_docs
                  └── SQL ────▶ db
```

### 2.1 Backend layering

Keep `backend/main.py` as a thin compatibility entry point and introduce a package:

```text
backend/
├── main.py                  # from app.main import app  (keeps uvicorn command working)
├── requirements.txt
├── .dockerignore
├── app/
│   ├── main.py              # FastAPI app, middleware, router registration
│   ├── core/
│   │   ├── config.py        # pydantic-settings, reads .env, no real secrets committed
│   │   ├── db.py            # SQLAlchemy engine/session, health checks
│   │   └── security.py      # role checks, publication guard
│   ├── api/v1/              # routers: companies, statements, metrics, comparison,
│   │                        # sectors, documents, ingestion, validation, publication
│   ├── schemas/             # Pydantic request/response DTOs
│   ├── models/              # SQLAlchemy models matching financial-data-model.md
│   ├── repositories/        # data access only; no HTTP or parsing here
│   ├── ingestion/
│   │   ├── sources/idx_id.py       # the ONLY place IDX URLs/params live
│   │   ├── downloader.py           # hash/size verification, raw_docs storage
│   │   └── runner.py               # job orchestration, CLI entry point
│   ├── parsers/
│   │   ├── xbrl_instance.py        # stdlib XML first; Arelle validation wrapper
│   │   ├── inline_xbrl.py
│   │   ├── xlsx.py                 # openpyxl, explicit Decimal coercion
│   │   └── pdf.py                  # PyMuPDF/pdfplumber fallback
│   ├── normalization/
│   │   ├── accounts.py             # concept registry + aliases
│   │   └── periods.py              # YTD → standalone quarter derivation
│   ├── validation/
│   │   ├── rules.py
│   │   └── engine.py
│   ├── metrics/
│   │   ├── definitions.py
│   │   └── calculator.py
│   └── tests/                      # or top-level tests/, whichever is simpler
```

This preserves the existing folder split and FastAPI entry point while adding the layers the current single-file backend lacks (see [Repository audit](repository-technical-audit.md#4-backend-architecture-and-specific-defects)).

### 2.2 Frontend layering

Extend, do not replace, the current `frontend/src/`:

```text
frontend/src/
├── app/                 # router, providers, global filters, shell
├── components/          # shared primitives, evidence rail, statement table
├── features/
│   ├── overview/
│   ├── statements/
│   ├── profitability/
│   ├── cashFlow/
│   ├── ratios/
│   ├── comparison/
│   ├── sector/
│   ├── dataManagement/
│   └── validation/
├── lib/api.ts           # typed API client + query layer
├── lib/format.ts        # migrate the existing Intl.NumberFormat('id-ID') helper
├── styles/designTokens.css
├── main.jsx
└── index.css            # Tailwind v4 @import "tailwindcss"
```

Existing D3 code in `Dashboard.jsx` should be extracted into reusable chart primitives (bar/line/donut are acceptable only where semantically justified) rather than discarded.

---

## 3. Backend work packages

| WP | Deliverable | Exit criteria |
|---|---|---|
| **B0 — Correctness** | Fix `allow_method` → `allow_methods` (`backend/main.py:15`), `'JunJul'` comma (`:40-41`), unused import; add `.env.example`, settings, `/health`, `/ready` | First API request no longer raises; health endpoint returns DB status |
| **B1 — Persistence** | SQLAlchemy models + Alembic initial migration per [Data model](financial-data-model.md) | `alembic upgrade head` on empty Compose DB; rollback tested once |
| **B2 — Ingestion** | `idx_id.py` adapter, downloader, job runner, raw file storage | BBCA FY2025 four files downloaded with matching hash/size; `ingestion_jobs` row created |
| **B3 — Parsers** | XBRL instance, inline XBRL, XLSX, PDF parsers; concept registry | 12/12 POC values reproduced by automated tests; parse status recorded |
| **B4 — Normalize/validate/metrics** | Period derivation, validation engine, metric calculator | YTD never summed; `FACT-*`/`XFORM-001` rules fire; publication gate blocks draft rows |
| **B5 — API** | v1 routers and DTOs from §6 | OpenAPI docs list all endpoints; CORS allows only configured origins with `allow_methods` |
| **B6 — Tests** | Pytest + httpx TestClient + parser fixtures | `pytest` green offline; publication-gate and YTD tests included |

**Dependency order:** B0 → B1 → B2/B3 (parallel after B1) → B4 → B5 → B6. B2 must not be parallelized with aggressive retry logic; the source has no published rate limit (see [IDX feasibility](idx-data-source-feasibility.md#33-credentials-restrictions-rate-limits)).

---

## 4. Docker Desktop / local development

### 4.1 Prerequisites

- Docker Desktop for Windows with **WSL2 backend enabled**; Linux containers.
- No host Node, host pip, or Windows venv required inside containers **[V environment finding]** .
- Create `.env` from `.env.example`; never commit `.env`.

### 4.2 Files to add

| File | Purpose |
|---|---|
| `docker-compose.yml` | Service definitions, named volumes, health checks |
| `backend/Dockerfile` | `python:3.11-slim`, install `requirements.txt`, run uvicorn |
| `frontend/Dockerfile` | `node:20-alpine`, `npm install`, run Vite dev server |
| `backend/.dockerignore` | Exclude `venv/`, `__pycache__/`, `.pytest_cache/`, `.env` |
| `frontend/.dockerignore` | Exclude `node_modules/`, `dist/`, `.env*` |
| `.env.example` | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL`, `CORS_ORIGINS`, `IDX_BASE_URL`, `IDX_REQUEST_DELAY_SECONDS`, `IDX_USER_AGENT` |
| `frontend/nginx.conf` | Only if a production-style frontend image is added later; not needed for dev |

Example non-secret values for `.env.example` only:

```dotenv
POSTGRES_USER=finance
POSTGRES_PASSWORD=change-me-locally
POSTGRES_DB=idx_finance
DATABASE_URL=postgresql+psycopg://finance:change-me-locally@db:5432/idx_finance
CORS_ORIGINS=http://localhost:5173
IDX_BASE_URL=https://www.idx.id
IDX_REQUEST_DELAY_SECONDS=1
IDX_USER_AGENT=IDX-Financial-Intelligence/0.1 (local-development)
```

### 4.3 Compose services

| Service | Image/build | Key settings |
|---|---|---|
| `db` | `postgres:16-alpine` | named volume `pgdata:/var/lib/postgresql/data`; env from `.env`; healthcheck `pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}` |
| `api` | `./backend/Dockerfile` | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`; bind `./backend:/app`; anonymous volume `/app/.venv` if used; `depends_on: db: condition: service_healthy`; ports `8000:8000` |
| `frontend` | `./frontend/Dockerfile` | `npm run dev -- --host 0.0.0.0`; bind `./frontend:/app`; anonymous volume `/app/node_modules`; ports `5173:5173`; Vite proxy `/api → http://api:8000` |
| `worker` | same image as `api` | `profiles: ["ingestion"]`; `command: python -m app.ingestion.runner`; shares `raw_docs` volume; `depends_on` db healthy |

Named volumes: `pgdata` (database persists across `docker compose down`), `raw_docs` (downloaded originals persist). Remove volumes only with explicit intent.

### 4.4 Operator commands

```bash
# Start everything
docker compose up --build

# Start detached
docker compose up -d

# Run a one-off BBCA FY2025 annual ingestion
docker compose --profile ingestion run --rm worker \
  python -m app.ingestion.runner --ticker BBCA --year 2025 --period audit

# Follow logs
docker compose logs -f api
docker compose logs -f worker

# Inspect database
docker compose exec db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB}

# Rebuild after dependency changes
docker compose build --no-cache api frontend

# Stop without deleting data
docker compose down

# DELETE volumes (destructive; requires explicit approval)
docker compose down -v
```

### 4.5 Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `api` exits with `ModuleNotFoundError: psycopg` | Dependency not added to `requirements.txt` | Add driver, `docker compose build --no-cache api` |
| `api` starts but first browser call fails | `allow_methods` fix not applied | See [Repository audit](repository-technical-audit.md#4-backend-architecture-and-specific-defects) |
| `db` unhealthy | Wrong `.env` credentials or stale volume | Check `.env`; `docker compose logs db`; only recreate volume with approval |
| Frontend 404 on `/api/*` | Vite proxy missing/wrong target | Verify `vite.config.js` proxy and Compose service name `api` |
| IDX 403 from container | Client headers/TLS behavior differ | Compare with `curl`; use `httpx` with normal headers; do **not** bypass controls |
| Windows CRLF diffs reappear | No `.gitattributes` | Add `.gitattributes` (`* text=auto eol=lf`) in a separate change |
| Disk grows quickly | `raw_docs`/`pgdata` accumulating | Retention policy in data-management module; never `down -v` casually |

---

## 5. Data management workflow

This workflow is implemented by WP2–B4 and surfaced in UI modules 8 and 9 (§8).

```text
1. Select source + company + year + period
   → idempotent discovery call to IDX metadata endpoint

2. Record metadata and attachments
   → financial_documents + document_attachments (pending)

3. Download documents
   → raw_docs volume; verify size + SHA-256; set parse_status='pending'

4. Parse in priority order
   → instance.zip → inlineXBRL.zip → .xlsx → .pdf
   → financial_facts rows with source_fact_id/context/unit untouched

5. Normalize
   → accounts registry/aliases, scale/unit conversion, period derivation

6. Validate
   → DOC-*, FACT-*, XFORM-*, PER-* rules write validation_logs

7. Review (human)
   → warnings may be overridden with reason; errors cannot be ignored

8. Calculate metrics
   → financial_metrics status='draft'

9. Publish (role-gated)
   → PUB-001/PUB-002 pass; status='published'; audit_event written

10. Dashboards read published data only
```

Manual upload uses the already-pinned `python-multipart` but follows the **same** steps 3–10; an uploaded file never bypasses validation or publication.

---

## 6. API surface (v1)

All routes live under `/api/v1`; keep the existing `/api/dashboard` etc. as temporary aliases only if needed during migration, then remove with approval.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/companies` | List issuers with sector filters |
| GET | `/api/v1/companies/{ticker}` | Company metadata + available periods/documents |
| GET | `/api/v1/periods?ticker=BBCA` | Period list with source codes |
| GET | `/api/v1/statements/{ticker}?period=FY2025&statement=balance_sheet&basis=consolidated` | Normalized statement table + source refs |
| GET | `/api/v1/metrics/{ticker}?period=FY2025` | Published ratios/metrics |
| POST | `/api/v1/comparisons` | Compare **max 5** tickers; reject 6th with 422 |
| GET | `/api/v1/sectors/{sector_code}/peers?year=2025` | Sector/peer analytics |
| GET | `/api/v1/documents?ticker=&year=&period=` | Document inventory, hash, parse status |
| POST | `/api/v1/ingestion/jobs` | Enqueue discovery/download/parse job |
| GET | `/api/v1/ingestion/jobs/{id}` | Job status and counters |
| POST | `/api/v1/validation/runs` | Run validation rules for a document/period |
| GET | `/api/v1/validation/logs?status=failed` | Operator queue |
| POST | `/api/v1/publication` | Publish selected metric IDs; requires `publisher`/`admin` role |
| GET | `/health`, `/ready` | Liveness/readiness for Compose |

CORS must use `allow_methods` and explicit origins from `CORS_ORIGINS`; no `allow_origins=["*"]` with credentials.

---

## 7. Backend verification strategy

- `pytest` + `httpx.AsyncClient(ASGITransport)` against the FastAPI app; no live IDX calls in unit tests.
- Parser golden tests use the four BBCA FY2025 files/POC values from [Extraction POC](financial-data-extraction-poc.md) as fixtures.
- `XFORM-001` test asserts exact equality of `Cash` and `Assets` across XBRL instance, XLSX, inline XBRL, and PDF.
- Period test asserts `standalone_Q2 = YTD_Q2 − YTD_Q1`, that summed YTD quarters are rejected, and that a missing Q1 yields "unavailable", not zero.
- Publication test asserts a draft metric with any failed error-severity validation cannot be published, and that a non-role actor receives 403.
- Ingestion adapter tests mock the JSON response shape documented in [IDX feasibility](idx-data-source-feasibility.md#3-access-mechanics-verified) and assert `File_Path` is used verbatim.
- Add `ruff` for linting; run `pytest` and `ruff check` in CI once `.github/workflows/` is introduced.

---

## 8. Frontend / original UI/UX direction

### 8.1 Nine proposed modules

| # | Module | Route | Primary purpose |
|---:|---|---|---|
| 1 | Overview | `/overview` | Selected company snapshot, available periods, data freshness |
| 2 | Financial statements | `/statements` | Balance sheet, income statement, cash flow, equity with source footnotes |
| 3 | Profitability & growth | `/profitability` | Margin trends, ROA/ROE, growth with YTD labels |
| 4 | Cash flow & liquidity | `/cash-flow` | Operating/investing/financing waterfall, current/quick ratios |
| 5 | Ratios & DuPont | `/ratios` | DuPont decomposition, leverage, efficiency |
| 6 | Company comparison | `/comparison` | Up to **5** tickers side-by-side; rank dot/slope charts |
| 7 | Sector & peers | `/sector` | IDX sector/subsector context (BBCA = G. Financials / G1. Banks **[V]**) |
| 8 | Data management | `/data` | Sources, documents, jobs, raw file status, retention |
| 9 | Validation & publication | `/validation` | Failed/warning queue, overrides, publish action, audit history |

Routes are proposals; the module boundaries are what matter. No redesign was performed in Phase 1.

### 8.2 Visual language — "editorial research sheet"

- **Palette:** ink `#111827`, paper `#F7F4ED`, copper `#B46A3C`, deep green `#1F4D43`, oxide red `#A33A2B`. Hairline borders, generous whitespace, no gradients/shadows-as-decoration.
- **Typography:** serif display headings; tabular figures via `font-variant-numeric: tabular-nums`; restrained sans for prose and mono for source IDs/period codes.
- **Shell:** persistent left section navigation; top global filters (year, period, reporting basis, up to 5 tickers); right evidence rail showing source file, concept, context, validation state for the current view.
- **Tables:** right-aligned numbers; indented subtotals; negative values in parentheses and oxide red; missing as `—`; reported zero as `0`; unit stated in header (`IDR millions` / `IDR absolute` toggle).
- **Charts:** slope/dumbbell for period comparison, rank dot plots for peer comparison, cash-flow waterfall, DuPont decomposition. D3 remains the rendering engine; the current generic bar/line/donut trio is retained only where it carries real meaning.
- **Avoid:** KPI-card grids, blue gradient background, multicolour donut-by-default, neon, glassmorphism, arbitrary icons, fake growth badges, decorative fills.
- **Responsive:** desktop-first; evidence rail collapses below tables on tablet; mobile stacks filters and tables horizontally scrollable with frozen first column.
- **Accessibility:** WCAG AA contrast, keyboard-navigable filters/tables, `aria-label` on D3 SVGs, non-colour-only negative/missing indicators.

### 8.3 Frontend work packages

| WP | Deliverable | Exit criteria |
|---|---|---|
| F0 | Fix Tailwind v4 CSS entry, `d3.lineChartRef`, `.append('react')`, typos `from-scale-100`/`ronded-full`, page title | Existing dashboard renders without console errors |
| F1 | Typed API client + query layer + router + global filter store | Filters drive API params; no hardcoded `rawData` |
| F2 | Shell, design tokens, statement table, evidence rail | BBCA FY2025 statement view shows source footnotes from API |
| F3 | Modules 3–7 with D3 chart primitives | Comparison enforces 5-ticker limit; YTD labels shown |
| F4 | Modules 8–9 | Operator can see job/validation status and publish only via role-gated API |
| F5 | Vitest + Playwright smoke tests | Lint/build green in Compose; no visual-regression snapshots of unverified data |

---

## 9. Delivery sequence

| Milestone | Scope | Exit criterion |
|---|---|---|
| **M0 — Foundations** | B0, F0, Docker Compose files, `.env.example`, `.gitattributes` proposal | `docker compose up --build` serves API docs + frontend without errors |
| **M1 — One end-to-end company** | B1, B2, B3, F1, F2 | BBCA FY2025 appears in statement view with source refs; 12 POC values reproduced |
| **M2 — Normalization & trust** | B4, F4 validation half | Validation queue works; publication gate blocks drafts; YTD rules tested |
| **M3 — Analytics** | B5, F3, F4 publication half | Ratios, comparison (max 5), sector views read published metrics only |
| **M4 — Hardening** | B6, F5, CI, docs | `pytest`, `ruff`, `npm run lint`, `npm run build` green; no secrets in repo |

**Not in this plan:** cloud deployment, deleting the committed `backend/venv/` (separate approved cleanup), changing frameworks, publishing unvalidated data, bypassing IDX access controls.

---

## 10. Risk links

Source instability, rate-limit uncertainty, taxonomy diversity, PDF quality, and environment gaps are assessed in [Feasibility report](phase-1-feasibility-report.md#6-risk-assessment). Mitigations are embedded in WP2/WP3 and §4.5 above.
