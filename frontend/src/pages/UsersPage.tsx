import { useState, type FormEvent } from 'react'

import { api } from '../api/client'
import type { OrgUser, RoleCode } from '../api/types'
import { useApi } from '../api/useApi'
import { useAuth } from '../auth/AuthContext'
import { formatRelative } from '../format'
import { Icon } from '../components/Icon'
import { LoaderRow } from '../components/Loader'
import { useToast } from '../components/Toasts'
import { Avatar, Card, ErrorAlert, PageHeader, StatusBadge } from '../components/ui'
import { useOrganization } from '../organization'

const ROLES: { value: RoleCode; label: string; hint: string }[] = [
  { value: 'agent', label: 'Contact centre agent', hint: 'Answers calls; sees masked details; records consent' },
  { value: 'relationship_manager', label: 'Relationship manager', hint: 'Full profiles; suggests corrections' },
  { value: 'steward', label: 'Data steward', hint: 'Merges duplicates, approves changes, syncs sources' },
  { value: 'compliance', label: 'Compliance officer', hint: 'KYC, AML, sanctions; reads the audit log' },
  { value: 'admin', label: 'Organization admin', hint: 'Everything, including users and settings' },
]

// The organization administrator's list of staff: add people, change roles, deactivate, reset passwords.
export function UsersPage() {
  const org = useOrganization()
  const { user: me } = useAuth()
  const toast = useToast()
  const { data, error, loading, reload } = useApi(() => api.users(), [])
  const [adding, setAdding] = useState(false)
  // The temporary password is shown once, right after creating or resetting, then never again.
  const [issued, setIssued] = useState<OrgUser | null>(null)

  const act = async (work: () => Promise<OrgUser>, done: string) => {
    try {
      const result = await work()
      if (result.temporary_password) setIssued(result)
      toast('success', done)
      reload()
    } catch (e) {
      toast('error', (e as Error).message)
    }
  }

  const copyIssued = () => {
    navigator.clipboard
      ?.writeText(issued?.temporary_password ?? '')
      .then(() => toast('success', 'Copied.'))
      .catch(() => toast('error', 'Could not copy. Select the password and copy it by hand.'))
  }

  return (
    <>
      <PageHeader
        title="Users and roles"
        description={`Everyone who can sign in to ${org.name}. Each role sees only what its job needs.`}
        actions={
          <button type="button" className="btn btn-primary" onClick={() => setAdding((v) => !v)}>
            <Icon name="customers" size={16} /> {adding ? 'Close' : 'Add user'}
          </button>
        }
      />
      {error && <ErrorAlert message={error} />}

      {issued && (
        <div className="issued" role="status">
          <Icon name="lock" size={18} />
          <div className="issued-text">
            <strong>Temporary password for {issued.username}</strong>
            <span className="text-sm">
              Give it to {issued.name} privately. It is shown only now; they must choose their own at first sign-in.
            </span>
          </div>
          <code className="issued-pw">{issued.temporary_password}</code>
          <button type="button" className="btn btn-sm" onClick={copyIssued}>
            Copy
          </button>
          <button type="button" className="btn btn-ghost btn-icon" title="Hide" onClick={() => setIssued(null)}>
            <Icon name="x" size={16} />
          </button>
        </div>
      )}

      {adding && (
        <AddUserCard
          onAdded={(u) => {
            setIssued(u)
            setAdding(false)
            toast('success', `${u.username} added.`)
            reload()
          }}
        />
      )}

      <Card flush footer={data && <span>{data.length} people</span>}>
        <div className="table-wrap">
          <table className="table customers-table">
            <thead>
              <tr>
                <th>Person</th>
                <th>Role</th>
                <th className="col-sm">Status</th>
                <th className="col-md">Last sign-in</th>
                <th className="right">Actions</th>
              </tr>
            </thead>
            {loading && !data ? (
              <LoaderRow kind="overlap" label="Loading people" columns={5} />
            ) : (
              <tbody>
                {data?.map((u) => {
                  const self = u.username === me?.username
                  return (
                    <tr key={u.id} className={u.is_active ? undefined : 'row-muted'}>
                      <td>
                        <div className="cell-person">
                          <Avatar name={u.name} />
                          <div>
                            <strong>
                              {u.name}
                              {self && <span className="muted"> (you)</span>}
                            </strong>
                            <span className="mono">{u.username}</span>
                          </div>
                        </div>
                      </td>
                      <td>
                        <select
                          className="select select-sm"
                          aria-label={`Role of ${u.username}`}
                          value={u.role ?? ''}
                          disabled={self || !u.is_active}
                          onChange={(e) =>
                            act(
                              () => api.updateUser(u.id, { role: e.target.value as RoleCode }),
                              `${u.username} is now ${ROLES.find((r) => r.value === e.target.value)?.label}.`,
                            )
                          }
                        >
                          {!u.role && <option value="">No role</option>}
                          {ROLES.map((r) => (
                            <option key={r.value} value={r.value}>
                              {r.label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="col-sm">
                        {!u.is_active ? (
                          <StatusBadge tone="neutral">Deactivated</StatusBadge>
                        ) : u.must_change_password ? (
                          <StatusBadge tone="warn">Temporary password</StatusBadge>
                        ) : (
                          <StatusBadge tone="good">Active</StatusBadge>
                        )}
                      </td>
                      <td className="col-md text-sm muted">{u.last_login ? formatRelative(u.last_login) : 'Never'}</td>
                      <td className="right">
                        {!self && (
                          <div className="row" style={{ gap: 6, justifyContent: 'flex-end' }}>
                            {u.is_active && (
                              <button
                                type="button"
                                className="btn btn-sm"
                                onClick={() =>
                                  act(() => api.resetPassword(u.id), `New temporary password for ${u.username}.`)
                                }
                              >
                                Reset password
                              </button>
                            )}
                            <button
                              type="button"
                              className="btn btn-sm"
                              onClick={() =>
                                act(
                                  () => api.updateUser(u.id, { is_active: !u.is_active }),
                                  u.is_active ? `${u.username} can no longer sign in.` : `${u.username} can sign in again.`,
                                )
                              }
                            >
                              {u.is_active ? 'Deactivate' : 'Reactivate'}
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            )}
          </table>
        </div>
      </Card>
    </>
  )
}

function AddUserCard({ onAdded }: { onAdded: (u: OrgUser) => void }) {
  const [username, setUsername] = useState('')
  const [first, setFirst] = useState('')
  const [last, setLast] = useState('')
  const [role, setRole] = useState<RoleCode>('agent')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onAdded(await api.createUser({ username, first_name: first, last_name: last, role }))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Add a user" description="They get a temporary password and choose their own at first sign-in.">
      <form className="form-grid" onSubmit={submit}>
        {error && (
          <div className="wide">
            <ErrorAlert message={error} />
          </div>
        )}
        <div className="form-field">
          <label htmlFor="nu-first">First name</label>
          <input id="nu-first" className="input" value={first} onChange={(e) => setFirst(e.target.value)} />
        </div>
        <div className="form-field">
          <label htmlFor="nu-last">Last name</label>
          <input id="nu-last" className="input" value={last} onChange={(e) => setLast(e.target.value)} />
        </div>
        <div className="form-field">
          <label htmlFor="nu-user">Username</label>
          <input
            id="nu-user"
            className="input"
            placeholder="e.g. priya.s"
            autoCapitalize="none"
            spellCheck={false}
            value={username}
            onChange={(e) => setUsername(e.target.value.toLowerCase())}
          />
        </div>
        <div className="form-field">
          <label htmlFor="nu-role">Role</label>
          <select id="nu-role" className="select" value={role} onChange={(e) => setRole(e.target.value as RoleCode)}>
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
          <span className="text-xs muted">{ROLES.find((r) => r.value === role)?.hint}</span>
        </div>
        <div className="wide row" style={{ justifyContent: 'flex-end' }}>
          <button type="submit" className="btn btn-primary" disabled={busy || !username}>
            {busy ? 'Adding...' : 'Add user'}
          </button>
        </div>
      </form>
    </Card>
  )
}
