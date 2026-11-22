# Financial Data Model

**Date:** 2026-11-22
**Status:** Proposed target schema for Phase 2; no database or migration was created during Phase 1.
**Evidence classification:** **[V]** verified from POC/source documents; **[F]** feasible design choice; **[A]** assumption to confirm with more companies.
**Cross-references:** [Repository audit](repository-technical-audit.md), [IDX feasibility](idx-data-source-feasibility.md), [Extraction POC](financial-data-extraction-poc.md), [Implementation plan](technical-implementation-plan.md), [Feasibility report](phase-1-feasibility-report.md).

---

## 1. Design principles

1. **Source-first:** every stored fact must resolve to a downloaded document, a source concept/context, and an ingestion job. No value is stored without provenance **[V requirement from POC]**.
2. **Append-only facts:** ingestion creates new versions; it never overwrites a previously published value. Restatements are linked, not deleted **[F]**.
3. **Original and normalized side by side:** retain `value_original`, `scale`, `unit`, `decimals` exactly as parsed and derive `value_normalized` in base currency/unit **[V]**.
4. **Missing ≠ zero:** an omitted concept is `NULL`/absent; a reported `0.0` is a real value. BBCA FY2025 explicitly reports zeros **[V]**.
5. **Use `NUMERIC`, never `FLOAT`**, for financial values. PostgreSQL `NUMERIC(38,10)` comfortably covers IDR absolute values and ratios **[F]**.
6. **Taxonomy-aware, not taxonomy-hardcoded:** keys are concept codes + taxonomy version; aliases handle label differences across entry points (Financial/Sharia vs General) **[V for BBCA; A for others]**.
7. **Consolidated vs separate is explicit:** the BBCA sample is "Entitas grup / Group entity" **[V]**; this attribute must be stored per fact/document, not inferred.
8. **Quarterly values are YTD by default:** never sum cumulative quarters. Derive standalone quarters only through validated differences (§6) **[V requirement]** .
9. **Publication is a separate, role-gated state:** parsing/writing facts does not make them visible to dashboards (§8).
10. **No fabricated or placeholder financial figures** in production tables. Test fixtures must be verified source extracts or clearly labeled non-production test data **[V requirement]** .

---

## 2. Entity overview

| Entity | Purpose | Natural / uniqueness key |
|---|---|---|
| `data_sources` | Configured source systems (IDX, OJK manuals) | `code` |
| `sectors` | IDX sector / subsector / industry classification | `code` |
| `companies` | Issuer master | `ticker` |
| `company_sectors` | Historical sector assignment if an issuer reclassifies | `(company_id, sector_id, valid_from)` |
| `financial_periods` | Company-specific fiscal periods with calendar mapping | `(company_id, fiscal_year, period_type, period_sequence)` |
| `taxonomy_versions` | IDX Taxonomy 2014 / 2020 / future versions | `(code, version)` |
| `financial_documents` | Downloaded original files and their metadata | `(data_source_id, source_document_id, file_type)` |
| `document_attachments` | Additional PDFs attached to a filing | `(financial_document_id, source_file_id)` |
| `financial_accounts` | Taxonomy concept definitions | `(taxonomy_version_id, concept_code)` |
| `account_aliases` | Localized/vendor labels mapped to concepts | `(account_id, alias, source)` |
| `financial_facts` | Parsed, versioned accounting facts | `(financial_document_id, source_fact_id)` plus current-version partial index |
| `metric_definitions` | Ratio / derived metric formulas with versioning | `(code, version)` |
| `financial_metrics` | Calculated metric values linked to source facts | `(company_id, period_id, metric_definition_id, is_current)` |
| `ingestion_jobs` | Discovery/download/parse run audit | `id` |
| `validation_logs` | Rule results per document/fact/metric | `(rule_code, entity_type, entity_id, run_id)` |
| `audit_events` | Human/system actions, especially publication | `id` |
| `users`, `roles`, `user_roles` | Minimal authorization for manual publication | `users.email`, `roles.name` |

---

## 3. Core schema (PostgreSQL, indicative DDL)

The following is a design specification, not applied migration code. Column names are final recommendations.

### 3.1 Master data

