# Financial Data Extraction Proof of Concept

**Date:** 2026-11-22
**Company:** BBCA (PT Bank Central Asia Tbk.)
**Document set:** FY2025 annual (audit) filing, four files, ≈1.1 MB total
**Evidence classification:** **[V]** verified in this POC; **[F]** feasible but not fully verified; **[A]** assumption.
**Cross-references:** [Source feasibility](idx-data-source-feasibility.md), [Data model](financial-data-model.md), [Implementation plan](technical-implementation-plan.md), [Feasibility report](phase-1-feasibility-report.md).

---

## 1. Objective and scope

Test whether a legitimately downloadable IDX filing can be parsed into the normalized fact structure required by the product, and whether the same financial value maps consistently across XLSX, XBRL instance, inline XBRL, and PDF. No extracted value was published to any database; all work was performed in `/tmp` outside the repository.

**Tested:** one company, one annual period, four documents, twelve selected accounts.
**Not tested:** quarterly filings, other four sample companies, Arelle validation, openpyxl, commercial PDF libraries, restatements, taxonomy extension concepts.

---

## 2. Sample documents

All four files were downloaded from `https://www.idx.id` using `File_Path` values returned by the official listing API (HTTP 200 each) **[V]**:

| File | Size | Role in POC |
|---|---:|---|
| `FinancialStatement-2025-Tahunan-BBCA.xlsx` | 306,452 B | Structured spreadsheet, 47 sheets |
| `instance.zip` → `instance.xbrl`, `Taxonomy.xsd` | 81,797 B | XBRL instance document |
| `inlineXBRL.zip` → 23 HTML files | 176,712 B | Inline XBRL rendering |
| `FinancialStatement-2025-Tahunan-BBCA.pdf` | 497,148 B | PDF fallback candidate |

Source metadata also states: entity `BBCA`, identification `AA331`, sector `G. Financials`, subsector `G1. Banks`, PSAK basis, "Entitas grup / Group entity" (consolidated), functional currency Rupiah **[V]**.

---

## 3. Methodology

The audit environment had **no openpyxl, Arelle, PyMuPDF, pdfplumber, pandas, or pip**. To avoid adding dependencies to the repository, the POC used Python 3.14 standard library only **[V]**:

1. **XLSX:** `zipfile` + `xml.etree.ElementTree`; read `xl/sharedStrings.xml`, `xl/workbook.xml`, `xl/_rels/workbook.xml.rels`, and `xl/worksheets/sheet*.xml`. Cell values were read from `<v>` with shared-string resolution; inline strings from `<is>`.
2. **XBRL instance:** `ElementTree` parsed `instance.xbrl`; facts are elements in namespace `http://www.idx.co.id/xbrl/taxonomy/2020-01-01/cor` (and `/dei`), with `id`, `contextRef`, `unitRef`, `decimals`. Contexts were resolved to instants or durations from `xbrli:context` elements.
3. **Inline XBRL:** regular-expression extraction of `<ix:nonFraction name="…" contextRef="…" unitRef="…" scale="…" format="ixt:numcommadot">…</ix:nonFraction>` from `4220000.html`.
4. **PDF:** `zlib` decompression of FlateDecode streams, then a minimal `(…)` `Tj` string reader. This is a diagnostic extractor, not a production parser.
5. **Comparison:** all parsed values were normalized to absolute IDR (XBRL instance = raw absolute; XLSX and inline XBRL displayed in millions, multiply by 1,000,000) and compared numerically.

No network calls other than the four document downloads and the metadata queries documented in [Source feasibility](idx-data-source-feasibility.md) were made.

---

## 4. Normalized structure achieved

A fact record was assembled with all required fields **[V]**:

```json
{
  "company_identifier": "BBCA",
  "reporting_period": {
    "fiscal_year": 2025,
    "type": "annual",
    "instant": "2025-12-31",
    "duration": ["2025-01-01", "2025-12-31"]
  },
  "statement_type": "balance_sheet",
  "account_code": "idx-cor:Assets",
  "original_account_name": "Jumlah aset / Total assets",
  "normalized_account_category": "TOTAL_ASSETS",
  "financial_value": 1586828536000000,
  "currency": "IDR",
  "unit": "IDR",
  "scale": 0,
  "reporting_basis": "consolidated",
  "source_document_reference": {
    "source": "IDX",
    "file_id": "b4cb4adf-9d81-408b-9dce-e4fe45e1ec35",
    "filename": "instance.xbrl",
    "fact_id": "IXF4220000E02_0027_00001_01_0001",
    "context": "CurrentYearInstant"
  }
}
```

