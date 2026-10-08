import { useState } from 'react'

import type { Overview } from '../api/types'

// Column chart: how many customers fall in each 0.1 band of trust score.
// Columns take the colour of the trust band they fall in (Low / Medium / High), and each band is
// labelled on the chart, so colour is never the only cue. Every column carries its count on top, so
// there is no y-axis to read; empty bands show a faint capsule so the 0 to 1 scale stays visible.

const W = 640
const H = 220
const M = { top: 36, right: 8, bottom: 28, left: 8 }
const PLOT_W = W - M.left - M.right
const PLOT_H = H - M.top - M.bottom
const GAP = 10 // breathing room between capsules
const RADIUS = 8

// The band cut-offs the trust badges use, drawn as reference lines.
const THRESHOLDS = [
  { at: 0.6, label: 'Medium' },
  { at: 0.8, label: 'High' },
]

// Same cut-offs as the trust badges. Status colours, reserved for trust bands only.
function bandKey(from: number): 'high' | 'medium' | 'low' {
  if (from >= 0.8) return 'high'
  if (from >= 0.6) return 'medium'
  return 'low'
}

function niceStep(max: number): number {
  if (max <= 5) return 1
  if (max <= 10) return 2
  if (max <= 25) return 5
  return Math.ceil(max / 5 / 10) * 10
}

// A column with rounded top corners and a flat base sitting on the axis.
function columnPath(x: number, y: number, w: number, h: number): string {
  const r = Math.min(RADIUS, w / 2, h)
  const base = y + h
  return `M${x},${base}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${base}Z`
}

export function TrustHistogram({ buckets }: { buckets: Overview['histogram'] }) {
  const [hover, setHover] = useState<number | null>(null)

  const step = niceStep(Math.max(1, ...buckets.map((b) => b.count)))
  const yMax = Math.max(step, Math.ceil(Math.max(...buckets.map((b) => b.count)) / step) * step)

  const slot = PLOT_W / buckets.length
  const x = (score: number) => M.left + score * PLOT_W
  const y = (count: number) => M.top + PLOT_H - (count / yMax) * PLOT_H

  const hovered = hover === null ? null : buckets[hover]

  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Number of customers in each trust score band">
        {/* Each band colour fades from full at the top to soft at the base */}
        <defs>
          {(['low', 'medium', 'high'] as const).map((k) => (
            <linearGradient key={k} id={`hist-${k}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={`var(--band-${k})`} />
              <stop offset="100%" stopColor={`var(--band-${k})`} stopOpacity="0.55" />
            </linearGradient>
          ))}
        </defs>

        {/* Faint capsule behind every slot */}
        {buckets.map((_, i) => (
          <path
            key={`track-${i}`}
            d={columnPath(M.left + i * slot + GAP / 2, M.top, slot - GAP, PLOT_H)}
            fill="var(--surface-sunken)"
          />
        ))}

        {/* Band thresholds */}
        <text x={M.left + 6} y={M.top - 22} fontSize="11" fill="var(--text-3)">
          Low
        </text>
        {THRESHOLDS.map((t) => (
          <g key={t.at}>
            <line
              x1={x(t.at)}
              x2={x(t.at)}
              y1={M.top - 18}
              y2={M.top + PLOT_H}
              stroke="var(--chart-axis)"
              strokeDasharray="3 3"
            />
            <text x={x(t.at) + 6} y={M.top - 22} fontSize="11" fill="var(--text-3)">
              {t.label}
            </text>
          </g>
        ))}

        {/* Columns */}
        {buckets.map((b, i) =>
          b.count > 0 ? (
            <g key={i} opacity={hover === null || hover === i ? 1 : 0.45} style={{ transition: 'opacity 120ms' }}>
              <path
                d={columnPath(M.left + i * slot + GAP / 2, y(b.count), slot - GAP, M.top + PLOT_H - y(b.count))}
                fill={`url(#hist-${bandKey(b.from)})`}
              />
              <text
                x={M.left + (i + 0.5) * slot}
                y={y(b.count) - 6}
                textAnchor="middle"
                fontSize="12"
                fontWeight="600"
                fill="var(--text)"
              >
                {b.count}
              </text>
            </g>
          ) : null,
        )}

        {/* Baseline and x-axis labels at band edges */}
        <line x1={M.left} x2={W - M.right} y1={M.top + PLOT_H} y2={M.top + PLOT_H} stroke="var(--chart-axis)" />
        {[0, 0.2, 0.4, 0.6, 0.8, 1].map((v) => (
          <text key={v} x={x(v)} y={H - 8} textAnchor="middle" fontSize="11" fill="var(--text-3)">
            {v.toFixed(1)}
          </text>
        ))}

        {/* Hit areas: the full column slot, larger than the mark */}
        {buckets.map((b, i) => (
          <rect
            key={i}
            x={M.left + i * slot}
            y={M.top}
            width={slot}
            height={PLOT_H}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
          >
            <title>{`${b.from.toFixed(1)} to ${b.to.toFixed(1)}: ${b.count} customers`}</title>
          </rect>
        ))}
      </svg>

      {hovered && hover !== null && (
        <div
          className="chart-tooltip"
          style={{
            left: `${((M.left + (hover + 0.5) * slot) / W) * 100}%`,
            top: `${(y(hovered.count) / H) * 100}%`,
          }}
        >
          <strong className="num">
            {hovered.count} customer{hovered.count === 1 ? '' : 's'}
          </strong>
          <span className="muted">
            Trust {hovered.from.toFixed(1)} to {hovered.to.toFixed(1)}
          </span>
        </div>
      )}

      {/* The same numbers as a table, for screen readers */}
      <table className="sr-only">
        <caption>Customers per trust score band</caption>
        <thead>
          <tr>
            <th>Trust score</th>
            <th>Customers</th>
          </tr>
        </thead>
        <tbody>
          {buckets.map((b) => (
            <tr key={b.from}>
              <td>
                {b.from.toFixed(1)} to {b.to.toFixed(1)}
              </td>
              <td>{b.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
