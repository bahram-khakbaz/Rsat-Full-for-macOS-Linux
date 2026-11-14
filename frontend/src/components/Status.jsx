export function Status({ ok, children }) {
  return (
    <span className={'status ' + (ok === true ? 'ok' : ok === false ? 'bad' : 'neutral')}>
      <i />
      {children}
    </span>
  );
}