The `scale` field is **source-specific**: the XBRL instance stores `1586828536000000` with no `scale` attribute, while inline XBRL stores `1,586,828,536` with `scale="6"` and XLSX/PDF display `1.586828536E9` / `1,586,828,536` (millions). Presence of `scale` must not be assumed; this is a unit-normalization requirement, not an inconsistency in the data **[V]**.

---

## 5. Extracted values and cross-format accuracy

All twelve selected FY2025 values matched across **all four** formats after unit normalization **[V]**. Displayed values below are exactly as shown in XLSX/inline XBRL/PDF; XBRL instance values are absolute IDR.

| Normalized category | XBRL concept | XBRL instance (IDR) | Displayed (millions, except EPS) | Match |
|---|---|---:|---:|---|
| Cash | `idx-cor:Cash` | 25,305,031,000,000 | 25,305,031 | **Yes [V]** |
| Total assets | `idx-cor:Assets` | 1,586,828,536,000,000 | 1,586,828,536 | **Yes [V]** |
| Total liabilities | `idx-cor:Liabilities` | 1,294,508,286,000,000 | 1,294,508,286 | **Yes [V]** |
| Total equity | `idx-cor:Equity` | 281,687,555,000,000 | 281,687,555 | **Yes [V]** |
| Revenue proxy (bank interest income) | `idx-cor:InterestIncome` | 98,912,652,000,000 | 98,912,652 | **Yes [V]** |
| Operating income | `idx-cor:ProfitFromOperation` | 71,260,876,000,000 | 71,260,876 | **Yes [V]** |
| Net income | `idx-cor:ProfitLoss` | 57,563,093,000,000 | 57,563,093 | **Yes [V]** |
| Net income attributable to parent | `idx-cor:ProfitLossAttributableToParentEntity` | 57,537,287,000,000 | 57,537,287 | **Yes [V]** |
| Operating cash flow | `idx-cor:NetCashFlowsReceivedFromUsedInOperatingActivities` | 77,508,785,000,000 | 77,508,785 | **Yes [V]** |
| Investing cash flow | `idx-cor:NetCashFlowsReceivedFromUsedInInvestingActivities` | -33,690,926,000,000 | (33,690,926) | **Yes [V]** |
| Financing cash flow | `idx-cor:NetCashFlowsReceivedFromUsedInFinancingActivities` | -41,708,637,000,000 | (41,708,637) | **Yes [V]** |
| Earnings per share | `idx-cor:BasicEarningsLossPerShareFromContinuingOperations` | 467 `IDRPerShares` | 467 | **Yes [V]** |

Comparison basis: XBRL instance vs XLSX (numeric equality after ×1e6) **[V]**, XBRL instance vs inline XBRL (`scale=6`) **[V]**, and XBRL/XLSX values located verbatim in PDF text **[V]**.

### 5.1 Mapping observations

- XBRL provides **stable concept IDs** (`idx-cor:Assets`) but industry-specific labels: BBCA uses the Financial and Sharia entry point (`4220000` = statement of financial position using order of liquidity, `4322000` = profit or loss before-tax OCI by nature, `4510000` = cash flows). A general-industry company will use different sheet/report IDs and concept names **[V for BBCA; F for others]**.
- The same concept appears in multiple XLSX sheets (e.g. `Assets` in `4220000` and in the reconciliation at row 238). A parser must select the primary statement sheet and deduplicate by `(concept, context, document)` rather than by value.
- XLSX numeric cells are stored as scientific-notation **strings** (`2.5305031E7`) **[V]**; openpyxl would expose them as strings unless coerced. A production parser must explicitly cast to `Decimal`.
- EPS uses unit `IDRPerShares` (`iso4217:IDR / shares`) with `decimals="INF"`, not the monetary `IDR` unit **[V]**. It must not be summed or scaled like currency.
- Negative cash flows use a raw minus sign in the XBRL instance and parenthesized display in PDF **[V]**. Sign handling must preserve the original and the normalized value separately.
- Zero values are explicitly reported (`0.0`) for many accounts **[V]**; these are distinguishable from omitted cells / empty accounts, which must be stored as missing, not zero.

---

