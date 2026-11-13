import { useState } from 'react';
import { Button } from './Button.jsx';
import { Field } from './Field.jsx';

export function Modal({
  title,
  subtitle,
  fields = [],
  initial = {},
  submitLabel = 'EXECUTE',
  danger = false,
  onClose,
  onSubmit,
  children,
}) {
  const [values, setValues] = useState(() =>
    Object.fromEntries(
      fields.map((f) => [
        f.name,
        initial[f.name] ?? f.default ?? (f.type === 'checkbox' ? false : ''),
      ]),
    ),
  );
  const [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await onSubmit(values);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="modal" onSubmit={submit}>
        <div className="modal-head">
          <div>
            <span className="eyebrow">SYSTEM DIALOG</span>
            <h3>{title}</h3>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button type="button" className="x" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="form-grid">
          {children ||
            fields.map((f) => (
              <Field
                key={f.name}
                field={f}
                value={values[f.name]}
                onChange={(v) => setValues({ ...values, [f.name]: v })}
              />
            ))}
        </div>
        {error && <div className="error-box">{error}</div>}
        <div className="modal-actions">
          <Button onClick={onClose}>CANCEL</Button>
          <Button type="submit" kind={danger ? 'danger' : 'primary'} disabled={busy}>
            {busy ? 'WORKING...' : submitLabel}
          </Button>
        </div>
      </form>
    </div>
  );
}
