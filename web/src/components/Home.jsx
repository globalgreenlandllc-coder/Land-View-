// Marketing landing page shown before the designer tool.
const TESTIMONIALS = [
  ["From a cold call to a signed contract in one meeting — the client saw their own yard with a pool and said yes on the spot.",
   "Maya R.", "Landscape designer", "#15803d"],
  ["I used to pay for renderings and wait days. Now I generate options live while the homeowner watches.",
   "Devon K.", "Design-build owner", "#0ea5e9"],
  ["The before/after on their actual house is the closer. Nothing else gets clients excited like this.",
   "Priya S.", "Outdoor living pro", "#b45309"],
];

const PLANS = [
  { name: "Starter", price: "Free", blurb: "Try it on any address.",
    feats: ["Satellite + scale", "1 style + vision", "Before/after + image export"], cta: "Start free" },
  { name: "Pro", price: "$49", per: "/mo", featured: true, blurb: "For working designers.",
    feats: ["Everything in Starter", "All elements + materials", "Cost estimates + client PDF", "Save unlimited designs"], cta: "Choose Pro" },
  { name: "Studio", price: "$149", per: "/mo", blurb: "For teams & high volume.",
    feats: ["Everything in Pro", "Live photorealistic renders", "Team seats & branding", "Priority support"], cta: "Choose Studio" },
];

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
          <HeroMockup />
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

      {/* testimonials */}
      <section className="testimonials">
        <h2>Designers close more with it</h2>
        <p className="sub">Sample testimonials — swap in your own.</p>
        <div className="quote-grid">
          {TESTIMONIALS.map(([quote, name, role, color], i) => (
            <figure className="quote" key={i}>
              <blockquote>“{quote}”</blockquote>
              <figcaption>
                <span className="avatar" style={{ background: color }}>{name[0]}</span>
                <span><b>{name}</b><br /><span className="muted small">{role}</span></span>
              </figcaption>
            </figure>
          ))}
        </div>
      </section>

      {/* pricing */}
      <section className="pricing" id="pricing">
        <h2>Simple pricing</h2>
        <p className="sub">Start free. Upgrade when it's winning you work.</p>
        <div className="plan-cards">
          {PLANS.map((p) => (
            <div className={"plan-card" + (p.featured ? " featured" : "")} key={p.name}>
              {p.featured && <div className="plan-badge">Most popular</div>}
              <div className="plan-name">{p.name}</div>
              <div className="plan-price">{p.price}<span>{p.per || ""}</span></div>
              <div className="plan-blurb muted small">{p.blurb}</div>
              <ul className="plan-feats">
                {p.feats.map((f) => <li key={f}>{f}</li>)}
              </ul>
              <button className={p.featured ? "primary big" : "big outline"} onClick={onStart}>{p.cta}</button>
            </div>
          ))}
        </div>
        <p className="muted small center">Pricing shown is illustrative for this demo.</p>
      </section>

      {/* final cta */}
      <section className="cta-band">
        <h2>Show clients their dream yard — on their real property.</h2>
        <button className="primary big" onClick={onStart}>Start designing →</button>
      </section>
    </div>
  );
}

function HeroMockup() {
  return (
    <svg viewBox="0 0 460 340" className="hero-mockup" role="img" aria-label="Preview of the Land-View backyard designer app">
      <defs>
        <linearGradient id="hm-lawn" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#9bd98f" /><stop offset="1" stopColor="#7cc66f" />
        </linearGradient>
        <filter id="hm-sh" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="10" stdDeviation="14" floodColor="#13351f" floodOpacity="0.18" />
        </filter>
      </defs>

      {/* window */}
      <g filter="url(#hm-sh)">
        <rect x="14" y="14" width="432" height="300" rx="16" fill="#ffffff" stroke="#e4e8e4" />
        {/* title bar */}
        <rect x="14" y="14" width="432" height="34" rx="16" fill="#f3f6f3" />
        <rect x="14" y="32" width="432" height="16" fill="#f3f6f3" />
        <circle cx="34" cy="31" r="4" fill="#e3675f" /><circle cx="48" cy="31" r="4" fill="#e9b34a" /><circle cx="62" cy="31" r="4" fill="#5bb36a" />
        <rect x="90" y="24" width="300" height="14" rx="7" fill="#e7ece7" />
        <text x="100" y="34" fontSize="9" fill="#8b968b">123 Maple Dr — backyard</text>

        {/* design canvas (left) */}
        <g>
          <rect x="28" y="60" width="250" height="240" rx="10" fill="url(#hm-lawn)" />
          <rect x="40" y="70" width="150" height="64" rx="6" fill="#d8cbb6" />{/* house */}
          <text x="48" y="106" fontSize="9" fill="#7c6f57">house</text>
          <rect x="52" y="150" width="120" height="60" rx="8" fill="#caa978" />{/* deck */}
          <rect x="78" y="224" width="120" height="58" rx="29" fill="#2bb6e6" />
          <rect x="78" y="224" width="120" height="58" rx="29" fill="#1b9fd0" opacity=".3" />
          <circle cx="252" cy="86" r="14" fill="#2f8f3e" /><circle cx="252" cy="128" r="12" fill="#37a247" />
          <circle cx="48" cy="286" r="10" fill="#2f8f3e" />
          <text x="206" y="295" fontSize="9" fontWeight="700" fill="#0d5a26">AFTER</text>
        </g>

        {/* side panel (right) */}
        <g>
          <rect x="290" y="60" width="142" height="240" rx="10" fill="#fbfdfb" stroke="#e9ede9" />
          <text x="302" y="80" fontSize="10" fontWeight="700" fill="#15803d">DESIGN</text>
          {/* style swatches */}
          <rect x="302" y="90" width="22" height="14" rx="3" fill="#e7e5e4" />
          <rect x="328" y="90" width="22" height="14" rx="3" fill="#0ea5e9" />
          <rect x="354" y="90" width="22" height="14" rx="3" fill="#16a34a" />
          <rect x="380" y="90" width="22" height="14" rx="3" fill="#d6a76b" />
          {/* fake fields */}
          <rect x="302" y="116" width="118" height="12" rx="4" fill="#eef2ee" />
          <rect x="302" y="134" width="92" height="12" rx="4" fill="#eef2ee" />
          {/* cost chip */}
          <rect x="302" y="158" width="118" height="34" rx="8" fill="#f0faf3" stroke="#cdeccf" />
          <text x="310" y="172" fontSize="8" fill="#5b7a63">Est. budget</text>
          <text x="310" y="186" fontSize="12" fontWeight="800" fill="#15803d">$48k – $72k</text>
          {/* generate button */}
          <rect x="302" y="200" width="118" height="26" rx="8" fill="#15803d" />
          <text x="338" y="217" fontSize="10" fontWeight="700" fill="#fff">Generate</text>
          {/* lines */}
          <rect x="302" y="236" width="118" height="9" rx="4" fill="#eef2ee" />
          <rect x="302" y="250" width="80" height="9" rx="4" fill="#eef2ee" />
        </g>
      </g>
    </svg>
  );
}
