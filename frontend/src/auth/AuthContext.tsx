import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

import { api, SIGNED_OUT_EVENT } from '../api/client'
import { atLeast, LOADER_MIN_MS } from '../api/useApi'
import type { Capability, User } from '../api/types'

interface AuthState {
  user: User | null
  checking: boolean // true while we ask Django whether we are already logged in
  endedQuietly: boolean // the session ended by itself (idle for 30 minutes)
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void> // reload the signed-in user (e.g. after changing the password)
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [checking, setChecking] = useState(true)
  const [endedQuietly, setEndedQuietly] = useState(false)

  // The server ends a session after 30 minutes without activity. The next request then fails, and the app
  // goes back to the sign-in page with a short explanation.
  useEffect(() => {
    const ended = () => {
      setUser((current) => {
        if (current) setEndedQuietly(true)
        return null
      })
      api.csrf().catch(() => undefined)
    }
    window.addEventListener(SIGNED_OUT_EVENT, ended)
    return () => window.removeEventListener(SIGNED_OUT_EVENT, ended)
  }, [])

  useEffect(() => {
    // Get the CSRF cookie first, then see if a login session already exists.
    // The opening splash stays for one full logo formation, like every first load.
    atLeast(
      api.csrf().then(() => api.me()),
      LOADER_MIN_MS,
    )
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setChecking(false))
  }, [])

  const login = async (username: string, password: string) => {
    setEndedQuietly(false)
    setUser(await api.login(username, password))
    await api.csrf() // Django gives a new CSRF token after login
  }

  const logout = async () => {
    try {
      await api.logout()
    } finally {
      // Leave the screen even if the server call failed, so nobody is stuck signed in on this device.
      setUser(null)
      await api.csrf().catch(() => undefined)
    }
  }

  const refresh = async () => setUser(await api.me())

  return <AuthContext.Provider value={{ user, checking, endedQuietly, login, logout, refresh }}>{children}</AuthContext.Provider>
}

// True if the signed-in user's role allows this. Only hides controls; the API enforces the same rule.
// eslint-disable-next-line react-refresh/only-export-components
export function useCan(capability: Capability): boolean {
  const { user } = useAuth()
  return !!user?.capabilities.includes(capability)
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const state = useContext(AuthContext)
  if (!state) throw new Error('useAuth must be used inside <AuthProvider>')
  return state
}
