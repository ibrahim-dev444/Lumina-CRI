import { useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { MatchSuggestion, SourceRecord } from '../api/types'
import { useApi } from '../api/useApi'
import { useCan } from '../auth/AuthContext'
import { Icon } from '../components/Icon'
import { useToast } from '../components/Toasts'
import { Card, EmptyState, ErrorAlert, PageHeader, Skeleton, StatusBadge } from '../components/ui'
import { FIELD_LABELS, FIELDS, formatDate, formatFieldValue } from '../format'

type Tab = 'pending' | 'accepted' | 'rejected'
const TABS: { value: Tab; label: string }[] = [
  { value: 'pending', label: 'To review' },
  { value: 'accepted', label: 'Merged' },
  { value: 'rejected', label: 'Kept apart' },
]

const sameValue = (a: string | null, b: string | null) =>
  (a ?? '').toLowerCase().replace(/[^a-z0-9]/g, '') === (b ?? '').toLowerCase().replace(/[^a-z0-9]/g, '')

// One sentence a steward can read before deciding: what agrees, what differs, what is missing.
function explain(a: SourceRecord, b: SourceRecord): string {
  const same: string[] = []
  const differ: string[] = []
  const missing: string[] = []
  for (const f of FIELDS) {
    const label = FIELD_LABELS[f].toLowerCase()
    if (!a[f] || !b[f]) missing.push(label)
    else if (sameValue(a[f], b[f])) same.push(label)
    else differ.push(label)
  }
  const list = (xs: string[]) => (xs.length > 1 ? `${xs.slice(0, -1).join(', ')} and ${xs.at(-1)}` : xs[0])
  const parts = []
  if (same.length) parts.push(`${list(same)} match${same.length === 1 ? 'es' : ''}`)
  if (differ.length) parts.push(`${list(differ)} differ${differ.length === 1 ? 's' : ''}`)
  if (missing.length) parts.push(`${list(missing)} cannot be compared`)
  const sentence = parts.join('; ')
  return sentence.charAt(0).toUpperCase() + sentence.slice(1) + '.'
}

export function ReviewPage() {
  const [tab, setTab] = useState<Tab>('pending')
  const { data, error, loading, reload } = useApi(() => api.suggestions(tab), [tab])
  // Counts for the tab labels, refreshed whenever a decision is made.
  const counts = useApi(
    () =>
      Promise.all(TABS.map((t) => api.suggestions(t.value))).then((pages) =>
        Object.fromEntries(TABS.map((t, i) => [t.value, pages[i].count])),
      ),
    [data],
  ).data

  return (
    <>
      <PageHeader
        title="Match review"
        description="Probably the same person, but not certain. You decide."
      />

      <div className="segmented" role="group" aria-label="Show">
        {TABS.map((t) => (
          <button key={t.value} type="button" aria-pressed={tab === t.value} onClick={() => setTab(t.value)}>
            {t.label}
            {counts && <span className="tab-count">{counts[t.value]}</span>}
          </button>
        ))}
      </div>

      {error && <ErrorAlert message={error} />}
      {loading && !data && (
        <div className="card card-body">
          <Skeleton height={160} />
        </div>
      )}
      {data?.results.length === 0 && (
        <div className="card">
          <EmptyState icon="check" title={tab === 'pending' ? 'All caught up' : 'Nothing here yet'}>
            {tab === 'pending' ? 'There are no possible duplicates waiting for a decision.' : null}
          </EmptyState>
        </div>
      )}
      {data?.results.map((s) => <SuggestionCard key={s.id} s={s} onDecided={reload} />)}
    </>
  )
}

function SuggestionCard({ s, onDecided }: { s: MatchSuggestion; onDecided: () => void }) {
  const [busy, setBusy] = useState<'merge' | 'reject' | null>(null)
  const toast = useToast()
  const canDecide = useCan('decide_matches')
  const a = s.record_a
  const b = s.record_b

  const decide = async (accept: boolean) => {
    setBusy(accept ? 'merge' : 'reject')
    try {
      await (accept ? api.acceptSuggestion(s.id) : api.rejectSuggestion(s.id))
      toast('success', accept ? `Merged ${a.name} and ${b.name} into one customer.` : `Kept ${a.name} and ${b.name} apart.`)
      onDecided()
    } catch (e) {
      toast('error', (e as Error).message)
      setBusy(null)
    }
  }

  const actions =
    s.status === 'pending' && !canDecide ? (
      <span className="text-sm muted row" style={{ gap: 6 }}>
        <Icon name="lock" size={14} /> A data steward decides
      </span>
    ) : s.status === 'pending' ? (
      <div className="row">
        <button type="button" className="btn" disabled={busy !== null} onClick={() => decide(false)}>
          <Icon name="x" size={16} />
          {busy === 'reject' ? 'Saving...' : 'Different people'}
        </button>
        <button type="button" className="btn btn-primary" disabled={busy !== null} onClick={() => decide(true)}>
          <Icon name="merge" size={16} />
          {busy === 'merge' ? 'Merging...' : 'Merge records'}
        </button>
      </div>
    ) : (
      <span className="text-sm muted">
        {s.status === 'accepted' ? 'Merged' : 'Kept apart'} {s.decided_at && `on ${formatDate(s.decided_at)}`}
      </span>
    )

  return (
    <Card
      title={
        <span className="row" style={{ gap: 10 }}>
          {a.name} <span className="muted">and</span> {b.name}
        </span>
      }
      description={`Match score ${s.points} · ${s.reason}`}
      actions={<StatusBadge tone={s.status === 'pending' ? 'warn' : s.status === 'accepted' ? 'good' : 'neutral'}>{s.status === 'pending' ? 'Needs decision' : s.status === 'accepted' ? 'Merged' : 'Kept apart'}</StatusBadge>}
      footer={
        <>
          <span className="match-note">
            <Icon name="info" size={16} />
            {explain(a, b)}
          </span>
          {actions}
        </>
      }
      flush
    >
      <div className="table-wrap">
        <table className="compare" style={{ minWidth: 640 }}>
          <colgroup>
            <col className="col-field" />
            <col />
            <col className="col-verdict" />
            <col />
          </colgroup>
          <thead>
            <tr>
              <th scope="col">Field</th>
              <th scope="col">
                {a.source_name} · {s.customer_a ? <Link to={`/customers/${s.customer_a.id}`} className="link mono">{s.customer_a.code}</Link> : a.source_record_id}
              </th>
              <th scope="col" className="verdict">
                <span className="sr-only">Same?</span>
              </th>
              <th scope="col">
                {b.source_name} · {s.customer_b ? <Link to={`/customers/${s.customer_b.id}`} className="link mono">{s.customer_b.code}</Link> : b.source_record_id}
              </th>
            </tr>
          </thead>
          <tbody>
            {FIELDS.map((f) => {
              const va = a[f]
              const vb = b[f]
              const kind = !va || !vb ? 'none' : sameValue(va, vb) ? 'same' : 'diff'
              return (
                <tr key={f}>
                  <th scope="row">{FIELD_LABELS[f]}</th>
                  <td>{va ? formatFieldValue(f, va) : <span className="muted">Not held</span>}</td>
                  <td className="verdict">
                    <span className={`verdict-icon ${kind}`}>
                      <Icon
                        name={kind === 'same' ? 'check' : kind === 'diff' ? 'neq' : 'minus'}
                        size={14}
                        label={kind === 'same' ? 'Same' : kind === 'diff' ? 'Different' : 'Cannot compare'}
                      />
                    </span>
                  </td>
                  <td>{vb ? formatFieldValue(f, vb) : <span className="muted">Not held</span>}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
