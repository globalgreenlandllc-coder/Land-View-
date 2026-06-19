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
  getElements: () => get("/api/elements"),
  getProperty: (q) => get(`/api/property?q=${encodeURIComponent(q)}`),
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
