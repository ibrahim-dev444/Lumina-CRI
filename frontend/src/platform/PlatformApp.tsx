import { useEffect, useState, type FormEvent } from 'react'
import { BrowserRouter, Navigate, NavLink, Route, Routes } from 'react-router-dom'

import { atLeast, LOADER_MIN_MS } from '../api/useApi'
import { BrandMark } from '../components/BrandMark'
import { Icon } from '../components/Icon'
import { Loader } from '../components/Loader'
import { ToastProvider } from '../components/Toasts'
import { ErrorAlert } from '../components/ui'
import { WakingBanner } from '../components/WakingBanner'
import { ActivityPage } from './ActivityPage'
import { platformApi, type PlatformUser } from './api'
import { OrganizationsPage } from './OrganizationsPage'

// The platform console at /platform: the Lumina team manages organizations here. It has its own sign-in
// (platform logins, not bank logins) and never shows any organization's customers.
export function PlatformApp() {
  const [user, setUser] = useState<PlatformUser | null>(null)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    document.title = 'Lumina CRI · Platform console'
    atLeast(
      platformApi.csrf().then(() => platformApi.me()),
      LOADER_MIN_MS,
    )
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setChecking(false))
  }, [])

  const signOut = async () => {
    try {
      await platformApi.logout()
    } finally {
      setUser(null)
      await platformApi.csrf().catch(() => undefined)
    }
  }

  if (checking) {
    return (
      <main className="splash">
        <WakingBanner />
        <Loader label="Opening the platform console" size={72} />
      </main>
    )
  }

  return (
    <ToastProvider>
      <WakingBanner />
      {!user ? (
        <PlatformSignIn
          onSignedIn={async (u) => {
            setUser(u)
            await platformApi.csrf() // a new CSRF token after signing in
          }}
        />
      ) : (
        <BrowserRouter basename="/platform">
          <div className="pf-shell">
            <header className="pf-bar">
              <div className="pf-bar-inner">
                <a className="lp-brand" href="/platform">
                  <BrandMark size={30} />
                  <span>Lumina CRI</span>
                  <span className="pf-tag">Platform</span>
                </a>
                <nav className="pf-nav" aria-label="Platform">
                  <NavLink to="/" end>
                    Organizations
                  </NavLink>
                  <NavLink to="/activity">Activity</NavLink>
                </nav>
                <span className="pf-user text-sm muted">{user.name}</span>
                <button type="button" className="btn btn-ghost btn-icon" onClick={signOut} title="Sign out">
                  <Icon name="logout" label="Sign out" />
                </button>
              </div>
            </header>
            <main className="pf-main">
              <div className="page">
                <Routes>
                  <Route index element={<OrganizationsPage />} />
                  <Route path="/activity" element={<ActivityPage />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </div>
            </main>
          </div>
        </BrowserRouter>
      )}
    </ToastProvider>
  )
}

function PlatformSignIn({ onSignedIn }: { onSignedIn: (u: PlatformUser) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onSignedIn(await platformApi.login(username, password))
    } catch (err) {
      setError((err as Error).message)
      setBusy(false)
    }
  }

  return (
    <main className="login">
      <div className="orbs" aria-hidden="true">
        <i />
        <i />
        <i />
        <i />
      </div>
      <form className="glass login-card" style={{ borderRadius: 'var(--radius-lg)' }} onSubmit={submit}>
        <div className="brand" style={{ padding: 0 }}>
          <BrandMark size={40} />
          <div>
            <div className="brand-name">Lumina CRI</div>
            <div className="brand-sub">Platform console</div>
          </div>
        </div>
        <div className="stack" style={{ gap: 6 }}>
          <h1>Platform sign-in</h1>
          <p className="muted text-sm">For the Lumina platform team only. Bank staff sign in at their organization.</p>
        </div>
        {error && <ErrorAlert message={error} />}
        <div className="form-field">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            className="input"
            autoComplete="username"
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div className="form-field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            className="input"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <button type="submit" className="btn btn-primary" style={{ height: 40 }} disabled={busy || !username || !password}>
          {busy ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
    </main>
  )
}
