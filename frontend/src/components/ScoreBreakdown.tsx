import type { Field, GoldenField } from '../api/types'
import { FIELD_HUES, FIELD_LABELS, FIELDS, formatScore } from '../format'

// "Why this score": each field's share of the trust score.
// The light track is the most the field can add (its weight); the solid bar is what it adds now
// (weight x trust of the source that supplied it). Track lengths are to scale across fields.

export function ScoreBreakdown({
  golden,
  weights,
  score,
}: {
  golden: GoldenField[]
  weights: Partial<Record<Field, string>>
  score: string | null
}) {
  const maxWeight = Math.max(...FIELDS.map((f) => Number(weights[f] ?? 0)), 0.0001)

  return (
    <div className="breakdown">
      {FIELDS.map((f) => {
        const weight = Number(weights[f] ?? 0)
        const g = golden.find((x) => x.field === f)
        const trust = g ? Number(g.trust) : 0
        const adds = weight * trust
        return (
          <div key={f} className={`breakdown-row hue-${FIELD_HUES[f]}`}>
            <span className="label">{FIELD_LABELS[f]}</span>
            <span className="value mono">
              {adds.toFixed(2)} <span className="muted">/ {weight.toFixed(2)}</span>
            </span>
            <span className="bar" aria-hidden="true">
              <span className="track" style={{ width: `${(weight / maxWeight) * 100}%` }} />
              <span className="fill" style={{ width: `${(adds / maxWeight) * 100}%` }} />
            </span>
            <span className="note">
              {g ? `${g.source_name} · trust ${g.trust}` : 'Not held by any connected source'}
            </span>
          </div>
        )
      })}
      <div className="breakdown-total">
        <span>Trust score</span>
        <span className="mono">{formatScore(score)}</span>
      </div>
    </div>
  )
}
