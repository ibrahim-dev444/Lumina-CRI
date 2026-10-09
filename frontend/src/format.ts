import type { Band, Field } from './api/types'

export const FIELDS: Field[] = [
  'name',
  'father_name',
  'dob',
  'gender',
  'pan',
  'aadhaar',
  'ckyc',
  'mobile',
  'email',
  'address',
  'perm_address',
  'occupation',
  'income',
]

export const FIELD_LABELS: Record<Field, string> = {
  name: 'Full name',
  father_name: "Father's name",
  dob: 'Date of birth',
  gender: 'Gender',
  pan: 'PAN',
  aadhaar: 'Aadhaar',
  ckyc: 'CKYC number',
  mobile: 'Mobile',
  email: 'Email',
  address: 'Current address',
  perm_address: 'Permanent address',
  occupation: 'Occupation',
  income: 'Annual income',
}

// Short labels for narrow table headers
export const FIELD_SHORT: Record<Field, string> = {
  name: 'Name',
  father_name: 'Father',
  dob: 'Birth',
  gender: 'Gender',
  pan: 'PAN',
  aadhaar: 'Aadhaar',
  ckyc: 'CKYC',
  mobile: 'Mobile',
  email: 'Email',
  address: 'Address',
  perm_address: 'Perm. addr.',
  occupation: 'Job',
  income: 'Income',
}

// Identity numbers and phone numbers read best in the monospaced font
export const MONO_FIELDS = new Set<Field>(['pan', 'aadhaar', 'ckyc', 'mobile'])

export const BAND_LABELS: Record<Band, string> = { high: 'High', medium: 'Medium', low: 'Low' }
export const BAND_CLASS: Record<Band, 'good' | 'warn' | 'bad'> = { high: 'good', medium: 'warn', low: 'bad' }

const SOURCE_LABELS: Record<string, string> = {
  flexcube: 'FLEXCUBE',
  salesforce: 'Salesforce',
  branch_csv: 'Branch upload',
}

// Identity hue (1 to 5, see styles/tokens.css) per source and per field. Fixed: an entity never changes colour.
const SOURCE_HUES: Record<string, number> = { flexcube: 1, salesforce: 4, branch_csv: 3 }


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

// Scores and trust are stored from 0 to 1 and shown from 0 to 100: 0.85 is shown as 85.
export function formatScore(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '-'
  return String(Math.round(Number(value) * 100))
}

export function formatFieldValue(field: Field, value: string | null): string {
  if (!value) return ''
  return field === 'dob' ? formatDate(value) : value
}
