# IDX Data Source Feasibility

**Date:** 2026-11-22
**Audience:** Phase 2 implementation team
**Evidence classification:** **[V]** verified by direct request/response or document download during this audit; **[F]** technically feasible but not verified end-to-end; **[A]** assumption requiring further investigation.
**Cross-references:** [Repository audit](repository-technical-audit.md), [Extraction POC](financial-data-extraction-poc.md), [Data model](financial-data-model.md), [Feasibility report](phase-1-feasibility-report.md).

---

## 1. Conclusion

IDX financial statements for all five sample companies are **publicly accessible without credentials [V]**. The exchange exposes a first-party JSON endpoint used by its own listing page, and the returned `File_Path` values resolve to downloadable documents on `www.idx.id` **[V]**. XLSX, PDF, XBRL instance ZIP, and inline-XBRL HTML ZIP are present for the tested periods, and all four formats were downloaded and parsed for BBCA FY2025 **[V]** (see [Extraction POC](financial-data-extraction-poc.md)).

Important qualifications:

- The JSON endpoint is **not a documented public API**. It was discovered by inspecting IDX's own Nuxt client bundle. It is a first-party web application endpoint, not an invented URL; treat it as a brittle integration and isolate it behind a source adapter.
- **No published rate limits or terms of automated access were found [A]**. Requests must be conservative, cached, and identify the application honestly. Do not bypass CAPTCHA, WAF challenges, or any future authentication.
- Some metadata gaps exist (notably FY2024 Q1 for four of five sample companies) **[V]**; the cause is unknown **[A]**.
- OJK is the regulator that mandates XBRL reporting, but IDX is the practical public distribution point **[V]**.

---

## 2. Official sources investigated

| Source | URL / document | Finding |
|---|---|---|
| IDX listing page | `https://www.idx.id/en/listed-companies/financial-statements-and-annual-report` **[V]** | Server-rendered Nuxt page with filters: report type (Financial Reports / Annual Reports), stocks/bonds, years 2026–2022, periods Q1/Q2/Q3/Annual. Embedded state contains `File_ID`, `File_Name`, `File_Path`, `File_Size`, `Report_Period`, `Report_Year`, `NamaEmiten`. |
| IDX report API | `GET https://www.idx.id/primary/ListedCompany/GetFinancialReport` **[V]** | Returns JSON `Search`, `ResultCount`, `Results[].Attachments[]`. Used by the page's own client bundle (`/_nuxt/00edcb5.js`). |
| IDX issuer helper | `GET https://www.idx.id/primary/Helper/GetEmiten?emitenType=s` **[V]** | Returns 946 entries of `{KodeEmiten, NamaEmiten}`; all five sample tickers present. |
| IDX XBRL page | `https://www.idx.id/en/listed-companies/xbrl/` **[V]** | Documents IDX Taxonomy 2014 and 2020, 8 industry entry points, mandatory XBRL since 2 Nov 2015, downloadable taxonomy/summary/guidebook/chart-of-accounts/instance-illustration/entry-point PDFs. |
| IDX Taxonomy 2020 guidebook | `https://www.idx.id/media/oxziiysv/04_idx_taxonomy_2020_guide_ver_2.pdf` **[V]** | Namespace `idx.co.id/xbrl/taxonomy/2020-04-30`; scope: statement of financial position, comprehensive income, cash flows, changes in equity; based on PSAK/IFRS/OJK rules. |
| IDX Taxonomy 2020 summary | `https://www.idx.id/media/qmqjgqsb/02_summary-information-for-idx-taxonomy-2020.pdf` **[V]** | Final status 23 Oct 2020, XBRL International "Acknowledged", namespaces `.../2020-01-01/cor`, `/dei`, `/rt`, `/ep/...`; 8 entry points (General, Property, Infrastructure, Financial and Sharia, Securities, Insurance, Collective Investment Contract, Financing). |
| OJK POJK 14/POJK.04/2022 | `https://ojk.go.id/id/regulasi/Pages/Penyampaian-Laporan-Keuangan-Berkala-Emiten-atau-Perusahaan-Publik.aspx` **[V]** | Regulates periodic financial statements; official PDF states submission through the electronic reporting system using XBRL with a PDF copy attached. This explains the format mix observed on IDX. |
| OJK POJK 7/POJK.04/2018 | `https://ojk.go.id/id/regulasi/Pages/Penyampaian-Laporan-melalui-Sistem-Pelaporan-Elektronik-Emiten-atau-Perusahaan-Publik.aspx` **[V]** | Regulates electronic submission by issuers. OJK's SPE is the filing channel; it is not an open anonymous download API for this project. |
| Arelle | `https://arelle.org/` **[V]** | Open-source XBRL processor, XBRL International certified, available as Python package (`arelle-release`), CLI, Docker image, and API. Supports Inline XBRL 1.0/1.1 and XBRL 2.1. |

