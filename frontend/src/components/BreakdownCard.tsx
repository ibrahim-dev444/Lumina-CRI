import { useState } from 'react'

import type { BreakdownGroup, CustomerBreakdown } from '../api/types'
import { Icon } from './Icon'
import { Loader } from './Loader'
import { Card, ErrorAlert } from './ui'

// The facts the super filter knows, in the order the URL keeps them.
export const FILTER_KEYS = ['score', 'kyc', 'country', 'residency', 'risk', 'source', 'gender', 'age'] as const
export type Filters = Partial<Record<(typeof FILTER_KEYS)[number], string[]>>

// Trust bands keep their meaning in colour (and always carry their label); every other fact is one series.
const SCORE_TONE: Record<string, string> = { high: 'is-high', medium: 'is-medium', low: 'is-low', none: 'is-none' }

function labelOf(data: CustomerBreakdown, key: string, value: string) {
  return data.options[key]?.find((o) => o.key === value)?.label ?? (value === 'unknown' ? 'Not known' : value)
}

// "Customer breakdown": how the customers split by one fact, with filters that combine. Clicking a bar filters
// the list below by that group; the same filters drive the chart, the list and its export.
export function BreakdownCard({
  data,
  error,
  filters,
  onBy,
  onFilters,
}: {
  data: CustomerBreakdown | null
  error: string | null
  filters: Filters
  onBy: (by: string) => void
  onFilters: (next: Filters) => void
}) {
  const [adding, setAdding] = useState(false)
  const [addKey, setAddKey] = useState('kyc')
  const [addValue, setAddValue] = useState('')
  const [hover, setHover] = useState<string | null>(null)

  const active = Object.entries(filters).flatMap(([k, values]) => (values ?? []).map((v) => [k, v] as const))
  const set = (key: string, values: string[]) => onFilters({ ...filters, [key]: values.length ? values : undefined })
  const toggle = (key: string, values: string[]) => {
    const current = filters[key as keyof Filters] ?? []
    const on = values.every((v) => current.includes(v))
    set(key, on ? current.filter((v) => !values.includes(v)) : [...new Set([...current, ...values])])
  }

  if (error) return <ErrorAlert message={error} />
  if (!data) {
    return (
      <div className="card">
        <Loader kind="stack" label="Counting customers" size={44} />
      </div>
    )
  }

  const max = Math.max(1, ...data.groups.map((g) => g.count))
  const dimLabel = data.dimensions.find((d) => d.key === data.by)?.label ?? ''
  const addOptions = data.options[addKey] ?? []
  const picked = (g: BreakdownGroup) => {
    const current = filters[data.by as keyof Filters] ?? []
    return (g.members ?? [g.key]).every((v) => current.includes(v))
  }

  return (
    <Card
      title="Customer breakdown"
      description="How your customers split. Click a bar to show only that group in the list below."
      actions={
        <label className="bd-by">
          <span className="text-sm muted">Break down by</span>
          <select className="select select-sm" value={data.by} onChange={(e) => onBy(e.target.value)}>
            {data.dimensions.map((d) => (
              <option key={d.key} value={d.key}>
                {d.label}
              </option>
            ))}
          </select>
        </label>
      }
    >
      <div className="bd">
        <div className="bd-head">
          <div className="bd-total">
            <strong className="num">{data.total.toLocaleString('en-IN')}</strong>
            <span className="text-sm muted">
              {active.length ? `of ${data.all.toLocaleString('en-IN')} customers match` : 'customers'}
            </span>
          </div>
          <div className="bd-filters" aria-label="Filters">
            {active.map(([k, v]) => (
              <button key={`${k}:${v}`} type="button" className="filter-chip" onClick={() => toggle(k, [v])}>
                <span className="muted">{data.dimensions.find((d) => d.key === k)?.label ?? k}:</span>{' '}
                {labelOf(data, k, v)} <Icon name="x" size={12} />
              </button>
            ))}
            {!adding && (
              <button type="button" className="btn btn-sm" onClick={() => setAdding(true)}>
                <Icon name="sliders" size={14} /> Add filter
              </button>
            )}
            {active.length > 0 && (
              <button type="button" className="link text-sm" onClick={() => onFilters({})}>
                Clear all
              </button>
            )}
          </div>
        </div>

        {adding && (
          <div className="bd-add">
            <select
              className="select select-sm"
              aria-label="Filter on"
              value={addKey}
              onChange={(e) => {
                setAddKey(e.target.value)
                setAddValue('')
              }}
            >
              {data.dimensions.map((d) => (
                <option key={d.key} value={d.key}>
                  {d.label}
                </option>
              ))}
            </select>
            <select className="select select-sm" aria-label="Value" value={addValue} onChange={(e) => setAddValue(e.target.value)}>
              <option value="">Choose...</option>
              {addOptions.map((o) => (
                <option key={o.key} value={o.key}>
                  {o.label} ({o.count})
                </option>
              ))}
            </select>
            <button
              type="button"
              className="btn btn-sm btn-primary"
              disabled={!addValue}
              onClick={() => {
                const option = addOptions.find((o) => o.key === addValue)
                const current = filters[addKey as keyof Filters] ?? []
                set(addKey, [...new Set([...current, ...(option?.members ?? [addValue])])])
                setAdding(false)
                setAddValue('')
              }}
            >
              Add
            </button>
            <button type="button" className="btn btn-sm" onClick={() => setAdding(false)}>
              Cancel
            </button>
          </div>
        )}

        {data.total === 0 ? (
          <p className="text-sm muted bd-empty">No customers match these filters.</p>
        ) : (
          <ul className="bd-bars" aria-label={`Customers by ${dimLabel.toLowerCase()}`}>
            {data.groups.map((g) => {
              const tone = data.by === 'score' ? SCORE_TONE[g.key] ?? '' : 'is-series'
              const on = picked(g)
              return (
                <li key={g.key}>
                  <button
                    type="button"
                    className={`bd-row${on ? ' is-on' : ''}`}
                    disabled={g.count === 0}
                    aria-pressed={on}
                    aria-label={`${g.label}: ${g.count} customers, ${g.share}%. ${on ? 'Remove filter' : 'Show only these'}`}
                    onMouseEnter={() => setHover(g.key)}
                    onMouseLeave={() => setHover(null)}
                    onFocus={() => setHover(g.key)}
                    onBlur={() => setHover(null)}
                    onClick={() => toggle(data.by, g.members ?? [g.key])}
                  >
                    <span className="bd-label">{g.label}</span>
                    <span className="bd-track" aria-hidden="true">
                      <i className={tone} style={{ width: `${(g.count / max) * 100}%`, minWidth: g.count ? 3 : 0 }} />
                    </span>
                    <span className="bd-value num">
                      {g.count.toLocaleString('en-IN')} <span className="muted">· {g.share}%</span>
                    </span>
                    {hover === g.key && g.count > 0 && (
                      <span className="chart-tooltip bd-tip" role="presentation">
                        <strong>{g.label}</strong>
                        {g.count.toLocaleString('en-IN')} customers · {g.share}% · {on ? 'click to remove filter' : 'click to filter'}
                      </span>
                    )}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </Card>
  )
}