## 6. Validation results

| Check | Result |
|---|---|
| All four files downloaded over HTTPS without credentials | **Pass [V]** |
| SHA/source metadata (`File_ID`, `File_Size`) available from listing API | **Pass [V]** |
| XBRL instance parses with stdlib XML and exposes 5,525 facts / 1,205 contexts | **Pass [V]** |
| Units resolvable (`IDR`, `IDRPerShares`) and contexts resolvable to instant/duration | **Pass [V]** |
| XLSX parses with stdlib ZIP/XML (47 sheets, 2,178 non-empty rows) | **Pass [V]** |
| 12/12 selected values match across XBRL, XLSX, inline XBRL, and PDF | **Pass [V]** |
| Reporting basis and sector identified from source | **Pass [V]** |
| Published to production tables | **Not done — by design** |

The only extraction anomalies were in the **diagnostic PDF reader**: it split some long numbers across text runs (e.g. `24,663,2 48`) and emitted negative signs as separate `( )` tokens **[V]**. The twelve audited values were still recoverable, but this confirms that a real PDF library plus validation is required for production.

---

## 7. Limitations

1. **No taxonomy validation.** Arelle was not installed; the POC parsed well-formed XML but did not validate the filing against IDX Taxonomy 2020 or run calculation-linkbase checks **[V limitation]**.
2. **One company/period only.** General-industry companies, quarterly YTD filings, and restatements were not tested **[A]**.
3. **No library-based XLSX/PDF parsing.** openpyxl and PyMuPDF/pdfplumber were unavailable; the stdlib/XLSX-XML and zlib/Tj approaches are diagnostic only **[V]**.
4. **No automated account normalization.** The 12 mappings were selected manually to prove cross-format consistency; a general mapping table is still required **[A]**.
5. **No FCF derivation.** Free cash flow was not computed in the POC because its definition (OCF − capex) requires a capex concept that was not part of the 12-value sample; this remains a metric-definition task **[A]**.
6. **Year-to-date logic untested.** Quarterly duration contexts were not parsed for BBCA FY2025 quarterly filings **[A]**. See [Data model](financial-data-model.md#6-financial-period-normalization).
7. **Sample values are not a golden dataset.** The numbers above come from the source document and are published here only as POC evidence; they must be re-verified against the source before use in tests **[V]**.

---

## 8. Reproducible manual procedure

1. Query the listing API for BBCA FY2025 Annual (`periode=audit`, `year=2025`, `reportType=rdf`, `EmitenType=s`, `kodeEmiten=BBCA`) and collect `File_Path` for the four files listed in §2.
2. Download each file with `https://www.idx.id` + `File_Path`; confirm HTTP 200 and byte size against `File_Size`.
3. Unzip `instance.zip` and `inlineXBRL.zip`.
4. In `instance.xbrl`, locate facts with IDs `IXF4220000E02_0027_00001_01_0001` (Assets) and `IXF4220000E02_0601_00001_01_0001` (Cash); confirm contexts `CurrentYearInstant` = 2025-12-31 and values in §5.
5. In XLSX sheet `4220000` (`xl/worksheets/sheet4.xml`), find row 7 (`Kas`/`Cash`) and row 119 (`Jumlah aset`/`Total assets`); values are `2.5305031E7` and `1.586828536E9` (millions).
6. In `inlineXBRL.zip/4220000.html`, find `name="idx-cor:Cash"` and `name="idx-cor:Assets"`; confirm `scale="6"` and displayed values in §5.
7. In the PDF, search the extracted text for `25,305,031` and `1,586,828,536`; both appear on the statement of financial position.
8. Multiply displayed millions by 1,000,000 and compare with XBRL instance values; expect exact equality for all twelve rows in §5.

The POC scripts used during the audit were kept in `/tmp/opencode/` and were **not** added to the repository. Phase 2 should reimplement them as tested modules under `backend/app/parsers/`.

---

## 9. Go / no-go for extraction

**Conditional go [V].** Structured extraction is demonstrably reliable for the tested BBCA annual filing, and cross-format consistency is exact for the twelve sampled accounts. The conditions are: add real parser libraries, add taxonomy validation via Arelle, implement a tested account-mapping registry, and gate database publication behind the validation workflow described in [Data model](financial-data-model.md#8-validation-and-publication) and [Implementation plan](technical-implementation-plan.md#5-data-management-workflow).