Yahoo Finance was **not** used. No third-party financial data provider was consulted for the availability matrix.

---

## 3. Access mechanics (verified)

### 3.1 Listing / metadata request

```text
GET https://www.idx.id/primary/ListedCompany/GetFinancialReport
    ?indexFrom=1
    &pageSize=20
    &year=2025
    &reportType=rdf
    &EmitenType=s
    &periode=audit
    &kodeEmiten=BBCA
    &SortColumn=KodeEmiten
    &SortOrder=asc
```

Observed response shape **[V]**:

```json
{
  "Search": {"ReportType":"rdf","KodeEmiten":"BBCA","Year":"2025", ...},
  "ResultCount": 1,
  "Results": [{
    "KodeEmiten": "BBCA",
    "File_Modified": "2025-04-23T17:28:34.323",
    "Report_Period": "TW1",
    "Report_Year": "2025",
    "NamaEmiten": "PT Bank Central Asia Tbk.",
    "Attachments": [{
      "Emiten_Code": "BBCA",
      "File_ID": "...",
      "File_Name": "FinancialStatement-2025-I-BBCA.xlsx",
      "File_Path": "/Portals/0/StaticData/ListedCompanies/.../FinancialStatement-2025-I-BBCA.xlsx",
      "File_Size": 224941,
      "File_Type": ".xlsx",
      "Report_Period": "TW1",
      "Report_Type": "rdf",
      "Report_Year": "2025",
      "NamaEmiten": "PT Bank Central Asia Tbk."
    }]
  }]
}
```

Parameter values verified from the first-party bundle **[V]**:

- `reportType=rdf` — financial reports (the default used by the page).
- `EmitenType=s` — stocks.
- `periode`: `tw1`, `tw2`, `tw3`, `audit`.
- `indexFrom` appears to be 1-based page index; `pageSize` controls page size.
- Omitting `periode` returns only Q1, so each period must be requested explicitly **[V]**.

### 3.2 Document download

The `File_Path` field is a site-relative path. Prefixing it with `https://www.idx.id` produced HTTP 200 for all four tested BBCA files **[V]**. Prefixing with `https://www.idx.co.id` produced HTTP 403 for the same paths **[V]**. Use `www.idx.id` and treat the host as configurable, not hard-assumed.

Example verified path pattern (do not construct manually; always use the API-supplied `File_Path`):

```text
/Portals/0/StaticData/ListedCompanies/Corporate_Actions/New_Info_JSX/
Jenis_Informasi/01_Laporan_Keuangan/02_Soft_Copy_Laporan_Keuangan/
Laporan Keuangan Tahun 2025/Audit/BBCA/FinancialStatement-2025-Tahunan-BBCA.xlsx
```

### 3.3 Credentials, restrictions, rate limits

| Question | Finding |
|---|---|
| API credentials required? | **No [V]** — no headers beyond normal browser defaults were sent; no authentication challenge appeared. The client bundle contains placeholder `X_PUBLIC_KEY: "xxx"`, `X_HASHKEY: "xxx"` in development config, but these were not needed for the observed GETs. |
| CAPTCHA / authentication bypassed? | **No [V]** — none encountered; no bypass attempted. |
| Rate limits published? | **Not found [A]** — no `robots.txt` content was returned, and no documented limit was located. This audit used ~115 metadata GETs with ~0.12 s spacing and four small document downloads. Phase 2 must use conservative polling, caching, backoff, and a configurable user agent. |
| Access anomalies | Python `urllib.request` received **HTTP 403** for an endpoint that `curl` retrieved with HTTP 200 using the same URL **[V]**. Root cause not established (likely WAF/TLS/header policy) **[A]**. A production adapter should use a well-behaved HTTP client (e.g. `httpx`) with normal headers and verify in the deployment environment; do not treat the 403 as a restriction to circumvent. |
| URL stability | Endpoints are discovered from first-party JS and are undocumented **[V]**; they can change without notice. Isolate in `backend/app/ingestion/sources/idx_id.py`. |

