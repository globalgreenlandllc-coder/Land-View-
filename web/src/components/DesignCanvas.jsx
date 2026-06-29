import { useRef, useState } from "react";

// Palette of placeable elements. `type` flows into the render prompt + cost.
// Types match the backend element catalog so placed items get materials + cost.
const PALETTE = [
  { type: "trees", label: "Tree" },
  { type: "beds", label: "Plant bed" },
  { type: "lawn", label: "Lawn" },
  { type: "patio", label: "Patio" },
  { type: "deck", label: "Deck" },
  { type: "pool", label: "Pool" },
  { type: "hot_tub", label: "Hot tub" },
  { type: "pathway", label: "Path" },
  { type: "fence", label: "Fence" },
  { type: "wall", label: "Wall" },
  { type: "fire", label: "Fire pit" },
  { type: "pergola", label: "Pergola" },
  { type: "gazebo", label: "Gazebo" },
  { type: "kitchen", label: "Kitchen" },
  { type: "seating", label: "Seating" },
  { type: "lighting", label: "Lighting" },
];
const LABEL = Object.fromEntries(PALETTE.map((p) => [p.type, p.label]));

const MERC_R = 6378137, SPAN_M = 120, FT = 3.28084;
const toMerc = (lng, lat) => [
  MERC_R * lng * Math.PI / 180,
  MERC_R * Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)),
];

let _idc = 0;
const newId = () => `el_${Date.now().toString(36)}_${_idc++}`;

