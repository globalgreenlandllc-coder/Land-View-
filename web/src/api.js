// Land-View API client. Relative paths; the Vite dev server proxies /api to Flask.

// --- token storage ---------------------------------------------------------
const ACCESS_KEY = "lv_access", REFRESH_KEY = "lv_refresh";
export const tokens = {
  get access() { return localStorage.getItem(ACCESS_KEY) || ""; },
  get refresh() { return localStorage.getItem(REFRESH_KEY) || ""; },
  set(access, refresh) {
    if (access) localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() { localStorage.removeItem(ACCESS_KEY); localStorage.removeItem(REFRESH_KEY); },
};

function authHeaders(extra) {
  const h = { ...(extra || {}) };
  if (tokens.access) h.Authorization = `Bearer ${tokens.access}`;
  return h;
}

// Try a one-time refresh of the access token using the refresh token.
async function tryRefresh() {
  if (!tokens.refresh) return false;
  const res = await fetch("/api/auth/refresh", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: tokens.refresh }),
  });
  if (!res.ok) { tokens.clear(); return false; }
  const d = await res.json();
  tokens.set(d.access_token, d.refresh_token);
  return true;
}

// fetch wrapper: attaches the bearer token and auto-refreshes once on a 401.
async function authedFetch(path, opts = {}, _retried = false) {
  const res = await fetch(path, { ...opts, headers: authHeaders(opts.headers) });
  if (res.status === 401 && !_retried && (await tryRefresh())) {
    return authedFetch(path, opts, true);
  }
  return res;
}

async function get(path) {
  const res = await authedFetch(path);
  if (!res.ok) throw new Error((await res.json().catch(() => ({})))?.error || `HTTP ${res.status}`);
  return res.json();
}
async function post(path, body) {
  const res = await authedFetch(path, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({})))?.error || `HTTP ${res.status}`);
  return res.json();
}

// Auth calls don't go through the token-refresh path (they mint the tokens).
async function authPost(path, body) {
  const res = await fetch(path, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.error || `HTTP ${res.status}`);
  return data;
}

export const api = {
  getHealth: () => get("/api/health"),
  // auth
  async register(email, password) {
    const d = await authPost("/api/auth/register", { email, password });
    tokens.set(d.access_token, d.refresh_token);
    return d.user;
  },
  async login(email, password) {
    const d = await authPost("/api/auth/login", { email, password });
    tokens.set(d.access_token, d.refresh_token);
    return d.user;
  },
  me: () => get("/api/auth/me").then((d) => d.user),
  logout() { tokens.clear(); },
  isAuthed: () => !!tokens.access,
  // admin
  adminUsers: () => get("/api/admin/users").then((d) => d.users),
  adminUpdateUser: (id, patch) => authedFetch(`/api/admin/users/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  }).then(async (r) => { const d = await r.json(); if (!r.ok) throw new Error(d?.error || `HTTP ${r.status}`); return d.user; }),
  adminDeleteUser: (id) => authedFetch(`/api/admin/users/${id}`, { method: "DELETE" })
    .then(async (r) => { const d = await r.json(); if (!r.ok) throw new Error(d?.error || `HTTP ${r.status}`); return d; }),
  adminConnections: () => get("/api/admin/connections").then((d) => d.connections),
  adminSetConnection: (service, payload) => authedFetch(`/api/admin/connections/${service}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then(async (r) => { const d = await r.json(); if (!r.ok) throw new Error(d?.error || `HTTP ${r.status}`); return d.connections; }),
  adminDeleteConnection: (service) => authedFetch(`/api/admin/connections/${service}`, { method: "DELETE" })
    .then(async (r) => { const d = await r.json(); if (!r.ok) throw new Error(d?.error || `HTTP ${r.status}`); return d.connections; }),
  adminAnalytics: () => get("/api/admin/analytics"),
  adminAudit: () => get("/api/admin/audit").then((d) => d.audit),
  getStyles: () => get("/api/styles"),
  getElements: () => get("/api/elements"),
  getProperty: (q) => get(`/api/property?q=${encodeURIComponent(q)}`),
  getParcel: (q, kind = "auto") => get(`/api/parcel?q=${encodeURIComponent(q)}&kind=${kind}`),
  getMapConfig: () => get("/api/map-config"),
  render: (payload) => post("/api/render", payload),
  cost: (payload) => post("/api/cost", payload),
  // designs
  listDesigns: () => get("/api/designs"),
  saveDesign: (payload) => post("/api/designs", payload),
  getDesign: (id) => get(`/api/designs/${id}`),
  deleteDesign: async (id) => {
    const res = await fetch(`/api/designs/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },
  // pdf download (Blob)
  async downloadPdf(payload) {
    const res = await fetch("/api/pdf", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`PDF failed (HTTP ${res.status})`);
    const blob = await res.blob();
    const cd = res.headers.get("Content-Disposition") || "";
    const m = cd.match(/filename="(.+?)"/);
    return { blob, filename: m ? m[1] : "land-view.pdf" };
  },
  // same-origin proxy for allow-listed image hosts (taint-free export)
  proxied: (url) => `/api/img?u=${encodeURIComponent(url)}`,
};
