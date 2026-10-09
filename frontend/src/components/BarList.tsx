import type { ReactNode } from 'react'

// Ranked horizontal bars: label on the left, bar in the middle, value on the right. One hue, because the
// bars compare one measure; the number is always printed, so the bar length is never the only cue.

export interface BarRow {
  key: string
  label: ReactNode
  value: number // drawn length, 0..max
  shown: ReactNode // printed value
  extra?: ReactNode
}

export function BarList({ rows, max, ariaLabel }: { rows: BarRow[]; max: number; ariaLabel: string }) {
  return (
    <ul className="barlist" aria-label={ariaLabel}>
      {rows.map((r) => (
        <li key={r.key}>
          <span className="barlist-label">{r.label}</span>
          <span className="barlist-track" aria-hidden="true">
            <i style={{ width: `${max ? Math.max(0, Math.min(1, r.value / max)) * 100 : 0}%` }} />
          </span>
          <span className="barlist-value">
            <span className="num">{r.shown}</span>
            {r.extra}
          </span>
        </li>
      ))}
    </ul>
  )
}
