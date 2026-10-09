import { useParams, useSearchParams } from 'react-router-dom'

import { api } from '../api/client'
import type { CustomerDetail } from '../api/types'
import { useApi } from '../api/useApi'
import { useCan } from '../auth/AuthContext'
import { AgreementGrid } from '../components/AgreementGrid'
import { ComplianceTab, KycBadge } from '../components/ComplianceTab'
import { RISK_LABEL } from '../compliance'
import { CorrectionsCard } from '../components/CorrectionsCard'
import { GoldenFieldRow } from '../components/GoldenFieldRow'
import { RevealPanel } from '../components/RevealPanel'
import { Icon } from '../components/Icon'
import { ScoreBreakdown } from '../components/ScoreBreakdown'
import {
  Avatar,
  BandBadge,
  Card,
  EmptyState,
  ErrorAlert,
  PageHeader,
  Skeleton,
  SourceChips,
  StatusBadge,
} from '../components/ui'
import { FIELD_LABELS, FIELD_SHORT, FIELDS, MONO_FIELDS, formatDateTime, formatFieldValue, formatRelative, formatScore } from '../format'

type Tab = 'identity' | 'sources' | 'compliance' | 'activity'

export function CustomerDetailPage() {
  const id = Number(useParams().id)
  const [params, setParams] = useSearchParams()
  const canSeeAudit = useCan('view_audit')
  const { data: c, error, reload } = useApi(() => api.customer(id), [id])

  const tabs: { value: Tab; label: string }[] = [
    { value: 'identity', label: 'Identity' },
    { value: 'sources', label: 'Sources' },
    { value: 'compliance', label: 'Compliance' },
    ...(canSeeAudit ? [{ value: 'activity' as Tab, label: 'Activity' }] : []),
  ]
  const wanted = params.get('tab') as Tab | null
  const tab: Tab = tabs.some((t) => t.value === wanted) ? (wanted as Tab) : 'identity'
  const setTab = (t: Tab) => setParams(t === 'identity' ? {} : { tab: t }, { replace: true })

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

      <section className="card">
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
              <div className="row" style={{ gap: 6 }}>
                <KycBadge status={c.compliance.kyc_status} />
                {c.compliance.aml && (
                  <StatusBadge tone={RISK_LABEL[c.compliance.aml.risk].tone}>
                    {RISK_LABEL[c.compliance.aml.risk].label}
                  </StatusBadge>
                )}
                {c.compliance.aml?.pep && <StatusBadge tone="bad">Politically exposed</StatusBadge>}
                {c.compliance.aml?.sanctions === 'potential_match' && (
                  <StatusBadge tone="bad">Sanctions review</StatusBadge>
                )}
              </div>
            </div>
          </div>
          <div className="score-block">
            <span className="score-label">Trust score</span>
            <span className="score-value">
              {formatScore(c.trust_score)}
              <span className="score-of">/100</span>
            </span>
            <BandBadge band={c.band} />
            <span className="text-xs muted">Recalculated {formatRelative(c.score_updated_at).toLowerCase()}</span>
          </div>
        </div>
        <div className="tabs" role="tablist" aria-label="Customer sections">
          {tabs.map((t) => (
            <button
              key={t.value}
              type="button"
              role="tab"
              aria-selected={tab === t.value}
              className="tab"
              onClick={() => setTab(t.value)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </section>

      {c.masked && (
        <div className="notice" role="note">
          <Icon name="lock" size={16} />
          <span>
            <strong>Some details are hidden for your role.</strong> Mobile, email and date of birth show only enough to
            confirm the customer on a call. PAN, CKYC and Aadhaar are masked for every role.
          </span>
        </div>
      )}

      {tab === 'identity' && <IdentityTab c={c} onChanged={reload} />}
      {tab === 'sources' && <SourcesTab c={c} />}
      {tab === 'compliance' && <ComplianceTab c={c} onChanged={reload} />}
      {tab === 'activity' && <ActivityTab c={c} />}
    </>
  )
}

function IdentityTab({ c, onChanged }: { c: CustomerDetail; onChanged: () => void }) {
  return (
    <>
      <div className="grid-2">
        <Card title="Golden record" description="The value we use for each field, and where it came from." flush>
          <dl className="fields">
            {FIELDS.map((f) => (
              <GoldenFieldRow key={f} field={f} golden={c.golden.find((x) => x.field === f)} records={c.records} />
            ))}
          </dl>
        </Card>
        <Card title="Why this score" description="Points each field adds, out of 100.">
          <ScoreBreakdown golden={c.golden} weights={c.weights} score={c.trust_score} />
        </Card>
      </div>
      <RevealPanel customer={c} />
      <CorrectionsCard customer={c} onChanged={onChanged} />
    </>
  )
}

function SourcesTab({ c }: { c: CustomerDetail }) {
  return (
    <>
      <Card title="Do the sources agree?" description="Each source against each field, compared with the golden record.">
        <AgreementGrid customer={c} />
      </Card>

      <Card title="What each source says" description="Highlighted values are the ones in use." flush>
        <div className="table-wrap">
          <table className="table" style={{ minWidth: 1700 }}>
            <thead>
              <tr>
                <th>Source</th>
                {FIELDS.map((f) => (
                  <th key={f} title={FIELD_LABELS[f]}>
                    {FIELD_SHORT[f]}
                  </th>
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
                        {r.source_record_id} · trust {formatScore(r.source_trust)}
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
                      <td
                        key={f}
                        className={[used ? 'win' : '', MONO_FIELDS.has(f) ? 'mono nowrap' : ''].join(' ').trim() || undefined}
                      >
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

// Who opened, changed or corrected this customer. Compliance officers and administrators only.
function ActivityTab({ c }: { c: CustomerDetail }) {
  const { data, error } = useApi(() => api.audit({ search: c.code }), [c.code])
  return (
    <Card title="Who has touched this record" description="Newest first, from the audit log." flush>
      {error && <ErrorAlert message={error} />}
      {!data && !error && (
        <div className="card-body">
          <Skeleton height={120} />
        </div>
      )}
      {data && data.results.length === 0 && <EmptyState icon="audit" title="No activity yet" />}
      {data && data.results.length > 0 && (
        <ol className="timeline">
          {data.results.map((e) => (
            <li key={e.id}>
              <span className="timeline-when">{formatDateTime(e.at)}</span>
              <span className="timeline-dot" aria-hidden="true" />
              <span className="timeline-what">
                <strong>{e.actor_name}</strong> {e.action_label.toLowerCase()}
                {typeof e.detail.field === 'string' && ` · ${FIELD_LABELS[e.detail.field as keyof typeof FIELD_LABELS] ?? e.detail.field}`}
                {e.detail.masked === true && <span className="muted"> · contact details hidden</span>}
              </span>
            </li>
          ))}
        </ol>
      )}
    </Card>
  )
}
