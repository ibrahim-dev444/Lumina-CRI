import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/tokens.css'
import './styles/base.css'
import './styles/components.css'
import './styles/landing.css'
import App from './App.tsx'
import { LandingPage } from './landing/LandingPage'
import { ORG_CODE } from './organization'
import { OrganizationSignInPage } from './pages/OrganizationSignInPage'
import { PlatformApp } from './platform/PlatformApp'
import { applyTheme, getTheme } from './theme'

applyTheme(getTheme())

const PUBLIC_PATH = window.location.pathname.replace(/\/+$/, '') || '/'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* /t/<org>/... is an organization's workspace; /platform is the platform team's console; /sign-in asks
        for the organization code; anything else is the public landing page. */}
    {ORG_CODE ? (
      <App />
    ) : PUBLIC_PATH === '/platform' || PUBLIC_PATH.startsWith('/platform/') ? (
      <PlatformApp />
    ) : PUBLIC_PATH === '/sign-in' ? (
      <OrganizationSignInPage />
    ) : (
      <LandingPage />
    )}
  </StrictMode>,
)
