import { useEffect, useState } from "react";
import { api } from "./api.js";
import Home from "./components/Home.jsx";
import ElementEditor from "./components/ElementEditor.jsx";
import CostPanel from "./components/CostPanel.jsx";
import DesignsBar from "./components/DesignsBar.jsx";

const TIMES = [
  ["day", "☀️ Day"],
  ["dusk", "🌆 Dusk"],
  ["evening", "🌙 Evening"],
];

const sqft = (n) => (n == null ? "—" : n.toLocaleString() + " sq ft");

export default function App() {
  const [view, setView] = useState("home"); // "home" | "app"
  const [styles, setStyles] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [address, setAddress] = useState("");
  const [property, setProperty] = useState(null);
  const [styleKey, setStyleKey] = useState("modern");
  const [vision, setVision] = useState("");
  const [els, setEls] = useState([]);
  const [cost, setCost] = useState(null);
  const [timeOfDay, setTimeOfDay] = useState("day");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState("");   // "" | "property" | "render"
  const [error, setError] = useState("");
  const [stylesError, setStylesError] = useState(false);
  const [satError, setSatError] = useState(false);
  const [showPrompt, setShowPrompt] = useState(false);

  useEffect(() => {
    api.getStyles().then((d) => setStyles(d.styles)).catch(() => setStylesError(true));
    api.getElements().then((d) => setCatalog(d.elements)).catch(() => {});
  }, []);

  // Recompute the cost estimate (debounced) whenever the elements change.
  useEffect(() => {
    const t = setTimeout(() => {
      api.cost({ elements: els, sizes: property?.sizes })
        .then(setCost).catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [els, property]);

  // Inputs changed since the last render -> the shown before/after is stale.
  function pickStyle(k) { setStyleKey(k); setResult(null); }
  function changeVision(v) { setVision(v); setResult(null); }
  function changeTime(k) { setTimeOfDay(k); setResult(null); }
  function changeEls(next) { setEls(next); setResult(null); }

  function buildDesign() {
    return { address: property?.address || address, property, style: styleKey,
             vision, elements: els, time_of_day: timeOfDay };
  }
  function loadDesign(d) {
    if (!d) return;
    setProperty(d.property || null);
    setAddress(d.address || "");
    setStyleKey(d.style || "modern");
    setVision(d.vision || "");
    setEls(d.elements || []);
    setTimeOfDay(d.time_of_day || "day");
    setResult(null);
  }
  async function downloadPdf() {
    try {
      const { blob, filename } = await api.downloadPdf({
        ...buildDesign(), after_url: result?.after_url,
      });
      const a = document.createElement("a");
      const u = URL.createObjectURL(blob);
      a.href = u; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(u), 4000);
    } catch (e) { setError(e.message); }
  }

  async function findProperty(e) {
    e?.preventDefault();
    if (!address.trim()) return;
    setLoading("property"); setError(""); setResult(null); setSatError(false);
    try {
      setProperty(await api.getProperty(address.trim()));
    } catch (e2) {
      setError(e2.message); setProperty(null);
    } finally { setLoading(""); }
  }

  async function generate() {
    setLoading("render"); setError("");
    try {
      setResult(await api.render({ property, style: styleKey, vision,
        elements: els, time_of_day: timeOfDay }));
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
      const objUrl = URL.createObjectURL(blob);
      a.href = objUrl;
      a.download = "land-view-design.png";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(objUrl), 4000); // revoke after download starts
    } catch {
      window.open(url, "_blank");
    }
  }

  const sizes = property?.sizes || {};

  const goHome = () => { setView("home"); window.scrollTo(0, 0); };
  const launch = () => { setView("app"); window.scrollTo(0, 0); };

  return (
    <div className="app">
      <header className="hdr">
        <button className="brand" onClick={goHome}><span className="dot" /> Land-View</button>
        {view === "home"
          ? <button className="nav-btn primary" onClick={launch}>Launch app</button>
          : <button className="nav-btn" onClick={goHome}>← Home</button>}
      </header>

      {view === "home" && <Home styles={styles} onStart={launch} />}

      {view === "app" && (
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
                {satError
                  ? <div className="sat-fallback">Satellite image unavailable for this location.</div>
                  : <img src={property.satellite_url} alt="satellite view" onError={() => setSatError(true)} />}
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
            {stylesError && <div className="err">Couldn't load styles — is the API running?</div>}
            <div className="styles">
              {styles.map((s) => (
                <button key={s.key} type="button" aria-pressed={styleKey === s.key}
                  className={"style-card" + (styleKey === s.key ? " on" : "")}
                  onClick={() => pickStyle(s.key)}>
                  <div className="swatches">
                    {s.palette.map((c, i) => <span key={i} style={{ background: c }} />)}
                  </div>
                  <div className="style-name">{s.name}</div>
                  <div className="style-blurb">{s.blurb}</div>
                </button>
              ))}
            </div>

            <label className="lbl">Describe the vision</label>
            <textarea rows={3} value={vision} onChange={(e) => changeVision(e.target.value)}
              placeholder='e.g. "kidney pool, cedar privacy fence, stone patio with seating, trees along the back"' />

            <label className="lbl">Elements</label>
            <ElementEditor catalog={catalog} els={els} onChange={changeEls} />

            <label className="lbl">Lighting</label>
            <div className="seg">
              {TIMES.map(([k, label]) => (
                <button key={k} type="button" aria-pressed={timeOfDay === k}
                  className={timeOfDay === k ? "on" : ""} onClick={() => changeTime(k)}>{label}</button>
              ))}
            </div>

            <button type="button" className="primary block big" disabled={loading === "render"} onClick={generate}>
              {loading === "render" ? "Generating…" : "✨ Generate design"}
            </button>

            <label className="lbl" style={{ marginTop: 18 }}>Estimated budget</label>
            <CostPanel cost={cost} />
          </section>
        )}

        {/* SAVED DESIGNS */}
        {property && (
          <section className="card">
            <h2><span className="num">★</span> My designs</h2>
            <DesignsBar buildDesign={buildDesign} onLoad={loadDesign} />
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
            {result.note && !result.demo && <div className="demo-banner">{result.note}</div>}
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
              <button type="button" className="primary" onClick={downloadAfter}>⬇ Export image</button>
              <button type="button" onClick={downloadPdf}>📄 Client PDF</button>
              <button type="button" onClick={() => window.print()}>🖨 Print</button>
              <button type="button" onClick={() => setShowPrompt((v) => !v)}>
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
      )}

      <footer className="foot">
        Land-View · satellite + scale + style + AI prompt pipeline. Renders are
        property-conditioned once an image API is connected.
      </footer>
    </div>
  );
}
