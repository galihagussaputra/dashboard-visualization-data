import { apiGet, apiPost } from "./api";
import { getToken } from "./authApi";

function toQuery(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  });
  return query.toString();
}

function auth() {
  return { token: getToken() };
}

export function listMappings(status) {
  return apiGet(`/v1/normalization/mappings?${toQuery({ status })}`, auth());
}

export function derivePeriods({ ticker, period, basis }) {
  return apiPost(`/v1/periods/derive?${toQuery({ ticker, period, basis })}`, {}, auth());
}

export function recalculateMetrics({ ticker, period, basis }) {
  return apiPost(`/v1/metrics/recalculate?${toQuery({ ticker, period, basis })}`, {}, auth());
}

export function listMetrics({ ticker, period, basis, publishedOnly }) {
  return apiGet(`/v1/metrics?${toQuery({ ticker, period, basis, published_only: publishedOnly })}`, auth());
}

export function runValidation({ ticker, period, basis }) {
  return apiPost(`/v1/validation/run?${toQuery({ ticker, period, basis })}`, {}, auth());
}

export function listValidationLogs() {
  return apiGet("/v1/validation/logs", auth());
}

export function publishScope(payload) {
  return apiPost("/v1/publication/publish", payload, auth());
}

export function listPublicationEvents() {
  return apiGet("/v1/publication/events", auth());
}

export function listRestatements({ ticker, period }) {
  return apiGet(`/v1/restatements?${toQuery({ ticker, period })}`, auth());
}

export function listAuditEvents() {
  return apiGet("/v1/audit/events", auth());
}