```sql
CREATE TABLE data_sources (
  id            BIGSERIAL PRIMARY KEY,
  code          VARCHAR(40) NOT NULL UNIQUE,
  display_name  VARCHAR(160) NOT NULL,
  base_url      TEXT NOT NULL,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sectors (
  id          BIGSERIAL PRIMARY KEY,
  code        VARCHAR(30) NOT NULL UNIQUE,
  sector      VARCHAR(80) NOT NULL,
  subsector   VARCHAR(80),
  industry    VARCHAR(80),
  subindustry VARCHAR(80),
  taxonomy_entry_point VARCHAR(80)
);

CREATE TABLE companies (
  id                 BIGSERIAL PRIMARY KEY,
  ticker             VARCHAR(10) NOT NULL UNIQUE,
  name               TEXT NOT NULL,
  source_company_id  VARCHAR(40),
  data_source_id     BIGINT NOT NULL REFERENCES data_sources(id),
  accounting_standard VARCHAR(30),
  reporting_basis_default VARCHAR(20) NOT NULL DEFAULT 'unknown'
                       CHECK (reporting_basis_default IN ('consolidated','separate','unknown')),
  is_active          BOOLEAN NOT NULL DEFAULT TRUE,
  metadata           JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

BBCA metadata from the sample maps directly: `ticker='BBCA'`, `name='PT Bank Central Asia Tbk.'`, `accounting_standard='PSAK'`, `reporting_basis_default='consolidated'`, sector `G. Financials` / `G1. Banks` **[V]**.

### 3.2 Periods

```sql
CREATE TABLE financial_periods (
  id                 BIGSERIAL PRIMARY KEY,
  company_id         BIGINT NOT NULL REFERENCES companies(id),
  fiscal_year        SMALLINT NOT NULL,
  calendar_year      SMALLINT NOT NULL,
  period_type        VARCHAR(10) NOT NULL CHECK (period_type IN ('Q1','Q2','Q3','FY')),
  period_sequence    SMALLINT NOT NULL CHECK (period_sequence BETWEEN 1 AND 4),
  is_ytd             BOOLEAN NOT NULL,
  start_date         DATE NOT NULL,
  end_date           DATE NOT NULL,
  instant_date       DATE NOT NULL,
  source_period_code VARCHAR(20) NOT NULL,
  label              VARCHAR(40) NOT NULL,
  UNIQUE (company_id, fiscal_year, period_type, period_sequence)
);
```

`source_period_code` stores the IDX value (`tw1`, `tw2`, `tw3`, `audit`) without translating it away **[V]**. `label` is the UI-facing value (`FY2025 Q2 (YTD)`, `FY2025 Annual`). For annual data, `start_date`/`end_date` span the fiscal year and `instant_date` is the balance-sheet date (2025-12-31 for BBCA) **[V]**.

### 3.3 Documents

```sql
CREATE TABLE financial_documents (
  id                 BIGSERIAL PRIMARY KEY,
  data_source_id     BIGINT NOT NULL REFERENCES data_sources(id),
  company_id         BIGINT NOT NULL REFERENCES companies(id),
  period_id          BIGINT NOT NULL REFERENCES financial_periods(id),
  source_document_id TEXT NOT NULL,
  source_file_id     TEXT,
  file_name          TEXT NOT NULL,
  file_type          VARCHAR(12) NOT NULL CHECK (file_type IN ('.xlsx','.pdf','.zip','.xbrl','.html')),
  file_role          VARCHAR(20) NOT NULL
                     CHECK (file_role IN ('instance_xbrl','inline_xbrl','spreadsheet','pdf','annual_report','other')),
  source_url         TEXT NOT NULL,
  raw_storage_path   TEXT NOT NULL,
  file_size_bytes    BIGINT,
  source_file_size   BIGINT,
  sha256             CHAR(64),
  downloaded_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  parse_status       VARCHAR(20) NOT NULL DEFAULT 'pending'
                     CHECK (parse_status IN ('pending','parsed','warning','failed','skipped')),
  parsed_at          TIMESTAMPTZ,
  source_metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
  ingestion_job_id   BIGINT REFERENCES ingestion_jobs(id),
  UNIQUE (data_source_id, source_document_id, file_type, file_role)
);
```

`source_url` is the full resolved URL built from the API-supplied `File_Path` only; it must never be guessed **[V requirement]** . `source_metadata` keeps the entire `Attachments` object, including `File_ID`, `Report_Period`, `Report_Year`, and `File_Size` **[V]**.

### 3.4 Accounts and aliases

```sql
CREATE TABLE taxonomy_versions (
  id          BIGSERIAL PRIMARY KEY,
  code        VARCHAR(40) NOT NULL,
  version     VARCHAR(20) NOT NULL,
  namespace   TEXT NOT NULL,
  entry_points JSONB NOT NULL DEFAULT '[]'::jsonb,
  source_url  TEXT,
  UNIQUE (code, version)
);

