# Testing and QA

**Status:** Phase 2, milestone M2 final regression.
**Scope:** M1 regression, M2 unit and API tests, lint/build checks, migration checks, and endpoint evidence.

## Commands

```bash
docker compose exec api ruff check .
docker compose exec api python -m pytest -q
docker compose exec frontend npm run lint
docker compose exec frontend npm run build
docker compose exec api alembic current
docker compose exec api alembic history
```

## Test coverage

| File | Coverage |
| --- | --- |
| `backend/tests/test_m1_reconciliation.py` | M1 12/12 source-format reconciliation and validation gates. |
| `backend/tests/test_m1_api.py` | M1 catalog, document, statement, and job APIs. |
| `backend/tests/test_m2_account_mapping.py` | Exact taxonomy, source name preservation, unknown/ambiguous handling, industry isolation, taxonomy specificity, rule versioning, rejected rules. |
| `backend/tests/test_m2_periods.py` | Instant/duration classification, all supported quarter derivations, missing inputs, basis/currency/unit/scale guards, restatement review, duplicate context, negative values, fiscal-year mismatch. |
| `backend/tests/test_m2_metrics.py` | Average-balance ratios, direct ratios, inventory turnover, free cash flow, zero denominators, missing inputs, negative values, incompatible period/basis/unit, formula version, timestamp behavior. |
| `backend/tests/test_m2_api.py` | Auth requirement, login/current user, statement provenance, validation workflow statuses, publisher role enforcement. |

## Final results

| Check | Result |
| --- | --- |
| `ruff check .` | Pass |
| `python -m pytest -q` | `53 passed, 5 warnings` |
| `npm run lint` | Pass; no errors or warnings |
| `npm run build` | Pass; Vite production bundle generated |
| `alembic current` | `d4e7b9c1a2f3 (head)` |
| Login endpoint | `200` |
| Period derivation endpoint | `200` |
| Metric recalculation endpoint | `200`, 11 current metrics persisted |
| Validation run endpoint | `200`, status `validated`, 0 issues, `can_publish=true` |
| Draft statement endpoint | `200`, 5 facts, provenance fields present |
| Published statement endpoint without publication | `404`, confirming no default publication |
| Real IDX requests | None issued during M2 |
| Publication performed | No; real Phase 1 fixture data was not published |

## Manual QA evidence

- `GET /api/v1/statements/BBCA?period=2025&statement=balance_sheet&basis=consolidated&visibility=draft` returns cash, assets, liabilities, equity, and syirkah facts with `standard_account=CASH` for cash and `period_kind=instant` for instant facts.
- The same request with `visibility=published` returns `404` because no publication event exists.
- `POST /api/v1/metrics/recalculate` persists all 11 `m2-v1` metric rows. `NET_PROFIT_MARGIN` is calculated; other metrics remain `unavailable` with explicit missing-input reasons instead of fabricated values.
- `POST /api/v1/validation/run` groups findings under a `validation_run` and completes with `validated`.
- CORS remains restricted to configured origins with credentials enabled; sensitive endpoints require bearer tokens and roles.

## Known non-blockers

- The three pytest warnings are SWIG deprecation notices emitted by the offline Arelle dependency at import time.
- Frontend lint reports a stale `baseline-browser-mapping` advisory from the installed dependency; it is not an ESLint error.
- Missing opening balances and several standard accounts in the fixture produce explicit unavailable metric reasons; this is intentional and preferable to invented values.
