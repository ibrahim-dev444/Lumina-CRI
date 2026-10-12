import { useCountUp } from './useReveal'

// The hero animation: the same customer as three disagreeing records (one per bank system) flows along
// glowing lines into one golden record, and its trust score counts up. It shows Lumina's whole idea at once.
const SOURCES = [
  { system: 'Core banking', trust: 85, name: 'SURESH KUMAR', mobile: '+91 98221 04521', tone: 'c1' },
  { system: 'CRM', trust: 55, name: 'Sooresh Kumar', mobile: '98221 07788', tone: 'c2' },
  { system: 'Branch file', trust: 40, name: 'Suresh K', mobile: '9822107788', tone: 'c3' },
]

const FIELDS = [
  { label: 'Name', value: 'Suresh Kumar', from: 'Core banking' },
  { label: 'Mobile', value: '+91 98221 04521', from: 'Core banking' },
  { label: 'PAN', value: 'XXXXX1234F', from: 'Core banking' },
  { label: 'Email', value: 'suresh.kumar@mail.example', from: 'Core banking' },
]

// Paths from the right edge of each source card to the golden card, in the SVG's 100 x 100 space.
const LINES = ['M 34 18 C 46 18, 42 50, 52 50', 'M 34 50 C 42 50, 44 50, 52 50', 'M 34 82 C 46 82, 42 50, 52 50']

export function HeroVisual() {
  const score = useCountUp(85, 1500, 1700)
  const ring = 2 * Math.PI * 34

  return (
    <div className="lp-visual" aria-label="Three records of the same customer become one trusted golden record" role="img">
      <svg className="lp-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <linearGradient id="lp-line" x1="0" x2="1">
            <stop offset="0" stopColor="var(--accent)" stopOpacity="0.15" />
            <stop offset="1" stopColor="var(--accent)" stopOpacity="0.9" />
          </linearGradient>
        </defs>
        {LINES.map((d, i) => (
          <g key={d}>
            <path className={`lp-line lp-line-${i}`} d={d} pathLength={1} />
            <circle className="lp-pulse" r="0.9">
              <animateMotion dur="2.6s" begin={`${1.2 + i * 0.25}s`} repeatCount="indefinite" path={d} />
            </circle>
          </g>
        ))}
      </svg>

      <div className="lp-sources">
        {SOURCES.map((s, i) => (
          <div key={s.system} className={`lp-src lp-src-${i} hue-${i + 1}`}>
            <div className="lp-src-head">
              <span className="lp-src-dot" />
              <span>{s.system}</span>
              <span className="lp-src-trust">trust {s.trust}</span>
            </div>
            <strong>{s.name}</strong>
            <span className="mono">{s.mobile}</span>
          </div>
        ))}
      </div>

      <div className="lp-golden">
        <div className="lp-golden-head">
          <span className="lp-golden-tag">Golden record</span>
          <div className="lp-score">
            <svg viewBox="0 0 80 80" aria-hidden="true">
              <circle cx="40" cy="40" r="34" className="lp-score-track" />
              <circle
                cx="40"
                cy="40"
                r="34"
                className="lp-score-fill"
                strokeDasharray={ring}
                strokeDashoffset={ring * (1 - score / 100)}
              />
            </svg>
            <div>
              <strong>{score}</strong>
              <span>High trust</span>
            </div>
          </div>
        </div>
        <ul className="lp-golden-fields">
          {FIELDS.map((f, i) => (
            <li key={f.label} style={{ animationDelay: `${1.6 + i * 0.14}s` }}>
              <span className="lp-field-label">{f.label}</span>
              <span className="lp-field-value">{f.value}</span>
              <span className="lp-field-check" aria-hidden="true">
                ✓
              </span>
            </li>
          ))}
        </ul>
        <div className="lp-golden-foot">3 systems · 1 customer · every change audited</div>
      </div>
    </div>
  )
}
