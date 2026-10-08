import type { Band, Field } from './api/types'

export const FIELDS: Field[] = ['name', 'mobile', 'email', 'address', 'dob']

export const FIELD_LABELS: Record<Field, string> = {
  name: 'Name',
  mobile: 'Mobile',
  email: 'Email',
  address: 'Address',
  dob: 'Date of birth',
}

export const BAND_LABELS: Record<Band, string> = { high: 'High', medium: 'Medium', low: 'Low' }
export const BAND_CLASS: Record<Band, 'good' | 'warn' | 'bad'> = { high: 'good', medium: 'warn', low: 'bad' }

const SOURCE_LABELS: Record<string, string> = {
  flexcube: 'FLEXCUBE',
  salesforce: 'Salesforce',
  branch_csv: 'Branch upload',
}

// Identity hue (1 to 5, see styles/tokens.css) per source and per field. Fixed: an entity never changes colour.
const SOURCE_HUES: Record<string, number> = { flexcube: 1, salesforce: 4, branch_csv: 3 }
export const FIELD_HUES: Record<Field, number> = { name: 1, mobile: 2, email: 3, address: 4, dob: 5 }

export function sourceHue(code: string): string {
  return `hue-${SOURCE_HUES[code] ?? 1}`
}

// A stable pastel for a person's avatar, picked from their name so it is the same on every screen.
export function nameHue(name: string): string {
  let sum = 0
  for (const ch of name) sum = (sum * 31 + ch.charCodeAt(0)) % 997
  return `hue-${(sum % 5) + 1}`
}

// Trust tiers for sources (not customers): core systems, staff-entered CRMs, manual files.
export function sourceTier(trust: number): { tone: 'good' | 'warn' | 'bad'; label: string } {
  if (trust >= 0.8) return { tone: 'good', label: 'High' }
  if (trust >= 0.5) return { tone: 'warn', label: 'Medium' }
  return { tone: 'bad', label: 'Low' }
}

export function sourceLabel(code: string): string {
  return SOURCE_LABELS[code] ?? code
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

export function formatDate(value: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  // A masked date such as "1984-••-••" is not a real date: show it as it came.
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function formatDateTime(value: string | null): string {
  if (!value) return 'Never'
  return new Date(value).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

// "3 min ago", "2 h ago", "4 Oct". Used where recency matters more than the exact time.
export function formatRelative(value: string | null): string {
  if (!value) return 'Never'
  const minutes = Math.round((Date.now() - new Date(value).getTime()) / 60000)
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  return formatDate(value)
}

export function formatScore(value: string | null): string {
  return value === null ? '-' : Number(value).toFixed(2)
}

export function formatFieldValue(field: Field, value: string | null): string {
  if (!value) return ''
  return field === 'dob' ? formatDate(value) : value
}
