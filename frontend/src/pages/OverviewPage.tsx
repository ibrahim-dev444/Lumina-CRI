import { useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api } from '../api/client'
import type { Source } from '../api/types'
import { useApi } from '../api/useApi'
import { useCan } from '../auth/AuthContext'
import { Icon, type IconName } from '../components/Icon'
import { useToast } from '../components/Toasts'
import { TrustHistogram } from '../components/TrustHistogram'
import { Avatar, Card, ErrorAlert, PageHeader, Skeleton, SourceChips, StatusBadge, TrustCell } from '../components/ui'
import { exportCustomersCsv } from '../exportCsv'
import { formatRelative, formatScore, sourceTier } from '../format'

const TARGET = 0.85 // the average trust the data team is working towards

export function OverviewPage() {
  const { data, error, reload } = useApi(() => api.overview(), [])
  const navigate = useNavigate()
  const toast = useToast()
  const [busy, setBusy] = useState<'sync' | 'export' | null>(null)

  const syncAll = async () => {
    if (!data) return
    setBusy('sync')
    try {
      const enabled = data.sources.filter((s) => s.enabled)
      for (const s of enabled) await api.syncSource(s.code) // one at a time: each rebuild sees the last
      toast('success', `Synced ${enabled.length} sources. Golden records and scores are up to date.`)
      reload()
    } catch (e) {
      toast('error', (e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const exportCsv = async () => {
    setBusy('export')
    try {
      await exportCustomersCsv()
      toast('success', 'Customer list downloaded as CSV.')
    } catch (e) {
      toast('error', (e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const average = data ? Number(data.average_trust) : 0
  const canExport = useCan('export')
  const canSync = useCan('manage_sources')
  const canSeeMatches = useCan('view_matches')

  return (
    <>
      <PageHeader
        title="Overview"
        description={
          data
            ? `How reliable your customer data is right now. Last sync ${formatRelative(data.last_synced_at).toLowerCase()}.`
            : 'How reliable your customer data is right now.'
        }
        actions={
          <>
            {canExport && (
              <button type="button" className="btn" onClick={exportCsv} disabled={busy !== null}>
                <Icon name="file" size={16} />
                {busy === 'export' ? 'Preparing...' : 'Export CSV'}
              </button>
            )}
            {canSync && (
              <button type="button" className="btn btn-primary" onClick={syncAll} disabled={busy !== null || !data}>
                <Icon name="refresh" size={16} className={busy === 'sync' ? 'spin' : undefined} />
                {busy === 'sync' ? 'Syncing...' : 'Sync all sources'}
              </button>
            )}
          </>
        }
      />
      {error && <ErrorAlert message={error} />}

      <div className="kpis">
        <Kpi hue={1} icon="customers" label="Customers" value={data?.customers}>
          <span className="kpi-sub">{data && `Built from ${data.source_records} source records`}</span>
          <div className="kpi-foot">
            <span>{data && `${data.sources.filter((s) => s.enabled).length} sources feeding`}</span>
          </div>
        </Kpi>

        <Kpi hue={5} icon="shield" label="Average trust" value={data && formatScore(data.average_trust)} mono>
          <div className="target-meter" aria-hidden="true">
            <i style={{ width: `${average * 100}%`, background: 'var(--c5)' }} />
            <b style={{ left: `${TARGET * 100}%` }} />
          </div>
          <div className="kpi-foot">
            <span>Target {TARGET.toFixed(2)}</span>
            <span className="num">{Math.round(average * 100)}%</span>
          </div>
        </Kpi>

        <Kpi
          hue={2}
          icon="alert"
          label="Low trust"
          value={data?.bands.low}
          tag={data && data.bands.low > 0 ? <StatusBadge tone="bad">Attention</StatusBadge> : undefined}
          to="/customers?band=low"
        >
          <div className="kpi-foot">
            <span>{data && `${data.bands.medium} medium · ${data.bands.high} high`}</span>
            <Icon name="chevronRight" size={16} />
          </div>
        </Kpi>

        <Kpi
          hue={3}
          icon="merge"
          label="Matches to review"
          value={data?.pending_reviews}
          tag={data && data.pending_reviews > 0 ? <StatusBadge tone="warn">Review</StatusBadge> : undefined}
          to={canSeeMatches ? '/review' : undefined}
        >
          <div className="kpi-foot">
            <span>Awaiting a steward's decision</span>
            <Icon name="chevronRight" size={16} />
          </div>
        </Kpi>
      </div>

      <div className="grid-2">
        <Card
          title="Trust score distribution"
          description="Customers per 0.1 of trust score"
          actions={
            <div className="legend" aria-hidden="true">
              <span>
                <i style={{ background: 'var(--band-low)' }} />
                Low &lt; 0.6
              </span>
              <span>
                <i style={{ background: 'var(--band-medium)' }} />
                Medium 0.6–0.8
              </span>
              <span>
                <i style={{ background: 'var(--band-high)' }} />
                High ≥ 0.8
              </span>
            </div>
          }
        >
          {data ? (
            <>
              <TrustHistogram buckets={data.histogram} />
              <div className="chart-foot">
                <span className="num">
                  {data.customers} customers · {data.bands.low} low · {data.bands.medium} medium · {data.bands.high}{' '}
                  high
                </span>
                <span>Bin width 0.1</span>
              </div>
            </>
          ) : (
            <Skeleton height={240} />
          )}
        </Card>

        <Card
          title="Sources"
          description={data ? `${data.sources.length} configured` : undefined}
          flush
          footer={
            <Link to="/connectors" className="link row" style={{ gap: 4 }}>
              Manage connectors <Icon name="chevronRight" size={14} />
            </Link>
          }
        >
          <div>
            {data?.sources.map((s) => (
              <SourceRow key={s.code} s={s} />
            ))}
          </div>
        </Card>
      </div>

      <Card
        title="Lowest trust customers"
        description="Start clean-up here"
        flush
        actions={
          <Link to="/customers" className="link text-sm">
            View all
          </Link>
        }
      >
        <div className="table-wrap">
          <table className="table" style={{ minWidth: 600 }}>
            <thead>
              <tr>
                <th>Customer</th>
                <th>Trust</th>
                <th>Found in</th>
                <th className="right">Action</th>
              </tr>
            </thead>
            <tbody>
              {data?.lowest_trust.map((c) => (
                <tr key={c.id} className="clickable" onClick={() => navigate(`/customers/${c.id}`)}>
                  <td>
                    <div className="cell-person">
                      <Avatar name={c.name} />
                      <div>
                        <strong>{c.name || 'Unnamed'}</strong>
                        <span className="mono">{c.code}</span>
                      </div>
                    </div>
                  </td>
                  <td>
                    <TrustCell score={c.trust_score} band={c.band} />
                  </td>
                  <td>
                    <SourceChips codes={c.sources} />
                  </td>
                  <td className="right">
                    <Link to={`/customers/${c.id}`} className="btn btn-sm" onClick={(e) => e.stopPropagation()}>
                      Review
                    </Link>
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

function Kpi({
  hue,
  icon,
  label,
  value,
  mono = false,
  tag,
  to,
  children,
}: {
  hue: number
  icon: IconName
  label: string
  value: string | number | null | undefined
  mono?: boolean
  tag?: ReactNode
  to?: string
  children?: ReactNode
}) {
  const body = (
    <>
      <div className="kpi-top">
        <span className="kpi-label">{label}</span>
        <span className="kpi-icon">
          <Icon name={icon} />
        </span>
      </div>
      <div className="row" style={{ gap: 10 }}>
        <span className={`kpi-value${mono ? ' mono' : ''}`}>{value ?? <Skeleton width={60} height={28} />}</span>
        {tag}
      </div>
      {children}
    </>
  )
  const className = `card kpi hue-${hue}`
  return to ? (
    <Link to={to} className={className}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  )
}

function SourceRow({ s }: { s: Source }) {
  const tier = sourceTier(Number(s.trust))
  return (
    <div
      className="row"
      style={{ justifyContent: 'space-between', padding: '14px 20px', borderBottom: '1px solid var(--border)' }}
    >
      <div className="stack" style={{ gap: 2 }}>
        <span className="row" style={{ gap: 8, fontWeight: 600 }}>
          {s.name}
        </span>
        <span className="text-xs muted mono">{s.record_count} records</span>
      </div>
      <div className="stack" style={{ gap: 4, alignItems: 'flex-end' }}>
        {s.enabled ? (
          <StatusBadge tone={tier.tone}>
            <span className="mono">{s.trust}</span> {tier.label}
          </StatusBadge>
        ) : (
          <StatusBadge tone="neutral">Disconnected</StatusBadge>
        )}
        <span className="text-xs muted">Synced {formatRelative(s.last_synced_at).toLowerCase()}</span>
      </div>
    </div>
  )
}