CREATE TABLE financial_accounts (
  id                BIGSERIAL PRIMARY KEY,
  taxonomy_version_id BIGINT NOT NULL REFERENCES taxonomy_versions(id),
  concept_code      VARCHAR(120) NOT NULL,
  concept_qname     VARCHAR(180) NOT NULL,
  namespace         TEXT NOT NULL,
  label_id          TEXT,
  label_en          TEXT,
  statement_type    VARCHAR(30) NOT NULL
                    CHECK (statement_type IN ('balance_sheet','income_statement','cash_flow','equity','comprehensive_income','notes','dei','unknown')),
  normal_sign       SMALLINT NOT NULL DEFAULT 1 CHECK (normal_sign IN (-1,0,1)),
  data_type         VARCHAR(20) NOT NULL DEFAULT 'monetary'
                    CHECK (data_type IN ('monetary','shares','per_share','percentage','text','boolean')),
  unit_hint         VARCHAR(50),
  parent_account_id BIGINT REFERENCES financial_accounts(id),
  is_abstract       BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (taxonomy_version_id, concept_code)
);

CREATE TABLE account_aliases (
  id         BIGSERIAL PRIMARY KEY,
  account_id BIGINT NOT NULL REFERENCES financial_accounts(id),
  alias      TEXT NOT NULL,
  locale     VARCHAR(10) NOT NULL DEFAULT 'id',
  source     VARCHAR(40) NOT NULL DEFAULT 'idx',
  UNIQUE (account_id, alias, locale, source)
);
```

Examples: `idx-cor:Assets` → `statement_type='balance_sheet'`, `normal_sign=1`, `unit_hint='IDR'`; `idx-cor:BasicEarningsLossPerShareFromContinuingOperations` → `data_type='per_share'`, `unit_hint='IDRPerShares'` **[V]**. Aliases store `Jumlah aset`, `Total assets`, and XLSX sheet-style labels without changing the primary concept.

### 3.5 Facts

```sql
CREATE TABLE financial_facts (
  id                    BIGSERIAL PRIMARY KEY,
  company_id            BIGINT NOT NULL REFERENCES companies(id),
  period_id             BIGINT NOT NULL REFERENCES financial_periods(id),
  document_id           BIGINT NOT NULL REFERENCES financial_documents(id),
  account_id            BIGINT NOT NULL REFERENCES financial_accounts(id),
  ingestion_job_id      BIGINT NOT NULL REFERENCES ingestion_jobs(id),
  source_fact_id        TEXT NOT NULL,
  source_context_ref    TEXT NOT NULL,
  context_start_date    DATE,
  context_end_date      DATE,
  context_instant_date  DATE,
  value_original        TEXT NOT NULL,
  value_normalized      NUMERIC(38,10) NOT NULL,
  currency              CHAR(3),
  unit                  VARCHAR(50) NOT NULL,
  source_scale          INTEGER NOT NULL DEFAULT 0,
  source_decimals       VARCHAR(10),
  reporting_basis       VARCHAR(20) NOT NULL
                        CHECK (reporting_basis IN ('consolidated','separate','unknown')),
  is_restated           BOOLEAN NOT NULL DEFAULT FALSE,
  fact_version          INTEGER NOT NULL DEFAULT 1,
  is_current            BOOLEAN NOT NULL DEFAULT TRUE,
  superseded_by         BIGINT REFERENCES financial_facts(id),
  validation_status     VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (validation_status IN ('pending','passed','warning','failed','overridden')),
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (document_id, source_fact_id, fact_version)
);
CREATE INDEX idx_facts_current ON financial_facts
  (company_id, period_id, account_id) WHERE is_current;
