import { useId } from 'react'

// Lumina's loaders are the logo family in motion: separate parts come together into one, the way Lumina joins
// many records into one customer. Each kind fits what is loading:
//   overlap  - the logo itself; app start and general pages
//   stack    - record cards settle into one pile; customer lists
//   orbit    - arcs lock into a ring around a core; source system connections
//   converge - rays meet in one bright point; building a golden record
//   pair     - two record cards slide together and link; match review
//   check    - one tick, then a second tick (maker, then checker); approvals
//   shield   - a shield draws itself and a check appears; compliance
//   trail    - steps light up one after another along a line; audit log and activity
// With "reduce motion" switched on in the operating system, the finished picture shows without movement.
export type LoaderKind = 'overlap' | 'stack' | 'orbit' | 'converge' | 'pair' | 'check' | 'shield' | 'trail'

// Gradient ids must be unique on the page; useId gives ":r1:"-style values, which url(#...) cannot use.
function useSvgId() {
  return useId().replace(/[^a-zA-Z0-9_-]/g, '')
}

export function LogoArt({ kind, size, animated }: { kind: LoaderKind; size: number; animated: boolean }) {
  const id = useSvgId()
  const bg = ['overlap', 'orbit', 'check', 'shield'].includes(kind) ? `${id}-bg1` : `${id}-bg2`
  return (
    <svg
      className={`logo-art logo-${kind}${animated ? ' is-animated' : ''}`}
      width={size}
      height={size}
      viewBox="0 0 64 64"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={`${id}-bg1`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6d5cf0" />
          <stop offset="1" stopColor="#3b2fc9" />
        </linearGradient>
        <linearGradient id={`${id}-bg2`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#8b5cf6" />
          <stop offset="0.55" stopColor="#5b47e0" />
          <stop offset="1" stopColor="#2f3fd6" />
        </linearGradient>
        <linearGradient id={`${id}-shine`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity="0.25" />
          <stop offset="0.5" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
        <linearGradient id={`${id}-ray`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#fff" stopOpacity="0.15" />
          <stop offset="1" stopColor="#fff" stopOpacity="0.95" />
        </linearGradient>
        <radialGradient id={`${id}-orb`} cx="0.4" cy="0.35" r="0.7">
          <stop offset="0" stopColor="#fff" />
          <stop offset="0.6" stopColor="#f3e8ff" />
          <stop offset="1" stopColor="#c4b5fd" />
        </radialGradient>
        <radialGradient id={`${id}-glow`}>
          <stop offset="0" stopColor="#fff" stopOpacity="0.8" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </radialGradient>
      </defs>

      <rect width="64" height="64" rx="15" fill={`url(#${bg})`} />
      <rect width="64" height="64" rx="15" fill={`url(#${id}-shine)`} />

      {kind === 'overlap' && (
        <>
          <g className="blend">
            <circle className="part p1" cx="32" cy="24" r="12" fill="#c4b5fd" fillOpacity="0.8" />
            <circle className="part p2" cx="24.5" cy="37" r="12" fill="#f9a8d4" fillOpacity="0.75" />
            <circle className="part p3" cx="39.5" cy="37" r="12" fill="#5eead4" fillOpacity="0.7" />
          </g>
          <g className="core">
            <circle cx="32" cy="32.7" r="8" fill={`url(#${id}-glow)`} />
            <circle cx="32" cy="32.7" r="3.2" fill="#fff" />
          </g>
        </>
      )}

      {kind === 'stack' && (
        <>
          <rect className="part p1" x="19" y="13" width="30" height="22" rx="5" fill="#fff" fillOpacity="0.28" />
          <rect className="part p2" x="16" y="20" width="32" height="23" rx="5" fill="#fff" fillOpacity="0.5" />
          <g className="part p3">
            <rect x="13" y="27" width="34" height="24" rx="6" fill="#fff" />
            <rect x="18" y="33" width="14" height="3" rx="1.5" fill="#5b47e0" fillOpacity="0.55" />
            <rect x="18" y="40" width="20" height="3" rx="1.5" fill="#5b47e0" fillOpacity="0.3" />
          </g>
          <g className="core">
            <circle cx="44" cy="30" r="8" fill={`url(#${id}-glow)`} />
            <circle cx="44" cy="30" r="3.6" fill="#fff" stroke="#5b47e0" strokeWidth="1.6" />
          </g>
        </>
      )}

      {kind === 'orbit' && (
        <>
          <g fill="none" strokeWidth="5" strokeLinecap="round">
            <path className="part arc p1" d="M19.98 19.98A17 17 0 0 1 44.02 19.98" stroke="#c4b5fd" />
            <path className="part arc p2" d="M48.42 27.6A17 17 0 0 1 36.4 48.42" stroke="#5eead4" />
            <path className="part arc p3" d="M27.6 48.42A17 17 0 0 1 15.58 27.6" stroke="#f9a8d4" />
          </g>
          <g className="core">
            <circle cx="32" cy="32" r="9" fill={`url(#${id}-glow)`} />
            <circle cx="32" cy="32" r="4" fill="#fff" />
          </g>
        </>
      )}

      {kind === 'converge' && (
        <>
          <g fill="none" stroke={`url(#${id}-ray)`} strokeLinecap="round">
            <path className="ray p1" pathLength={1} d="M13 18C26 18 30 32 42 32" strokeWidth="4" />
            <path className="ray p2" pathLength={1} d="M13 32H42" strokeWidth="4.5" />
            <path className="ray p3" pathLength={1} d="M13 46C26 46 30 32 42 32" strokeWidth="4" />
          </g>
          <circle className="halo" cx="45" cy="32" r="14" fill={`url(#${id}-glow)`} />
          <circle className="core" cx="45" cy="32" r="7" fill={`url(#${id}-orb)`} />
        </>
      )}

      {kind === 'pair' && (
        <>
          <g className="part p1">
            <rect x="7" y="18" width="20" height="28" rx="4" fill="#fff" />
            <rect x="11" y="24" width="12" height="2.5" rx="1.25" fill="#5b47e0" fillOpacity="0.55" />
            <rect x="11" y="30" width="8" height="2.5" rx="1.25" fill="#5b47e0" fillOpacity="0.35" />
            <rect x="11" y="36" width="10" height="2.5" rx="1.25" fill="#5b47e0" fillOpacity="0.35" />
          </g>
          <g className="part p2">
            <rect x="37" y="18" width="20" height="28" rx="4" fill="#fff" fillOpacity="0.85" />
            <rect x="41" y="24" width="12" height="2.5" rx="1.25" fill="#5b47e0" fillOpacity="0.55" />
            <rect x="41" y="30" width="8" height="2.5" rx="1.25" fill="#5b47e0" fillOpacity="0.35" />
            <rect x="41" y="36" width="10" height="2.5" rx="1.25" fill="#5b47e0" fillOpacity="0.35" />
          </g>
          <g className="core">
            <circle cx="32" cy="32" r="7" fill={`url(#${id}-glow)`} />
            <rect x="27" y="30.75" width="10" height="2.5" rx="1.25" fill="#fff" />
            <circle cx="32" cy="32" r="3" fill="#fff" stroke="#5b47e0" strokeWidth="1.4" />
          </g>
        </>
      )}

      {kind === 'check' && (
        <>
          <g fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="5">
            <path className="ray tick1" pathLength={1} d="M12 33l7.5 7.5L33 27" stroke="#fff" strokeOpacity="0.55" />
            <path className="ray tick2" pathLength={1} d="M24 33l7.5 7.5L50 22" stroke="#fff" />
          </g>
          <g className="core">
            <circle cx="50" cy="22" r="7" fill={`url(#${id}-glow)`} />
          </g>
        </>
      )}

      {kind === 'shield' && (
        <>
          <path
            className="core"
            d="M32 12L48 18V31C48 41.5 41 48.5 32 52C23 48.5 16 41.5 16 31V18Z"
            fill="#fff"
            fillOpacity="0.16"
          />
          <g fill="none" stroke="#fff" strokeLinecap="round" strokeLinejoin="round">
            <path
              className="ray p1"
              pathLength={1}
              d="M32 12L48 18V31C48 41.5 41 48.5 32 52C23 48.5 16 41.5 16 31V18Z"
              strokeWidth="3.5"
            />
            <path className="ray seal" pathLength={1} d="M25 32l5 5 9.5-10" strokeWidth="4" />
          </g>
        </>
      )}

      {kind === 'trail' && (
        <>
          <path className="ray p1" pathLength={1} d="M13 32H51" stroke="#fff" strokeOpacity="0.4" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          <circle className="step s1" cx="14" cy="32" r="3.2" fill="#fff" fillOpacity="0.6" />
          <circle className="step s2" cx="26" cy="32" r="3.2" fill="#fff" fillOpacity="0.7" />
          <circle className="step s3" cx="38" cy="32" r="3.2" fill="#fff" fillOpacity="0.85" />
          <g className="step s4">
            <circle cx="50" cy="32" r="9" fill={`url(#${id}-glow)`} />
            <circle cx="50" cy="32" r="4.2" fill="#fff" />
          </g>
          <rect className="step s1" x="11" y="40" width="6" height="2.5" rx="1.25" fill="#fff" fillOpacity="0.45" />
          <rect className="step s2" x="23" y="40" width="6" height="2.5" rx="1.25" fill="#fff" fillOpacity="0.45" />
          <rect className="step s3" x="35" y="40" width="6" height="2.5" rx="1.25" fill="#fff" fillOpacity="0.45" />
          <rect className="step s4" x="47" y="40" width="6" height="2.5" rx="1.25" fill="#fff" fillOpacity="0.6" />
        </>
      )}

      <rect x="0.5" y="0.5" width="63" height="63" rx="14.5" fill="none" stroke="#fff" strokeOpacity="0.18" />
    </svg>
  )
}

// A loading state for a page, a card or a table. The label says what is being loaded.
export function Loader({ kind = 'overlap', label, size = 56 }: { kind?: LoaderKind; label: string; size?: number }) {
  return (
    <div className="loader" role="status" aria-live="polite">
      <LogoArt kind={kind} size={size} animated />
      <span className="loader-label">{label}</span>
    </div>
  )
}

// The same, as the body of a table that is still loading.
export function LoaderRow({ kind, label, columns }: { kind: LoaderKind; label: string; columns: number }) {
  return (
    <tbody aria-busy="true">
      <tr>
        <td colSpan={columns} className="loader-cell">
          <Loader kind={kind} label={label} />
        </td>
      </tr>
    </tbody>
  )
}
