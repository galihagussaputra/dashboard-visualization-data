const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function detailMessage(body, status) {
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) return body.detail.map((item) => item.msg).join("; ");
  if (body?.detail?.message) return body.detail.message;
  return body?.error?.message || `Request failed with status ${status}`;
}

function authHeaders(token, extra = {}) {
  return {
    Accept: "application/json",
    ...extra,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export async function apiRequest(path, { method = "GET", body, signal, token } = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: authHeaders(token, body === undefined ? {} : { "Content-Type": "application/json" }),
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(detailMessage(payload, response.status), response.status, payload);
  }
  return payload;
}

export async function apiGet(path, options = {}) {
  return apiRequest(path, { ...options, method: "GET" });
}

export async function apiPost(path, body, options = {}) {
  return apiRequest(path, { ...options, method: "POST", body });
}
