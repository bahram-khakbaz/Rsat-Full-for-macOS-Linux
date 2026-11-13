export function Field({ field, value, onChange }) {
  if (field.type === 'select')
    return (
      <label>
        <span>{field.label}</span>
        <select value={value ?? field.default ?? ''} onChange={(e) => onChange(e.target.value)}>
          {field.options.map((x) => (
            <option key={x} value={x}>
              {x}
            </option>
          ))}
        </select>
      </label>
    );
  if (field.type === 'checkbox')
    return (
      <label className="check">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span>{field.label}</span>
      </label>
    );
  return (
    <label>
      <span>{field.label}</span>
      <input
        type={field.type || 'text'}
        value={value ?? ''}
        placeholder={field.placeholder || ''}
        minLength={field.minLength}
        maxLength={field.maxLength}
        required={field.required || false}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}
