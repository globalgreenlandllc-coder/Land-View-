import { useRef, useState } from "react";

// Palette of placeable elements. `type` flows into the render prompt + cost.
// Types match the backend element catalog so placed items get materials + cost.
const PALETTE = [
  { type: "trees", label: "Tree", emoji: "🌳" },
  { type: "beds", label: "Plant bed", emoji: "🌷" },
  { type: "lawn", label: "Lawn", emoji: "🟩" },
  { type: "patio", label: "Patio", emoji: "🟫" },
  { type: "deck", label: "Deck", emoji: "🪵" },
  { type: "pool", label: "Pool", emoji: "🏊" },
  { type: "hot_tub", label: "Hot tub", emoji: "♨️" },
  { type: "pathway", label: "Path", emoji: "🥾" },
  { type: "fence", label: "Fence", emoji: "🧱" },
  { type: "wall", label: "Wall", emoji: "🪨" },
  { type: "fire", label: "Fire pit", emoji: "🔥" },
  { type: "pergola", label: "Pergola", emoji: "⛱️" },
  { type: "gazebo", label: "Gazebo", emoji: "⛩️" },
  { type: "kitchen", label: "Kitchen", emoji: "🍴" },
  { type: "seating", label: "Seating", emoji: "🪑" },
  { type: "lighting", label: "Lighting", emoji: "💡" },
];
const EMOJI = Object.fromEntries(PALETTE.map((p) => [p.type, p.emoji]));

const MERC_R = 6378137, SPAN_M = 120, FT = 3.28084;
const toMerc = (lng, lat) => [
  MERC_R * lng * Math.PI / 180,
  MERC_R * Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)),
];

let _idc = 0;
const newId = () => `el_${Date.now().toString(36)}_${_idc++}`;

export default function DesignCanvas({ parcel, els, onChange }) {
  const ref = useRef(null);
  const dragRef = useRef(null);
  const [measure, setMeasure] = useState(false);
  const [mpts, setMpts] = useState([]);

  // Boundary polygon -> canvas fractions (0..1), via the satellite frame's mercator bbox.
  function boundaryPoints() {
    const ring = parcel?.boundary;
    if (!ring || !ring.length) return "";
    const [cx, cy] = toMerc(parcel.lng, parcel.lat);
    const half = (SPAN_M / Math.cos(parcel.lat * Math.PI / 180)) / 2;
    return ring.map(([lng, lat]) => {
      const [mx, my] = toMerc(lng, lat);
      const fx = (mx - (cx - half)) / (2 * half);
      const fy = ((cy + half) - my) / (2 * half);
      return `${(fx * 100).toFixed(2)},${(fy * 100).toFixed(2)}`;
    }).join(" ");
  }

  function addEl(p) {
    onChange([...(els || []), { id: newId(), type: p.type, label: p.label,
      x: 0.5, y: 0.5, options: {} }]);
  }
  function removeEl(id) { onChange((els || []).filter((e) => e.id !== id)); }

  function startDrag(e, id) {
    e.preventDefault();
    dragRef.current = id;
    const move = (ev) => {
      const r = ref.current.getBoundingClientRect();
      const cx = (ev.touches ? ev.touches[0].clientX : ev.clientX);
      const cy = (ev.touches ? ev.touches[0].clientY : ev.clientY);
      const x = Math.min(1, Math.max(0, (cx - r.left) / r.width));
      const y = Math.min(1, Math.max(0, (cy - r.top) / r.height));
      onChange((els || []).map((el) => el.id === dragRef.current ? { ...el, x, y } : el));
    };
    const up = () => {
      dragRef.current = null;
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
            <span className="pal-emoji">{p.emoji}</span>{p.label}
          </button>
        ))}
      </div>

      <div className="canvas" ref={ref} onClick={clickCanvas}>
        <img src={parcel.satellite_url} alt="parcel" className="canvas-bg" draggable={false} />
        <svg className="canvas-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
          {boundaryPoints() &&
            <polygon points={boundaryPoints()} className="boundary-poly" />}
          {measure && mpts.length > 0 &&
            <polyline points={mpts.map(([x, y]) => `${x * 100},${y * 100}`).join(" ")}
              className="measure-line-svg" />}
          {measure && mpts.map(([x, y], i) =>
            <circle key={i} cx={x * 100} cy={y * 100} r="0.9" className="measure-dot" />)}
        </svg>

        {placed.map((el) => (
          <div key={el.id} className="placed" onPointerDown={(e) => startDrag(e, el.id)}
            style={{ left: `${el.x * 100}%`, top: `${el.y * 100}%` }}
            title={el.label || el.type}>
            <span className="placed-emoji">{EMOJI[el.type] || "📍"}</span>
            <button type="button" className="placed-x" onClick={(e) => { e.stopPropagation(); removeEl(el.id); }}>×</button>
          </div>
        ))}

        <div className="scale-bar"><span /> ≈ {Math.round(SPAN_M * FT)} ft across</div>
      </div>

      <div className="canvas-actions">
        <button type="button" className={measure ? "on" : ""}
          onClick={() => { setMeasure((m) => !m); if (measure) setMpts([]); }}>
          📏 {measure ? "Measuring… (click)" : "Measure"}
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
