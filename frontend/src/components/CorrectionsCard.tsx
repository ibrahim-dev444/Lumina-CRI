import { useState, type FormEvent } from 'react'

import { api } from '../api/client'
import type { CustomerDetail, Field, FieldCorrection } from '../api/types'
import { useCan } from '../auth/AuthContext'
import { FIELD_LABELS, FIELDS, formatDateTime, formatFieldValue } from '../format'
import { Icon } from './Icon'
import { useToast } from './Toasts'
import { Card, StatusBadge } from './ui'

const PLACEHOLDER: Record<Field, string> = {
  name: 'Full name as on the ID document',
  mobile: '10-digit mobile, e.g. 9822104521',
  email: 'name@example.com',
  address: 'Full address with PIN code',
  dob: 'YYYY-MM-DD or DD/MM/YYYY',
}

// On the customer profile: propose a fix with evidence, and see this customer's recent corrections.
export function CorrectionsCard({ customer, onChanged }: { customer: CustomerDetail; onChanged: () => void }) {
  const canPropose = useCan('propose_corrections')
  const toast = useToast()
  const [field, setField] = useState<Field>('mobile')
  const [value, setValue] = useState('')
  const [evidence, setEvidence] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!canPropose && customer.corrections.length === 0) return null

  const current = customer.golden.find((g) => g.field === field)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.proposeCorrection(customer.id, { field, value, evidence_ref: evidence, reason })
      toast('success', `${FIELD_LABELS[field]} correction sent for approval. Another person must approve it.`)
      setValue('')
      setEvidence('')
      setReason('')
      onChanged()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card
      title="Corrections"
      description="Fix a wrong value with evidence. A second person must approve it before it changes the golden record."
      flush
    >
      {canPropose && (
        <form className="card-body stack" style={{ gap: 14 }} onSubmit={submit}>
          <div className="form-grid">
            <div className="form-field">
              <label htmlFor="corr-field">Field</label>
              <select
                id="corr-field"
                className="select"
                value={field}
                onChange={(e) => setField(e.target.value as Field)}
              >
                {FIELDS.map((f) => (
                  <option key={f} value={f}>
                    {FIELD_LABELS[f]}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="corr-value">Correct value</label>
              <input
                id="corr-value"
                className="input"
                placeholder={PLACEHOLDER[field]}
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            </div>
            <div className="form-field">
              <label htmlFor="corr-evidence">Evidence reference</label>
              <input
                id="corr-evidence"
                className="input"
                placeholder="e.g. KYC form #4471, call ID 88213"
                value={evidence}
                onChange={(e) => setEvidence(e.target.value)}
              />
            </div>
            <div className="form-field wide">
              <label htmlFor="corr-reason">Why is the current value wrong?</label>
              <textarea
                id="corr-reason"
                className="textarea"
                placeholder="e.g. Customer confirmed on a recorded call that this number is no longer theirs."
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </div>
          </div>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="text-sm muted">
              Current {FIELD_LABELS[field].toLowerCase()}:{' '}
              <strong>{current ? formatFieldValue(field, current.value) : 'none'}</strong>
            </span>
            <button type="submit" className="btn btn-primary" disabled={busy || !value || !evidence || !reason}>
              <Icon name="edit" size={16} />
              {busy ? 'Sending...' : 'Send for approval'}
            </button>
          </div>
          {error && <p className="text-sm" style={{ color: 'var(--bad-text)' }}>{error}</p>}
        </form>
      )}

      {customer.corrections.length > 0 && (
        <div className="correction-list">
          {customer.corrections.map((c) => (
            <CorrectionLine key={c.id} c={c} />
          ))}
        </div>
      )}
    </Card>
  )
}

export function CorrectionStatus({ status }: { status: FieldCorrection['status'] }) {
  if (status === 'approved') return <StatusBadge tone="good">Approved</StatusBadge>
  if (status === 'rejected') return <StatusBadge tone="bad">Rejected</StatusBadge>
  return <StatusBadge tone="warn">Waiting for approval</StatusBadge>
}

function CorrectionLine({ c }: { c: FieldCorrection }) {
  return (
    <div className="correction-item">
      <div className="stack" style={{ gap: 4 }}>
        <span className="change">
          <strong style={{ color: 'var(--text)' }}>{FIELD_LABELS[c.field]}:</strong>
          {c.previous_value && <span className="old">{formatFieldValue(c.field, c.previous_value)}</span>}
          <Icon name="chevronRight" size={14} />
          <span className="new">{formatFieldValue(c.field, c.value)}</span>
        </span>
        <span className="text-xs muted">
          Evidence {c.evidence_ref} · proposed by {c.proposed_by_name} {formatDateTime(c.proposed_at)}
          {c.decided_at && ` · ${c.status} by ${c.decided_by_name} ${formatDateTime(c.decided_at)}`}
        </span>
        {c.decision_note && <span className="text-xs muted">Note: {c.decision_note}</span>}
      </div>
      <CorrectionStatus status={c.status} />
    </div>
  )
}
