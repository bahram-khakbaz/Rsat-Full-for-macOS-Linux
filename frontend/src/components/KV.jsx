export function KV({ items }) {
  return (
    <div className="kv">
      {items.map(([k, v]) => (
        <div key={k}>
          <span>{k}</span>
          <b>{String(v ?? '—')}</b>
        </div>
      ))}
    </div>
  );
}
