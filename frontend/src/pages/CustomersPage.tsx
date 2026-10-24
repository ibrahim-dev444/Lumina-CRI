import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { api } from '../api/client'
import { useApi } from '../api/useApi'
import { BreakdownCard, FILTER_KEYS, type Filters } from '../components/BreakdownCard'
import { KycBadge } from '../components/ComplianceTab'
import { Icon } from '../components/Icon'
import { LoaderRow } from '../components/Loader'
import {
  Avatar,
  Card,
  EmptyState,
  ErrorAlert,
  PageHeader,
  SourceChips,
  TrustCell,
} from '../components/ui'
import { formatRelative } from '../format'


export function CustomersPage() {
  // Filters live in the URL (?kyc=overdue&country=India&q=suresh) so a filtered list can be bookmarked or shared.
  // "band" is the older name for the trust filter; links that still use it keep working.
  const [params, setParams] = useSearchParams()
  const ordering = params.get('sort') ?? 'score'
  const by = params.get('by') ?? 'score'
  const filters: Filters = {}
  for (const key of FILTER_KEYS) {
    const values = [...params.getAll(key), ...(key === 'score' ? params.getAll('band') : [])].filter(Boolean)
    if (values.length) filters[key] = [...new Set(values)]
  }
  const filterQuery = new URLSearchParams(
    Object.entries(filters).flatMap(([k, vs]) => (vs ?? []).map((v) => [k, v])),
  ).toString()
  const setFilters = (next: Filters) => {
    const p = new URLSearchParams(params)
    for (const key of [...FILTER_KEYS, 'band', 'page']) p.delete(key)
    for (const [k, vs] of Object.entries(next)) for (const v of vs ?? []) p.append(k, v)
    setParams(p, { replace: true })
  }
  const [search, setSearch] = useState(params.get('q') ?? '')
  const navigate = useNavigate()

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page') // a new filter starts again at page 1
    setParams(next, { replace: true })
  }

  // Wait until typing pauses for 300 ms before searching.
  useEffect(() => {
    const timer = setTimeout(() => setParam('q', search.trim()), 300)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search])

  const q = params.get('q') ?? ''
  const page = Number(params.get('page') ?? '1')
  const { data, error, loading } = useApi(
    () => api.customers({ search: q, ordering, page: page > 1 ? String(page) : undefined }, filterQuery),
    [q, ordering, filterQuery, page],
  )
  const breakdown = useApi(() => api.customerBreakdown(by, filterQuery), [by, filterQuery])
  const pages = data ? Math.max(1, Math.ceil(data.count / 50)) : 1 // backend PAGE_SIZE is 50

  return (
    <>
      <PageHeader
        title="Customers"
        description="Lowest trust first, so clean-up starts where it matters."
      />

      <BreakdownCard
        data={breakdown.data}
        error={breakdown.error}
        filters={filters}
        onBy={(next) => setParam('by', next === 'score' ? '' : next)}
        onFilters={setFilters}
      />

      <div className="toolbar">
        <div className="input-wrap">
          <Icon name="search" size={16} />
          <input
            className="input"
            type="search"
            aria-label="Search customers by name or ID"
            placeholder="Search name or ID, e.g. C-10001"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="select"
          aria-label="Sort customers"
          value={ordering}
          onChange={(e) => setParam('sort', e.target.value === 'score' ? '' : e.target.value)}
        >
          <option value="score">Lowest trust first</option>
          <option value="-score">Highest trust first</option>
          <option value="name">Name A to Z</option>
        </select>
      </div>

      {error && <ErrorAlert message={error} />}

      <Card
        flush
        footer={
          data && (
            <>
              <span>
                {data.count} customers · sorted by{' '}
                {ordering === 'name' ? 'name' : ordering === '-score' ? 'highest trust' : 'lowest trust'}
              </span>
              <div className="pager">
                <button
                  type="button"
                  className="btn btn-sm"
                  disabled={!data.previous}
                  onClick={() => setParam('page', String(page - 1))}
                >
                  Previous
                </button>
                <span className="text-sm muted" style={{ alignSelf: 'center' }}>
                  Page {page} of {pages}
                </span>
                <button
                  type="button"
                  className="btn btn-sm"
                  disabled={!data.next}
                  onClick={() => setParam('page', String(page + 1))}
                >
                  Next
                </button>
              </div>
            </>
          )
        }
      >
        <div className="table-wrap">
          <table className="table customers-table">
            <thead>
              <tr>
                <th>Customer</th>
                <th>Trust score</th>
                <th className="col-sm">Found in</th>
                <th className="right col-md">Conflicts</th>
                <th className="col-md">Review</th>
                <th className="col-xs">KYC</th>
                <th className="right col-md">Updated</th>
              </tr>
            </thead>
            {loading && !data ? (
              <LoaderRow kind="stack" label="Loading customers" columns={7} />
            ) : (
              <tbody>
                {data?.results.map((c) => (
                  <tr key={c.id} className="clickable" onClick={() => navigate(`/customers/${c.id}`)}>
                    <td>
                      <div className="cell-person">
                        <Avatar name={c.name} />
                        <div>
                          <Link to={`/customers/${c.id}`} onClick={(e) => e.stopPropagation()}>
                            <strong>{c.name || 'Unnamed'}</strong>
                          </Link>
                          <span className="mono">{c.code}</span>
                        </div>
                      </div>
                    </td>
                    <td>
                      <TrustCell score={c.trust_score} band={c.band} />
                    </td>
                    <td className="col-sm">
                      <SourceChips codes={c.sources} names={c.source_names} />
                    </td>
                    <td className="right mono col-md">{c.conflict_fields ? c.conflict_fields : <span className="muted">-</span>}</td>
                    <td className="col-md nowrap">
                      {c.needs_review ? (
                        <span className="text-sm">
                          {c.needs_review} field{c.needs_review > 1 ? 's' : ''}
                        </span>
                      ) : (
                        <span className="muted">-</span>
                      )}
                    </td>
                    <td className="col-xs">
                      <KycBadge status={c.kyc_status} />
                    </td>
                    <td className="right text-sm muted col-md nowrap">{formatRelative(c.score_updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            )}
          </table>
          {data?.results.length === 0 && (
            <EmptyState icon="search" title="No customers match">
              Try a different name, or clear the trust filter.
            </EmptyState>
          )}
        </div>
      </Card>
    </>
  )
}
