import type { Band } from '../api/types'
import { formatScore } from '../format'
import { BandBadge } from './ui'

// A half-ring gauge from 0 to 1. The track is split into the three trust bands (soft tints),
// the arc fills to the score in its band's colour, and the cut-offs 0.6 and 0.8 are ticked.

const W = 240
const H = 142
const CX = W / 2
const CY = 122
const R = 100
const STROKE = 14

const BAND_COLOUR: Record<Band, string> = {
  low: 'var(--band-low)',
  medium: 'var(--band-medium)',
  high: 'var(--band-high)',
}

// Point on the half circle for a value from 0 (left) to 1 (right).
function point(value: number, radius = R) {
  const angle = Math.PI * (1 - value)
  return { x: CX + radius * Math.cos(angle), y: CY - radius * Math.sin(angle) }
}

function arc(from: number, to: number) {
  const a = point(from)
  const b = point(to)
  return `M${a.x},${a.y} A${R},${R} 0 0 1 ${b.x},${b.y}`
}

export function ScoreGauge({ score, band }: { score: string | null; band: Band }) {
  const value = score === null ? 0 : Math.max(0, Math.min(1, Number(score)))

  return (
    <div className="gauge">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Trust score ${formatScore(score)} out of 1, ${band}`}>
        {/* Band zones as a soft track */}
        <path d={arc(0, 0.6)} fill="none" stroke="var(--band-low)" strokeOpacity="0.16" strokeWidth={STROKE} />
        <path d={arc(0.6, 0.8)} fill="none" stroke="var(--band-medium)" strokeOpacity="0.2" strokeWidth={STROKE} />
        <path d={arc(0.8, 1)} fill="none" stroke="var(--band-high)" strokeOpacity="0.18" strokeWidth={STROKE} />

        {/* The score */}
        {value > 0 && (
          <path d={arc(0, value)} fill="none" stroke={BAND_COLOUR[band]} strokeWidth={STROKE} strokeLinecap="round" />
        )}

        {/* Ticks at the band cut-offs */}
        {[0.6, 0.8].map((t) => {
          const inner = point(t, R - STROKE / 2 - 4)
          const outer = point(t, R + STROKE / 2 + 4)
          return (
            <line key={t} x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y} stroke="var(--surface)" strokeWidth="3" />
          )
        })}
        <text x={point(0).x} y={CY + 14} textAnchor="middle" fontSize="11" fill="var(--text-3)">
          0
        </text>
        <text x={point(1).x} y={CY + 14} textAnchor="middle" fontSize="11" fill="var(--text-3)">
          1
        </text>
      </svg>
      <div className="gauge-value">{formatScore(score)}</div>
      <div style={{ display: 'flex', justifyContent: 'center', marginTop: 4 }}>
        <BandBadge band={band} />
      </div>
    </div>
  )
}
