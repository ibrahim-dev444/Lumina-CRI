import { api } from '../api/client'
import type { BriefingAlert } from '../api/types'
import { useApi } from '../api/useApi'
import { formatRelative } from '../format'
import { Icon, type IconName } from './Icon'
import { Loader } from './Loader'
import { Card, ErrorAlert } from './ui'

const LEVEL: Record<BriefingAlert['level'], { icon: IconName; label: string }> = {
  bad: { icon: 'alert', label: 'Handle first' },
  warn: { icon: 'info', label: 'Check' },
  info: { icon: 'info', label: 'Note' },
}

// Customer profile, "Before you speak": what to know in the ten seconds before a call or a meeting.
// The server decides what each role may see (no amounts for data stewards, no AML flags for front-line staff).
export function BriefingPanel({ customerId, version, onLog }: { customerId: number; version: number; onLog: () => void }) {
  const { data, error } = useApi(() => api.briefing(customerId), [customerId, version])

  if (error) return <ErrorAlert message={error} />
  if (!data) {
    return (
      <div className="card">
        <Loader label="Preparing the briefing" />
      </div>
    )
  }

  const worst = data.alerts[0]?.level
  return (
    <div className="briefing-grid">
      <Card
        title={
          <span className={`briefing-headline is-${worst ?? 'calm'}`}>
            <Icon name={worst === 'bad' ? 'alert' : worst ? 'info' : 'check'} size={18} />
            {data.headline}
          </span>
        }
        description={
          data.last_contact
            ? `Last spoke ${formatRelative(data.last_contact.at).toLowerCase()} by ${data.last_contact.channel.toLowerCase()} (${data.last_contact.by}). ${data.contacts_last_90_days} contact${data.contacts_last_90_days === 1 ? '' : 's'} in 90 days.`
            : 'No conversation logged yet.'
        }
        actions={
          <button type="button" className="btn btn-primary btn-sm" onClick={onLog}>
            <Icon name="edit" size={14} /> Log a conversation
          </button>
        }
      >
        {data.alerts.length === 0 ? (
          <p className="muted">No open complaints, overdue products, KYC or consent issues.</p>
        ) : (
          <ul className="briefing-alerts">
            {data.alerts.map((a, i) => (
              <li key={i} className={`briefing-alert is-${a.level}`}>
                <span className="briefing-alert-icon" aria-label={LEVEL[a.level].label}>
                  <Icon name={LEVEL[a.level].icon} size={16} />
                </span>
                <span className="stack" style={{ gap: 2 }}>
                  <strong>{a.title}</strong>
                  <span className="text-sm muted">{a.action}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Talking points" description="What they hold, and ideas only when they agreed to hear offers.">
        {data.talking_points.length === 0 ? (
          <p className="muted">Nothing on file to talk about yet.</p>
        ) : (
          <ul className="briefing-points">
            {data.talking_points.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        )}
        {data.last_contact && (
          <div className="briefing-last">
            <span className="text-xs muted">Last note</span>
            <p className="text-sm">{data.last_contact.summary}</p>
          </div>
        )}
      </Card>
    </div>
  )
}