CREATE INDEX idx_facts_document ON financial_facts (document_id);
```

BBCA FY2025 `instance.xbrl` fact `IXF4220000E02_0027_00001_01_0001` becomes one row with `value_original='1586828536000000'`, `value_normalized=1586828536000000`, `source_scale=0`, `unit='IDR'`, `context_instant_date='2025-12-31'`, `source_context_ref='CurrentYearInstant'`, `reporting_basis='consolidated'` **[V]**.

### 3.6 Metrics and workflow tables

```sql
CREATE TABLE metric_definitions (
  id             BIGSERIAL PRIMARY KEY,
  code           VARCHAR(60) NOT NULL,
  name           VARCHAR(160) NOT NULL,
  version        VARCHAR(20) NOT NULL,
  category       VARCHAR(40) NOT NULL,
  unit           VARCHAR(50) NOT NULL,
  formula        JSONB NOT NULL,
  dependencies   JSONB NOT NULL DEFAULT '[]'::jsonb,
  applicable_entry_points JSONB NOT NULL DEFAULT '[]'::jsonb,
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE (code, version)
);

CREATE TABLE financial_metrics (
  id                    BIGSERIAL PRIMARY KEY,
  company_id            BIGINT NOT NULL REFERENCES companies(id),
  period_id             BIGINT NOT NULL REFERENCES financial_periods(id),
  metric_definition_id  BIGINT NOT NULL REFERENCES metric_definitions(id),
  value                 NUMERIC(38,10) NOT NULL,
  unit                  VARCHAR(50) NOT NULL,
  source_fact_ids       JSONB NOT NULL DEFAULT '[]'::jsonb,
  formula_version       VARCHAR(20) NOT NULL,
  is_derived_from_ytd   BOOLEAN NOT NULL DEFAULT FALSE,
  status                VARCHAR(20) NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','validated','published','rejected')),
  is_current            BOOLEAN NOT NULL DEFAULT TRUE,
  computed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  published_at          TIMESTAMPTZ,
  published_by          BIGINT REFERENCES users(id),
  UNIQUE (company_id, period_id, metric_definition_id, is_current, computed_at)
);
```

`ingestion_jobs`, `validation_logs`, `audit_events`, `users`, `roles`, and `user_roles` follow conventional designs: job parameters as `JSONB`, timestamps, status enums, error messages, actor IDs, and immutable before/after JSON. `validation_logs` must store `expected_value`, `actual_value`, `severity`, and `override_reason` so that a human waiver is itself auditable.

---

## 4. Identifier and naming conventions

| Concept | Convention | Example |
|---|---|---|
| Ticker | Uppercase exchange code | `BBCA` |
| Company period | `FY<year>-<Q1|Q2|Q3|FY>` | `FY2025-Q2` |
| Source period code | Verbatim IDX value | `tw2`, `audit` |
| Concept | `idx-<namespace>:<ElementName>` | `idx-cor:Assets` |
| Fact ID | Verbatim XBRL `id` when present; deterministic `<document_id>:<sheet>:<cell>` otherwise | `IXF4220000E02_0027_00001_01_0001` |
| Document ID | IDX `File_ID` / `File_Path` preserved | from API metadata |
| Hash | Lowercase SHA-256 hex | `CHAR(64)` |
| Metric code | Snake case, category-prefixed | `profitability_roe`, `liquidity_current_ratio` |
| Validation rule | `<PREFIX>-<NNN>` | `FACT-003` |

Do not encode scale or units in column names. `value_normalized` always means base unit (`IDR`, `IDRPerShares`, ratio decimal, etc.), described by `unit`.

---

## 5. Source traceability

```text
company → financial_period → financial_document → financial_fact → financial_metric
             │                       │                   │
             └── source_period_code  └── source_url/hash └── source_fact_ids/context
