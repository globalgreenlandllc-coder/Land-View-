const money = (n) => (n == null ? "—" : "$" + Math.round(n).toLocaleString());

// Rough budget estimate from the selected elements.
export default function CostPanel({ cost }) {
  if (!cost || !cost.line_items?.length) {
    return <p className="muted small">Add elements to see a rough cost estimate.</p>;
  }
  return (
    <div>
      <table className="cost">
        <tbody>
          {cost.line_items.map((li, i) => (
            <tr key={i}>
              <td><b>{li.label}</b>{li.detail ? <div className="muted small">{li.detail} {li.unit}</div> : null}</td>
              <td className="amt">{money(li.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="cost-range">
        Estimated range <b>{money(cost.low)} – {money(cost.high)}</b>
      </div>
      <p className="muted small">{cost.note}</p>
    </div>
  );
}
