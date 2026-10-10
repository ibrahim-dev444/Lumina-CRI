import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { AuditEvent } from '../api/types'
import { useApi } from '../api/useApi'
import { Icon } from '../components/Icon'
import { LoaderRow } from '../components/Loader'
import { Avatar, Card, EmptyState, ErrorAlert, PageHeader, StatusBadge } from '../components/ui'

const ACTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All actions' },
  { value: 'view_customer', label: 'Viewed customer' },
  { value: 'export', label: 'Exported customers' },
  { value: 'merge', label: 'Merged records' },
  { value: 'keep_apart', label: 'Kept records apart' },
  { value: 'corr_proposed', label: 'Proposed correction' },
  { value: 'corr_approved', label: 'Approved correction' },
  { value: 'corr_rejected', label: 'Rejected correction' },
  { value: 'consent', label: 'Recorded consent' },
  { value: 'reveal', label: 'Revealed identity number' },
  { value: 'sync_source', label: 'Synced source' },
  { value: 'update_source', label: 'Changed source' },
  { value: 'login', label: 'Signed in' },
  { value: 'login_failed', label: 'Sign-in failed' },
  { value: 'logout', label: 'Signed out' },
  { value: 'denied', label: 'Access denied' },
]

// How loud each kind of event should look. Failures and refusals stand out; routine reads stay quiet.
function tone(action: string): 'good' | 'warn' | 'bad' | 'neutral' {
  if (action === 'login_failed' || action === 'denied' || action === 'corr_rejected') return 'bad'
  if (action === 'corr_approved') return 'good'
  if (action === 'corr_proposed') return 'warn'
  if (action === 'merge' || action === 'keep_apart' || action === 'update_source' || action === 'export') return 'warn'
  if (action === 'login') return 'good'
  return 'neutral'
}

const ROLE_LABELS: Record<string, string> = {
  relationship_manager: 'Relationship manager',
  agent: 'Contact centre agent',
  steward: 'Data steward',
  compliance: 'Compliance officer',
  admin: 'Administrator',
}

function describe(e: AuditEvent): string {
  const d = e.detail
  if (e.action === 'view_customer') return d.masked ? 'Contact details masked' : 'Full contact details shown'
  if (e.action === 'export') return `${d.rows ?? 0} rows`
  if (e.action === 'sync_source') return `${d.fetched ?? 0} records read`
  if (e.action === 'update_source') return Object.entries((d.changes as object) ?? {}).map(([k, v]) => `${k} → ${v}`).join(', ')
  if (e.action.startsWith('corr_')) return `${String(d.field ?? '')} · ${String(d.evidence ?? d.proposed_by ?? '')}`
  if (e.action === 'denied') return `Needed: ${String(d.capability ?? '').replace('_', ' ')}`
  return ''
}

export function AuditPage() {
  const [action, setAction] = useState('')
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [page, setPage] = useState(1)

  useEffect(() => {
    const t = setTimeout(() => {
      setDebounced(search.trim())
      setPage(1)
    }, 300)
    return () => clearTimeout(t)
  }, [search])

  const { data, error, loading } = useApi(
    () => api.audit({ action: action || undefined, search: debounced || undefined, page: page > 1 ? String(page) : undefined }),
    [action, debounced, page],
  )

  return (
    <>
      <PageHeader
        title="Audit log"
        description="Who did what, and when. Entries cannot be edited or deleted."
      />

      <div className="toolbar">
        <div className="input-wrap">
          <Icon name="search" size={16} />
          <input
            className="input"
            type="search"
            aria-label="Search by user or customer"
            placeholder="Search user or target, e.g. C-10001"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="select"
          aria-label="Filter by action"
          value={action}
          onChange={(e) => {
            setAction(e.target.value)
            setPage(1)
          }}
        >
          {ACTIONS.map((a) => (
            <option key={a.value} value={a.value}>
              {a.label}
            </option>
          ))}
        </select>
      </div>

      {error && <ErrorAlert message={error} />}

      <Card
        flush
        footer={
          data && (
            <>
              <span>{data.count} events</span>
              <div className="pager">
                <button type="button" className="btn btn-sm" disabled={!data.previous} onClick={() => setPage(page - 1)}>
                  Previous
                </button>
                <button type="button" className="btn btn-sm" disabled={!data.next} onClick={() => setPage(page + 1)}>
                  Next
                </button>
              </div>
            </>
          )
        }
      >
        <div className="table-wrap">
          <table className="table" style={{ minWidth: 860 }}>
            <thead>
              <tr>
                <th>When</th>
                <th>Who</th>
                <th>Action</th>
                <th>Target</th>
                <th>Details</th>
                <th className="right">IP address</th>
              </tr>
            </thead>
            {loading && !data ? (
              <LoaderRow kind="overlap" label="Loading the audit log" columns={6} />
            ) : (
              <tbody>
                {data?.results.map((e) => (
                  <tr key={e.id}>
                    <td className="text-sm" style={{ whiteSpace: 'nowrap' }}>
                      {new Date(e.at).toLocaleString('en-GB', {
                        day: 'numeric',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      })}
                    </td>
                    <td>
                      <div className="cell-person">
                        <Avatar name={e.actor_name} />
                        <div>
                          <strong style={{ fontSize: 'var(--text-sm)' }}>{e.actor_name}</strong>
                          <span>{ROLE_LABELS[e.role] ?? 'No role'}</span>
                        </div>
                      </div>
                    </td>
                    <td>
                      <StatusBadge tone={tone(e.action)}>{e.action_label}</StatusBadge>
                    </td>
                    <td className="mono text-sm">{e.target || <span className="muted">-</span>}</td>
                    <td className="text-sm muted">{describe(e)}</td>
                    <td className="right mono text-xs muted">{e.ip ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            )}
          </table>
          {data?.results.length === 0 && (
            <EmptyState icon="audit" title="No events match">
              Try another action or clear the search.
            </EmptyState>
          )}
        </div>
      </Card>
    </>
  )
}
