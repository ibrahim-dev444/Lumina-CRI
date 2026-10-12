import { useEffect, useState, type ReactNode } from 'react'

import { lookupOrganization, ORG_CODE, OrganizationContext, type Organization } from '../organization'
import { Loader } from './Loader'

// Opens an organization's workspace only after the server confirms the code in the address exists and is
// active. Everything inside can read the organization with useOrganization().
export function OrganizationGate({ children }: { children: ReactNode }) {
  const [org, setOrg] = useState<Organization | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!ORG_CODE) return
    // No minimum wait here: the sign-in check right after holds the same loader for its full moment.
    lookupOrganization(ORG_CODE)
      .then((found) => {
        setOrg(found)
        document.title = `Lumina CRI · ${found.name}`
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  if (error) {
    return (
      <main className="login">
        <div className="glass login-card" style={{ borderRadius: 'var(--radius-lg)' }}>
          <h1>Organization not available</h1>
          <p className="muted">{error}</p>
          <a className="btn btn-primary" href="/sign-in">
            Choose another organization
          </a>
        </div>
      </main>
    )
  }

  if (!org) {
    return (
      <main className="splash">
        <Loader label="Opening Lumina" size={72} />
      </main>
    )
  }

  return <OrganizationContext.Provider value={org}>{children}</OrganizationContext.Provider>
}
