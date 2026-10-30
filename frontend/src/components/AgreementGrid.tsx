import type { CustomerDetail, Field, SourceRecord } from '../api/types'
import { FIELD_LABELS, FIELD_SHORT, FIELDS, formatFieldValue, formatScore } from '../format'
import { trustFor } from './agreement'
import { Icon } from './Icon'

// Agreement grid: every system (rows) against every field (columns) for one customer.
// A cell says whether that system's value matches the golden record, differs, or is not held.
// A system holding several records for the customer is one row; a cell differs if any of its records differs.
// Shape and symbol carry the meaning (✓, ×, empty), colour only reinforces it.

type Kind = 'same' | 'diff' | 'none'

function systems(records: SourceRecord[]) {
  const bySource = new Map<string, SourceRecord[]>()
  for (const r of records) bySource.set(r.source_code, [...(bySource.get(r.source_code) ?? []), r])
  return [...bySource.values()]
}

function cell(field: Field, records: SourceRecord[]): { kind: Kind; values: string[] } {
  const holding = records.filter((r) => r[field] && r.agreement?.[field] !== null && r.agreement?.[field] !== undefined)
  if (!holding.length) return { kind: 'none', values: [] }
  const values = [...new Set(holding.map((r) => formatFieldValue(field, r[field] as string)))]
  return { kind: holding.every((r) => r.agreement?.[field] === true) ? 'same' : 'diff', values }
}

// "trust 80", or "trust 52 to 80" when the administrator set some fields differently.
function trustRange(r: SourceRecord) {
  const held = FIELDS.filter((f) => r[f])
  const values = (held.length ? held : FIELDS).map((f) => Math.round(trustFor(r, f) * 100))
  const low = Math.min(...values)
  const high = Math.max(...values)
  return low === high ? `trust ${high}` : `trust ${low} to ${high}, by field`
}

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
            {systems(customer.records).map((records) => {
              const first = records[0]
              let held = 0
              let matched = 0
              const cells = FIELDS.map((f) => {
                const c = cell(f, records)
                if (c.kind !== 'none') held += 1
                if (c.kind === 'same') matched += 1
                return { f, ...c }
              })
              return (
                <tr key={first.source_code}>
                  <td>
                    <div className="stack" style={{ gap: 1 }}>
                      <span style={{ fontWeight: 500 }}>{first.source_name}</span>
                      <span className="text-xs muted">{trustRange(first)}</span>
                      {records.length > 1 && (
                        <span className="records-note" title={records.map((r) => r.source_record_id).join(', ')}>
                          {records.length} records
                        </span>
                      )}
                    </div>
                  </td>
                  {cells.map((c) => (
                    <td key={c.f} className="center">
                      <span
                        className={`agree-cell ${c.kind}`}
                        title={
                          c.kind === 'none'
                            ? `${FIELD_LABELS[c.f]}: not held`
                            : `${FIELD_LABELS[c.f]}: ${c.values.join(' / ')} (${c.kind === 'same' ? 'matches' : 'differs'}) · trust ${formatScore(trustFor(first, c.f))}`
                        }
                      >
                        {c.kind === 'same' && <Icon name="check" size={14} label="Matches" />}
                        {c.kind === 'diff' && <Icon name="x" size={14} label="Differs" />}
                      </span>
                    </td>
                  ))}
                  <td className="right num nowrap">
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