```

Rules **[V requirement]**:

- Keep the raw downloaded file on disk with `raw_storage_path`; never parse from a re-encoded copy only.
- Store the full API `Attachments` object in `source_metadata`.
- Verify `sha256` and `file_size_bytes` before parsing; a mismatch blocks ingestion and creates `DOC-001` failure.
- A metric cannot be published if any contributing fact is missing, failed validation, or superseded.
- UI "evidence rail" (see [Implementation plan](technical-implementation-plan.md#8-frontend--original-uiux-direction)) reads these links to show source file, concept, context, and validation state.

---

## 6. Financial period normalization

This is the highest-risk modeling area.

### 6.1 Rules

1. IDX `tw1/tw2/tw3/audit` are **year-to-date** for flow statements. Q2 contains Jan–Jun, Q3 contains Jan–Sep, audit contains the full year **[V for annual BBCA; A for quarterly but standard IDX practice]**.
2. Never sum Q1 + Q2 + Q3 + FY. That double-counts.
3. Balance-sheet accounts are **instants** (`context_instant_date`), not durations. Never derive an "average assets" by summing quarterly instants; use an explicit average formula if a metric requires it **[V]**.
4. Annual FY is the authoritative annual value; it is not "Q4" in the user interface unless explicitly labeled **FY2025 Annual**.
5. A standalone quarter may be derived **only** when all of the following hold **[F]**:
   - same `company_id`, same `fiscal_year`, same `account_id`, same `reporting_basis`;
   - both YTD facts exist, are `is_current`, and have `validation_status IN ('passed','warning','overridden')`;
   - units and scales normalize identically;
   - the later period's `end_date` is strictly after the earlier period's;
   - a restated later YTD uses the restated earlier YTD if available, otherwise the derivation is blocked.
6. Derived values are stored in `financial_metrics` with `is_derived_from_ytd=TRUE` and `source_fact_ids` containing both inputs. They are **not** inserted into `financial_facts` **[F]**.

### 6.2 Derivation formulas

```text
standalone_Q1 = YTD_Q1
standalone_Q2 = YTD_Q2 − YTD_Q1
standalone_Q3 = YTD_Q3 − YTD_Q2
standalone_Q4 = FY − YTD_Q3     (only if explicitly requested and validated)
annual         = FY             (never derived from quarterly sums)
```

If `YTD_Q1` is absent (e.g. the confirmed FY2024 Q1 gap for BBCA/BBRI/TLKM/ASII **[V]**), then `standalone_Q2` and `standalone_Q3` derived from it must be marked unavailable; the UI shows `—`, not `0` and not an estimate **[V requirement]** .

### 6.3 Restatements

When a company republishes an earlier period:

- create a new `financial_fact` row with `fact_version = old + 1`;
- set old row `is_current=FALSE`, `superseded_by=new_id`, keep original bytes;
- set new row `is_restated=TRUE`;
- re-run dependent metrics and validation;
- append an `audit_event` with the source document and reason.

---

## 7. Account normalization and taxonomy handling

1. **Primary key is concept code**, not label. `Jumlah aset` and `Total assets` are aliases of `idx-cor:Assets` **[V]**.
2. **Entry points differ.** BBCA uses Financial and Sharia; general issuers use General/Other entry points. A universal "revenue" alias must map `InterestIncome` for banks and `Revenue`/`SalesRevenueNet`-style concepts for non-banks, with `applicable_entry_points` on the metric definition **[V for BBCA; F for general]**.
3. **Scale handling:** XBRL instance has no `scale` and absolute values; inline XBRL uses `scale="6"`; XLSX/PDF display in millions **[V]**. Normalize with `value_normalized = value_original × 10^source_scale` only for display-scaled sources; for XBRL instance, `source_scale=0`.
4. **Sign handling:** preserve original sign; `normal_sign` on account definitions supports display conventions, but never silently flip a stored fact. Negative cash flows arrive as `-33,690,926,000,000` in XBRL and `(33,690,926)` in display **[V]**.
5. **Special units:** EPS uses `IDRPerShares` with `decimals="INF"` **[V]**; percentages use decimal ratios or a `percentage` unit consistently, never a bare `NUMERIC` without unit.
6. **Decimals:** `decimals="-6"` indicates rounded to millions in the BBCA instance **[V]**; retain it for precision-aware validation but do not treat it as a scaling error.
7. **Omitted concepts:** absence from a document is not zero. Only explicit `0` / `0.0` cells become facts **[V]**.

---

## 8. Validation and publication

### 8.1 Rule catalog

| Rule | Severity | Check |
|---|---|---|
| `DOC-001` | error | Downloaded file size and SHA-256 match source metadata / stored hash |
| `DOC-002` | error | Parser produced ≥1 fact and no fatal parse exception |
| `DOC-003` | warning | Additional attachment had `File_Size: 0` or could not be fetched **[V case exists]** |
| `FACT-001` | error | Required core facts for a statement exist (e.g. Assets, Liabilities, Equity; Assets ≈ Liabilities + Equity within tolerance) |
| `FACT-002` | error | Currency/unit consistent with account definition |
| `FACT-003` | error | No duplicate `(context_ref, account_id)` in the same current document |
| `FACT-004` | warning | Value sign/plausibility differs from `normal_sign` or prior period by configurable threshold |
| `XFORM-001` | error | When multiple formats are parsed, normalized values match exactly (12/12 in POC **[V]**) |
| `PER-001` | warning | Expected periods missing; logs the FY2024 Q1 gap rather than inventing data **[V]** |
| `MET-001` | error | All formula dependencies exist, current, and validated |
| `MET-002` | warning | Derived YTD quarter used in a metric; label accordingly |
| `PUB-001` | error | No unresolved `severity='error'` validation logs for target entities |
| `PUB-002` | error | Actor has `publisher`/`admin` role; otherwise publication is blocked |

### 8.2 State transitions

```text
downloaded → parsed → validated → [reviewed] → published
     ↘ failed ↗        ↘ failed ↗      ↘ rejected