---

## 4. Initial company availability matrix

Query window: fiscal years **2021–2025**, periods **Q1 (`tw1`), Q2 (`tw2`), Q3 (`tw3`), Annual (`audit`)**, `reportType=rdf`, `EmitenType=s`. One `ResultCount=1` row means a filing record existed for that company/year/period.

### 4.1 Filing availability

| Ticker | Company (from IDX helper) | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| BBCA | PT Bank Central Asia Tbk. | Q1 Q2 Q3 AN | Q1 Q2 Q3 AN | Q1 Q2 Q3 AN | **Q2 Q3 AN** (Q1 absent) | Q1 Q2 Q3 AN |
| BBRI | PT Bank Rakyat Indonesia (Persero) Tbk | Q1 Q2 Q3 AN | Q1 Q2 Q3 AN | Q1 Q2 Q3 AN | **Q2 Q3 AN** (Q1 absent) | Q1 Q2 Q3 AN |
| TLKM | PT Telkom Indonesia (Persero) Tbk | Q1 Q2 Q3 AN | Q1 Q2 Q3 AN | Q1 Q2 Q3 AN | **Q2 Q3 AN** (Q1 absent) | Q1 Q2 Q3 AN |
| ASII | Astra International Tbk | Q1 Q2 Q3 AN | Q1 Q2 Q3 AN | Q1 Q2 Q3 AN | **Q2 Q3 AN** (Q1 absent) | Q1 Q2 Q3 AN |
| ICBP | Indofood CBP Sukses Makmur Tbk | Q1 Q2 Q3 AN | Q1 Q2 Q3 AN | Q1 Q2 Q3 AN | Q1 Q2 Q3 AN | Q1 Q2 Q3 AN |

**AN = Annual (`audit`).** All cells above are **[V]**.

The FY2024 Q1 absence for BBCA, BBRI, TLKM, and ASII was re-queried individually and confirmed **[V]**. ICBP FY2024 Q1 is present **[V]**. Possible causes (changed period code, migration to a different report type, filing gap) are **unverified [A]** and must not be assumed.

### 4.2 Formats per available filing

| Period kind | Formats observed in `Attachments` | Notes |
|---|---|---|
| Q1/Q2/Q3 **[V]** | 1 × `FinancialStatement-<year>-<roman>-<ticker>.xlsx`; 1 × same-name `.pdf`; 1 × `instance.zip`; 1 × `inlineXBRL.zip`; plus 2–6 extra company-specific PDFs (e.g. `Lapkeu BCA Mar25.pdf`, disclosure checklists, director statements) | Extra PDFs vary by company and period. |
| Annual (`audit`) **[V]** | 1 × `FinancialStatement-<year>-Tahunan-<ticker>.xlsx`; 1 × `.pdf`; `instance.zip`; `inlineXBRL.zip`; 4–11 additional PDF attachments including audited reports (IND/ENG) and `AnnualReport<year>-<ticker>-attN.pdf` entries | Several `AnnualReport...attN.pdf` entries carry `File_Size: 0` in metadata **[V]**; their actual availability/size needs checking before use **[F]**. |

**Result:** the five-year target is achievable for all five companies at annual granularity **[V]**; quarterly completeness has one confirmed gap **[V]**.

### 4.3 Historical and current coverage

- FY2021–FY2025: verified as above **[V]**.
- FY2026: listing page shows Q1 filings for AADI/AALI (and other tickers) **[V]**; a search-indexed PDF for `GOTO` Q3 2026 exists under `/StaticData/NewsAndAnnouncement/From_EREP/...` **[V via search result]**. FY2026 was not part of the systematic matrix.
- Earlier than FY2021: **not tested [A]**.
- Annual report documents (as distinct from annual financial statements) are attached to `audit` filings, but a dedicated annual-report report type was not enumerated **[A]**.

---

## 5. Verified document download results

Four BBCA FY2025 annual documents were downloaded (total ≈ 1.1 MB):

