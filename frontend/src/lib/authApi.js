import { apiGet, apiPost } from "./api";

const TOKEN_KEY = "ifi-m2-token";

export function getToken() {
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

export async function login({ email, password }) {
  const payload = await apiPost("/v1/auth/login", { email, password });
  setToken(payload.access_token);
  return payload.user;
}

export async function currentUser() {
  const token = getToken();
  if (!token) return null;
  try {
    return await apiGet("/v1/auth/me", { token });
  } catch {
    setToken(null);
    return null;
  }
}

export async function logout() {
  const token = getToken();
  if (!token) return;
  try {
    await apiPost("/v1/auth/logout", {}, { token });
  } finally {
    setToken(null);
  }
}
