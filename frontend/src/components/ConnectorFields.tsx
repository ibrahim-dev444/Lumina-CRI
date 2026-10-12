import type { ConnectorField } from '../api/types'

// The form fields a connector type asks for (from the catalog). Secret fields are password boxes; when a
// secret is already stored they say so and stay empty: leaving them empty keeps the stored value.
export function ConnectorFields({
  fields,
  values,
  onChange,
  secretStored = false,
}: {
  fields: ConnectorField[]
  values: Record<string, string>
  onChange: (next: Record<string, string>) => void
  secretStored?: boolean
}) {
  const set = (name: string, value: string) => onChange({ ...values, [name]: value })

  return (
    <>
      {fields.map((f) => {
        const id = `cf-${f.name}`
        return (
          <div key={f.name} className={`form-field${f.name === 'connection_string' || f.name === 'url' ? ' wide' : ''}`}>
            <label htmlFor={id}>
              {f.label}
              {!f.required && <span className="muted"> (optional)</span>}
            </label>
            {f.kind === 'select' ? (
              <select id={id} className="select" value={values[f.name] ?? f.default} onChange={(e) => set(f.name, e.target.value)}>
                {f.choices.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id={id}
                className="input"
                type={f.secret ? 'password' : f.kind === 'number' ? 'number' : 'text'}
                autoComplete={f.secret ? 'new-password' : 'off'}
                spellCheck={false}
                placeholder={f.secret && secretStored ? 'Saved. Leave empty to keep it.' : f.default}
                value={values[f.name] ?? ''}
                onChange={(e) => set(f.name, e.target.value)}
              />
            )}
            {f.help && <span className="text-xs muted">{f.help}</span>}
          </div>
        )
      })}
    </>
  )
}