| File | Size (bytes) | HTTP | Content-Type |
|---|---:|---:|---|
| `FinancialStatement-2025-Tahunan-BBCA.xlsx` | 306,452 | 200 | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| `instance.zip` | 81,797 | 200 | `application/x-zip-compressed` |
| `inlineXBRL.zip` | 176,712 | 200 | `application/x-zip-compressed` |
| `FinancialStatement-2025-Tahunan-BBCA.pdf` | 497,148 | 200 | `application/pdf` |

Archive contents **[V]**:

- `instance.zip`: `instance.xbrl` (1,863,031 bytes) + `Taxonomy.xsd` (18,231 bytes).
- `inlineXBRL.zip`: 23 HTML files named by taxonomy element ID, e.g. `1000000.html` (DEI), `4220000.html` (statement of financial position), `4322000.html` (profit or loss), `4510000.html` (cash flows), `4695000.html` (notes).
- XLSX: 47 worksheets; sheet names are taxonomy element IDs plus `Context`, `InlineXBRL`, `hidden`, `Token`.

All four formats were parsed; results are in [Extraction POC](financial-data-extraction-poc.md).

---

## 6. Inconsistencies and risks observed at the source

| Observation | Classification | Impact |
|---|---|---|
| FY2024 Q1 metadata missing for 4/5 sample companies | **[V]** | Historical quarterly continuity cannot be assumed; needs fallback search before declaring data unavailable |
| Bank companies (BBCA, BBRI) use Financial/Sharia taxonomy entry points; TLKM/ASII/ICBP use General/Other entry points | **[V]** in BBCA XBRL; **[A]** for the others until parsed | Account labels and concept sets differ; universal formulas will fail for banks |
| XBRL instance values are absolute IDR with `decimals="-6"` and no `scale`; inline XBRL and XLSX display `scale="6"` values in millions | **[V]** | Unit/scale normalization is mandatory (see [Data model](financial-data-model.md)) |
| XLSX stores numbers in scientific notation as strings | **[V]** | Parser must coerce text to `NUMERIC`; do not trust cell type alone |
| Some annual attachments report `File_Size: 0` | **[V]** | Treat as unverified until fetched and hashed |
| Endpoint is undocumented and derived from client JS | **[V]** | Adapter must be isolated, cached, and monitored; no reliance on URL construction |
| Different total PDF counts per filing (2–11) | **[V]** | PDF fallback must select documents by metadata, not by filename convention |
| Python `urllib` 403 vs curl 200 on the same endpoint | **[V]** | HTTP client compatibility must be validated in the target runtime |

Risk ratings and mitigations are consolidated in [Feasibility report](phase-1-feasibility-report.md#6-risk-assessment).

---

## 7. Recommended source strategy for Phase 2

1. **Primary metadata:** `GET /primary/ListedCompany/GetFinancialReport` with explicit year and period; cache responses by the full query key.
2. **Ticker master:** `GET /primary/Helper/GetEmiten?emitenType=s`, refreshed on a slow schedule; store `KodeEmiten` → `NamaEmiten` locally.
3. **Document download:** use the returned `File_Path` verbatim with the configured `www.idx.id` base; verify SHA-256 and byte size against metadata; store the original file and metadata in `financial_documents`.
4. **Parser priority:** `instance.zip` (XBRL) → `inlineXBRL.zip` → XLSX → PDF. XBRL gives stable concept IDs; use XLSX/PDF mostly for cross-validation and human review.
5. **Restraint:** one metadata pass per company/year/period, conditional requests where supported, exponential backoff, no parallel bursts, no scraping of authentication-protected areas.
6. **Fallback for metadata gaps:** query adjacent period codes and the announcement archive only after the standard lookup fails, and record the fallback in `ingestion_jobs`/`validation_logs`.

---

## 8. Method

Requests were issued with `curl` from the audit environment on 2026-11-22. The availability matrix was produced by 100 metadata GETs (5 tickers × 5 years × 4 periods), plus targeted verification GETs and four document downloads. JS bundle evidence came from `https://www.idx.id/_nuxt/00edcb5.js`, which contains the `/primary/ListedCompany/GetFinancialReport` call and the period values. No credentials were supplied, no access-control mechanism was circumvented, and no large dataset was downloaded.
