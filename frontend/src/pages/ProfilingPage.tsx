import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { ProfileCheck } from '../api/types'
import { useApi } from '../api/useApi'
import { Icon } from '../components/Icon'
import { Loader } from '../components/Loader'
import { Card, EmptyState, ErrorAlert, PageHeader } from '../components/ui'

// A chosen bar: "<check key>:<value>", the form the API takes.
type Pick = string

// Columns shown in the records list, in this order, when the source sent them.
const SHOWN: { field: 'name' | 'mobile' | 'pan' | 'email' | 'dob' | 'gender'; label: string }[] = [
  { field: 'name', label: 'Name' },
  { field: 'mobile', label: 'Mobile' },
  { field: 'pan', label: 'PAN' },
  { field: 'email', label: 'Email' },
  { field: 'dob', label: 'Date of birth' },
  { field: 'gender', label: 'Gender' },
]

// Data profiling: how each column's values look as the bank's systems sent them, before Lumina cleans them.
// Click a bar to see the records behind it; bars from different columns combine.
export function ProfilingPage() {
  const [source, setSource] = useState('all')
  const [picks, setPicks] = useState<Pick[]>([])
  const [all, setAll] = useState(false)
  const [page, setPage] = useState(1)
  const recordsRef = useRef<HTMLDivElement>(null)
  const summary = useApi(() => api.profiling(source), [source])
  const records = useApi(
    () => (picks.length ? api.profilingRecords(source, picks, page, all ? 50 : 10) : Promise.resolve(null)),
    [source, picks.join('|'), all, page],
  )

  const toggle = (pick: Pick) => {
    const adding = !picks.includes(pick)
    setPicks((p) => (p.includes(pick) ? p.filter((x) => x !== pick) : [...p, pick]))
    setAll(false)
    setPage(1)
    // Bring the matching records into view; they sit above the column cards.
    if (adding) requestAnimationFrame(() => recordsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }
  const labelOf = (pick: Pick) => {
    const [key, value] = [pick.slice(0, pick.indexOf(':')), pick.slice(pick.indexOf(':') + 1)]
    const check = summary.data?.checks.find((c) => c.key === key)
    return check ? `${check.column} ${check.label.toLowerCase()}: ${value}` : value
  }

  const data = summary.data
  const pages = records.data ? Math.max(1, Math.ceil(records.data.count / records.data.page_size)) : 1

  return (
    <>
      <PageHeader
        title="Data profiling"
        description="How each column looks as your systems send it, before Lumina cleans it. Select a bar to see the records behind it."
        actions={
          <select
            className="select"
            aria-label="Systems to profile"
            value={source}
            onChange={(e) => {
              setSource(e.target.value)
              setPage(1)
              setAll(false)
            }}
          >
            <option value="all">All connected systems</option>
            {data?.sources.map((s) => (
              <option key={s.code} value={s.code}>
                {s.name}
              </option>
            ))}
          </select>
        }
      />

      {summary.error && <ErrorAlert message={summary.error} />}
      {!data && !summary.error && (
        <div className="card">
          <Loader kind="stack" label="Profiling the records" />
        </div>
      )}

      {data && data.profiled === 0 && (
        <Card>
          <EmptyState icon="search" title="Nothing profiled yet">
            Records are profiled when a connector syncs. Open Connectors and click Sync now once on each system.
          </EmptyState>
        </Card>
      )}

      {data && data.profiled > 0 && (
        <>
          <div className="profile-summary">
            <span>
              <strong>{data.records.toLocaleString('en-IN')}</strong> records
              {data.profiled < data.records && (
                <span className="muted"> · {data.records - data.profiled} not profiled yet (sync their connector)</span>
              )}
            </span>
            {picks.length > 0 && (
              <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
                {picks.map((p) => (
                  <button key={p} type="button" className="filter-chip" onClick={() => toggle(p)}>
                    {labelOf(p)} <Icon name="x" size={12} />
                  </button>
                ))}
                <button type="button" className="link" onClick={() => setPicks([])}>
                  Clear
                </button>
              </div>
            )}
          </div>

          <div ref={recordsRef} className="profile-anchor" />
          {picks.length > 0 && (
            <Card
              title="Matching records"
              description={
                records.data
                  ? `Showing ${records.data.results.length} of ${records.data.count.toLocaleString('en-IN')}${records.data.masked ? '. Contact details are masked for your role.' : '.'}`
                  : 'Finding the records'
              }
              actions={
                records.data &&
                records.data.count > 10 &&
                (all ? (
                  <button type="button" className="btn btn-sm" onClick={() => { setAll(false); setPage(1) }}>
                    Show first 10
                  </button>
                ) : (
                  <button type="button" className="btn btn-primary btn-sm" onClick={() => { setAll(true); setPage(1) }}>
                    See all {records.data.count.toLocaleString('en-IN')} records
                  </button>
                ))
              }
              footer={
                all && records.data && pages > 1 && (
                  <>
                    <span className="text-sm muted">
                      Page {page} of {pages}
                    </span>
                    <div className="row" style={{ gap: 8 }}>
                      <button type="button" className="btn btn-sm" disabled={page <= 1} onClick={() => setPage((n) => n - 1)}>
                        Previous
                      </button>
                      <button type="button" className="btn btn-sm" disabled={page >= pages} onClick={() => setPage((n) => n + 1)}>
                        Next
                      </button>
                    </div>
                  </>
                )
              }
              flush
            >
              {records.error && (
                <div className="card-body">
                  <ErrorAlert message={records.error} />
                </div>
              )}
              {!records.data && !records.error && <Loader kind="stack" label="Finding the records" size={44} />}
              {records.data && records.data.count === 0 && (
                <EmptyState icon="search" title="No record matches all of these">
                  Remove a filter to widen the search.
                </EmptyState>
              )}
              {records.data && records.data.count > 0 && (
                <div className="table-wrap">
                  <table className="table" style={{ minWidth: 860 }}>
                    <thead>
                      <tr>
                        <th>Record</th>
                        <th>System</th>
                        {SHOWN.map((s) => (
                          <th key={s.field}>{s.label}</th>
                        ))}
                        <th>Customer</th>
                      </tr>
                    </thead>
                    <tbody>
                      {records.data.results.map((r) => (
                        <tr key={r.id}>
                          <td className="mono text-sm nowrap">{r.record_id}</td>
                          <td className="text-sm">{r.source_name}</td>
                          {SHOWN.map((s) => (
                            <td key={s.field} className={s.field === 'name' ? undefined : 'mono text-sm'}>
                              {r.values[s.field] ? (
                                <span className="sent-value">{r.values[s.field]}</span>
                              ) : (
                                <span className="muted">-</span>
                              )}
                            </td>
                          ))}
                          <td>
                            {r.customer ? (
                              <Link to={`/customers/${r.customer.id}`} className="link mono text-sm">
                                {r.customer.code}
                              </Link>
                            ) : (
                              <span className="muted">-</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          )}

          <div className="profile-grid">
            {data.checks.map((check) => (
              <CheckCard key={check.key} check={check} picks={picks} onToggle={toggle} />
            ))}
          </div>
        </>
      )}
    </>
  )
}

function CheckCard({ check, picks, onToggle }: { check: ProfileCheck; picks: Pick[]; onToggle: (p: Pick) => void }) {
  return (
    <Card
      title={
        <span className="stack" style={{ gap: 2 }}>
          <span className="text-xs muted profile-column">{check.column}</span>
          {check.label}
        </span>
      }
      actions={<span className="text-sm muted num">{check.records.toLocaleString('en-IN')} records</span>}
    >
      <ul className="profile-bars">
        {check.values.map((v) => {
          const pick = `${check.key}:${v.value}`
          const on = picks.includes(pick)
          const tone = v.value === 'Empty' || /Invalid|Wrong|Missing|future|Over 100|Unreadable|letters/i.test(v.value)
          return (
            <li key={v.value}>
              <button type="button" className={`profile-bar${on ? ' is-on' : ''}`} aria-pressed={on} onClick={() => onToggle(pick)}>
                <span className="profile-bar-label">{v.value}</span>
                <span className="profile-bar-track" aria-hidden="true">
                  <i className={tone ? 'is-issue' : undefined} style={{ width: `${Math.max(v.share, 1.5)}%` }} />
                </span>
                <span className="profile-bar-count num">
                  {v.count.toLocaleString('en-IN')} <span className="muted">· {v.share}%</span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
