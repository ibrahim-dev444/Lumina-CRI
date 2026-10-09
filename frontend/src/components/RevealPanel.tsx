import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { CustomerDetail } from '../api/types'
import { useCan } from '../auth/AuthContext'
import { Icon } from './Icon'
import { useToast } from './Toasts'
import { Card } from './ui'

const REASONS = ['Regulatory request', 'Suspicious transaction review', 'Customer dispute', 'KYC re-verification']
const SHOW_SECONDS = 60

// Compliance officers and administrators can see a full PAN or CKYC number, one at a time, with a reason.
// The server writes who, when, which number and why to the audit log. The number hides again after a minute.
export function RevealPanel({ customer }: { customer: CustomerDetail }) {
  const canReveal = useCan('reveal_identity')
  const toast = useToast()
  const [reason, setReason] = useState('')
  const [shown, setShown] = useState<{ field: 'pan' | 'ckyc'; value: string } | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!shown) return
    const timer = setTimeout(() => setShown(null), SHOW_SECONDS * 1000)
    return () => clearTimeout(timer)
  }, [shown])

  if (!canReveal) return null
  const has = (f: 'pan' | 'ckyc') => customer.golden.some((g) => g.field === f)

  const reveal = async (field: 'pan' | 'ckyc') => {
    setBusy(true)
    try {
      setShown(await api.reveal(customer.id, field, reason))
    } catch (e) {
      toast('error', (e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card
      title="View a full identity number"
      description="Numbers stay masked unless you need them. Your reason is written to the audit log."
    >
      <div className="row" style={{ alignItems: 'flex-end', gap: 12 }}>
        <div className="form-field" style={{ flex: '1 1 240px', maxWidth: 320 }}>
          <label htmlFor="reveal-reason">Reason</label>
          <select id="reveal-reason" className="select" value={reason} onChange={(e) => setReason(e.target.value)}>
            <option value="">Choose a reason</option>
            {REASONS.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </div>
        <button type="button" className="btn" disabled={!reason || busy || !has('pan')} onClick={() => reveal('pan')}>
          <Icon name="lock" size={16} /> Show full PAN
        </button>
        <button type="button" className="btn" disabled={!reason || busy || !has('ckyc')} onClick={() => reveal('ckyc')}>
          <Icon name="lock" size={16} /> Show CKYC number
        </button>
      </div>
      {shown && (
        <div className="reveal-box" role="status">
          <span className="text-sm muted">{shown.field === 'pan' ? 'PAN' : 'CKYC number'}</span>
          <span className="mono reveal-value">{shown.value}</span>
          <span className="text-xs muted">Hides automatically in {SHOW_SECONDS} seconds. This view is in the audit log.</span>
          <button type="button" className="btn btn-sm" onClick={() => setShown(null)}>
            Hide now
          </button>
        </div>
      )}
    </Card>
  )
}
