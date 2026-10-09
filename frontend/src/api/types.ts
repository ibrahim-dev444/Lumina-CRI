// Shapes of the JSON our Django API returns. Keep in sync with backend/api/serializers.py.
// Decimals (trust, trust_score) arrive as strings like "0.85" so no precision is lost.

export type Field = 'name' | 'mobile' | 'email' | 'address' | 'dob'
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
  mobile: string
  email: string
  address: string
  dob: string | null
  source_updated_at: string | null
  match_reason: string
}

export interface CustomerDetail extends CustomerSummary {
  golden: GoldenField[]
  records: SourceRecord[]
  weights: Partial<Record<Field, string>>
  masked: boolean // mobile, email and date of birth were hidden for this user's role
  corrections: FieldCorrection[]
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
}

export interface Reference {
  roles: { role: string; label: string; capabilities: Capability[] }[]
  weights: Partial<Record<Field, string>>
  sources: { code: string; name: string; trust: string; enabled: boolean }[]
  matching: {
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
