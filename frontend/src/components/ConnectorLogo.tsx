import { BRAND_MARKS } from '../brandMarks'
import { Icon, type IconName } from './Icon'

// Brands whose owners do not allow their mark in icon sets get a lettered tile in their colour instead.
const LETTERED: Record<string, { letters: string; hex: string; title: string }> = {
  salesforce: { letters: 'SF', hex: '#0B5CAB', title: 'Salesforce' },
  servicenow: { letters: 'SN', hex: '#1F6F5C', title: 'ServiceNow' },
}

// Lumina's own connectors and the built-in demo sources keep a plain icon.
const GENERIC: Record<string, IconName> = {
  rest_api: 'cloud',
  push_api: 'cloud',
  file_upload: 'file',
  demo_core_banking: 'connectors',
  demo_salesforce: 'cloud',
  demo_branch_files: 'file',
}

// The logo of the system a connector reads from: its brand mark, a lettered tile, or a generic icon.
export function ConnectorLogo({ type, size = 40 }: { type: string; size?: number }) {
  const mark = BRAND_MARKS[type]
  const lettered = LETTERED[type]
  const style = { width: size, height: size }
  if (mark) {
    return (
      <span className="connector-logo" style={style}>
        <svg viewBox="0 0 24 24" width={size * 0.66} height={size * 0.66} role="img" aria-label={mark.title}>
          <path d={mark.path} fill={mark.hex} />
        </svg>
      </span>
    )
  }
  if (lettered) {
    return (
      <span
        className="connector-logo is-lettered"
        style={{ ...style, background: lettered.hex, fontSize: size * 0.34 }}
        role="img"
        aria-label={lettered.title}
      >
        {lettered.letters}
      </span>
    )
  }
  return (
    <span className="connector-logo is-generic" style={style}>
      <Icon name={GENERIC[type] ?? 'connectors'} size={size / 2} />
    </span>
  )
}
