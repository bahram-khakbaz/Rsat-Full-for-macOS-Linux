export function Panel({ title, code, actions, children, className = '' }) {
  return (
    <section className={'panel ' + className}>
      <div className="panel-title">
        <div>
          <b>[{code}]</b>
          <span>{title}</span>
        </div>
        <div className="panel-actions">{actions}</div>
      </div>
      {children}
    </section>
  );
}
