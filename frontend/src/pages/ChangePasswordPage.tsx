import { useState, type FormEvent } from 'react'

import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { BrandMark } from '../components/BrandMark'
import { Icon } from '../components/Icon'
import { OrgLogo } from '../components/OrgLogo'
import { useToast } from '../components/Toasts'
import { Card, ErrorAlert, PageHeader } from '../components/ui'
import { useOrganization } from '../organization'

// Choose your own password. "forced" is the full-screen version shown after an administrator set a
// temporary password: nothing else opens until it is done. The normal version lives under the account menu.
export function ChangePasswordPage({ forced = false }: { forced?: boolean }) {
  const { refresh, logout } = useAuth()
  const org = useOrganization()
  const toast = useToast()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [repeat, setRepeat] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const mismatch = repeat.length > 0 && next !== repeat

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (next !== repeat) return
    setBusy(true)
    setError(null)
    try {
      await api.changePassword(current, next)
      await refresh()
      toast('success', 'Password changed.')
      setCurrent('')
      setNext('')
      setRepeat('')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const form = (
    <form className="stack" style={{ gap: 16 }} onSubmit={submit}>
      {error && <ErrorAlert message={error} />}
      <div className="form-field">
        <label htmlFor="pw-current">{forced ? 'Temporary password' : 'Current password'}</label>
        <input
          id="pw-current"
          className="input"
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
        />
      </div>
      <div className="form-field">
        <label htmlFor="pw-new">New password</label>
        <input
          id="pw-new"
          className="input"
          type="password"
          autoComplete="new-password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
        />
        <span className="text-xs muted">At least 8 characters. Not only numbers, not a common password.</span>
      </div>
      <div className="form-field">
        <label htmlFor="pw-repeat">Type the new password again</label>
        <input
          id="pw-repeat"
          className="input"
          type="password"
          autoComplete="new-password"
          value={repeat}
          onChange={(e) => setRepeat(e.target.value)}
        />
        {mismatch && <span className="text-xs" style={{ color: 'var(--bad-text)' }}>The two passwords differ.</span>}
      </div>
      <button
        type="submit"
        className="btn btn-primary"
        style={{ height: 40 }}
        disabled={busy || !current || !next || next !== repeat}
      >
        {busy ? 'Saving...' : 'Save new password'}
      </button>
    </form>
  )

  if (!forced) {
    return (
      <>
        <PageHeader title="Change password" description="Choose a password only you know." />
        <div style={{ maxWidth: 480 }}>
          <Card>{form}</Card>
        </div>
      </>
    )
  }

  return (
    <main className="login">
      <div className="glass login-card" style={{ borderRadius: 'var(--radius-lg)' }}>
        <div className="brand" style={{ padding: 0 }}>
          <BrandMark size={40} />
          <div>
            <div className="brand-name">Lumina CRI</div>
            <div className="brand-sub">Customer data platform</div>
          </div>
        </div>
        <div className="org-signin">
          <OrgLogo org={org} size={36} />
          <div>
            <span className="text-xs muted">Signed in to</span>
            <strong>{org.name}</strong>
          </div>
        </div>
        <div className="stack" style={{ gap: 6 }}>
          <h1>Choose your password</h1>
          <p className="muted text-sm">
            Your administrator gave you a temporary password. Replace it with one only you know before you continue.
          </p>
        </div>
        {form}
        <button type="button" className="btn btn-ghost" onClick={logout}>
          <Icon name="logout" size={16} /> Sign out
        </button>
      </div>
    </main>
  )
}