```

- Parser/job writes facts with `validation_status='pending'` and metrics with `status='draft'`.
- Validation job updates `validation_logs` and fact/metric statuses; a human may set `'overridden'` only with a reason.
- Publication endpoint checks `PUB-001` and `PUB-002`, sets `financial_metrics.status='published'`, `published_at`, `published_by`, and writes an `audit_event`.
- Dashboards read **only** published rows. Draft/admin views are separate and role-protected.

---

## 9. Example queries

Normalized total assets for BBCA FY2025:

```sql
SELECT p.label, f.value_normalized, f.unit, d.file_name, f.source_context_ref
FROM financial_facts f
JOIN companies c ON c.id = f.company_id
JOIN financial_periods p ON p.id = f.period_id
JOIN financial_documents d ON d.id = f.document_id
JOIN financial_accounts a ON a.id = f.account_id
WHERE c.ticker = 'BBCA'
  AND p.fiscal_year = 2025 AND p.period_type = 'FY'
  AND a.concept_qname = 'idx-cor:Assets'
  AND f.is_current AND f.validation_status = 'passed';
-- expected value_normalized = 1586828536000000 [V]
```

Standalone Q2 net income (derived, not stored as a fact):

```sql
WITH ytd AS (
  SELECT p.period_sequence, f.value_normalized
  FROM financial_facts f
  JOIN financial_periods p ON p.id = f.period_id
  JOIN companies c ON c.id = f.company_id
  JOIN financial_accounts a ON a.id = f.account_id
  WHERE c.ticker = 'BBCA'
    AND p.fiscal_year = 2025
    AND a.concept_qname = 'idx-cor:ProfitLoss'
    AND f.is_current AND f.validation_status = 'passed'
)
SELECT MAX(value_normalized) FILTER (WHERE period_sequence = 2)
     - MAX(value_normalized) FILTER (WHERE period_sequence = 1) AS standalone_q2
FROM ytd;
```

---

## 10. Migration and evolution

- Use Alembic migrations from the first schema version; no ad-hoc `CREATE TABLE` in application startup.
- Add "Taxonomy version" rows before parsing new filings; never repoint an old fact to a new taxonomy version silently.
- All later changes are additive first (new columns nullable, backfill, then constraints); destructive changes require explicit approval.
- The committed `backend/venv/` and line-ending noise are unrelated to the schema and must be handled per [Repository audit](repository-technical-audit.md#2-repository-structure-verified).
