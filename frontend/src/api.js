// REST client. The JWT is kept in localStorage and sent as a Bearer token.

const TOKEN_KEY = "expense_tracker_token";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable (private mode) - session will not persist */
  }
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, { method = "GET", body, params, raw = false } = {}) {
  const url = new URL(path, window.location.origin);
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  });
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload = body;
  if (body && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const response = await fetch(url, { method, headers, body: payload });
  if (response.status === 401 && token) {
    setToken(null);
    window.dispatchEvent(new Event("auth:logout"));
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = data.detail;
    const message = Array.isArray(detail)
      ? detail.map((d) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join("; ")
      : detail || `Request failed (${response.status})`;
    throw new ApiError(message, response.status);
  }
  if (raw) return response;
  return response.status === 204 ? null : response.json();
}

export const api = {
  register: (data) => request("/api/auth/register", { method: "POST", body: data }),
  login: (data) => request("/api/auth/login", { method: "POST", body: data }),
  me: () => request("/api/auth/me"),
  demoInfo: () => request("/api/demo"),

  meta: () => request("/api/expenses/meta"),
  listExpenses: (params) => request("/api/expenses", { params }),
  createExpense: (data) => request("/api/expenses", { method: "POST", body: data }),
  updateExpense: (id, data) => request(`/api/expenses/${id}`, { method: "PUT", body: data }),
  deleteExpense: (id) => request(`/api/expenses/${id}`, { method: "DELETE" }),
  importCsv: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/api/expenses/import", { method: "POST", body: form });
  },
  exportCsv: (params) => request("/api/expenses/export", { params, raw: true }),
  loadDemo: (replace = false) =>
    request("/api/expenses/demo", { method: "POST", params: { months: 18, replace } }),

  budgets: (month) => request("/api/budgets", { params: { month } }),
  setBudget: (data) => request("/api/budgets", { method: "PUT", body: data }),
  deleteBudget: (category) =>
    request(`/api/budgets/${encodeURIComponent(category)}`, { method: "DELETE" }),

  summary: (month) => request("/api/analytics/summary", { params: { month } }),
  monthly: (months = 12) => request("/api/analytics/monthly", { params: { months } }),
  forecast: (horizon = 3) => request("/api/forecast", { params: { horizon } }),
};
