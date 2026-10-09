import { useState } from 'react'

import type { Field, GoldenField, SourceRecord } from '../api/types'
import { FIELD_LABELS, formatDate, formatFieldValue, formatScore, MONO_FIELDS } from '../format'
import { Icon } from './Icon'
import { StatusBadge } from './ui'

// Same rule the backend uses to count conflicts: "Suresh Kumar" and "suresh  kumar" are one value.
const normalise = (v: string) => v.toLowerCase().replace(/[^a-z0-9]/g, '')

interface ValueGroup {
  value: string
  records: SourceRecord[] // every source holding this value, most trusted first
}

// Every distinct value any connected source holds for this field, grouped by value. Records the server
// marked as agreeing with the golden record form one group; masked identity numbers are never compared here.
function groupValues(field: Field, records: SourceRecord[]): ValueGroup[] {
  const holding = records
    .filter((r) => r.source_enabled && r[field])
    .sort((a, b) => Number(b.source_trust) - Number(a.source_trust))
  const groups = new Map<string, ValueGroup>()
  for (const r of holding) {
    const value = r[field] as string
    const agrees = r.agreement?.[field]
    const key = agrees === true ? '__golden__' : normalise(value)
    if (!groups.has(key)) groups.set(key, { value, records: [] })
    groups.get(key)!.records.push(r)
  }
  return [...groups.values()]
}

export function GoldenFieldRow({
  field,
  golden,
  records,
}: {
  field: Field
  golden: GoldenField | undefined
  records: SourceRecord[]
}) {
  const [open, setOpen] = useState(false)
  const groups = groupValues(field, records)

  if (!golden) {
    return (
      <div className="field-row">
        <dt>{FIELD_LABELS[field]}</dt>
        <dd>
          <span className="muted">Not held by any connected source</span>
        </dd>
        <dd>
          <StatusBadge tone="bad">Missing</StatusBadge>
        </dd>
      </div>
    )
  }

  const winner =
    groups.find((g) => g.records.some((r) => r.id === golden.source_record_id)) ??
    groups.find((g) => g.records.some((r) => r.agreement?.[field] === true))
  const agreeing = winner?.records.filter((r) => r.id !== golden.source_record_id) ?? []
  const others = groups.filter((g) => g !== winner)

  return (
    <div className="field-row">
      <dt>{FIELD_LABELS[field]}</dt>
      <dd>
        <div className={`field-value${MONO_FIELDS.has(field) ? ' mono' : ''}`}>{formatFieldValue(field, golden.value)}</div>
        {golden.correction ? (
          <div className="field-source">
            <strong>Approved correction</strong> · evidence {golden.correction.evidence_ref} · proposed by{' '}
            {golden.correction.proposed_by}, approved by {golden.correction.approved_by}
            {golden.last_updated && ` on ${formatDate(golden.last_updated)}`}
          </div>
        ) : (
          <div className="field-source">
            From <strong>{golden.source_name}</strong> · trust {formatScore(golden.trust)}
            {golden.last_updated && ` · updated ${formatDate(golden.last_updated)}`}
          </div>
        )}
        {agreeing.length > 0 && (
          <div className="field-source">
            <Icon name="check" size={12} /> Also in {agreeing.map((r) => r.source_name).join(', ')}
          </div>
        )}

        {others.length > 0 && (
          <>
            <button
              type="button"
              className="field-toggle"
              aria-expanded={open}
              onClick={() => setOpen((v) => !v)}
            >
              <Icon name="chevronRight" size={14} className={open ? 'rot-90' : undefined} />
              {open ? 'Hide' : 'Show'} {others.length} other value{others.length > 1 ? 's' : ''}
            </button>
            {open && (
              <ul className="alternatives">
                {others.map((g) => {
                  const best = g.records[0]
                  const lowerTrust = Number(best.source_trust) < Number(golden.trust)
                  return (
                    <li key={g.value}>
                      <span className="alt-value">{formatFieldValue(field, g.value)}</span>
                      <span className="alt-meta">
                        {g.records.map((r) => `${r.source_name} (${formatScore(r.source_trust)})`).join(', ')}
                        {' · '}
                        {golden.correction ? 'replaced by the approved correction' : lowerTrust ? 'lower trust' : 'same trust, older update'}
                      </span>
                    </li>
                  )
                })}
              </ul>
            )}
          </>
        )}
      </dd>
      <dd>
        {golden.correction ? (
          <StatusBadge tone="good">Corrected</StatusBadge>
        ) : Number(golden.trust) <= 0.4 ? (
          <StatusBadge tone="bad">Low trust</StatusBadge>
        ) : others.length ? (
          <StatusBadge tone="warn">Sources disagree</StatusBadge>
        ) : agreeing.length ? (
          <StatusBadge tone="good">Sources agree</StatusBadge>
        ) : (
          <StatusBadge tone="neutral">One source</StatusBadge>
        )}
      </dd>
    </div>
  )
}
