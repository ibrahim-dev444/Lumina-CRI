import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import type { Capability } from './api/types'

import { AuthProvider, useAuth } from './auth/AuthContext'
import { Icon } from './components/Icon'
import { Layout } from './components/Layout'
import { ToastProvider } from './components/Toasts'
import { ApprovalsPage } from './pages/ApprovalsPage'
import { AuditPage } from './pages/AuditPage'
import { ConnectorsPage } from './pages/ConnectorsPage'
import { CustomerDetailPage } from './pages/CustomerDetailPage'
import { CustomersPage } from './pages/CustomersPage'
import { LoginPage } from './pages/LoginPage'
import { OverviewPage } from './pages/OverviewPage'
import { ReviewPage } from './pages/ReviewPage'

function Routed() {
  const { user, checking, logout } = useAuth()
  if (checking) return null
  if (!user) return <LoginPage />
  if (!user.role) {
    return (
      <main className="login">
        <div className="glass login-card" style={{ borderRadius: 'var(--radius-lg)' }}>
          <h1>No role assigned yet</h1>
          <p className="muted">
            You are signed in as <strong>{user.username}</strong>, but your account has no Lumina role. Ask an
            administrator to add you to one of: Relationship manager, Contact centre agent, Data steward, Compliance
            officer.
          </p>
          <button type="button" className="btn" onClick={logout}>
            <Icon name="logout" size={16} /> Sign out
          </button>
        </div>
      </main>
    )
  }
  const can = (c: Capability) => user.capabilities.includes(c)

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<OverviewPage />} />
        <Route path="/customers" element={<CustomersPage />} />
        <Route path="/customers/:id" element={<CustomerDetailPage />} />
        {can('view_matches') && <Route path="/review" element={<ReviewPage />} />}
        {can('view_audit') && <Route path="/audit" element={<AuditPage />} />}
        {(can('approve_corrections') || can('propose_corrections')) && (
          <Route path="/approvals" element={<ApprovalsPage />} />
        )}
        <Route path="/connectors" element={<ConnectorsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routed />
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  )
}
