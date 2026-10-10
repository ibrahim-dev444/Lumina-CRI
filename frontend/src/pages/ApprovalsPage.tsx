import { useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { FieldCorrection } from '../api/types'
import { useApi } from '../api/useApi'
import { useCan } from '../auth/AuthContext'
import { CorrectionStatus } from '../components/CorrectionsCard'
import { Icon } from '../components/Icon'
import { Loader } from '../components/Loader'
import { useToast } from '../components/Toasts'
import { Avatar, Card, EmptyState, ErrorAlert, PageHeader } from '../components/ui'
import { FIELD_LABELS, formatDateTime, formatFieldValue } from '../format'

type Tab = 'pending' | 'approved' | 'rejected'
const TABS: { value: Tab; label: string }[] = [
  { value: 'pending', label: 'Waiting' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
]

export function ApprovalsPage() {
  const [tab, setTab] = useState<Tab>('pending')
  const { data, error, loading, reload } = useApi(() => api.corrections({ status: tab }), [tab])
  const counts = useApi(
    () =>
      Promise.all(TABS.map((t) => api.corrections({ status: t.value }))).then((pages) =>
        Object.fromEntries(TABS.map((t, i) => [t.value, pages[i].count])),
      ),
    [data],
  ).data

  return (
    <>
      <PageHeader
        title="Approvals"
        description="Corrections waiting for a second person. Nobody approves their own change."
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
        <div className="card">
          <Loader kind="pingpong" label="Loading changes waiting for approval" />
        </div>
      )}
      {data?.results.length === 0 && (
        <div className="card">
          <EmptyState icon="approve" title={tab === 'pending' ? 'Nothing waiting' : 'Nothing here yet'}>
            {tab === 'pending' ? 'No corrections are waiting for approval.' : null}
          </EmptyState>
        </div>
      )}
      {data?.results.map((c) => <ApprovalCard key={c.id} c={c} onDecided={reload} />)}
    </>
  )
}

function ApprovalCard({ c, onDecided }: { c: FieldCorrection; onDecided: () => void }) {
  const canApprove = useCan('approve_corrections')
  const toast = useToast()
  const [busy, setBusy] = useState<'approve' | 'reject' | null>(null)
  const [rejecting, setRejecting] = useState(false)
  const [note, setNote] = useState('')

  const decide = async (approve: boolean) => {
    setBusy(approve ? 'approve' : 'reject')
    try {
      await (approve ? api.approveCorrection(c.id) : api.rejectCorrection(c.id, note))
      toast(
        'success',
        approve
          ? `Approved. ${c.customer.name}'s ${FIELD_LABELS[c.field].toLowerCase()} is updated and the score recalculated.`
          : 'Rejected. The proposer can see your note.',
      )
      onDecided()
    } catch (e) {
      toast('error', (e as Error).message)
      setBusy(null)
    }
  }

  let actions = null
  if (c.status === 'pending' && c.mine) {
    actions = (
      <span className="text-sm muted row" style={{ gap: 6 }}>
        <Icon name="lock" size={14} /> You proposed this. Another person must approve it.
      </span>
    )
  } else if (c.status === 'pending' && canApprove && !rejecting) {
    actions = (
      <div className="row">
        <button type="button" className="btn" disabled={busy !== null} onClick={() => setRejecting(true)}>
          <Icon name="x" size={16} /> Reject
        </button>
        <button type="button" className="btn btn-primary" disabled={busy !== null} onClick={() => decide(true)}>
          <Icon name="check" size={16} />
          {busy === 'approve' ? 'Approving...' : 'Approve'}
        </button>
      </div>
    )
  } else if (c.status === 'pending' && canApprove && rejecting) {
    actions = (
      <div className="row">
        <button type="button" className="btn" disabled={busy !== null} onClick={() => setRejecting(false)}>
          Cancel
        </button>
        <button type="button" className="btn btn-primary" disabled={busy !== null || !note.trim()} onClick={() => decide(false)}>
          {busy === 'reject' ? 'Rejecting...' : 'Confirm reject'}
        </button>
      </div>
    )
  }

  return (
    <Card
      title={
        <span className="row" style={{ gap: 10 }}>
          <Link to={`/customers/${c.customer.id}`} className="link">
            {c.customer.name || c.customer.code}
          </Link>
          <span className="muted mono text-sm">{c.customer.code}</span>
        </span>
      }
      description={`${FIELD_LABELS[c.field]} correction`}
      actions={<CorrectionStatus status={c.status} />}
      footer={
        <>
          <span className="row" style={{ gap: 8 }}>
            <Avatar name={c.proposed_by_name} />
            Proposed by {c.proposed_by_name} · {formatDateTime(c.proposed_at)}
            {c.decided_at && ` · ${c.status} by ${c.decided_by_name}`}
          </span>
          {actions}
        </>
      }
    >
      <div className="stack" style={{ gap: 12 }}>
        <span className="change" style={{ fontSize: 'var(--text-md)' }}>
          <span className="old">{c.previous_value ? formatFieldValue(c.field, c.previous_value) : 'no value'}</span>
          <Icon name="chevronRight" size={16} />
          <span className="new">{formatFieldValue(c.field, c.value)}</span>
        </span>
        <dl className="kv">
          <div>
            <dt>Evidence</dt>
            <dd className="mono">{c.evidence_ref}</dd>
          </div>
          <div>
            <dt>Reason</dt>
            <dd>{c.reason}</dd>
          </div>
          {c.decision_note && (
            <div>
              <dt>Decision note</dt>
              <dd>{c.decision_note}</dd>
            </div>
          )}
        </dl>
        {rejecting && (
          <div className="form-field">
            <label htmlFor={`note-${c.id}`}>Why are you rejecting it?</label>
            <textarea
              id={`note-${c.id}`}
              className="textarea"
              placeholder="e.g. The KYC form shows a different number. Please attach the latest form."
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
        )}
      </div>
    </Card>
  )
}