// Ray-casting point-in-polygon. `poly` is [[x,y],...] in any consistent units.
function inPoly(x, y, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

// Distance from point (px,py) to a polyline (array of [x,y]) in the same units.
function distToLine(px, py, line) {
  let min = Infinity;
  for (let i = 1; i < line.length; i++) {
    const [x1, y1] = line[i - 1], [x2, y2] = line[i];
    const dx = x2 - x1, dy = y2 - y1;
    const len2 = dx * dx + dy * dy || 1e-9;
    let t = ((px - x1) * dx + (py - y1) * dy) / len2;
    t = Math.max(0, Math.min(1, t));
    const d = Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
    if (d < min) min = d;
  }
  return min;
}
const ACCESS_CLEARANCE = 0.025; // ~3 m clearance kept around driveways/walkways

export default function DesignCanvas({ parcel, els, onChange }) {
  const ref = useRef(null);
  const dragRef = useRef(null);
  const lastValidRef = useRef(null);
  const [measure, setMeasure] = useState(false);
  const [mpts, setMpts] = useState([]);
  const [warning, setWarning] = useState("");

  // Convert a geo ring ([[lng,lat],...]) to canvas fractions [[fx,fy],...] via the
  // satellite frame's mercator bbox (same projection the image was rendered in).
  function ringToFractions(ring) {
    if (!ring || !ring.length) return [];
    const [cx, cy] = toMerc(parcel.lng, parcel.lat);
    const half = (SPAN_M / Math.cos(parcel.lat * Math.PI / 180)) / 2;
    return ring.map(([lng, lat]) => {
      const [mx, my] = toMerc(lng, lat);
      return [(mx - (cx - half)) / (2 * half), ((cy + half) - my) / (2 * half)];
    });
  }
  const ptsToStr = (fr) => fr.map(([x, y]) => `${(x * 100).toFixed(2)},${(y * 100).toFixed(2)}`).join(" ");

  const parcelFr = parcel?.boundary ? ringToFractions(parcel.boundary) : [];
  const setbackFr = parcel?.setback ? ringToFractions(parcel.setback) : [];
  const structFr = (parcel?.structures || []).map(ringToFractions);
  const accessFr = (parcel?.access || []).map(ringToFractions);

  // Is (x,y) a legal spot? Inside the lot, off structures, and clear of access ways.
  function legalSpot(x, y) {
    if (parcelFr.length && !inPoly(x, y, parcelFr))
      return { ok: false, reason: "Outside the property line" };
    for (const s of structFr)
      if (s.length && inPoly(x, y, s))
        return { ok: false, reason: "On the house / structure — kept clear" };
    for (const a of accessFr)
      if (a.length > 1 && distToLine(x, y, a) < ACCESS_CLEARANCE)
        return { ok: false, reason: "Blocks driveway / access — kept clear" };
    return { ok: true };
  }

  // Find an open-ground spot: parcel centroid first, else scan a grid for the
  // first legal cell, so new elements never spawn on a structure or off-lot.
  function openSpot() {
    if (!parcelFr.length) return { x: 0.5, y: 0.5 };
    const cx = parcelFr.reduce((s, p2) => s + p2[0], 0) / parcelFr.length;
    const cy = parcelFr.reduce((s, p2) => s + p2[1], 0) / parcelFr.length;
    if (legalSpot(cx, cy).ok) return { x: cx, y: cy };
    for (let gy = 0.1; gy <= 0.9; gy += 0.1)
      for (let gx = 0.1; gx <= 0.9; gx += 0.1)
        if (legalSpot(gx, gy).ok) return { x: gx, y: gy };
    return { x: cx, y: cy };
  }
  function addEl(p) {
    const { x, y } = openSpot();
    onChange([...(els || []), { id: newId(), type: p.type, label: p.label, x, y, options: {} }]);
  }
  function removeEl(id) { onChange((els || []).filter((e) => e.id !== id)); }

  function startDrag(e, id) {
    e.preventDefault();
    dragRef.current = id;
    const cur = (els || []).find((el) => el.id === id);
    lastValidRef.current = cur ? { x: cur.x, y: cur.y } : { x: 0.5, y: 0.5 };
    const move = (ev) => {
      const r = ref.current.getBoundingClientRect();
      const px = (ev.touches ? ev.touches[0].clientX : ev.clientX);
      const py = (ev.touches ? ev.touches[0].clientY : ev.clientY);
      const x = Math.min(1, Math.max(0, (px - r.left) / r.width));
      const y = Math.min(1, Math.max(0, (py - r.top) / r.height));
      const check = legalSpot(x, y);
      if (check.ok) {
        lastValidRef.current = { x, y };
        setWarning("");
        onChange((els || []).map((el) => el.id === dragRef.current ? { ...el, x, y } : el));
      } else {
        // Boundary lock / structure protection: hold at the last legal spot + warn.
        setWarning(check.reason);
        const lv = lastValidRef.current;
        onChange((els || []).map((el) => el.id === dragRef.current ? { ...el, x: lv.x, y: lv.y } : el));
      }
    };
    const up = () => {
      dragRef.current = null;
      setTimeout(() => setWarning(""), 1800);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  function clickCanvas(e) {
    if (!measure) return;
    const r = ref.current.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
    setMpts((p) => [...p, [x, y]]);
  }

  // Measurement in real units (canvas frame ≈ SPAN_M metres wide & tall).
  let dist = 0;
  for (let i = 1; i < mpts.length; i++) {
    const dx = (mpts[i][0] - mpts[i - 1][0]) * SPAN_M;
    const dy = (mpts[i][1] - mpts[i - 1][1]) * SPAN_M;
    dist += Math.hypot(dx, dy);
  }
  let area = 0;
  if (mpts.length >= 3) {
    for (let i = 0; i < mpts.length; i++) {
      const [x1, y1] = mpts[i], [x2, y2] = mpts[(i + 1) % mpts.length];
      area += (x1 * SPAN_M) * (y2 * SPAN_M) - (x2 * SPAN_M) * (y1 * SPAN_M);
    }
    area = Math.abs(area) / 2;
  }
  const placed = (els || []).filter((e) => e.x != null && e.y != null);

  return (
    <div className="canvas-tool">
      <div className="palette">
        {PALETTE.map((p) => (
          <button key={p.type} type="button" className="pal-item"
            onClick={() => addEl(p)} title={`Add ${p.label}`}>
            {p.label}
          </button>
        ))}
      </div>

      <div className="canvas" ref={ref} onClick={clickCanvas}>
        <img src={parcel.satellite_url} alt="parcel" className="canvas-bg" draggable={false} />
        <svg className="canvas-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
          {parcelFr.length > 0 && <polygon points={ptsToStr(parcelFr)} className="boundary-poly" />}
          {setbackFr.length > 0 && <polygon points={ptsToStr(setbackFr)} className="setback-poly" />}
          {structFr.map((s, i) => s.length > 0 &&
            <polygon key={i} points={ptsToStr(s)} className="structure-poly" />)}
          {accessFr.map((a, i) => a.length > 1 &&
            <polyline key={`a${i}`} points={ptsToStr(a)} className="access-line" />)}
          {measure && mpts.length > 0 &&
            <polyline points={mpts.map(([x, y]) => `${x * 100},${y * 100}`).join(" ")}
              className="measure-line-svg" />}
          {measure && mpts.map(([x, y], i) =>
            <circle key={i} cx={x * 100} cy={y * 100} r="0.9" className="measure-dot" />)}
        </svg>

        {placed.map((el) => (
          <div key={el.id} className="placed" onPointerDown={(e) => startDrag(e, el.id)}
            style={{ left: `${el.x * 100}%`, top: `${el.y * 100}%` }}
            title={el.label || LABEL[el.type] || el.type}>
            <span className="placed-pin" />
            <span className="placed-label">{el.label || LABEL[el.type] || el.type}</span>
            <button type="button" className="placed-x" onClick={(e) => { e.stopPropagation(); removeEl(el.id); }}>×</button>
          </div>
        ))}

        {warning && <div className="canvas-warning">{warning}</div>}
        <div className="scale-bar"><span /> ≈ {Math.round(SPAN_M * FT)} ft across</div>
      </div>

      <div className="site-legend">
        <span><i className="lg-boundary" /> Property line</span>
        <span><i className="lg-setback" /> Setback</span>
        <span><i className="lg-structure" /> No-design (structure)</span>
        {accessFr.length > 0 && <span><i className="lg-access" /> Driveway / access</span>}
        {parcel?.designable_sqft != null &&
          <span className="designable">Designable area: <b>{parcel.designable_sqft.toLocaleString()} sq ft</b></span>}
      </div>

      <div className="canvas-actions">
        <button type="button" className={measure ? "on" : ""}
          onClick={() => { setMeasure((m) => !m); if (measure) setMpts([]); }}>
          {measure ? "Measuring… (click)" : "Measure"}
        </button>
        {measure && mpts.length > 0 && (
          <>
            <span className="measure-readout">
              <b>{(dist * FT).toFixed(0)} ft</b>
              {area > 0 && <> · <b>{(area * 10.7639).toLocaleString(undefined, { maximumFractionDigits: 0 })} sq ft</b></>}
            </span>
            <button type="button" onClick={() => setMpts([])}>Clear</button>
          </>
        )}
        <span className="muted small">Tip: click a tile to add it, then drag to position.</span>
      </div>
    </div>
  );
}
