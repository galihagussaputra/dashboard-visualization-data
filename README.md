# dashboard-visualization-data

IDX Financial Intelligence is a multi-company financial analytics application for Indonesian Stock Exchange-listed issuers.

The repository preserves the original React/Vite frontend and FastAPI backend while adding a PostgreSQL data layer, controlled ingestion, validation, and an editorial financial research interface.

## Structure

```text
backend/
  main.py                 compatibility entry point
  app/
    main.py               FastAPI application
    api/v1/               versioned API routers
    core/                 config, database, logging, errors
    ingestion/            IDX source adapter and job runner
    models/               SQLAlchemy models (M1+)
    parsers/              XBRL/XLSX/PDF parsers (M1+)
    normalization/        account and period normalization (M1-M2)
    validation/           validation rules and engine (M2+)
    metrics/              ratio definitions and calculator (M2+)
  tests/
frontend/
  src/
    app/                  shell and routing
    components/           shared components and legacy demo
    features/             nine product modules
    lib/                  API client and formatters
    styles/               editorial design tokens
docs/
  analysis/               approved Phase 1 feasibility baseline
  implementation/         Phase 2 decisions and operational guides
```

The committed `backend/venv/` is legacy Windows content. It is ignored for new work and excluded from Docker builds; untracking it requires explicit approval.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: `http://localhost:${FRONTEND_PORT:-5173}` (`FRONTEND_PORT=5174 docker compose up -d` if 5173 is occupied)
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/v1/health`
- Statement API: `http://localhost:8000/api/v1/statements/BBCA?period=FY2025&statement=balance_sheet&basis=consolidated`

Seed the draft BBCA FY2025 source-backed view:

```bash
docker compose exec api alembic upgrade head
docker compose --profile ingestion run --rm worker python -m app.ingestion.runner --ticker BBCA --year 2025 --period audit --source fixture
```

The statement view is at `#/performance` and is draft/internal only until later publication gates pass.

Seed local M2 review users:

```bash
M2_ADMIN_PASSWORD='local-admin-password' \
M2_ANALYST_PASSWORD='local-analyst-password' \
docker compose exec -e M2_ADMIN_PASSWORD -e M2_ANALYST_PASSWORD api \
python -m app.cli.seed_users
```

Use `#/validation` for validation, metric recalculation, publication controls, and `#/audit` for publication history, restatements, and audit events. Published reads require an active publication event; draft reads remain available for local review.

See [Docker Development Guide](docs/implementation/docker-development-guide.md) for operations and troubleshooting.

## Data integrity rules

- Never fabricate financial data.
- Never replace missing values with zero.
- Never mix consolidated and separate statements.
- Never sum cumulative YTD periods.
- Never publish data that failed validation.
- Preserve source documents, contexts, units, currency, and audit history.

## Documentation

- [Phase 1 execution assessment](docs/implementation/phase-2-execution-plan.md)
- [Architecture decisions](docs/implementation/architecture-decisions.md)
- [Database schema](docs/implementation/database-schema.md)
- [Financial data pipeline](docs/implementation/financial-data-pipeline.md)
- [Financial validation rules](docs/implementation/financial-validation-rules.md)
- [Testing and QA](docs/implementation/testing-and-qa.md)
- [Docker Development Guide](docs/implementation/docker-development-guide.md)
- [Phase 1 analysis](docs/analysis/phase-1-feasibility-report.md)
