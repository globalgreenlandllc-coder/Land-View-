// Add / configure / remove backyard elements. Each element carries its type +
// per-element options (pool shape, deck material, fence type…) and an optional
// size; these feed the render prompt and the cost estimate.
export default function ElementEditor({ catalog, els, onChange }) {
  const byKey = Object.fromEntries(catalog.map((e) => [e.key, e]));

  function add(key) {
    if (!key) return;
    const def = byKey[key];
    const options = Object.fromEntries(def.options.map((o) => [o.key, o.choices[0]]));
    onChange([...els, { type: key, options, size: def.default_size }]);
  }
  function update(i, patch) {
    onChange(els.map((e, idx) => (idx === i ? { ...e, ...patch } : e)));
  }
  function setOpt(i, k, v) {
    onChange(els.map((e, idx) => (idx === i ? { ...e, options: { ...e.options, [k]: v } } : e)));
  }
  function remove(i) { onChange(els.filter((_, idx) => idx !== i)); }

  const unit = (kind) => (kind === "area" ? "sq ft" : kind === "linear" ? "ft" : "qty");

  return (
    <div>
      <div className="add-el">
        <select value="" onChange={(e) => add(e.target.value)}>
          <option value="">+ Add element…</option>
          {catalog.map((e) => <option key={e.key} value={e.key}>{e.name}</option>)}
        </select>
      </div>

      {els.length === 0 && <p className="muted small">No elements yet — add a pool, patio, fence, plants…</p>}

      <div className="el-list">
        {els.map((el, i) => {
          const def = byKey[el.type];
          if (!def) return null;
          return (
            <div className="el-card" key={i}>
              <div className="el-head">
                <b>{def.name}</b>
                <button type="button" className="rm" onClick={() => remove(i)}>✕</button>
              </div>
              <div className="el-opts">
                {def.options.map((o) => (
                  <label key={o.key}>
                    <span>{o.label}</span>
                    <select value={el.options?.[o.key] ?? o.choices[0]}
                      onChange={(e) => setOpt(i, o.key, e.target.value)}>
                      {o.choices.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </label>
                ))}
                <label>
                  <span>Size ({unit(def.kind)})</span>
                  <input type="number" min="0" value={el.size ?? def.default_size}
                    onChange={(e) => update(i, { size: Number(e.target.value) })} />
                </label>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
