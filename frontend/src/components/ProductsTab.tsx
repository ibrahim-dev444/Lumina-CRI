import type { ReactNode } from 'react'

import type { CustomerDetail, Product } from '../api/types'
import { formatDate, formatMoney, formatRelative } from '../format'
import { Icon, type IconName } from './Icon'
import { Card, EmptyState, StatusBadge } from './ui'

const STATUS: Record<Product['status'], { label: string; tone: 'good' | 'warn' | 'bad' | 'neutral' }> = {
  active: { label: 'Active', tone: 'good' },
  overdue: { label: 'Overdue', tone: 'bad' },
  dormant: { label: 'Dormant', tone: 'warn' },
  closed: { label: 'Closed', tone: 'neutral' },
}

const OWED: Product['type'][] = ['home_loan', 'personal_loan', 'vehicle_loan', 'loan', 'credit_card']

// Customer profile, Products tab: accounts, deposits, loans and cards from every connected system.
// Amounts come from the server only for roles that may see them; account numbers only as their last four.
export function ProductsTab({ c }: { c: CustomerDetail }) {
  const p = c.products
  if (p.items.length === 0) {
    return (
      <Card title="Products">
        <EmptyState icon="file" title="No products on file">
          None of the connected systems lists an account, loan or card for this customer. Connectors read products once
          an accounts table is mapped.
        </EmptyState>
      </Card>
    )
  }
  const open = p.items.filter((i) => i.status !== 'closed')
  const closed = p.items.filter((i) => i.status === 'closed')

  return (
    <>
      <div className="kpis kpis-compact">
        <Tile hue={1} icon="file" label="Products held" value={String(p.count)}>
          {closed.length > 0 && `${closed.length} closed not counted`}
        </Tile>
        <Tile hue={5} icon="shield" label="With the bank" value={p.amounts_hidden ? 'Hidden' : formatMoney(p.deposits, true)}>
          Savings, current and deposits
        </Tile>
        <Tile hue={3} icon="key" label="Owed" value={p.amounts_hidden ? 'Hidden' : formatMoney(p.owed, true)}>
          Loans and cards outstanding
        </Tile>
        <Tile
          hue={2}
          icon="alert"
          label="Needs attention"
          value={String(p.overdue + p.dormant)}
          tone={p.overdue ? 'bad' : p.dormant ? 'warn' : undefined}
        >
          {p.overdue + p.dormant === 0 ? 'Nothing overdue or dormant' : `${p.overdue} overdue · ${p.dormant} dormant`}
        </Tile>
      </div>

      {p.amounts_hidden && (
        <div className="notice" role="note">
          <Icon name="lock" size={16} />
          <span>Balances and amounts owed are hidden for your role. You can still see which products the customer holds.</span>
        </div>
      )}

      <Card title="Accounts, loans and cards" description="As each system reports them. Account numbers show the last four only." flush>
        <div className="table-wrap">
          <table className="table" style={{ minWidth: 760 }}>
            <thead>
              <tr>
                <th>Product</th>
                <th>Account</th>
                <th>Status</th>
                <th>Opened</th>
                <th className="num">{p.amounts_hidden ? 'Amount' : 'Balance or owed'}</th>
                <th>From</th>
              </tr>
            </thead>
            <tbody>
              {[...open, ...closed].map((item) => (
                <tr key={item.id} className={item.status === 'closed' ? 'is-muted' : undefined}>
                  <td>
                    <div className="stack" style={{ gap: 2 }}>
                      <strong>{item.name || item.type_label}</strong>
                      {item.name && <span className="text-xs muted">{item.type_label}</span>}
                    </div>
                  </td>
                  <td className="mono">{item.account || '-'}</td>
                  <td>
                    <StatusBadge tone={STATUS[item.status].tone}>{STATUS[item.status].label}</StatusBadge>
                  </td>
                  <td>{item.opened_on ? formatDate(item.opened_on) : '-'}</td>
                  <td className="num">
                    {item.balance === null ? (
                      <span className="muted">{p.amounts_hidden ? 'Hidden' : '-'}</span>
                    ) : (
                      <span className={OWED.includes(item.type) ? 'amount-owed' : undefined}>
                        {OWED.includes(item.type) ? '−' : ''}
                        {formatMoney(item.balance)}
                      </span>
                    )}
                  </td>
                  <td>
                    <div className="stack" style={{ gap: 2 }}>
                      <span>{item.source_name}</span>
                      <span className="text-xs muted">Updated {formatRelative(item.updated_at)}</span>
                    </div>
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

function Tile({
  hue,
  icon,
  label,
  value,
  tone,
  children,
}: {
  hue: number
  icon: IconName
  label: string
  value: string
  tone?: 'bad' | 'warn'
  children?: ReactNode
}) {
  return (
    <div className={`card kpi hue-${hue}`}>
      <div className="kpi-top">
        <span className="kpi-label">{label}</span>
        <span className="kpi-icon">
          <Icon name={icon} />
        </span>
      </div>
      <span className={`kpi-value${tone ? ` tone-${tone}` : ''}`}>{value}</span>
      {children && <span className="kpi-sub">{children}</span>}
    </div>
  )
}
