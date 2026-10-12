import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/tokens.css'
import './styles/base.css'
import './styles/components.css'
import App from './App.tsx'
import { ORG_CODE } from './organization'
import { OrganizationSignInPage } from './pages/OrganizationSignInPage'
import { applyTheme, getTheme } from './theme'

applyTheme(getTheme())

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* /t/<org>/... is an organization's workspace; anything else is the public entry. */}
    {ORG_CODE ? <App /> : <OrganizationSignInPage />}
  </StrictMode>,
)
