// One place that talks to the backend. Every page calls the functions at the bottom, never fetch() directly.

import type {
  AuditEvent,
  ComplianceQueue,
  CustomerDetail,
  CustomerSummary,
  Field,
  FieldCorrection,
  MatchSuggestion,
  Overview,
  Page,
  Reference,
  Source,
  SyncResult,
  User,
} from './types'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// The hosted demo's free server sleeps after 15 minutes without visitors. While it starts again (up to a
// minute) every request gets 502, 503 or 504, or no answer at all. Wait and retry instead of failing, and tell
// the screen so it can say what is happening.
const WAKING_STATUSES = [502, 503, 504]
const WAKING_LIMIT_MS = 90_000
const WAKING_RETRY_MS = 5_000

let waking = false
const wakingListeners = new Set<() => void>()

function setWaking(value: boolean) {
  if (value === waking) return
  waking = value
  wakingListeners.forEach((listener) => listener())
}

export const serverWaking = {
  get: () => waking,
  subscribe: (listener: () => void) => {
    wakingListeners.add(listener)
    return () => {
      wakingListeners.delete(listener)
    }
  },
}

async function fetchWhileWaking(url: string, init: RequestInit): Promise<Response> {
  const started = Date.now()
  for (;;) {
    let response: Response | null = null
    try {
      response = await fetch(url, init)
    } catch {
      response = null // no answer at all
    }
    if (response && !WAKING_STATUSES.includes(response.status)) {
      setWaking(false)
      return response
    }
    if (Date.now() - started > WAKING_LIMIT_MS) {
      setWaking(false)
      if (response) return response
      throw new ApiError(0, 'The server did not answer. Please try again in a minute.')
    }
    setWaking(true)
    await new Promise((resolve) => setTimeout(resolve, WAKING_RETRY_MS))
  }
}

// Django rejects POST/PATCH without the CSRF token it put in the csrftoken cookie.
function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetchWhileWaking(`/api${path}`, {
    method,
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(method !== 'GET' ? { 'X-CSRFToken': csrfToken() } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (response.status === 204) return undefined as T
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new ApiError(response.status, data.detail ?? `Request failed (${response.status})`)
  }
  return data as T
}

const get = <T>(path: string) => request<T>('GET', path)
const post = <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {})
const patch = <T>(path: string, body: unknown) => request<T>('PATCH', path, body)

function query(params: Record<string, string | undefined>): string {
  const clean = Object.entries(params).filter(([, v]) => v) as [string, string][]
  return clean.length ? `?${new URLSearchParams(clean)}` : ''
}

export const api = {
  // Login
  csrf: () => get<{ detail: string }>('/auth/csrf/'),
  login: (username: string, password: string) => post<User>('/auth/login/', { username, password }),
  logout: () => post<void>('/auth/logout/'),
  me: () => get<User>('/auth/me/'),

  overview: () => get<Overview>('/overview/'),
  reference: () => get<Reference>('/reference/'),

  // Connectors
  sources: () => get<Page<Source>>('/sources/'),
  updateSource: (code: string, changes: Partial<Pick<Source, 'enabled' | 'trust'>>) =>
    patch<Source>(`/sources/${code}/`, changes),
  syncSource: (code: string) => post<SyncResult>(`/sources/${code}/sync/`),

  // Customers
  customers: (params: { search?: string; ordering?: string; band?: string; page?: string }) =>
    get<Page<CustomerSummary>>(`/customers/${query(params)}`),
  customer: (id: number) => get<CustomerDetail>(`/customers/${id}/`),

  // Full PAN or CKYC number, with an audited reason (compliance officers and admins)
  reveal: (customerId: number, field: 'pan' | 'ckyc', reason: string) =>
    post<{ field: 'pan' | 'ckyc'; value: string }>(`/customers/${customerId}/reveal/`, { field, reason }),

  // Compliance
  compliance: (params: { status?: string; risk?: string }) => get<ComplianceQueue>(`/compliance/${query(params)}`),
  recordConsent: (customerId: number, body: { purpose: string; status: string; channel: string; note: string }) =>
    post<{ purpose: string; status: string }>(`/customers/${customerId}/consent/`, body),

  // Corrections (maker-checker)
  proposeCorrection: (customerId: number, body: { field: Field; value: string; evidence_ref: string; reason: string }) =>
    post<FieldCorrection>(`/customers/${customerId}/corrections/`, body),
  corrections: (params: { status?: string; customer?: string; page?: string }) =>
    get<Page<FieldCorrection>>(`/corrections/${query(params)}`),
  approveCorrection: (id: number) => post<FieldCorrection>(`/corrections/${id}/approve/`),
  rejectCorrection: (id: number, note: string) => post<FieldCorrection>(`/corrections/${id}/reject/`, { note }),

  // Audit log
  audit: (params: { action?: string; search?: string; page?: string }) =>
    get<Page<AuditEvent>>(`/audit/${query(params)}`),

  // CSV download: the server builds the file (and writes the audit entry).
  exportCustomers: async (): Promise<Blob> => {
    const response = await fetchWhileWaking('/api/customers/export/', { credentials: 'same-origin' })
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new ApiError(response.status, data.detail ?? `Export failed (${response.status})`)
    }
    return response.blob()
  },

  // Match review
  suggestions: (status?: string) => get<Page<MatchSuggestion>>(`/suggestions/${query({ status })}`),
  acceptSuggestion: (id: number) => post<MatchSuggestion>(`/suggestions/${id}/accept/`),
  rejectSuggestion: (id: number) => post<MatchSuggestion>(`/suggestions/${id}/reject/`),
}
