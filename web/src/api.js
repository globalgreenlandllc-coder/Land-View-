// Land-View API client. Relative paths; the Vite dev server proxies /api to Flask.

async function get(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error((await res.json().catch(() => ({})))?.error || `HTTP ${res.status}`);
  return res.json();
}
async function post(path, body) {
  const res = await fetch(path, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({})))?.error || `HTTP ${res.status}`);
  return res.json();
}

export const api = {
  getStyles: () => get("/api/styles"),
  getProperty: (q) => get(`/api/property?q=${encodeURIComponent(q)}`),
  render: (payload) => post("/api/render", payload),
  // same-origin proxy for allow-listed image hosts (taint-free export)
  proxied: (url) => `/api/img?u=${encodeURIComponent(url)}`,
};
