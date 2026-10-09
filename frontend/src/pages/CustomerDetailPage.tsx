import { useParams } from 'react-router-dom'

import { api } from '../api/client'
import { useApi } from '../api/useApi'
import { GoldenFieldRow } from '../components/GoldenFieldRow'
import { Icon } from '../components/Icon'
import { CorrectionsCard } from '../components/CorrectionsCard'
import { ScoreBreakdown } from '../components/ScoreBreakdown'
import { ScoreGauge } from '../components/ScoreGauge'
import {
  Avatar,
  Card,
  ErrorAlert,
  PageHeader,
  Skeleton,
  SourceChips,
  StatusBadge,
} from '../components/ui'
import { FIELD_LABELS, FIELDS, formatFieldValue, formatRelative } from '../format'

export function CustomerDetailPage() {
  const id = Number(useParams().id)
  const { data: c, error, reload } = useApi(() => api.customer(id), [id])

  const crumbs = [{ label: 'Customers', to: '/customers' }, { label: c?.code ?? '...' }]

  if (error) {
    return (
      <>
        <PageHeader title="Customer" crumbs={crumbs} />
        <ErrorAlert message={error} />
      </>
    )
  }

  if (!c) {
    return (
      <>
        <PageHeader title={<Skeleton width={240} height={24} />} crumbs={crumbs} />
        <div className="card card-body">
          <Skeleton height={80} />
        </div>
      </>
    )
  }

  return (
    <>
      <PageHeader crumbs={crumbs} title="Customer profile" />

      <section className="card glass">
        <div className="card-body row" style={{ justifyContent: 'space-between', alignItems: 'center', gap: 24 }}>
          <div className="row" style={{ gap: 16, flexWrap: 'nowrap', minWidth: 0 }}>
            <Avatar name={c.name} large />
            <div className="stack" style={{ gap: 6, minWidth: 0 }}>
              <h2 style={{ fontSize: 'var(--text-xl)' }}>{c.name || 'Unnamed'}</h2>
              <div className="row text-sm muted">
                <span className="mono">{c.code}</span>
                <span aria-hidden="true">·</span>
                <span>
                  Found in {c.record_count} source{c.record_count === 1 ? '' : 's'}
                </span>
              </div>
              <SourceChips codes={c.sources} />
            </div>
          </div>
          <div className="stack profile-score">
            <ScoreGauge score={c.trust_score} band={c.band} />
            <span className="text-xs muted">Trust score · recalculated {formatRelative(c.score_updated_at).toLowerCase()}</span>
          </div>
        </div>
      </section>

      {c.masked && (
        <div className="notice" role="note">
          <Icon name="lock" size={16} />
          <span>
            <strong>Some details are hidden for your role.</strong> Mobile, email and date of birth show only enough to
            confirm the customer on a call. Every profile you open is recorded in the audit log.
          </span>
        </div>
      )}

      <div className="grid-2">
        <Card
          title="Golden record"
          description="Each field uses the value from the most trusted source; on a tie, the most recent wins. Open a field to see what the other sources hold."
          flush
        >
          <dl className="fields">
            {FIELDS.map((f) => (
              <GoldenFieldRow key={f} field={f} golden={c.golden.find((x) => x.field === f)} records={c.records} />
            ))}
          </dl>
        </Card>

        <Card glass title="Why this score" description="What each field adds: its weight × the trust of its source">
          <ScoreBreakdown golden={c.golden} weights={c.weights} score={c.trust_score} />
        </Card>
      </div>

      <CorrectionsCard customer={c} onChanged={reload} />

      <Card
        title="What each source says"
        description="Every record linked to this customer. Highlighted values are the ones used in the golden record."
        flush
      >
        <div className="table-wrap">
          <table className="table" style={{ minWidth: 1000 }}>
            <thead>
              <tr>
                <th>Source</th>
                {FIELDS.map((f) => (
                  <th key={f}>{FIELD_LABELS[f]}</th>
                ))}
                <th>Why linked</th>
              </tr>
            </thead>
            <tbody>
              {c.records.map((r) => (
                <tr key={r.id}>
                  <td>
                    <div className="stack" style={{ gap: 2 }}>
                      <span style={{ fontWeight: 500 }}>{r.source_name}</span>
                      <span className="text-xs muted mono">
                        {r.source_record_id} · trust {r.source_trust}
                      </span>
                      {!r.source_enabled && (
                        <span>
                          <StatusBadge tone="neutral">Disconnected</StatusBadge>
                        </span>
                      )}
                    </div>
                  </td>
                  {FIELDS.map((f) => {
                    const value = r[f]
                    if (!value)
                      return (
                        <td key={f} className="muted">
                          -
                        </td>
                      )
                    const used = c.golden.some((g) => g.field === f && g.source_record_id === r.id)
                    return (
                      <td key={f} className={used ? 'win' : undefined}>
                        {formatFieldValue(f, value)}
                      </td>
                    )
                  })}
                  <td className="text-xs muted" style={{ maxWidth: 220 }}>
                    {r.match_reason}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}
