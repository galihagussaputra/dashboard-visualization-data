# Docker Development Guide

**Status:** M1 quality gate passed. Update as later milestones add validation, publication and analytics.

---

## Prerequisites

- Docker Desktop for Windows with WSL2 integration enabled and Linux containers.
- Docker Compose v2+ (`docker compose version`).
- No host Python packages, host `node`, or committed Windows venv are required.

---

## Initial setup

```bash
cp .env.example .env
docker compose up --build
```

Services:

| Service | URL | Purpose |
|---|---|---|
| `frontend` | `http://localhost:${FRONTEND_PORT:-5173}` | React application |
| `api` | `http://localhost:8000` | FastAPI v1 API |
| `api docs` | `http://localhost:8000/docs` | OpenAPI UI |
| `db` | internal only | PostgreSQL 16 |

The database port is intentionally not published to the host. Use `docker compose exec db psql ...`.

If host port 5173 is already occupied, set `FRONTEND_PORT` before starting Compose, for example `FRONTEND_PORT=5174 docker compose up -d`. Leave `CORS_ORIGINS` unchanged when using the Vite `/api` proxy.

---

## Environment variables

`.env.example` is committed; `.env` is ignored and must contain local values only.

| Variable | Used by | Purpose |
|---|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | `db` | Database bootstrap |
| `DATABASE_URL` | `api`, `worker` | SQLAlchemy connection string |
| `CORS_ORIGINS` | `api` | Comma-separated browser origins |
| `LOG_LEVEL`, `ENVIRONMENT` | `api`, `worker` | Logging and runtime behavior |
| `IDX_BASE_URL` | `worker` | Configurable source host; use `https://www.idx.id` |
| `IDX_REQUEST_DELAY_SECONDS` | `worker` | Conservative request spacing |
| `IDX_USER_AGENT` | `worker` | Honest application identification |
| `VITE_API_BASE_URL` | `frontend` | Browser API prefix |
| `FRONTEND_PORT` | `frontend` | Host port mapped to container port 5173; defaults to 5173 |

Never commit a real `.env`.

---

## Common operations

```bash
docker compose up -d
docker compose ps
docker compose logs -f api
docker compose logs -f frontend
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
docker compose exec api python -m pytest
docker compose exec api ruff check .
docker compose exec frontend npm run lint
docker compose exec frontend npm run build

docker compose --profile ingestion run --rm worker \
  python -m app.ingestion.runner --ticker BBCA --year 2025 --period audit

docker compose down
```

`docker compose down` preserves the `pgdata` and `raw_docs` named volumes. `docker compose down -v` deletes them and requires explicit approval.

---

## Health checks

- API liveness: `GET http://localhost:8000/api/v1/health`
- API readiness: `GET http://localhost:8000/api/v1/ready`
- DB: `pg_isready` inside the `db` container
- Frontend: `wget http://127.0.0.1:5173/` inside the `frontend` container; host URL uses `${FRONTEND_PORT:-5173}`

`/ready` reports `database.status = unavailable` if PostgreSQL is unreachable; it does not expose connection strings or passwords.

---

## Troubleshooting

| Symptom | Action |
|---|---|
| `api` cannot connect to `db` | Confirm `db` is healthy with `docker compose ps`; check `DATABASE_URL` uses host `db`, not `localhost` |
| CORS error in browser | Confirm `CORS_ORIGINS` matches the direct browser API origin; Vite proxy usage does not require an alternate origin |
| Port 5173 already allocated | Set `FRONTEND_PORT=5174` (or another free port) and restart `frontend`; do not stop unrelated containers |
| Frontend `/api/*` 404 | Confirm `VITE_API_BASE_URL=/api` and Vite proxy target `http://api:8000` |
| Fixture ingestion must be rerun | `docker compose --profile ingestion run --rm worker python -m app.ingestion.runner --ticker BBCA --year 2025 --period audit --source fixture` |
| Statement view is empty | Confirm the ingestion job is `validated` and the selected basis is `consolidated` |
| `npm install` changes lockfile | Review `frontend/package-lock.json` before committing |
| Stale image after dependency edits | `docker compose build --no-cache api frontend` |
| Need a clean database | Requires explicit approval; do not run `docker compose down -v` casually |

---

## Data persistence

- `pgdata`: PostgreSQL data directory.
- `raw_docs`: original source documents downloaded by the ingestion worker.
- `frontend_node_modules`: anonymous dependency cache for the Vite container.

No volume is deleted by this milestone.

---

## Migration commands

The M1 initial schema migration is `a70b95fcb2e3_initial_m1_schema.py`.

```bash
docker compose exec api alembic current
docker compose exec api alembic upgrade head
docker compose exec api alembic downgrade -1
```

The migration was downgraded and reapplied once while the schema was empty. Downgrades that drop tables or columns require explicit approval if they affect stored data.
