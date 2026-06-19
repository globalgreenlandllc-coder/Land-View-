import { useEffect, useState } from "react";
import { api } from "../api.js";

// Save / load / delete designs (persisted server-side in SQLite).
export default function DesignsBar({ buildDesign, onLoad }) {
  const [name, setName] = useState("");
  const [designs, setDesigns] = useState([]);
  const [status, setStatus] = useState("");

  const refresh = () => api.listDesigns().then((d) => setDesigns(d.designs)).catch(() => {});
  useEffect(() => { refresh(); }, []);

  async function save() {
    setStatus("Saving…");
    try {
      const rec = await api.saveDesign({ ...buildDesign(), name: name || "Untitled design" });
      setStatus(`Saved “${rec.name}”.`);
      refresh();
    } catch (e) { setStatus("Error: " + e.message); }
  }
  async function load(id) {
    try { onLoad(await api.getDesign(id)); setStatus("Loaded."); }
    catch (e) { setStatus("Error: " + e.message); }
  }
  async function del(id) {
    try { await api.deleteDesign(id); refresh(); } catch {}
  }

  return (
    <div>
      <div className="save-row">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Design name" />
        <button type="button" className="primary" onClick={save}>Save</button>
      </div>
      {status && <div className="status">{status}</div>}
      {designs.length > 0 && (
        <div className="design-list">
          {designs.map((d) => (
            <div className="design-row" key={d.id}>
              <button type="button" className="design-load" onClick={() => load(d.id)}>
                <b>{d.name}</b>
                <span className="muted small">{d.address || "—"} · {d.style} · {d.elements} elements</span>
              </button>
              <button type="button" className="rm" onClick={() => del(d.id)}>✕</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
