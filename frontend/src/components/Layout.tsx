import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'

import { api } from '../api/client'
import type { Capability, Source } from '../api/types'
import { formatRelative } from '../format'
import { applyTheme, getTheme, type Theme } from '../theme'
import { useAuth } from '../auth/AuthContext'
import { Icon, type IconName } from './Icon'
import { Avatar } from './ui'

type NavItem = { to: string; label: string; icon: IconName; end?: boolean; needs?: Capability[] }

const GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: 'Workspace',
    items: [
      { to: '/', label: 'Overview', icon: 'overview', end: true },
      { to: '/customers', label: 'Customers', icon: 'customers' },
      { to: '/review', label: 'Match review', icon: 'merge', needs: ['view_matches'] },
      {
        to: '/approvals',
        label: 'Approvals',
        icon: 'approve',
        needs: ['approve_corrections', 'propose_corrections'],
      },
    ],
  },
  {
    label: 'Data',
    items: [{ to: '/connectors', label: 'Connectors', icon: 'connectors' }],
  },
  {
    label: 'Governance',
    items: [{ to: '/audit', label: 'Audit log', icon: 'audit', needs: ['view_audit'] }],
  },
  {
    label: 'Help',
    items: [{ to: '/how-it-works', label: 'How it works', icon: 'info' }],
  },
]

const PAGE_TITLES = [
  { path: '/', title: 'Overview', exact: true },
  { path: '/customers', title: 'Customers' },
  { path: '/review', title: 'Match review' },
  { path: '/connectors', title: 'Connectors' },
  { path: '/audit', title: 'Audit log' },
  { path: '/approvals', title: 'Approvals' },
  { path: '/how-it-works', title: 'How it works' },
]

export function Layout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const [pending, setPending] = useState<number | null>(null)
  const [pendingCorrections, setPendingCorrections] = useState<number | null>(null)
  const [sources, setSources] = useState<Source[] | null>(null)
  const [theme, setTheme] = useState<Theme>(getTheme)

  const toggleTheme = () => {
    const next = theme === 'light' ? 'dark' : 'light'
    applyTheme(next)
    setTheme(next)
  }

  // Refresh the "Match review" count whenever the user moves between pages.
  const canSeeMatches = !!user?.capabilities.includes('view_matches')
  const canApprove = !!user?.capabilities.includes('approve_corrections')
  useEffect(() => {
    if (canApprove) {
      api
        .corrections({ status: 'pending' })
        .then((page) => setPendingCorrections(page.count))
        .catch(() => setPendingCorrections(null))
    }
    if (canSeeMatches) {
      api
        .suggestions('pending')
        .then((page) => setPending(page.count))
        .catch(() => setPending(null))
    }
    api
      .sources()
      .then((page) => setSources(page.results))
      .catch(() => setSources(null))
  }, [location.pathname, canSeeMatches, canApprove])

  const page = PAGE_TITLES.find((p) => (p.exact ? location.pathname === p.path : location.pathname.startsWith(p.path)))
  const off = sources?.filter((s) => !s.enabled).length ?? 0
  const lastSync = sources
    ?.map((s) => s.last_synced_at)
    .filter(Boolean)
    .sort()
    .at(-1)

  return (
    <div className="shell">
      <aside className="sidebar" aria-label="Main navigation">
        <Link to="/" className="brand" title="Go to Overview">
          <span className="brand-mark" aria-hidden="true">
            L
          </span>
          <div className="rail-text">
            <div className="brand-name">Lumina</div>
            <div className="brand-sub">Customer data platform</div>
          </div>
        </Link>

        {GROUPS.map((group) => ({ ...group, items: group.items.filter((i) => !i.needs || i.needs.some((c) => user?.capabilities.includes(c))) }))
          .filter((group) => group.items.length > 0)
          .map((group) => (
          <nav key={group.label} className="nav-group" aria-label={group.label}>
            <div className="nav-label">
              <span className="rail-text">{group.label}</span>
            </div>
            {group.items.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className="nav-link">
                <Icon name={item.icon} />
                <span className="rail-text">{item.label}</span>
                {item.to === '/review' && pending ? <span className="nav-count">{pending}</span> : null}
                {item.to === '/approvals' && pendingCorrections ? (
                  <span className="nav-count">{pendingCorrections}</span>
                ) : null}
              </NavLink>
            ))}
          </nav>
        ))}

        <div className="sidebar-foot">
          <Avatar name={user?.name ?? ''} />
          <div className="sidebar-user rail-text">
            <strong>{user?.name}</strong>
            <span>{user?.role_label}</span>
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-icon theme-toggle"
            onClick={toggleTheme}
            title={theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme'}
          >
            <Icon name={theme === 'light' ? 'moon' : 'sun'} label={theme === 'light' ? 'Dark theme' : 'Light theme'} />
          </button>
          <button type="button" className="btn btn-ghost btn-icon" onClick={logout} title="Sign out">
            <Icon name="logout" label="Sign out" />
          </button>
        </div>
      </aside>

      <main className="content">
        <header className="topbar glass">
          <div className="topbar-path">
            <Link to="/" className="topbar-home">
              Lumina
            </Link>
            <Icon name="chevronRight" size={14} />
            <strong>{page?.title ?? 'Workspace'}</strong>
          </div>
          {sources && (
            <span className="pill" title="Status of the bank systems Lumina reads from">
              <span className={`badge-dot ${off ? 'warn' : 'live'}`} />
              {off
                ? `${off} source${off > 1 ? 's' : ''} disconnected`
                : `All ${sources.length} sources connected · synced ${formatRelative(lastSync ?? null).toLowerCase()}`}
            </span>
          )}
        </header>
        <div className="content-inner">
          <div className="page">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  )
}
