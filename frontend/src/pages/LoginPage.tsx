import { useState, type FormEvent } from 'react'

import { useAuth } from '../auth/AuthContext'
import { BrandMark } from '../components/BrandMark'
import { Icon } from '../components/Icon'
import { ErrorAlert } from '../components/ui'

export function LoginPage() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(username, password)
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
            <div className="brand-name">Lumina</div>
            <div className="brand-sub">Customer data platform</div>
          </div>
        </div>

        <div className="stack" style={{ gap: 6 }}>
          <h1>Sign in</h1>
          <p className="muted text-sm">Use the account your administrator created for you.</p>
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
          <div className="input-wrap">
            <input
              id="password"
              className="input"
              style={{ paddingLeft: 12, paddingRight: 64 }}
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              type="button"
              className="pw-toggle"
              onClick={() => setShowPassword((v) => !v)}
              aria-pressed={showPassword}
            >
              {showPassword ? 'Hide' : 'Show'}
            </button>
          </div>
        </div>

        <button type="submit" className="btn btn-primary" style={{ height: 40 }} disabled={busy || !username || !password}>
          {busy ? 'Signing in...' : 'Sign in'}
        </button>

        <div className="notice">
          <Icon name="shield" size={16} />
          <span>
            <strong>Authorised bank staff only.</strong> Customer data shown here is confidential. Sign out when you
            leave your desk.
          </span>
        </div>
      </form>
    </main>
  )
}
