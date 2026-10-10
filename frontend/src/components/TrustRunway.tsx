import { useState, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import type { Overview } from '../api/types'
import { formatScore } from '../format'

// Trust runway: every customer is one dot on a 0 to 100 line. Dots that would overlap stack upward,
// so a crowded score shows as a column. The three trust zones are labelled on the chart, so colour is
// never the only cue. Select a dot (mouse or keyboard) to open that customer.

const W = 960
const H = 150
const M = { left: 16, right: 16, top: 30, bottom: 30 }
const BASE = H - M.bottom // the axis line
const R = 6
const STEP = 15 // vertical distance between stacked dots

const ZONES = [
  { from: 0, to: 60, label: 'Low', colour: 'var(--band-low)' },
  { from: 60, to: 80, label: 'Medium', colour: 'var(--band-medium)' },
  { from: 80, to: 100, label: 'High', colour: 'var(--band-high)' },
]

const x = (v: number) => M.left + (v / 100) * (W - M.left - M.right)

function zoneColour(v: number) {
  return v >= 80 ? 'var(--band-high)' : v >= 60 ? 'var(--band-medium)' : 'var(--band-low)'
}

// Place dots left to right (scores arrive sorted); a dot too close to the previous one climbs one level.
function placeDots(scores: Overview['scores']) {
  const placed: (Overview['scores'][number] & { v: number; px: number; py: number; level: number })[] = []
  for (const s of scores) {
    const v = Number(s.score) * 100
    const px = x(v)
    const prev = placed.at(-1)
    const level = prev && px - prev.px < R * 2 + 1 ? Math.min(prev.level + 1, 5) : 0
    placed.push({ ...s, v, px, py: BASE - 12 - level * STEP, level })
  }
  return placed
}

export function TrustRunway({ scores }: { scores: Overview['scores'] }) {
  const navigate = useNavigate()
  const [hover, setHover] = useState<number | null>(null)

  const dots = placeDots(scores)
  const focused = dots.find((d) => d.id === hover)

  const open = (id: number) => navigate(`/customers/${id}`)
  const onKey = (e: KeyboardEvent, id: number) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      open(id)
    }
  }

  return (
    // On phones the chart keeps a readable size and scrolls sideways instead of shrinking.
    <div className="chart-scroll">
      <div className="chart runway">
        <svg viewBox={`0 0 ${W} ${H}`} role="group" aria-label="Every customer placed by trust score, 0 to 100">
          {ZONES.map((z) => (
            <g key={z.label}>
              <rect x={x(z.from)} y={M.top - 6} width={x(z.to) - x(z.from)} height={BASE - M.top + 6} fill={z.colour} fillOpacity="0.06" />
              <text x={x(z.from) + 8} y={M.top - 12} fontSize="12" fontWeight="600" fill="var(--text-3)">
                {z.label}
              </text>
            </g>
          ))}
          {[60, 80].map((t) => (
            <line key={t} x1={x(t)} x2={x(t)} y1={M.top - 22} y2={BASE} stroke="var(--border-strong)" strokeDasharray="3 4" />
          ))}
          <line x1={x(0)} x2={x(100)} y1={BASE} y2={BASE} stroke="var(--chart-axis)" />
          {[0, 20, 40, 60, 80, 100].map((t) => (
            <g key={t}>
              <line x1={x(t)} x2={x(t)} y1={BASE} y2={BASE + 5} stroke="var(--chart-axis)" />
              <text x={x(t)} y={BASE + 19} textAnchor="middle" fontSize="11" fill="var(--text-3)">
                {t}
              </text>
            </g>
          ))}
          {dots.map((d) => (
            <circle
              key={d.id}
              cx={d.px}
              cy={d.py}
              r={hover === d.id ? R + 2 : R}
              fill={zoneColour(d.v)}
              stroke="var(--surface)"
              strokeWidth="2"
              tabIndex={0}
              role="link"
              aria-label={`${d.name || d.code}, trust ${formatScore(d.score)}`}
              style={{ cursor: 'pointer', outline: 'none', transition: 'r 120ms' }}
              onMouseEnter={() => setHover(d.id)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(d.id)}
              onBlur={() => setHover(null)}
              onClick={() => open(d.id)}
              onKeyDown={(e) => onKey(e, d.id)}
            />
          ))}
        </svg>
        {focused && (
          <div className="chart-tooltip" style={{ left: `${(focused.px / W) * 100}%`, top: `${(focused.py / H) * 100}%` }}>
            <strong>{focused.name || focused.code}</strong>
            <span className="muted">
              {focused.code} · trust <span className="num">{formatScore(focused.score)}</span>
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
