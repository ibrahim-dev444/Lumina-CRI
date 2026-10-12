import { useState, type FormEvent } from 'react'

import { useApi } from '../api/useApi'
import { formatRelative } from '../format'
import { Icon } from '../components/Icon'
import { Loader } from '../components/Loader'
import { OrgLogo } from '../components/OrgLogo'
import { useToast } from '../components/Toasts'
import { Card, ErrorAlert, PageHeader, StatusBadge } from '../components/ui'
import { platformApi, type PlatformOrganization } from './api'

// Every organization as a health card: counts and dates only, never a customer's name or details.
export function OrganizationsPage() {
  const toast = useToast()
  const { data, error, loading, reload } = useApi(() => platformApi.organizations(), [])
  const [adding, setAdding] = useState(false)
  const [created, setCreated] = useState<PlatformOrganization | null>(null)

  const totals = data && {
    orgs: data.length,
    active: data.filter((o) => o.status === 'active').length,
    users: data.reduce((n, o) => n + o.health.users, 0),
    customers: data.reduce((n, o) => n + o.health.customers, 0),
  }

  return (
    <>
      <PageHeader
        title="Organizations"
        description="Every bank on Lumina. You see how each one is doing, never its customers."
        actions={
          <button type="button" className="btn btn-primary" onClick={() => setAdding((v) => !v)}>
            <Icon name="connectors" size={16} /> {adding ? 'Close' : 'Add organization'}
          </button>
        }
      />
      {error && <ErrorAlert message={error} />}

      {totals && (
        <div className="kpis">
          <Total label="Organizations" value={totals.orgs} note={`${totals.active} active`} />
          <Total label="People with access" value={totals.users} note="active logins, all banks" />
          <Total label="Customers managed" value={totals.customers} note="golden records, all banks" />
        </div>
      )}

      {created && (
        <div className="issued" role="status">
          <Icon name="lock" size={18} />
          <div className="issued-text">
            <strong>
              {created.name} is ready. First admin: {created.admin_username}
            </strong>
            <span className="text-sm">
              Give this temporary password to their administrator privately. It is shown only now; they choose their
              own at first sign-in at /t/{created.code}/.
            </span>
          </div>
          <code className="issued-pw">{created.temporary_password}</code>
          <button type="button" className="btn btn-ghost btn-icon" title="Hide" onClick={() => setCreated(null)}>
            <Icon name="x" size={16} />
          </button>
        </div>
      )}

      {adding && (
        <AddOrganizationCard
          onCreated={(org) => {
            setCreated(org)
            setAdding(false)
            toast('success', `${org.name} added.`)
            reload()
          }}
        />
      )}

      {loading && !data ? (
        <div className="card">
          <Loader kind="orbit" label="Checking every organization" />
        </div>
      ) : (
        <div className="pf-orgs">
          {data?.map((org) => <OrganizationCard key={org.code} org={org} onChanged={reload} />)}
        </div>
      )}
    </>
  )
}

function Total({ label, value, note }: { label: string; value: number; note: string }) {
  return (
    <div className="card kpi">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
      <span className="text-sm muted">{note}</span>
    </div>
  )
}

