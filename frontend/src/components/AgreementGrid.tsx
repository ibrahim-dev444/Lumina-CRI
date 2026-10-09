import type { CustomerDetail } from '../api/types'
import { FIELD_LABELS, FIELD_SHORT, FIELDS, formatFieldValue, formatScore } from '../format'
import { Icon } from './Icon'

// Agreement grid: every source (rows) against every field (columns) for one customer.
// A cell says whether that source's value matches the golden record, differs, or is not held.
// Shape and symbol carry the meaning (✓, ×, empty), colour only reinforces it.

export function AgreementGrid({ customer }: { customer: CustomerDetail }) {
  return (
    <div className="stack" style={{ gap: 12 }}>
      <div className="table-wrap">
        <table className="agree">
          <thead>
            <tr>
              <th>Source</th>
              {FIELDS.map((f) => (
                <th key={f} className="center" title={FIELD_LABELS[f]}>
                  {FIELD_SHORT[f]}
                </th>
              ))}
              <th className="right">Agrees</th>
            </tr>
          </thead>
          <tbody>
            {customer.records.map((r) => {
              let held = 0
              let matched = 0
              const cells = FIELDS.map((f) => {
                const value = r[f]
                const verdict = r.agreement?.[f]
                if (!value || verdict === null || verdict === undefined) return { f, kind: 'none' as const, value }
                held += 1
                const same = verdict === true
                if (same) matched += 1
                return { f, kind: same ? ('same' as const) : ('diff' as const), value }
              })
              return (
                <tr key={r.id}>
                  <td>
                    <div className="stack" style={{ gap: 1 }}>
                      <span style={{ fontWeight: 500 }}>{r.source_name}</span>
                      <span className="text-xs muted">trust {formatScore(r.source_trust)}</span>
                    </div>
                  </td>
                  {cells.map((c) => (
                    <td key={c.f} className="center">
                      <span
                        className={`agree-cell ${c.kind}`}
                        title={
                          c.kind === 'none'
                            ? `${FIELD_LABELS[c.f]}: not held`
                            : `${FIELD_LABELS[c.f]}: ${formatFieldValue(c.f, c.value)} (${c.kind === 'same' ? 'matches' : 'differs'})`
                        }
                      >
                        {c.kind === 'same' && <Icon name="check" size={14} label="Matches" />}
                        {c.kind === 'diff' && <Icon name="x" size={14} label="Differs" />}
                      </span>
                    </td>
                  ))}
                  <td className="right num">
                    {matched} of {held}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="legend">
        <span>
          <span className="agree-cell same small">
            <Icon name="check" size={10} />
          </span>
          Matches the golden record
        </span>
        <span>
          <span className="agree-cell diff small">
            <Icon name="x" size={10} />
          </span>
          Different value
        </span>
        <span>
          <span className="agree-cell none small" />
          Not held by this source
        </span>
      </div>
    </div>
  )
}
