// Shapes of the JSON our Django API returns. Keep in sync with backend/api/serializers.py.
// Decimals (trust, trust_score) arrive as strings like "0.85" so no precision is lost.

export type Field =
  | 'name'
  | 'father_name'
  | 'dob'
  | 'gender'
  | 'pan'
  | 'aadhaar'
  | 'ckyc'
  | 'mobile'
  | 'email'
  | 'address'
  | 'perm_address'
  | 'occupation'
  | 'income'
export type Band = 'high' | 'medium' | 'low'

export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export type Capability =
  | 'view_pii'
  | 'manage_sources'
  | 'view_matches'
  | 'decide_matches'
  | 'propose_corrections'
  | 'approve_corrections'
  | 'reveal_identity'
  | 'view_compliance'
  | 'record_consent'
  | 'export'
  | 'view_audit'

export interface User {
  username: string
  name: string
  is_staff: boolean
  role: string | null
  role_label: string
  capabilities: Capability[]
}

export interface AuditEvent {
  id: number
  at: string
  actor_name: string
  role: string
  action: string
  action_label: string
  target: string
  detail: Record<string, unknown>
  ip: string | null
}

export interface Source {
  code: string
  name: string
  category: string
  trust: string
  enabled: boolean
  last_synced_at: string | null
  record_count: number
}

export interface SyncResult {
  fetched: number
  created: number
  updated: number
  customers: number
  new_suggestions: number
}

export interface CustomerSummary {
  id: number
  code: string
  name: string
  trust_score: string | null
  band: Band
  record_count: number
  sources: string[]
  conflict_fields: number
  kyc_status: 'verified' | 'due_soon' | 'overdue' | 'no_record'
  needs_review: number
  score_updated_at: string | null
}

export interface GoldenField {
  field: Field
  value: string
  trust: string
  conflicts: number
  source_code: string
  source_name: string
  source_record_id: number | null
  last_updated: string | null
  // Set when the value comes from an approved correction instead of a source system.
  correction: { id: number; evidence_ref: string; proposed_by: string; approved_by: string } | null
}

export interface FieldCorrection {
  id: number
  customer: { id: number; code: string; name: string }
  field: Field
  value: string
  previous_value: string
  evidence_ref: string
  reason: string
  status: 'pending' | 'approved' | 'rejected'
  proposed_by_name: string
  proposed_at: string
  decided_by_name: string
  decided_at: string | null
  decision_note: string
  mine: boolean // the signed-in user proposed it, so they cannot approve it
}

export interface SourceRecord {
  id: number
  source_code: string
  source_name: string
  source_trust: string
  source_enabled: boolean
  source_record_id: string
  name: string
  father_name: string
  dob: string | null
  gender: string
  pan: string // always masked, e.g. XXXXX1234X
  aadhaar: string // always masked, e.g. XXXX XXXX 4521
  ckyc: string // always masked
  mobile: string
  email: string
  address: string
  perm_address: string
  occupation: string
  income: string
  source_updated_at: string | null
  match_reason: string
  // Per field: true = agrees with the golden record, false = differs, null = not held. Worked out by
  // the server, because masked or encrypted values cannot be compared in the browser.
  agreement?: Partial<Record<Field, boolean | null>>
}

export interface CustomerDetail extends CustomerSummary {
  golden: GoldenField[]
  records: SourceRecord[]
  weights: Partial<Record<Field, string>>
  masked: boolean // mobile, email and date of birth were hidden for this user's role
  corrections: FieldCorrection[]
  compliance: {
    kyc_status: 'verified' | 'due_soon' | 'overdue' | 'no_record'
    re_kyc_due: string | null
    has_pan: boolean
    consents: {
      purpose: string
      label: string
      status: 'granted' | 'revoked' | 'pending' | 'unknown'
      channel: string
      recorded_by: string
      recorded_at: string | null
    }[]
    // Only for compliance roles; null for everyone else
    aml: {
      risk: 'low' | 'medium' | 'high'
      risk_reason: string
      last_kyc: string
      pep: boolean
      pep_note: string
      sanctions: 'clear' | 'potential_match'
      sanctions_checked: string | null
    } | null
  }
}

export interface ComplianceQueue {
  summary: {
    customers: number
    overdue: number
    due_soon: number
    verified: number
    no_record: number
    high_risk: number
    medium_risk: number
    low_risk: number
    pep: number
    sanctions_review: number
  }
  results: {
    id: number
    code: string
    name: string
    trust_score: string | null
    kyc_status: string
    re_kyc_due: string | null
    last_kyc: string | null
    risk: 'low' | 'medium' | 'high' | null
    risk_reason: string
    pep: boolean
    sanctions: 'clear' | 'potential_match' | null
  }[]
}

export interface Overview {
  customers: number
  source_records: number
  average_trust: string
  bands: Record<Band, number>
  histogram: { from: number; to: number; count: number }[]
  pending_reviews: number
  pending_corrections: number
  last_synced_at: string | null
  sources: Source[]
  lowest_trust: CustomerSummary[]
  scores: { id: number; code: string; name: string; score: string }[]
  conflicts_by_field: { field: Field; customers: number }[]
  source_agreement: { code: string; name: string; trust: string; held: number; matched: number }[]
}

export interface Reference {
  roles: { role: string; label: string; capabilities: Capability[] }[]
  weights: Partial<Record<Field, string>>
  sources: { code: string; name: string; trust: string; enabled: boolean }[]
  matching: {
    points_pan: number
    points_mobile: number
    points_email: number
    points_dob: number
    points_name_max: number
    match_threshold: number
    review_threshold: number
    min_name_similarity: number
  }
  bands: { medium: string; high: string }
  correction_trust: string
}

export interface MatchSuggestion {
  id: number
  points: number
  reason: string
  status: 'pending' | 'accepted' | 'rejected'
  created_at: string
  decided_at: string | null
  record_a: SourceRecord
  record_b: SourceRecord
  customer_a: { id: number; code: string } | null
  customer_b: { id: number; code: string } | null
}
