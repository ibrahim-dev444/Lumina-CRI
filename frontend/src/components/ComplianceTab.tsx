import { useState, type FormEvent } from 'react'

import { api } from '../api/client'
import type { CustomerDetail } from '../api/types'
import { useCan } from '../auth/AuthContext'
import { KYC_LABEL, RISK_LABEL } from '../compliance'
import { formatDate, formatDateTime } from '../format'
import { Icon } from './Icon'
import { useToast } from './Toasts'
import { Card, StatusBadge } from './ui'

const CONSENT_TONE: Record<string, 'good' | 'warn' | 'bad' | 'neutral'> = {
  granted: 'good',
  pending: 'warn',
  revoked: 'bad',
  unknown: 'neutral',
}

const CHANNELS = ['Call', 'Branch', 'Email', 'WhatsApp', 'Net banking']

export function KycBadge({ status }: { status: string }) {
  const k = KYC_LABEL[status] ?? KYC_LABEL.no_record
  return <StatusBadge tone={k.tone}>{k.label}</StatusBadge>
}

// Customer profile, Compliance tab. Everyone sees KYC status and consent; AML risk, politically exposed
// person and sanctions only come from the server for compliance roles (the API leaves them out otherwise).
export function ComplianceTab({ c, onChanged }: { c: CustomerDetail; onChanged: () => void }) {
  const comp = c.compliance
  const aml = comp.aml

  return (
    <>
      <div className={aml ? 'grid-halves' : undefined}>
        <Card title="KYC" description="Re-KYC is due every 2, 8 or 10 years for high, medium and low risk.">
          <dl className="kv">
            <div>
              <dt>Status</dt>
              <dd>
                <KycBadge status={comp.kyc_status} />
              </dd>
            </div>
            <div>
              <dt>Re-KYC due</dt>
              <dd>{comp.re_kyc_due ? formatDate(comp.re_kyc_due) : '-'}</dd>
            </div>
            {aml && (
              <div>
                <dt>Last KYC</dt>
                <dd>{formatDate(aml.last_kyc)}</dd>
              </div>
            )}
          </dl>
          {comp.kyc_status === 'no_record' && (
            <p className="text-sm muted" style={{ marginTop: 12 }}>
              {comp.has_pan
                ? 'The compliance systems hold no KYC for this PAN.'
                : 'No PAN on file, so KYC records cannot be linked to this customer yet.'}
            </p>
          )}
          {(comp.kyc_status === 'overdue' || comp.kyc_status === 'due_soon') && (
            <p className="text-sm" style={{ marginTop: 12 }}>Ask the customer to submit updated KYC documents at their next contact.</p>
          )}
        </Card>

        {aml ? (
          <Card title="AML" description="Visible to compliance roles only. Never share with the customer.">
            <dl className="kv">
              <div>
                <dt>Risk</dt>
                <dd className="row" style={{ gap: 8 }}>
                  <StatusBadge tone={RISK_LABEL[aml.risk].tone}>{RISK_LABEL[aml.risk].label}</StatusBadge>
                  <span className="text-sm muted">{aml.risk_reason}</span>
                </dd>
              </div>
              <div>
                <dt>Politically exposed</dt>
                <dd>{aml.pep ? <StatusBadge tone="bad">{aml.pep_note || 'Yes'}</StatusBadge> : 'No'}</dd>
              </div>
              <div>
                <dt>Sanctions check</dt>
                <dd className="row" style={{ gap: 8 }}>
                  {aml.sanctions === 'potential_match' ? (
                    <StatusBadge tone="bad">Potential match: review</StatusBadge>
                  ) : (
                    <StatusBadge tone="good">Clear</StatusBadge>
                  )}
                  {aml.sanctions_checked && <span className="text-sm muted">checked {formatDate(aml.sanctions_checked)}</span>}
                </dd>
              </div>
            </dl>
          </Card>
        ) : null}
      </div>

      <ConsentCard c={c} onChanged={onChanged} />
    </>
  )
}

function ConsentCard({ c, onChanged }: { c: CustomerDetail; onChanged: () => void }) {
  const canRecord = useCan('record_consent')
  const toast = useToast()
  const [purpose, setPurpose] = useState('marketing')
  const [status, setStatus] = useState('revoked')
  const [channel, setChannel] = useState('Call')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      await api.recordConsent(c.id, { purpose, status, channel, note })
      toast('success', 'Consent recorded. It applies from now on and is in the audit log.')
      setNote('')
      onChanged()
    } catch (err) {
      toast('error', (err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Consent" description="What the customer allows the bank to use their data for." flush>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Purpose</th>
              <th>Status</th>
              <th>How</th>
              <th className="right">Recorded</th>
            </tr>
          </thead>
          <tbody>
            {c.compliance.consents.map((x) => (
              <tr key={x.purpose}>
                <td>{x.label}</td>
                <td>
                  <StatusBadge tone={CONSENT_TONE[x.status]}>
                    {x.status === 'unknown' ? 'Not recorded' : x.status[0].toUpperCase() + x.status.slice(1)}
                  </StatusBadge>
                </td>
                <td className="text-sm muted">{x.channel || '-'}</td>
                <td className="right text-sm muted">
                  {x.recorded_at ? `${formatDateTime(x.recorded_at)} · ${x.recorded_by}` : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {canRecord && c.compliance.has_pan && (
        <form className="card-body form-grid" onSubmit={submit} style={{ borderTop: '1px solid var(--border)' }}>
          <div className="form-field">
            <label htmlFor="consent-purpose">Purpose</label>
            <select id="consent-purpose" className="select" value={purpose} onChange={(e) => setPurpose(e.target.value)}>
              {c.compliance.consents.map((x) => (
                <option key={x.purpose} value={x.purpose}>
                  {x.label}
                </option>
              ))}
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="consent-status">The customer has</label>
            <select id="consent-status" className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="granted">Given consent</option>
              <option value="revoked">Withdrawn consent</option>
              <option value="pending">Not decided</option>
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="consent-channel">Told us by</label>
            <select id="consent-channel" className="select" value={channel} onChange={(e) => setChannel(e.target.value)}>
              {CHANNELS.map((ch) => (
                <option key={ch}>{ch}</option>
              ))}
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="consent-note">Note (optional)</label>
            <input id="consent-note" className="input" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
          <div className="wide row" style={{ justifyContent: 'flex-end' }}>
            <button type="submit" className="btn btn-primary" disabled={busy}>
              <Icon name="check" size={16} />
              {busy ? 'Saving...' : 'Record consent'}
            </button>
          </div>
        </form>
      )}
    </Card>
  )
}
