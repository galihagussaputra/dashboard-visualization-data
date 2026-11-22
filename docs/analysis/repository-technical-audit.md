# Repository Technical Audit

**Scope:** Phase 1 read-only audit of `dashboard-visualization-data`.
**Date:** 2026-11-22
**Status of findings:** Verified by direct file inspection and local commands. No application code was modified.
**Cross-references:** [IDX data feasibility](idx-data-source-feasibility.md), [Extraction POC](financial-data-extraction-poc.md), [Data model](financial-data-model.md), [Implementation plan](technical-implementation-plan.md), [Feasibility report](phase-1-feasibility-report.md).

---

## 1. Executive verdict

The repository is a **minimal React + FastAPI demo scaffold**, not a financial data platform. It contains exactly **16 tracked project files** plus a committed Windows Python virtual environment. There is no database, no ORM, no migration system, no ingestion, no parsing, no validation, no authentication, no test suite, no environment configuration, no container configuration, and no documentation beyond a stale root README and the untouched Vite template README.

The intended stack partially matches reality: React, D3, FastAPI, Pandas, and Tailwind are present. PostgreSQL, Arelle, openpyxl, PyMuPDF/pdfplumber, Pytest, and Docker are **not** present. Crucially, both existing runtime entry points contain defects (see §4 and §5), and the frontend does not call the backend at all.

