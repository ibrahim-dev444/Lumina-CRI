import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api/client'
import { useApi } from '../api/useApi'
import { formatDate, formatRelative } from '../format'
import { Avatar, Card, EmptyState, ErrorAlert, Skeleton, StatusBadge } from './ui'

// Overview: complaints and follow-ups nobody has closed yet, oldest first. Each opens the customer's conversations.
export function OpenItemsCard() {
  const navigate = useNavigate()
  const { data, error } = useApi(() => api.openInteractions(), [])
  const [today] = useState(() => new Date().toISOString().slice(0, 10))
  const late = data?.filter((i) => i.kind === 'complaint' || (i.follow_up_on && i.follow_up_on < today)).length ?? 0

  return (
    <Card
      title="Waiting on us"
      description="Complaints and follow-ups nobody has closed yet, oldest first."
      actions={
        data &&
        data.length > 0 && (
          <span className="text-sm muted num">
            {data.length} open{late > 0 && ` · ${late} urgent`}
          </span>
        )
      }
      flush
    >
      {error && (
        <div className="card-body">
          <ErrorAlert message={error} />
        </div>
      )}
      {!data && !error && (
        <div className="card-body">
          <Skeleton height={96} />
        </div>
      )}
      {data && data.length === 0 && (
        <EmptyState icon="check" title="Nothing waiting">
          Every complaint and follow-up has been closed.
        </EmptyState>
      )}
      {data && data.length > 0 && (
        <ul className="open-items">
          {data.slice(0, 6).map((i) => {
            const overdue = i.follow_up_on !== null && i.follow_up_on < today
            return (
              <li key={i.id}>
                <button
                  type="button"
                  className="open-item"
                  onClick={() => navigate(`/customers/${i.customer?.id}?tab=conversations`)}
                >
                  <Avatar name={i.customer?.name || '?'} />
                  <span className="stack" style={{ gap: 2, minWidth: 0 }}>
                    <span className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
                      <strong>{i.customer?.name || 'Unnamed'}</strong>
                      <span className="mono text-xs muted">{i.customer?.code}</span>
                    </span>
                    <span className="text-sm muted open-item-summary">{i.summary}</span>
                  </span>
                  <span className="stack open-item-meta" style={{ gap: 4 }}>
                    <StatusBadge tone={i.kind === 'complaint' || overdue ? 'bad' : 'warn'}>
                      {i.kind === 'complaint'
                        ? 'Complaint'
                        : i.follow_up_on
                          ? `${overdue ? 'Missed' : 'Due'} ${formatDate(i.follow_up_on)}`
                          : i.outcome_label}
                    </StatusBadge>
                    <span className="text-xs muted">{formatRelative(i.created_at)}</span>
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}
