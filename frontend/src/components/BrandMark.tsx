// Lumina's logo: three records (lines of different trust) flow into one point of light, the golden record.
// Colours come from the theme tokens, so it follows light and dark mode. public/favicon.svg is the same
// drawing with fixed colours, for the browser tab.
export function BrandMark({ size = 32 }: { size?: number }) {
  return (
    <svg className="brand-mark" width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="var(--accent)" />
      <g fill="none" stroke="var(--on-accent)" strokeWidth="2.4" strokeLinecap="round">
        <path d="M7.5 9.5C13.5 9.5 15.5 16 21 16" strokeOpacity="0.7" />
        <path d="M7.5 16H21" />
        <path d="M7.5 22.5C13.5 22.5 15.5 16 21 16" strokeOpacity="0.45" />
      </g>
      <circle cx="23" cy="16" r="5.5" fill="var(--on-accent)" fillOpacity="0.22" />
      <circle cx="23" cy="16" r="3.2" fill="var(--on-accent)" />
    </svg>
  )
}