**Recommendation:** preserve the existing structure (`frontend/`, `backend/`) and the React/FastAPI/D3 choices, but treat the current implementation as a disposable demo layer to be incrementally replaced behind new modules. No large-scale refactor is required to start Phase 2; a small number of correctness fixes and a new layered architecture are required. See [Feasibility report](phase-1-feasibility-report.md#go--conditional-go--no-go).

---

## 2. Repository structure (verified)

```text
dashboard-visualization-data/
├── README.md                     # 19 lines; stale/incorrect structure description
├── backend/
│   ├── main.py                   # 119 lines; the entire backend
│   ├── requirements.txt          # 6 pins
│   └── venv/                     # COMMITTED Windows CPython 3.11 venv (7,964 tracked files, ~184 MB)
├── frontend/
│   ├── .gitignore
│   ├── README.md                 # Unmodified Vite template README
│   ├── eslint.config.js
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── public/vite.svg
│   ├── src/
│   │   ├── App.css               # Unused Vite template CSS
│   │   ├── App.jsx               # 7 lines; renders <Dashboard />
│   │   ├── assets/react.svg
│   │   ├── components/Dashboard.jsx   # 458 lines; all UI logic
│   │   ├── index.css             # Tailwind directives + commented Vite default CSS
│   │   └── main.jsx
│   ├── tailwind.config.js
│   └── vite.config.js
└── docs/analysis/                # NEW: this audit (created during Phase 1)
```

`git ls-files` confirms there are **no** other source files. `git log --oneline` shows 7 commits, ending at `a970897 Main Python`.

### 2.1 Working-tree state

`git status --short` reports all 16 project files and thousands of `backend/venv/` files as modified. `git diff --stat -- . ':(exclude)backend/venv'` shows equal insertion/deletion counts for every file (e.g. `Dashboard.jsx | 914 ++++----`), and a sample diff of `backend/main.py` shows every line removed and re-added with identical content. This is a **CRLF vs LF line-ending artifact** on the Windows checkout, not a content change. No `.gitattributes` exists and `core.autocrlf` is unset.

**Implication:** add `.gitattributes` and a root `.gitignore` in a later phase, and remove the committed venv from version control in a separate, explicitly approved cleanup. Do not do this during Phase 1.

---

## 3. Existing implementation inventory

| Area | State | Evidence |
|---|---|---|
| Frontend framework | **Implemented** | `frontend/package.json:15-16` React 19.2; `src/main.jsx:6-10` `createRoot` + `StrictMode` |
| Build tooling | **Implemented** | Vite 7.2 (`package.json:30`, `vite.config.js:5-7`) |
| Styling | **Partially implemented / broken** | Tailwind 4.1 dependency but Tailwind-3-style `@tailwind base/components/utilities` in `src/index.css:2-4`; `tailwind.config.js` is v3-shaped and not loaded by default in v4 |
| Visualization | **Partially implemented / broken** | D3 7.9 (`package.json:13`), three charts in `Dashboard.jsx:70-304`; see §5 for defects |
| Icons | Implemented | `lucide-react` 0.554 (`package.json:14`) |
| Frontend↔backend integration | **Missing** | No `fetch`, `axios`, or HTTP client anywhere in `frontend/src/`; `Dashboard.jsx:14-50` hardcodes `rawData` |
| Backend framework | **Implemented / partly broken** | FastAPI 0.104.1, single `app` in `backend/main.py:8` |
| REST API | **Implemented (demo only)** | `backend/main.py:75-115`: `/`, `/api/dashboard`, `/api/revenue`, `/api/customers`, `/api/categories` |
| Data layer | **Missing** | No models beyond 4 Pydantic response DTOs (`main.py:20-36`); data is `random.randint` (`main.py:39-72`) |
| Database / migrations | **Missing** | No `sqlalchemy`, `psycopg`, `asyncpg`, `alembic`, `migrations/`, `models/`, or schema files |
| Ingestion / source adapters | **Missing** | No HTTP client or source code |
| Document parsers (XLSX/XBRL/PDF) | **Missing** | No `openpyxl`, `arelle`, `pymupdf`, `pdfplumber` in `requirements.txt` |
| Validation engine | **Missing** | No validation code or validation tables |
| Metric/calculation engine | **Missing** | No ratio formulas |
| Auth / authorization | **Missing** | No users, roles, tokens, or protected routes |
| Background jobs | **Missing** | No worker, queue, or scheduler |
| Tests | **Missing** | No `pytest.ini`, `tests/`, frontend test script, or test files |
| Environment configuration | **Missing** | No `.env`, `.env.example`, or settings module |
| Containerization | **Missing** | No `Dockerfile`, `docker-compose.yml`, `.dockerignore`, or health checks |
| CI/CD | **Missing** | No `.github/workflows/` |
| Documentation | **Minimal** | Root `README.md` describes files that do not exist (`frontend/public/index.html`, `frontend/src/index.jsx`, `backend/data/sample_data.py`) |

---

## 4. Backend architecture and specific defects

`backend/main.py` is a single 119-line module. It defines four Pydantic models (`RevenueData`, `CustomerData`, `CategoryDistribution`, `DashboardData`), a random sample-data generator, and five GET routes.

### Verified defects

1. **CORS middleware raises on first request.** `backend/main.py:15` passes `allow_method=["*"]`; Starlette 0.27 `CORSMiddleware.__init__` accepts `allow_methods` (verified in the committed `backend/venv/Lib/site-packages/starlette/middleware/cors.py:18`). Starlette builds the middleware stack lazily on the first ASGI call (`starlette/applications.py:120-121`), so the server starts but the first HTTP request raises `TypeError: __init__() got an unexpected keyword argument 'allow_method'`.
2. **Month list is malformed.** `backend/main.py:40-41` omits the comma between `'Jun'` and `'Jul'`, producing the single label `'JunJul'` and only 11 data points. The frontend separately hardcodes 12 months, so the two are inconsistent.
3. **Values are random on every request.** `generate_sample_data()` uses `random.randint`, so identical API calls return different numbers. This is unacceptable as a data source for analytics and must not be reused for financial facts.
4. **`datetime` import is unused** (`main.py:6`).
5. **No persistence, no error handling, no pagination, no filtering semantics**, and `year` query parameters are echoed back but ignored (`main.py:93-115`).

### Reusable backend pieces

- FastAPI application instance and OpenAPI docs at `/docs` come free and can be retained.
- Pydantic 2.5 is already available for request/response schemas; extend it with typed DTOs for companies, periods, statements, ratios, validation results, and ingestion job status.
- `python-multipart` 0.0.6 is already pinned, which is useful for the future manual-upload endpoint.
- Pandas 2.1.3 and NumPy 1.26.2 are installed but currently unused; Pandas is a reasonable fit for the normalization layer, but binary wheels in the committed venv are Windows/CPython-3.11-specific.

---

## 5. Frontend architecture and specific defects

`App.jsx` simply renders `DataVisualizationDahsboard` (note the misspelling in `Dashboard.jsx:5` and `:458`). All state and markup live in one 458-line component. Three D3 charts are drawn imperatively into `useRef` containers.

### Verified defects

| Location | Defect |
|---|---|
| `Dashboard.jsx:14-50` | All data is hardcoded (`Produk A`…`E`); no API call exists despite the footer claim "Data dari FastAPI Backend" at `:451` |
| `Dashboard.jsx:155` | `d3.select(d3.lineChartRef.current)` uses a non-existent property on the `d3` object instead of `lineChartRef.current`; the line-chart effect throws at runtime |
| `Dashboard.jsx:116` | Bars are created with `.append('react')`, an invalid SVG element; the bar chart renders no bars |
| `Dashboard.jsx:317` | Tailwind class `from-scale-100` is a typo for `from-slate-100` |
| `Dashboard.jsx:436` | Class `ronded-full` is a typo for `rounded-full` |
| `Dashboard.jsx:6-8, 333-354` | Year/category/chart filter state exists but never affects data |
| `Dashboard.jsx:374, 383, 392, 401` | Growth percentages are hardcoded strings disconnected from the data |
| `src/App.css` | Present but never imported; contains Vite logo animations |
| `src/index.css:1-4` | Tailwind v4 is installed but v3 `@tailwind` directives are used; v4 requires `@import "tailwindcss"` (or an explicit `@config`) |
| `index.html:7` | Page title is still `frontend` |

These defects are **pre-existing**; none were changed during this audit.

### Existing UI/UX assessment against the mandated design direction

The current interface is a recognisable generic starter dashboard: blue-to-slate gradient background, four identical rounded KPI cards with large icons, `shadow-lg rounded-xl` panels, and a blue bar / green line / multicolour donut chart trio. It uses Indonesian labels and `Intl.NumberFormat('id-ID', { currency: 'IDR' })`, which is a useful localisation foundation, but the data itself is fictional. It does not yet satisfy any of the originality requirements in §9 of the brief: no domain-specific information architecture, no evidence/source rail, no differentiated financial table treatment, and no explicit positive/negative/unavailable semantics.

**No redesign was performed.** A proposed visual direction is documented in [Technical implementation plan](technical-implementation-plan.md#8-frontend--original-uiux-direction).

---

## 6. Dependency assessment

### Backend (`backend/requirements.txt`)

| Package | Present | Assessment |
|---|---|---|
| fastapi 0.104.1 | Yes | Keep |
| uvicorn[standard] 0.24.0 | Yes | Keep |
| python-multipart 0.0.6 | Yes | Keep (manual uploads) |
| pydantic 2.5.0 | Yes | Keep |
| pandas 2.1.3 | Yes | Keep for normalization; currently unused |
| numpy 1.26.2 | Yes | Keep (pandas dependency); currently unused |
| PostgreSQL driver (psycopg/asyncpg) | **No** | Add when persistence is implemented |
| SQLAlchemy / Alembic | **No** | Add for ORM + migrations |
| HTTP client (httpx/requests) | **No** | Add for IDX source adapter |
| openpyxl | **No** | Add for XLSX parsing |
| Arelle (`arelle-release`) | **No** | Add for validating XBRL; stdlib XML parsing was sufficient for the POC but not for taxonomy validation |
| PyMuPDF / pdfplumber | **No** | Add for production PDF fallback |
| pytest / pytest-asyncio / httpx test client | **No** | Add for the proposed test strategy |
| python-dotenv / pydantic-settings | **No** | Add for `.env` configuration |

### Frontend (`frontend/package.json`)

| Package | Present | Assessment |
|---|---|---|
| react 19.2, react-dom 19.2 | Yes | Keep |
| d3 7.9 | Yes | Keep |
| lucide-react 0.554 | Yes | Keep, but use only functional icons (brief forbids arbitrary icons) |
| vite 7.2, @vitejs/plugin-react 5.1 | Yes | Keep |
| tailwindcss 4.1, postcss, autoprefixer | Yes | Keep, but fix CSS configuration |
| eslint 9 + react-hooks + react-refresh | Yes | Keep |
| Router | **No** | Add for 9 dashboard modules |
| Server-state/data-fetching library | **No** | Recommend TanStack Query or a small typed API layer |
| Test tooling (Vitest / Testing Library / Playwright) | **No** | Add in Phase 2 |
| Tabular/editorial web fonts | **No** | Add for the proposed design system |

### Environment note

The audit environment has Python 3.14, npm 11.12.1, Docker CLI/daemon 29.7.2, but **no `node` binary, no `pip`, and no installed `node_modules`**. Consequently `npm run lint`, `npm run build`, and Pytest could not be executed here; findings about frontend runtime defects are based on static source inspection. Docker Desktop on Windows is expected to supply Node inside the frontend container, which avoids requiring a host Node install.

The committed `backend/venv` is a **Windows CPython 3.11** environment (`pyvenv.cfg` points to `C:\Users\...\Python3.11`) and is unusable on Linux or in a Linux container. It must be excluded from Docker build contexts (`.dockerignore`) and eventually untracked.

---

## 7. What can be reused, what needs modification, what is missing

### Reuse as-is
- Repository split into `frontend/` and `backend/`.
- FastAPI app + `/docs` + Pydantic response-model pattern.
- React 19 + Vite 7 + D3 7 dependency choices.
- `Intl.NumberFormat('id-ID', …)` currency formatting helper in `Dashboard.jsx:52-59`.
- The concept of a filter bar and export action, once rewired to real data.

### Modify (small, justified changes)
- Fix `allow_method` → `allow_methods` before any browser integration.
- Fix `d3.lineChartRef` → `lineChartRef` and `.append('react')` → `.append('rect')` if the demo charts are kept during transition.
- Fix Tailwind v4 CSS entrypoint and the two class typos.
- Replace `random` sample generation with repository-backed data via new modules; do not reuse it for financial values.
- Add `.gitattributes`, root `.gitignore`, `.dockerignore`.

### Missing and required for the product
- PostgreSQL schema, migrations, and persistence layer (see [Data model](financial-data-model.md)).
- Source adapters, parsers, normalization, validation, calculation, comparison, sector analytics.
- REST API surface for all nine dashboard modules.
- Global filters, company selector (max 5), statement tables, ratio views, comparison and sector views, data-management and validation UI.
- Containerized local environment with Docker Desktop + Compose (see [Implementation plan](technical-implementation-plan.md#4-docker-desktop--local-development)).
- Tests, environment configuration, documentation, deployment configuration.

### Architectural conflicts

| Conflict | Resolution |
|---|---|
| Frontend hardcodes data; backend generates random data | Introduce a real API contract and a data-access layer; keep both frameworks |
| Single 458-line component vs. nine modules | Add routing and feature directories incrementally; do not rewrite D3 chart primitives at once |
| Tailwind 4 installed but configured as v3 | Align CSS configuration first; this is a two-line fix, not a framework replacement |
| Windows-only committed venv vs. Linux containers | Ignore it in Docker and remove it from git in a later, explicit cleanup |
| No auth model but manual publication must be authorized | Add minimal role model before enabling publication endpoints |
| Demo response DTOs named `RevenueData`/`CustomerData` | Replace with domain DTOs; no existing external consumers to preserve |

---

## 8. Audit method and evidence

- `git ls-files`, `git status --short`, `git log --oneline -10`, `git diff --stat` — tracked files, history, line-ending diagnosis.
- Direct reads of all 16 project files.
- `python3` inspection of Starlette 0.27 sources inside the committed venv to confirm `allow_methods` and lazy middleware construction.
- `python3 --version`, `node --version`, `docker --version`, `docker info`, `du -sh backend/venv`, `git ls-files backend/venv | wc -l`.
- No application files were edited; only `docs/analysis/` was created.
