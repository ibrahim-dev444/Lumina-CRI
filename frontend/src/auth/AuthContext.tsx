import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

import { api } from '../api/client'
import type { Capability, User } from '../api/types'

interface AuthState {
  user: User | null
  checking: boolean // true while we ask Django whether we are already logged in
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    // Get the CSRF cookie first, then see if a login session already exists.
    api
      .csrf()
      .then(() => api.me())
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setChecking(false))
  }, [])

  const login = async (username: string, password: string) => {
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

  return <AuthContext.Provider value={{ user, checking, login, logout }}>{children}</AuthContext.Provider>
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
