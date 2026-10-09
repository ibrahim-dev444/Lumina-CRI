import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api } from '../api/client'
import { useApi } from '../api/useApi'
import { KycBadge } from '../components/ComplianceTab'
import { RISK_LABEL } from '../compliance'
import { Avatar, Card, EmptyState, ErrorAlert, PageHeader, Skeleton, SkeletonRows, StatusBadge } from '../components/ui'
import { formatDate, formatScore } from '../format'

type Filter = { label: string; status?: string; risk?: string }
const FILTERS: Filter[] = [
  { label: 'All' },
  { label: 'Overdue', status: 'overdue' },
  { label: 'Due soon', status: 'due_soon' },
  { label: 'High risk', risk: 'high' },
]

export function CompliancePage() {
  const [filter, setFilter] = useState<Filter>(FILTERS[0])
  const { data, error, loading } = useApi(
    () => api.compliance({ status: filter.status, risk: filter.risk }),
    [filter.status, filter.risk],
  )
  const navigate = useNavigate()
  const s = data?.summary

  return (
    <>
      <PageHeader
        title="Compliance"
        description="KYC and AML status for every customer, highest risk first. Not visible to front-line staff."
      />
      {error && <ErrorAlert message={error} />}

      <div className="kpis">
        <Tile label="Re-KYC overdue" value={s?.overdue} tone="bad" />
        <Tile label="Re-KYC due in 6 months" value={s?.due_soon} tone="warn" />
        <Tile label="High AML risk" value={s?.high_risk} tone="bad" />
        <Tile label="Politically exposed" value={s?.pep} tone="warn" />
        <Tile label="Sanctions to review" value={s?.sanctions_review} tone="bad" />
      </div>

      <div className="grid-halves">
        <Card title="KYC status" description="Share of customers in each state.">
          {s ? (
            <Composition
              total={s.customers}
              parts={[
                { label: 'Verified', value: s.verified, colour: 'var(--band-high)' },
                { label: 'Due soon', value: s.due_soon, colour: 'var(--band-medium)' },
                { label: 'Overdue', value: s.overdue, colour: 'var(--band-low)' },
                { label: 'No record', value: s.no_record, colour: 'var(--border-strong)' },
              ]}
            />
          ) : (
            <Skeleton height={60} />
          )}
        </Card>
        <Card title="AML risk" description="Customers with a KYC record, by risk rating.">
          {s ? (
            <Composition
              total={s.low_risk + s.medium_risk + s.high_risk}
              parts={[
                { label: 'Low', value: s.low_risk, colour: 'var(--band-high)' },
                { label: 'Medium', value: s.medium_risk, colour: 'var(--band-medium)' },
                { label: 'High', value: s.high_risk, colour: 'var(--band-low)' },
              ]}
            />
          ) : (
            <Skeleton height={60} />
          )}
        </Card>
      </div>

      <div className="segmented" role="group" aria-label="Filter">
        {FILTERS.map((f) => (
          <button key={f.label} type="button" aria-pressed={filter.label === f.label} onClick={() => setFilter(f)}>
            {f.label}
          </button>
        ))}
      </div>

      <Card flush footer={data && <span>{data.results.length} customers</span>}>
        <div className="table-wrap">
          <table className="table" style={{ minWidth: 980 }}>
            <thead>
              <tr>
                <th>Customer</th>
                <th>AML risk</th>
                <th>Politically exposed</th>
                <th>KYC</th>
                <th>Last KYC</th>
                <th>Re-KYC due</th>
                <th>Sanctions</th>
                <th className="right">Trust</th>
              </tr>
            </thead>
            {loading && !data ? (
              <SkeletonRows columns={8} />
            ) : (
              <tbody>
                {data?.results.map((r) => (
                  <tr key={r.id} className="clickable" onClick={() => navigate(`/customers/${r.id}?tab=compliance`)}>
                    <td>
                      <div className="cell-person">
                        <Avatar name={r.name} />
                        <div>
                          <Link to={`/customers/${r.id}?tab=compliance`} onClick={(e) => e.stopPropagation()}>
                            <strong>{r.name || 'Unnamed'}</strong>
                          </Link>
                          <span className="mono">{r.code}</span>
                        </div>
                      </div>
                    </td>
                    <td>
                      {r.risk ? (
                        <span className="stack" style={{ gap: 2 }}>
                          <StatusBadge tone={RISK_LABEL[r.risk].tone}>{RISK_LABEL[r.risk].label}</StatusBadge>
                          <span className="text-xs muted">{r.risk_reason}</span>
                        </span>
                      ) : (
                        <span className="muted">-</span>
                      )}
                    </td>
                    <td>{r.pep ? <StatusBadge tone="bad">Yes</StatusBadge> : <span className="muted">No</span>}</td>
                    <td>
                      <KycBadge status={r.kyc_status} />
                    </td>
                    <td className="text-sm">{r.last_kyc ? formatDate(r.last_kyc) : '-'}</td>
                    <td className="text-sm">{r.re_kyc_due ? formatDate(r.re_kyc_due) : '-'}</td>
                    <td>
                      {r.sanctions === 'potential_match' ? (
                        <StatusBadge tone="bad">Review</StatusBadge>
                      ) : r.sanctions ? (
                        <span className="muted">Clear</span>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td className="right mono">{formatScore(r.trust_score)}</td>
                  </tr>
                ))}
              </tbody>
            )}
          </table>
          {data?.results.length === 0 && <EmptyState icon="check" title="Nothing in this view" />}
        </div>
      </Card>
    </>
  )
}

function Tile({ label, value, tone }: { label: string; value: number | undefined; tone: 'bad' | 'warn' }) {
  return (
    <div className="card kpi">
      <span className="kpi-label">{label}</span>
      <span className="row" style={{ gap: 10 }}>
        <span className="kpi-value">{value ?? <Skeleton width={40} height={28} />}</span>
        {value ? <StatusBadge tone={tone}>{tone === 'bad' ? 'Act' : 'Watch'}</StatusBadge> : null}
      </span>
    </div>
  )
}

// One bar split into parts of a whole. Every part is labelled with its name and count, so colour is never
// the only cue; a 2px gap separates neighbours.
function Composition({ total, parts }: { total: number; parts: { label: string; value: number; colour: string }[] }) {
  const shown = parts.filter((p) => p.value > 0)
  return (
    <div className="stack" style={{ gap: 12 }}>
      <div className="composition" role="img" aria-label={parts.map((p) => `${p.label} ${p.value}`).join(', ')}>
        {shown.map((p) => (
          <i
            key={p.label}
            style={{ flex: p.value, background: p.colour }}
            title={`${p.label}: ${p.value} of ${total}`}
          />
        ))}
      </div>
      <div className="legend">
        {parts.map((p) => (
          <span key={p.label}>
            <i style={{ background: p.colour }} />
            {p.label} <strong className="num">{p.value}</strong>
            <span className="muted num">{total ? ` ${Math.round((p.value / total) * 100)}%` : ''}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

