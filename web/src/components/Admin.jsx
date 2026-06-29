import { useEffect, useState } from "react";
import { api } from "../api.js";

const TABS = [
  ["analytics", "Analytics"],
  ["users", "Users"],
  ["connections", "API connections"],
  ["audit", "Audit log"],
];

export default function Admin({ me }) {
  const [tab, setTab] = useState("analytics");
  return (
    <main className="wrap">
      <section className="card">
        <h2>Admin</h2>
        <div className="seg admin-tabs">
          {TABS.map(([k, label]) => (
            <button key={k} type="button" aria-pressed={tab === k}
              className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{label}</button>
          ))}
        </div>
      </section>
      {tab === "analytics" && <Analytics />}
      {tab === "users" && <Users me={me} />}
      {tab === "connections" && <Connections />}
      {tab === "audit" && <Audit />}
    </main>
  );
}

function useAsync(fn, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const reload = () => {
    setLoading(true);
    fn().then(setData).then(() => setError("")).catch((e) => setError(e.message)).finally(() => setLoading(false));
  };
  useEffect(reload, deps); // eslint-disable-line
  return { data, error, loading, reload, setData };
}

function Analytics() {
  const { data, error, loading } = useAsync(() => api.adminAnalytics());
  if (loading) return <section className="card">Loading…</section>;
  if (error) return <section className="card"><div className="err">{error}</div></section>;
  const cards = [
    ["Total users", data.users_total],
    ["Active", data.users_active],
    ["Suspended", data.users_suspended],
    ["Admins", data.admins],
    ["Designs created", data.designs_total],
    ["Searches", data.searches],
    ["Renders", data.renders],
    ["Logins", data.logins],
  ];
  return (
    <section className="card">
      <h2>Analytics</h2>
      <div className="stat-grid">
        {cards.map(([label, val]) => (
          <div className="stat" key={label}><b>{val}</b><span>{label}</span></div>
        ))}
      </div>
    </section>
  );
}

