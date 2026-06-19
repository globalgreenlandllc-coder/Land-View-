import { useEffect, useState } from "react";
import { api } from "./api.js";

const TIMES = [
  ["day", "☀️ Day"],
  ["dusk", "🌆 Dusk"],
  ["evening", "🌙 Evening"],
];

const sqft = (n) => (n == null ? "—" : n.toLocaleString() + " sq ft");

export default function App() {
  const [styles, setStyles] = useState([]);
  const [address, setAddress] = useState("");
  const [property, setProperty] = useState(null);
  const [styleKey, setStyleKey] = useState("modern");
  const [vision, setVision] = useState("");
  const [timeOfDay, setTimeOfDay] = useState("day");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState("");   // "" | "property" | "render"
  const [error, setError] = useState("");
  const [showPrompt, setShowPrompt] = useState(false);

  useEffect(() => { api.getStyles().then((d) => setStyles(d.styles)).catch(() => {}); }, []);

  async function findProperty(e) {
    e?.preventDefault();
    if (!address.trim()) return;
    setLoading("property"); setError(""); setResult(null);
    try {
      setProperty(await api.getProperty(address.trim()));
    } catch (e2) {
      setError(e2.message); setProperty(null);
    } finally { setLoading(""); }
  }

  async function generate() {
    setLoading("render"); setError("");
    try {
      setResult(await api.render({ property, style: styleKey, vision, time_of_day: timeOfDay }));
    } catch (e2) {
      setError(e2.message);
    } finally { setLoading(""); }
  }

  async function downloadAfter() {
    const url = result?.after_url;
    if (!url) return;
    try {
      const src = url.startsWith("data:")
        ? url
        : (url.includes("arcgisonline.com") ? api.proxied(url) : url);
      const blob = await (await fetch(src)).blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "land-view-design.png";
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(a.href);
    } catch {
      window.open(url, "_blank");
    }
  }

  const sizes = property?.sizes || {};

  return (
    <div className="app">
      <header className="hdr">
        <div className="brand"><span className="dot" /> Land-View</div>
        <div className="tag">AI backyard designer — from your client's real property</div>
      </header>

      <main className="wrap">
        {/* STEP 1 — property */}
        <section className="card">
          <h2><span className="num">1</span> Property</h2>
          <form className="addr" onSubmit={findProperty}>
            <input value={address} onChange={(e) => setAddress(e.target.value)}
              placeholder="Enter a property address…" inputMode="text" />
            <button className="primary" disabled={loading === "property"}>
              {loading === "property" ? "Finding…" : "Find property"}
            </button>
          </form>
          {error && <div className="err">{error}</div>}

          {property && (
            <div className="prop">
              <div className="sat">
                <img src={property.satellite_url} alt="satellite view" />
                <span className="sat-tag">Satellite · current</span>
              </div>
              <div className="meta">
                <div className="addr-line">{property.address}</div>
                <div className="sizes">
                  <div><span>Lot</span><b>{sqft(sizes.lot_sqft)}</b></div>
                  <div><span>House</span><b>{sqft(sizes.house_sqft)}</b></div>
                  <div><span>Backyard</span><b>{sqft(sizes.backyard_sqft)}</b></div>
                  <div><span>View width</span><b>{sizes.view_width_ft ? sizes.view_width_ft + " ft" : "—"}</b></div>
                </div>
                <p className="muted small">{property.scale_note}</p>
              </div>
            </div>
          )}
        </section>

        {/* STEP 2 — design */}
        {property && (
          <section className="card">
            <h2><span className="num">2</span> Design</h2>

            <label className="lbl">Style</label>
            <div className="styles">
              {styles.map((s) => (
                <button key={s.key}
                  className={"style-card" + (styleKey === s.key ? " on" : "")}
                  onClick={() => setStyleKey(s.key)}>
                  <div className="swatches">
                    {s.palette.map((c, i) => <span key={i} style={{ background: c }} />)}
                  </div>
                  <div className="style-name">{s.name}</div>
                  <div className="style-blurb">{s.blurb}</div>
                </button>
              ))}
            </div>

            <label className="lbl">Describe the vision</label>
            <textarea rows={3} value={vision} onChange={(e) => setVision(e.target.value)}
              placeholder='e.g. "kidney pool, cedar privacy fence, stone patio with seating, trees along the back"' />

            <label className="lbl">Lighting</label>
            <div className="seg">
              {TIMES.map(([k, label]) => (
                <button key={k} className={timeOfDay === k ? "on" : ""} onClick={() => setTimeOfDay(k)}>{label}</button>
              ))}
            </div>

            <button className="primary block big" disabled={loading === "render"} onClick={generate}>
              {loading === "render" ? "Generating…" : "✨ Generate design"}
            </button>
          </section>
        )}

        {/* STEP 3 — result */}
        {result && (
          <section className="card">
            <h2><span className="num">3</span> Before / After</h2>
            {result.demo && (
              <div className="demo-banner">
                Demo mode — no image API connected yet, so the “after” is a placeholder.
                Connect an image model (set <code>RENDER_PROVIDER</code> + key) to produce the
                real photorealistic render. The exact AI prompt is shown below.
              </div>
            )}
            <div className="ba">
              <figure>
                <img src={result.before_url} alt="before" />
                <figcaption>Before — current property</figcaption>
              </figure>
              <figure>
                <img src={result.after_url} alt="after" className={result.demo ? "placeholder" : ""} />
                <figcaption>{result.demo ? "After — placeholder (demo)" : "After — proposed design"}</figcaption>
              </figure>
            </div>

            <div className="actions">
              <button className="primary" onClick={downloadAfter}>⬇ Export image</button>
              <button onClick={() => window.print()}>🖨 Print</button>
              <button onClick={() => setShowPrompt((v) => !v)}>
                {showPrompt ? "Hide" : "View"} AI prompt
              </button>
            </div>
            {showPrompt && (
              <pre className="prompt">{result.prompt}
                {"\n\n— negative —\n" + result.negative}</pre>
            )}
          </section>
        )}
      </main>

      <footer className="foot">
        Phase 1 · satellite + scale + style + prompt pipeline. Renders are
        property-conditioned once an image API is connected.
      </footer>
    </div>
  );
}
