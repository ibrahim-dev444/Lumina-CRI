import { useState } from 'react'

import type { Band } from '../api/types'
import { formatScore } from '../format'

// Trust mix: share of customers in each band, as a ring. Three parts of one whole, so a donut fits;
// the average score sits in the middle, and every segment is also listed with its count and share.

const BANDS: { band: Band; label: string; range: string; colour: string }[] = [
  { band: 'high', label: 'High', range: '0.8 and above', colour: 'var(--band-high)' },
  { band: 'medium', label: 'Medium', range: '0.6 to 0.8', colour: 'var(--band-medium)' },
  { band: 'low', label: 'Low', range: 'below 0.6', colour: 'var(--band-low)' },
]

const SIZE = 168
const STROKE = 18
const R = (SIZE - STROKE) / 2
const C = 2 * Math.PI * R
const GAP = 3 // surface gap between segments, in px of arc

export function TrustDonut({ bands, average }: { bands: Record<Band, number>; average: string }) {
  const [hover, setHover] = useState<Band | null>(null)
  const total = BANDS.reduce((sum, b) => sum + bands[b.band], 0)
  const present = BANDS.filter((b) => bands[b.band] > 0)

  // Each segment starts where the ones before it end.
  const lengths = present.map((b) => (bands[b.band] / Math.max(total, 1)) * C)
  const arcs = present.map((b, i) => ({
    ...b,
    length: lengths[i],
    offset: lengths.slice(0, i).reduce((sum, l) => sum + l, 0),
  }))

  const focus = hover ? BANDS.find((b) => b.band === hover)! : null

  return (
    <div className="donut-wrap">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        width={SIZE}
        height={SIZE}
        role="img"
        aria-label={`Trust mix: ${BANDS.map((b) => `${bands[b.band]} ${b.label.toLowerCase()}`).join(', ')}`}
      >
        <circle cx={SIZE / 2} cy={SIZE / 2} r={R} fill="none" stroke="var(--surface-sunken)" strokeWidth={STROKE} />
        <g transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}>
          {arcs.map((a) => (
            <circle
              key={a.band}
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={R}
              fill="none"
              stroke={a.colour}
              strokeWidth={hover === a.band ? STROKE + 4 : STROKE}
              strokeLinecap="butt"
              strokeDasharray={`${Math.max(a.length - (present.length > 1 ? GAP : 0), 0)} ${C}`}
              strokeDashoffset={-a.offset}
              opacity={hover && hover !== a.band ? 0.4 : 1}
              style={{ transition: 'opacity 120ms, stroke-width 120ms', cursor: 'default' }}
              onMouseEnter={() => setHover(a.band)}
              onMouseLeave={() => setHover(null)}
            >
              <title>{`${a.label}: ${bands[a.band]} customers`}</title>
            </circle>
          ))}
        </g>
        <text x="50%" y="47%" textAnchor="middle" fontSize="30" fontWeight="600" fill="var(--text)" className="num">
          {focus ? bands[focus.band] : formatScore(average)}
        </text>
        <text x="50%" y="62%" textAnchor="middle" fontSize="11" fill="var(--text-3)">
          {focus ? `${focus.label.toLowerCase()} trust` : 'average trust'}
        </text>
      </svg>

      <ul className="donut-list">
        {BANDS.map((b) => (
          <li key={b.band} onMouseEnter={() => setHover(b.band)} onMouseLeave={() => setHover(null)}>
            <i style={{ background: b.colour }} />
            <span>
              {b.label} <span className="share">· {b.range}</span>
            </span>
            <span className="num count">{bands[b.band]}</span>
            <span className="num share pct">{total ? Math.round((bands[b.band] / total) * 100) : 0}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