function Users({ me }) {
  const { data: users, error, loading, reload } = useAsync(() => api.adminUsers());
  const [busy, setBusy] = useState("");
  const [actErr, setActErr] = useState("");

  async function act(fn, id) {
    setBusy(id); setActErr("");
    try { await fn(); reload(); } catch (e) { setActErr(e.message); } finally { setBusy(""); }
  }
  if (loading) return <section className="card">Loading…</section>;
  if (error) return <section className="card"><div className="err">{error}</div></section>;

  return (
    <section className="card">
      <h2>Users</h2>
      {actErr && <div className="err">{actErr}</div>}
      <div className="table">
        <div className="trow thead"><span>Email</span><span>Role</span><span>Status</span><span>Actions</span></div>
        {users.map((u) => {
          const self = u.id === me.id;
          return (
            <div className="trow" key={u.id}>
              <span className="ellipsis" title={u.email}>{u.email}{self && <em className="you"> (you)</em>}</span>
              <span><span className={"pill " + (u.role === "admin" ? "pill-green" : "")}>{u.role}</span></span>
              <span><span className={"pill " + (u.status === "active" ? "pill-green" : "pill-red")}>{u.status}</span></span>
              <span className="row-actions">
                {self ? <span className="muted small">—</span> : (
                  <>
                    {u.status === "active"
                      ? <button disabled={busy === u.id} onClick={() => act(() => api.adminUpdateUser(u.id, { status: "suspended" }), u.id)}>Suspend</button>
                      : <button disabled={busy === u.id} onClick={() => act(() => api.adminUpdateUser(u.id, { status: "active" }), u.id)}>Activate</button>}
                    {u.role === "user"
                      ? <button disabled={busy === u.id} onClick={() => act(() => api.adminUpdateUser(u.id, { role: "admin" }), u.id)}>Make admin</button>
                      : <button disabled={busy === u.id} onClick={() => act(() => api.adminUpdateUser(u.id, { role: "user" }), u.id)}>Make user</button>}
                    <button className="danger" disabled={busy === u.id}
                      onClick={() => { if (confirm(`Delete ${u.email}? This removes their designs.`)) act(() => api.adminDeleteUser(u.id), u.id); }}>Delete</button>
                  </>
                )}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Connections() {
  const { data: conns, error, loading, reload } = useAsync(() => api.adminConnections());
  if (loading) return <section className="card">Loading…</section>;
  if (error) return <section className="card"><div className="err">{error}</div></section>;
  return (
    <section className="card">
      <h2>API connections</h2>
      <p className="muted small">Keys are encrypted at rest and never shown again — only a masked preview. Saving a key for <b>AI image rendering</b> turns on real renders immediately.</p>
      {conns.map((c) => <ConnRow key={c.service} c={c} onChange={reload} />)}
    </section>
  );
}

function ConnRow({ c, onChange }) {
  const [provider, setProvider] = useState(c.provider || c.providers[0]);
  const [endpoint, setEndpoint] = useState(c.endpoint || "");
  const [secret, setSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  async function save() {
    setBusy(true); setErr(""); setMsg("");
    try {
      await api.adminSetConnection(c.service, { provider, endpoint, secret: secret || undefined });
      setSecret(""); setMsg("Saved"); onChange();
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  }
  async function remove() {
    setBusy(true); setErr(""); setMsg("");
    try { await api.adminDeleteConnection(c.service); onChange(); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  }

  return (
    <div className="conn">
      <div className="conn-head">
        <div>
          <b>{c.label}</b>
          {!c.wired && <span className="pill pill-muted" title="Stored for an upcoming integration">not wired yet</span>}
        </div>
        <span className={"pill " + (c.configured ? "pill-green" : "pill-red")}>
          {c.configured ? `connected${c.source ? " · " + c.source : ""}` : "not configured"}
        </span>
      </div>
      <div className="conn-grid">
        <label className="lbl">Provider
          <select value={provider} onChange={(e) => setProvider(e.target.value)}>
            {c.providers.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <label className="lbl">{c.endpoint_label}
          <input value={endpoint} onChange={(e) => setEndpoint(e.target.value)} placeholder="optional"
            autoComplete="off" autoCorrect="off" autoCapitalize="off" spellCheck={false} name={`endpoint-${c.service}`} />
        </label>
        <label className="lbl">{c.secret_label}
          <input type="password" value={secret} onChange={(e) => setSecret(e.target.value)}
            autoComplete="new-password" name={`secret-${c.service}`}
            placeholder={c.secret_masked ? `current: ${c.secret_masked} (leave blank to keep)` : "paste key…"} />
        </label>
      </div>
      <div className="conn-actions">
        <button className="primary" disabled={busy} onClick={save}>Save</button>
        {c.configured && c.source === "database" &&
          <button className="danger" disabled={busy} onClick={remove}>Disconnect</button>}
        {msg && <span className="ok-msg">{msg}</span>}
        {err && <span className="err inline">{err}</span>}
      </div>
    </div>
  );
}

function Audit() {
  const { data: rows, error, loading } = useAsync(() => api.adminAudit());
  if (loading) return <section className="card">Loading…</section>;
  if (error) return <section className="card"><div className="err">{error}</div></section>;
  return (
    <section className="card">
      <h2>Audit log</h2>
      <p className="muted small">Most recent 200 events.</p>
      <div className="table audit">
        <div className="trow thead"><span>When</span><span>Actor</span><span>Action</span><span>Target</span></div>
        {rows.map((a, i) => (
          <div className="trow" key={i}>
            <span className="muted small">{new Date(a.ts).toLocaleString()}</span>
            <span className="ellipsis" title={a.actor_email}>{a.actor_email || "—"}</span>
            <span><span className="pill">{a.action}</span></span>
            <span className="ellipsis" title={a.target}>{a.target || ""}{a.detail ? ` (${a.detail})` : ""}</span>
          </div>
        ))}
        {rows.length === 0 && <div className="muted small" style={{ padding: 12 }}>No events yet.</div>}
      </div>
    </section>
  );
}
