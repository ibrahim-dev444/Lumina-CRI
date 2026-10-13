import { useState, type FormEvent } from 'react'

import { api } from '../api/client'
import type { Channel, Interaction, InteractionKind, NewInteraction, Outcome } from '../api/types'
import { useApi } from '../api/useApi'
import { formatDate, formatDateTime } from '../format'
import { Icon } from './Icon'
import { Loader } from './Loader'
import { useToast } from './Toasts'
import { Card, EmptyState, ErrorAlert, StatusBadge } from './ui'

const CHANNELS: [Channel, string][] = [
  ['call', 'Phone call'],
  ['branch', 'Branch visit'],
  ['email', 'Email'],
  ['whatsapp', 'WhatsApp'],
  ['chat', 'Chat'],
  ['sms', 'SMS'],
]
const KINDS: [InteractionKind, string][] = [
  ['query', 'Question'],
  ['request', 'Service request'],
  ['complaint', 'Complaint'],
  ['sales', 'Sales conversation'],
  ['feedback', 'Feedback'],
]
const OUTCOMES: [Outcome, string][] = [
  ['resolved', 'Resolved'],
  ['follow_up', 'Needs a follow-up'],
  ['escalated', 'Escalated'],
]

// Customer profile, Conversations tab: log what was said, see the history, close complaints and follow-ups.
export function ConversationsTab({
  customerId,
  version,
  formOpen,
  setFormOpen,
  onChanged,
}: {
  customerId: number
  version: number
  formOpen: boolean
  setFormOpen: (open: boolean) => void
  onChanged: () => void
}) {
  const { data, error, reload } = useApi(() => api.interactions(customerId), [customerId, version])
  const changed = () => {
    reload()
    onChanged()
  }

  return (
    <>
      {formOpen && <LogForm customerId={customerId} onDone={() => setFormOpen(false)} onSaved={changed} />}
      <Card
        title="Conversations"
        description="Newest first. Open complaints and follow-ups stay at the top of the briefing until closed."
        actions={
          !formOpen && (
            <button type="button" className="btn btn-primary btn-sm" onClick={() => setFormOpen(true)}>
              <Icon name="edit" size={14} /> Log a conversation
            </button>
          )
        }
        flush
      >
        {error && (
          <div className="card-body">
            <ErrorAlert message={error} />
          </div>
        )}
        {!data && !error && <Loader kind="trail" label="Loading conversations" />}
        {data && data.length === 0 && (
          <EmptyState icon="edit" title="No conversations yet">
            Log calls, branch visits and messages so the next colleague knows what was said.
          </EmptyState>
        )}
        {data && data.length > 0 && (
          <ol className="convo-list">
            {data.map((i) => (
              <TimelineItem key={i.id} item={i} onClosed={changed} />
            ))}
          </ol>
        )}
      </Card>
    </>
  )
}

