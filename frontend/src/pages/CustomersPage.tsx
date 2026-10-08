import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { api } from '../api/client'
import type { Band } from '../api/types'
import { useApi } from '../api/useApi'
import { Icon } from '../components/Icon'
import {
  Avatar,
  Card,
  EmptyState,
  ErrorAlert,
  PageHeader,
  SkeletonRows,
  SourceChips,
  StatusBadge,
  TrustCell,
} from '../components/ui'
import { formatRelative } from '../format'

const BANDS: { value: '' | Band; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
]

export function CustomersPage() {
  // Filters live in the URL (?band=low&q=suresh) so a filtered list can be bookmarked or shared.
  const [params, setParams] = useSearchParams()
  const band = params.get('band') ?? ''
  const ordering = params.get('sort') ?? 'score'
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
    () => api.customers({ search: q, ordering, band, page: page > 1 ? String(page) : undefined }),
    [q, ordering, band, page],
  )
  const pages = data ? Math.max(1, Math.ceil(data.count / 50)) : 1 // backend PAGE_SIZE is 50

  return (
    <>
      <PageHeader
        title="Customers"
        description="One record per real customer, built from every connected source. Lowest trust is shown first so clean-up starts where it matters."
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
        <div className="segmented" role="group" aria-label="Filter by trust">
          {BANDS.map((b) => (
            <button key={b.label} type="button" aria-pressed={band === b.value} onClick={() => setParam('band', b.value)}>
              {b.label}
            </button>
          ))}
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
          <table className="table" style={{ minWidth: 860 }}>
            <thead>
              <tr>
                <th>Customer</th>
                <th>Trust score</th>
                <th>Found in</th>
                <th className="right">Conflicts</th>
                <th>Review</th>
                <th className="right">Updated</th>
              </tr>
            </thead>
            {loading && !data ? (
              <SkeletonRows columns={6} />
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
                    <td>
                      <SourceChips codes={c.sources} />
                    </td>
                    <td className="right mono">{c.conflict_fields ? c.conflict_fields : <span className="muted">-</span>}</td>
                    <td>
                      {c.needs_review ? (
                        <StatusBadge tone="bad">
                          {c.needs_review} field{c.needs_review > 1 ? 's' : ''}
                        </StatusBadge>
                      ) : (
                        <StatusBadge tone="good">Complete</StatusBadge>
                      )}
                    </td>
                    <td className="right text-sm muted">{formatRelative(c.score_updated_at)}</td>
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
