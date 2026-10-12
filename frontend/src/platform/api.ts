import { request } from '../api/client'

// The platform console's API: /api/platform/... in the shared space, for platform administrators only.

export interface PlatformUser {
  username: string
  name: string
}

export interface OrganizationHealth {
  users: number
  admins: number
  customers: number
  source_records: number
  sources_enabled: number
  sources_total: number
  last_sync: string | null
  pending_reviews: number
  last_activity: string | null
}

export interface PlatformOrganization {
  code: string
  name: string
  status: 'active' | 'suspended'
  brand_color: string
  logo: string
  created_at: string
  health: OrganizationHealth
  admin_username?: string // only when just created
  temporary_password?: string // only when just created, shown once
}

export interface PlatformEvent {
  id: number
  at: string
  actor: string
  action: string
  target: string
  detail: Record<string, unknown>
}

export const platformApi = {
  csrf: () => request<{ detail: string }>('GET', '/platform/auth/csrf/'),
  login: (username: string, password: string) =>
    request<PlatformUser>('POST', '/platform/auth/login/', { username, password }),
  logout: () => request<void>('POST', '/platform/auth/logout/', {}),
  me: () => request<PlatformUser>('GET', '/platform/auth/me/'),
  organizations: () => request<PlatformOrganization[]>('GET', '/platform/organizations/'),
  createOrganization: (body: {
    code: string
    name: string
    brand_color: string
    admin_username: string
    admin_first_name: string
    admin_last_name: string
  }) => request<PlatformOrganization>('POST', '/platform/organizations/', body),
  updateOrganization: (code: string, body: Partial<Pick<PlatformOrganization, 'name' | 'brand_color' | 'status'>>) =>
    request<PlatformOrganization>('PATCH', `/platform/organizations/${code}/`, body),
  events: () => request<PlatformEvent[]>('GET', '/platform/events/'),
}
