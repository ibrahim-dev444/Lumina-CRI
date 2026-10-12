import { useState, type FormEvent } from 'react'

import { BrandMark } from '../components/BrandMark'
import { Icon } from '../components/Icon'
import { ErrorAlert } from '../components/ui'
import { lookupOrganization } from '../organization'

// Public entry: people type their organization's code (no list of organizations is ever shown), then go to
// that organization's own sign-in page at /t/<code>/.
export function OrganizationSignInPage() {
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const org = await lookupOrganization(code)
      window.location.assign(`/t/${org.code}/`)
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
            <div className="brand-sub">Customer data platform</div>
          </div>
        </div>

        <div className="stack" style={{ gap: 6 }}>
          <h1>Organization sign-in</h1>
          <p className="muted text-sm">Enter your organization code. Your administrator can tell you what it is.</p>
        </div>

        {error && <ErrorAlert message={error} />}

        <div className="form-field">
          <label htmlFor="org-code">Organization code</label>
          <input
            id="org-code"
            className="input"
            placeholder="e.g. axis"
            autoComplete="organization"
            autoCapitalize="none"
            spellCheck={false}
            autoFocus
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        </div>

        <button type="submit" className="btn btn-primary" style={{ height: 40 }} disabled={busy || !code.trim()}>
          {busy ? 'Checking...' : 'Continue'}
        </button>

        <div className="notice">
          <Icon name="shield" size={16} />
          <span>
            <strong>Each organization is separate.</strong> You only ever see your own organization's data.
          </span>
        </div>
      </form>
    </main>
  )
}