function OrganizationCard({ org, onChanged }: { org: PlatformOrganization; onChanged: () => void }) {
  const toast = useToast()
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(org.name)
  const [colour, setColour] = useState(org.brand_color || '#5b47e0')
  const [busy, setBusy] = useState(false)
  const h = org.health
  const suspended = org.status === 'suspended'

  const change = async (body: Partial<Pick<PlatformOrganization, 'name' | 'brand_color' | 'status'>>, done: string) => {
    setBusy(true)
    try {
      await platformApi.updateOrganization(org.code, body)
      toast('success', done)
      setEditing(false)
      onChanged()
    } catch (e) {
      toast('error', (e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const toggleStatus = () => {
    const next = suspended ? 'active' : 'suspended'
    const question = suspended
      ? `Resume ${org.name}? Its staff can sign in again.`
      : `Suspend ${org.name}? Everyone at ${org.name} is signed out of Lumina until you resume it.`
    if (window.confirm(question)) {
      change({ status: next }, suspended ? `${org.name} resumed.` : `${org.name} suspended.`)
    }
  }

  return (
    <article className={`card pf-org${suspended ? ' is-suspended' : ''}`}>
      <header className="pf-org-head">
        <OrgLogo org={org} size={44} />
        <div className="pf-org-title">
          <strong>{org.name}</strong>
          <span className="mono text-sm muted">/t/{org.code}/</span>
        </div>
        <StatusBadge tone={suspended ? 'bad' : 'good'}>{suspended ? 'Suspended' : 'Active'}</StatusBadge>
      </header>

      <dl className="pf-stats">
        <div>
          <dt>Users</dt>
          <dd>
            {h.users} <span className="muted text-sm">({h.admins} admin{h.admins === 1 ? '' : 's'})</span>
          </dd>
        </div>
        <div>
          <dt>Customers</dt>
          <dd>{h.customers}</dd>
        </div>
        <div>
          <dt>Sources live</dt>
          <dd>
            {h.sources_enabled} <span className="muted text-sm">of {h.sources_total}</span>
          </dd>
        </div>
        <div>
          <dt>Waiting review</dt>
          <dd>{h.pending_reviews}</dd>
        </div>
        <div>
          <dt>Last sync</dt>
          <dd className="text-sm">{h.last_sync ? formatRelative(h.last_sync) : 'Never'}</dd>
        </div>
        <div>
          <dt>Last activity</dt>
          <dd className="text-sm">{h.last_activity ? formatRelative(h.last_activity) : 'None yet'}</dd>
        </div>
      </dl>

      {editing ? (
        <form
          className="pf-edit"
          onSubmit={(e) => {
            e.preventDefault()
            change({ name, brand_color: colour }, 'Saved.')
          }}
        >
          <input className="input" aria-label="Organization name" value={name} onChange={(e) => setName(e.target.value)} />
          <input
            className="pf-colour"
            type="color"
            aria-label="Badge colour"
            value={colour}
            onChange={(e) => setColour(e.target.value)}
          />
          <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>
            Save
          </button>
          <button type="button" className="btn btn-sm" onClick={() => setEditing(false)}>
            Cancel
          </button>
        </form>
      ) : (
        <footer className="pf-org-actions">
          <a className="btn btn-sm" href={`/t/${org.code}/`} target="_blank" rel="noreferrer">
            Sign-in page
          </a>
          <button type="button" className="btn btn-sm" onClick={() => setEditing(true)}>
            Edit
          </button>
          <button type="button" className={`btn btn-sm${suspended ? ' btn-primary' : ''}`} disabled={busy} onClick={toggleStatus}>
            {suspended ? 'Resume' : 'Suspend'}
          </button>
        </footer>
      )}
    </article>
  )
}

function AddOrganizationCard({ onCreated }: { onCreated: (org: PlatformOrganization) => void }) {
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [colour, setColour] = useState('#5b47e0')
  const [adminUser, setAdminUser] = useState('')
  const [adminFirst, setAdminFirst] = useState('')
  const [adminLast, setAdminLast] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onCreated(
        await platformApi.createOrganization({
          code,
          name,
          brand_color: colour,
          admin_username: adminUser,
          admin_first_name: adminFirst,
          admin_last_name: adminLast,
        }),
      )
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card
      title="Add an organization"
      description="Lumina creates its own separate data space and its first administrator. This takes a few seconds."
    >
      <form className="form-grid" onSubmit={submit}>
        {error && (
          <div className="wide">
            <ErrorAlert message={error} />
          </div>
        )}
        <div className="form-field">
          <label htmlFor="org-name">Organization name</label>
          <input id="org-name" className="input" placeholder="e.g. ICICI Bank" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="form-field">
          <label htmlFor="org-code-new">Code (what staff type to sign in)</label>
          <input
            id="org-code-new"
            className="input"
            placeholder="e.g. icici"
            autoCapitalize="none"
            spellCheck={false}
            value={code}
            onChange={(e) => setCode(e.target.value.toLowerCase().replace(/[^a-z0-9]/g, ''))}
          />
          <span className="text-xs muted">Their address will be /t/{code || 'code'}/. It cannot be changed later.</span>
        </div>
        <div className="form-field">
          <label htmlFor="org-colour">Badge colour</label>
          <input id="org-colour" className="pf-colour" type="color" value={colour} onChange={(e) => setColour(e.target.value)} />
        </div>
        <div className="form-field">
          <label htmlFor="org-admin">First admin username</label>
          <input
            id="org-admin"
            className="input"
            placeholder="e.g. icici.admin"
            autoCapitalize="none"
            spellCheck={false}
            value={adminUser}
            onChange={(e) => setAdminUser(e.target.value.toLowerCase())}
          />
        </div>
        <div className="form-field">
          <label htmlFor="org-admin-first">Admin first name</label>
          <input id="org-admin-first" className="input" value={adminFirst} onChange={(e) => setAdminFirst(e.target.value)} />
        </div>
        <div className="form-field">
          <label htmlFor="org-admin-last">Admin last name</label>
          <input id="org-admin-last" className="input" value={adminLast} onChange={(e) => setAdminLast(e.target.value)} />
        </div>
        <div className="wide row" style={{ justifyContent: 'flex-end' }}>
          <button type="submit" className="btn btn-primary" disabled={busy || !name || !code || !adminUser}>
            {busy ? 'Creating its space...' : 'Add organization'}
          </button>
        </div>
      </form>
    </Card>
  )
}