function TimelineItem({ item, onClosed }: { item: Interaction; onClosed: () => void }) {
  const toast = useToast()
  const [closing, setClosing] = useState(false)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const close = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      await api.closeInteraction(item.id, note)
      toast('success', 'Closed. It no longer shows in the briefing.')
      onClosed()
    } catch (err) {
      toast('error', (err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <li className={`convo-item${item.state === 'open' ? ' is-open' : ''}`}>
      <span className="convo-dot" aria-hidden="true" />
      <div className="stack" style={{ gap: 6, minWidth: 0 }}>
        <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
          <strong>{item.kind_label}</strong>
          <span className="text-sm muted">
            {item.inbound ? 'from the customer' : 'to the customer'} · {item.channel_label}
          </span>
          {item.state === 'open' ? (
            <StatusBadge tone={item.kind === 'complaint' ? 'bad' : 'warn'}>
              {item.follow_up_on ? `Follow-up ${formatDate(item.follow_up_on)}` : item.outcome_label}
            </StatusBadge>
          ) : (
            <StatusBadge tone="good">{item.closed_at ? 'Closed' : item.outcome_label}</StatusBadge>
          )}
        </div>
        <p>{item.summary}</p>
        <span className="text-xs muted">
          {formatDateTime(item.created_at)} · {item.created_by}
          {item.closed_at && ` · closed ${formatDateTime(item.closed_at)} by ${item.closed_by}: ${item.closing_note}`}
        </span>
        {item.state === 'open' &&
          (closing ? (
            <form className="row" style={{ gap: 8, flexWrap: 'wrap' }} onSubmit={close}>
              <input
                className="input"
                style={{ flex: '1 1 240px' }}
                aria-label="How it was closed"
                placeholder="How was it settled? e.g. Fee reversed on 14 Oct"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                autoFocus
              />
              <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>
                {busy ? 'Closing...' : 'Close it'}
              </button>
              <button type="button" className="btn btn-sm" onClick={() => setClosing(false)}>
                Cancel
              </button>
            </form>
          ) : (
            <div>
              <button type="button" className="btn btn-sm" onClick={() => setClosing(true)}>
                <Icon name="check" size={14} /> Mark as done
              </button>
            </div>
          ))}
      </div>
    </li>
  )
}

function LogForm({ customerId, onDone, onSaved }: { customerId: number; onDone: () => void; onSaved: () => void }) {
  const toast = useToast()
  const [form, setForm] = useState<NewInteraction>({
    channel: 'call',
    kind: 'query',
    summary: '',
    outcome: 'resolved',
    inbound: true,
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = <K extends keyof NewInteraction>(k: K, v: NewInteraction[K]) => setForm((f) => ({ ...f, [k]: v }))
  const [tomorrow] = useState(() => new Date(Date.now() + 86_400_000).toISOString().slice(0, 10))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.logInteraction(customerId, {
        ...form,
        follow_up_on: form.outcome === 'follow_up' ? form.follow_up_on : undefined,
      })
      toast('success', 'Conversation saved for the next colleague.')
      onSaved()
      onDone()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Log a conversation" description="Write what matters for the next person. Never type full card or account numbers: they are masked anyway.">
      <form className="form-grid" onSubmit={submit}>
        {error && (
          <div className="wide">
            <ErrorAlert message={error} />
          </div>
        )}
        <div className="form-field">
          <label htmlFor="ix-channel">How</label>
          <select id="ix-channel" className="select" value={form.channel} onChange={(e) => set('channel', e.target.value as Channel)}>
            {CHANNELS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="ix-direction">Who started it</label>
          <select
            id="ix-direction"
            className="select"
            value={form.inbound ? 'in' : 'out'}
            onChange={(e) => set('inbound', e.target.value === 'in')}
          >
            <option value="in">The customer</option>
            <option value="out">The bank</option>
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="ix-kind">About</label>
          <select id="ix-kind" className="select" value={form.kind} onChange={(e) => set('kind', e.target.value as InteractionKind)}>
            {KINDS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="ix-outcome">Outcome</label>
          <select id="ix-outcome" className="select" value={form.outcome} onChange={(e) => set('outcome', e.target.value as Outcome)}>
            {OUTCOMES.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        {form.outcome === 'follow_up' && (
          <div className="form-field">
            <label htmlFor="ix-follow">Follow up on</label>
            <input
              id="ix-follow"
              type="date"
              className="input"
              min={tomorrow}
              value={form.follow_up_on ?? ''}
              onChange={(e) => set('follow_up_on', e.target.value)}
              required
            />
          </div>
        )}
        <div className="form-field wide">
          <label htmlFor="ix-summary">Summary</label>
          <textarea
            id="ix-summary"
            className="textarea"
            rows={3}
            maxLength={600}
            placeholder="e.g. Asked why the annual card fee was charged twice. Raised a reversal request."
            value={form.summary}
            onChange={(e) => set('summary', e.target.value)}
            required
          />
          <span className="text-xs muted">{form.summary.length} / 600</span>
        </div>
        <div className="wide row" style={{ justifyContent: 'flex-end', gap: 8 }}>
          <button type="button" className="btn" onClick={onDone}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={busy || form.summary.trim().length < 10}>
            <Icon name="check" size={16} /> {busy ? 'Saving...' : 'Save conversation'}
          </button>
        </div>
      </form>
    </Card>
  )
}
