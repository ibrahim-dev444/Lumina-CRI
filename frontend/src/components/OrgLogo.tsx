import type { Organization } from '../organization'

// The organization's own logo, shown as a small badge inside Lumina. Lumina keeps its own look everywhere;
// this badge is the only place a bank's identity appears. Without an uploaded logo it shows the
// organization's initials ("AX" for Axis Bank) on its colour.
export function OrgLogo({ org, size = 32 }: { org: Organization; size?: number }) {
  if (org.logo) {
    return (
      <img
        className="org-logo"
        src={org.logo}
        alt={`${org.name} logo`}
        width={size}
        height={size}
        style={{ width: size, height: size }}
      />
    )
  }
  const initials = org.name.replace(/[^A-Za-z ]/g, '').slice(0, 2).toUpperCase()
  return (
    <span
      className="org-logo org-initials"
      role="img"
      aria-label={`${org.name} logo`}
      style={{ width: size, height: size, fontSize: size * 0.38, background: org.brand_color || 'var(--accent)' }}
    >
      {initials}
    </span>
  )
}
