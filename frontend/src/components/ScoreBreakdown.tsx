import type { Field, GoldenField } from '../api/types'
import { FIELD_LABELS, FIELDS, formatScore } from '../format'

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
          <div key={f} className="breakdown-row">
            <span className="label">{FIELD_LABELS[f]}</span>
            <span className="value mono">
              {(adds * 100).toFixed(1)} <span className="muted">/ {Math.round(weight * 100)} pts</span>
            </span>
            <span className="bar" aria-hidden="true">
              <span className="track" style={{ width: `${(weight / maxWeight) * 100}%` }} />
              <span className="fill" style={{ width: `${(adds / maxWeight) * 100}%` }} />
            </span>
            <span className="note">
              {g ? `${g.source_name} · trust ${formatScore(g.trust)}` : 'Not held by any connected source'}
            </span>
          </div>
        )
      })}
      <div className="breakdown-total">
        <span>Trust score</span>
        <span className="mono">{formatScore(score)} / 100</span>
      </div>
    </div>
  )
}
