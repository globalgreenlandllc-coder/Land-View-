// Marketing landing page shown before the designer tool.
const STEPS = [
  ["📍", "Enter an address", "We pull the real satellite image and estimate the lot, house and backyard size."],
  ["🎨", "Pick a style", "Modern, Tropical, Tuscan, Zen and more — each drives materials, plants and mood."],
  ["✨", "Describe the vision", "“Kidney pool, cedar fence, stone patio…” — we render it on the real property."],
  ["📤", "Share with clients", "Before/after, a client PDF, a cost estimate, and saved designs."],
];

const PLACEABLE = [
  ["🏊", "Pools & spas"], ["🪵", "Decks & patios"], ["🔥", "Fire features"],
  ["🌳", "Trees & plants"], ["🧱", "Fences & walls"], ["💡", "Lighting"],
  ["⛱️", "Pergolas & gazebos"], ["🍳", "Outdoor kitchens"],
];

export default function Home({ styles, onStart }) {
  return (
    <div className="home">
      {/* hero */}
      <section className="hero">
        <div className="hero-copy">
          <div className="pill-tag">AI backyard design</div>
          <h1>Turn any address into a <span className="grad">photorealistic</span> backyard.</h1>
          <p>Land-View pulls your client's real satellite view, scales it to the actual
            lot, and designs a backyard they can picture instantly — pools, patios,
            plantings and more, on their property.</p>
          <div className="hero-cta">
            <button className="primary big" onClick={onStart}>Start designing →</button>
            <a className="ghost-link" href="#how">See how it works</a>
          </div>
          <div className="trust">No sign-up · works on any address · mobile-ready</div>
        </div>
        <div className="hero-art" aria-hidden="true">
          <BeforeAfterArt />
        </div>
      </section>

      {/* how it works */}
      <section className="how" id="how">
        <h2>From address to client-ready in four steps</h2>
        <div className="steps">
          {STEPS.map(([icon, title, body], i) => (
            <div className="step" key={i}>
              <div className="step-icon">{icon}</div>
              <div className="step-n">Step {i + 1}</div>
              <h3>{title}</h3>
              <p>{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* styles */}
      <section className="gallery">
        <h2>Pick a vibe, not a spec sheet</h2>
        <p className="sub">Eight curated styles set the materials, plants and palette automatically.</p>
        <div className="style-strip">
          {(styles || []).map((s) => (
            <div className="style-chip" key={s.key}>
              <div className="swatches">{s.palette.map((c, i) => <span key={i} style={{ background: c }} />)}</div>
              <div className="style-name">{s.name}</div>
            </div>
          ))}
        </div>
      </section>

      {/* placeable */}
      <section className="placeable">
        <h2>Everything you'd put in a yard</h2>
        <div className="place-grid">
          {PLACEABLE.map(([icon, label]) => (
            <div className="place-item" key={label}><span>{icon}</span>{label}</div>
          ))}
        </div>
      </section>

      {/* final cta */}
      <section className="cta-band">
        <h2>Show clients their dream yard — on their real property.</h2>
        <button className="primary big" onClick={onStart}>Start designing →</button>
      </section>
    </div>
  );
}

function BeforeAfterArt() {
  return (
    <svg viewBox="0 0 420 320" className="ba-art" role="img">
      <defs>
        <clipPath id="leftHalf"><rect x="0" y="0" width="210" height="320" /></clipPath>
        <clipPath id="rightHalf"><rect x="210" y="0" width="210" height="320" /></clipPath>
        <linearGradient id="sky" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#dff3e6" /><stop offset="1" stopColor="#cfeaf6" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="420" height="320" rx="18" fill="url(#sky)" />

      {/* BEFORE (left, muted) */}
      <g clipPath="url(#leftHalf)">
        <rect x="0" y="0" width="210" height="320" fill="#cdd3cd" />
        <rect x="30" y="40" width="150" height="90" rx="4" fill="#b7b2a8" />
        <rect x="40" y="150" width="150" height="140" rx="4" fill="#c3c8bd" />
        <rect x="0" y="0" width="210" height="320" fill="#7a8a7a" opacity="0.12" />
      </g>

      {/* AFTER (right, designed) */}
      <g clipPath="url(#rightHalf)">
        <rect x="210" y="0" width="210" height="320" fill="#8fcf86" />
        <rect x="220" y="36" width="150" height="86" rx="6" fill="#d8cbb6" />{/* house */}
        <rect x="232" y="150" width="120" height="70" rx="8" fill="#caa978" />{/* deck */}
        <rect x="250" y="232" width="120" height="60" rx="30" fill="#2bb6e6" />{/* pool */}
        <rect x="250" y="232" width="120" height="60" rx="30" fill="#1b9fd0" opacity=".35" />
        <circle cx="392" cy="60" r="16" fill="#2f8f3e" />
        <circle cx="392" cy="120" r="14" fill="#37a247" />
        <circle cx="240" cy="300" r="12" fill="#2f8f3e" />
      </g>

      {/* divider + handle */}
      <line x1="210" y1="0" x2="210" y2="320" stroke="#fff" strokeWidth="4" />
      <circle cx="210" cy="160" r="18" fill="#fff" />
      <path d="M204 160 l-7 -7 v14 z M216 160 l7 -7 v14 z" fill="#15803d" />
      <text x="22" y="28" fontSize="13" fontWeight="700" fill="#5b635b">BEFORE</text>
      <text x="330" y="28" fontSize="13" fontWeight="700" fill="#0d5a26">AFTER</text>
    </svg>
  );
}
