import { useState, type ReactNode } from 'react'

import { api } from '../api/client'
import type { FieldTrust, Source } from '../api/types'
import { useApi } from '../api/useApi'
import { useCan } from '../auth/AuthContext'
import { Icon } from './Icon'
import { Loader } from './Loader'
import { useToast } from './Toasts'
import { Card, EmptyState, ErrorAlert } from './ui'
import { FIELD_LABELS } from '../format'

function trustTone(value: number) {
  return value >= 80 ? 'good' : value >= 60 ? 'fix' : 'bad'
}

// Connector setup, "Trust": how much Lumina trusts this system for each detail it sends. The most trusted system
// wins each detail of a customer, and the trust feeds the score. An administrator ticks one or more details,
// gives them one value and saves; every customer is recalculated. Everyone else sees the values only.
export function FieldTrustStep({ source, title, onChanged }: { source: Source; title: ReactNode; onChanged: () => void }) {
  const toast = useToast()
  const canEdit = useCan('manage_settings')
  const saved = useApi(() => api.fieldTrust(source.code), [source.code])
  const [draft, setDraft] = useState<Record<string, number>>({})
  const [selected, setSelected] = useState<string[]>([])
  const [value, setValue] = useState(70)
  const [busy, setBusy] = useState(false)

  const data: FieldTrust | null = saved.data
  const fields = data?.fields ?? []
  const allChosen = fields.length > 0 && selected.length === fields.length
  const changed = Object.entries(draft).filter(([f, v]) => fields.find((x) => x.field === f)?.trust !== v)

  const toggle = (field: string) =>
    setSelected((s) => (s.includes(field) ? s.filter((x) => x !== field) : [...s, field]))
  const apply = () => {
    setDraft((d) => ({ ...d, ...Object.fromEntries(selected.map((f) => [f, value])) }))
    setSelected([])
  }

  const save = async () => {
    setBusy(true)
    try {
      await api.saveFieldTrust(source.code, Object.fromEntries(changed))
      toast('success', `Trust saved for ${changed.length} detail${changed.length === 1 ? '' : 's'}. Every customer has been recalculated.`)
      setDraft({})
      saved.reload()
      onChanged()
    } catch (e) {
      toast('error', (e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card
      title={title}
      description={
        canEdit
          ? 'How much Lumina trusts this system for each detail it sends. Tick details, give them one value, then save. The most trusted system wins each detail.'
          : 'How much Lumina trusts this system for each detail it sends. Only an administrator can change it.'
      }
      flush
      footer={
        canEdit && fields.length > 0 ? (
          <>
            <span className="text-sm muted">
              {changed.length ? `${changed.length} unsaved change${changed.length === 1 ? '' : 's'}` : 'No unsaved changes'}
            </span>
            <div className="row" style={{ gap: 8 }}>
              <button type="button" className="btn" disabled={!changed.length || busy} onClick={() => setDraft({})}>
                Undo changes
              </button>
              <button type="button" className="btn btn-primary" disabled={!changed.length || busy} onClick={save}>
                <Icon name="check" size={16} /> {busy ? 'Recalculating...' : 'Save and recalculate'}
              </button>
            </div>
          </>
        ) : undefined
      }
    >
      {saved.error && (
        <div className="card-body">
          <ErrorAlert message={saved.error} />
        </div>
      )}
      {!data && !saved.error && <Loader kind="converge" label="Loading trust" size={44} />}
      {data && fields.length === 0 && (
        <EmptyState icon="sliders" title="Nothing to trust yet">
          Choose what to read first. Each detail this connector maps then gets its own trust.
        </EmptyState>
      )}

      {data && fields.length > 0 && (
        <>
          {canEdit && (
            <div className="files-toolbar trust-toolbar">
              <span className="text-sm muted">
                {selected.length ? `${selected.length} selected` : 'Tick the details to give the same trust'}
              </span>
              <div className="trust-apply">
                <label htmlFor="trust-value" className="text-sm">
                  Trust
                </label>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={value}
                  onChange={(e) => setValue(Number(e.target.value))}
                  aria-label="Trust for the selected details"
                  style={{ accentColor: 'var(--accent)' }}
                />
                <input
                  id="trust-value"
                  className="input input-sm num"
                  type="number"
                  min={0}
                  max={100}
                  value={value}
                  onChange={(e) => setValue(Math.max(0, Math.min(100, Math.round(Number(e.target.value) || 0))))}
                />
                <button type="button" className="btn btn-sm" disabled={!selected.length} onClick={apply}>
                  Apply to {selected.length || ''} selected
                </button>
              </div>
            </div>
          )}

          <div className="table-wrap">
            <table className="table trust-table">
              <thead>
                <tr>
                  {canEdit && (
                    <th style={{ width: 36 }}>
                      <input
                        type="checkbox"
                        aria-label="Select every detail"
                        checked={allChosen}
                        onChange={() => setSelected(allChosen ? [] : fields.map((f) => f.field))}
                      />
                    </th>
                  )}
                  <th>Detail</th>
                  <th>Trust</th>
                  <th className="right trust-by">Set by</th>
                </tr>
              </thead>
              <tbody>
                {fields.map((f) => {
                  const current = draft[f.field] ?? f.trust
                  const edited = draft[f.field] !== undefined && draft[f.field] !== f.trust
                  const setBy = edited ? 'Unsaved' : f.own ? 'Administrator' : `Default (${data.default})`
                  return (
                    <tr key={f.field} className={selected.includes(f.field) ? 'is-selected' : undefined}>
                      {canEdit && (
                        <td>
                          <input
                            type="checkbox"
                            aria-label={`Select ${FIELD_LABELS[f.field] ?? f.label}`}
                            checked={selected.includes(f.field)}
                            onChange={() => toggle(f.field)}
                          />
                        </td>
                      )}
                      <td>
                        <strong>{FIELD_LABELS[f.field] ?? f.label}</strong>
                        <span className="trust-by-inline text-xs muted">{setBy}</span>
                      </td>
                      <td>
                        <span className="trust-cell">
                          <span className="trust-meter" aria-hidden="true">
                            <i className={`is-${trustTone(current)}`} style={{ width: `${current}%` }} />
                          </span>
                          <span className="num trust-num">{current}</span>
                          {edited && <span className="trust-was text-xs muted">was {f.trust}</span>}
                        </span>
                      </td>
                      <td className="right text-sm muted trust-by">{setBy}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  )
}
