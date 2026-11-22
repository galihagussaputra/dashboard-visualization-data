import { apiGet } from "./api";

function assertArray(value, label) {
  if (!Array.isArray(value)) throw new Error(`${label} response must be an array`);
  return value;
}

function assertObject(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} response must be an object`);
  }
  return value;
}

function assertString(value, label) {
  if (typeof value !== "string") throw new Error(`${label} must be a string`);
  return value;
}

function toQuery(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  });
  return query.toString();
}

function toCompany(value) {
  const company = assertObject(value, "company");
  return {
    ticker: assertString(company.ticker, "company.ticker"),
    name: assertString(company.name, "company.name"),
    accountingStandard: company.accounting_standard ?? null,
    reportingBasisDefault: assertString(company.reporting_basis_default, "company.reporting_basis_default"),
  };
}

function toPeriod(value) {
  const period = assertObject(value, "period");
  return {
    id: period.id,
    fiscalYear: period.fiscal_year,
    label: assertString(period.label, "period.label"),
    periodType: assertString(period.period_type, "period.period_type"),
    sourcePeriodCode: assertString(period.source_period_code, "period.source_period_code"),
    startDate: assertString(period.start_date, "period.start_date"),
    endDate: assertString(period.end_date, "period.end_date"),
    instantDate: assertString(period.instant_date, "period.instant_date"),
  };
}

function toDocument(value) {
  const document = assertObject(value, "document");
  return {
    id: document.id,
    fileName: assertString(document.file_name, "document.file_name"),
    fileRole: assertString(document.file_role, "document.file_role"),
    parseStatus: assertString(document.parse_status, "document.parse_status"),
    fileSizeBytes: document.file_size_bytes ?? null,
    sha256: document.sha256 ?? null,
    sourceUrl: assertString(document.source_url, "document.source_url"),
  };
}

function toFact(value) {
  const fact = assertObject(value, "statement fact");
  const numeric = Number(fact.value_normalized);
  if (!Number.isFinite(numeric)) throw new Error("statement fact value_normalized must be numeric");
  return {
    concept: assertString(fact.concept, "statement fact.concept"),
    labelId: fact.label_id ?? null,
    labelEn: fact.label_en ?? null,
    statementType: assertString(fact.statement_type, "statement fact.statement_type"),
    valueNormalized: numeric,
    valueDisplay: assertString(fact.value_display, "statement fact.value_display"),
    displayScale: fact.display_scale,
    currency: fact.currency ?? null,
    unit: assertString(fact.unit, "statement fact.unit"),
    sourceScale: fact.source_scale,
    sourceFactId: assertString(fact.source_fact_id, "statement fact.source_fact_id"),
    sourceContextRef: assertString(fact.source_context_ref, "statement fact.source_context_ref"),
    sourceFile: assertString(fact.source_file, "statement fact.source_file"),
    sourceUrl: assertString(fact.source_url, "statement fact.source_url"),
    validationStatus: assertString(fact.validation_status, "statement fact.validation_status"),
    documentVersion: fact.document_version,
    publicationStatus: fact.publication_status ?? "draft",
    periodKind: fact.period_kind ?? null,
    durationKind: fact.duration_kind ?? null,
    standardAccount: fact.standard_account ?? null,
    mappingStatus: fact.mapping_status ?? null,
    sourceContextDetails: fact.source_context_details ?? {},
  };
}

function toStatement(value) {
  const statement = assertObject(value, "statement");
  return {
    ticker: assertString(statement.ticker, "statement.ticker"),
    companyName: assertString(statement.company_name, "statement.company_name"),
    period: assertString(statement.period, "statement.period"),
    basis: assertString(statement.basis, "statement.basis"),
    statement: assertString(statement.statement, "statement.statement"),
    facts: assertArray(statement.facts, "statement.facts").map(toFact),
  };
}

export async function getCompanies() {
  return assertArray(await apiGet("/v1/companies"), "companies").map(toCompany);
}

export async function getPeriods(ticker) {
  const query = toQuery({ ticker });
  return assertArray(await apiGet(`/v1/periods?${query}`), "periods").map(toPeriod);
}

export async function getDocuments({ ticker, year, period }) {
  const query = toQuery({ ticker, year, period });
  return assertArray(await apiGet(`/v1/documents?${query}`), "documents").map(toDocument);
}

export async function getStatement({ ticker, period, statement, basis, visibility, asOf }) {
  const encodedTicker = encodeURIComponent(ticker);
  const query = toQuery({ period, statement, basis, visibility, as_of: asOf });
  return toStatement(await apiGet(`/v1/statements/${encodedTicker}?${query}`));
}
