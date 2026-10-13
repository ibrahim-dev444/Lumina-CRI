import { useEffect, useState } from 'react'

import { BrandMark } from '../components/BrandMark'
import { Icon, type IconName } from '../components/Icon'
import { LogoArt, type LoaderKind } from '../components/Loader'
import { HeroVisual } from './HeroVisual'
import { useRevealOnScroll } from './useReveal'

const STEPS: { kind: LoaderKind; title: string; text: string }[] = [
  {
    kind: 'orbit',
    title: 'Connect',
    text: 'Read customers and their accounts from core banking, loan systems, mobile apps, CRM, files and APIs: read-only, with your own credentials.',
  },
  {
    kind: 'stack',
    title: 'Clean',
    text: 'Keep an untouched copy of every record, then fix spacing, phone formats, dates and casing.',
  },
  {
    kind: 'pair',
    title: 'Match',
    text: 'Find the records that are the same person using PAN, mobile, email, birth date and name.',
  },
  {
    kind: 'converge',
    title: 'Trust',
    text: 'Build one golden record from the most trusted values and score it from 0 to 100.',
  },
]

const FEATURES: { icon: IconName; title: string; text: string }[] = [
  {
    icon: 'customers',
    title: 'Golden record',
    text: 'One profile per customer with 13 key details, each from the system you trust most, and every source side by side.',
  },
  {
    icon: 'shield',
    title: 'Trust score',
    text: 'A 0 to 100 score that shows how far a record can be relied on, and exactly which details raise or lower it.',
  },
  {
    icon: 'merge',
    title: 'Match review',
    text: 'Clear duplicates are joined automatically. Uncertain pairs wait for a data steward to merge or keep apart.',
  },
  {
    icon: 'approve',
    title: 'Maker-checker changes',
    text: 'Staff propose corrections with evidence; a different person approves them. Nobody approves their own change.',
  },
  {
    icon: 'lock',
    title: 'KYC, AML and consent',
    text: 'Re-KYC due dates by risk, PEP and sanctions flags for compliance only, and consent kept as a full history.',
  },
  {
    icon: 'audit',
    title: 'Audit log',
    text: 'Every sign-in, view, merge, change and revealed number is recorded in a log nobody can edit.',
  },
  {
    icon: 'alert',
    title: 'Before you speak',
    text: 'Ten seconds before a call: open complaints, overdue products, re-KYC and consent, each with what to do.',
  },
  {
    icon: 'file',
    title: 'Every product, one view',
    text: 'Accounts, deposits, loans and cards from every connected system, with totals and overdue warnings.',
  },
  {
    icon: 'edit',
    title: 'Conversation history',
    text: 'Calls, branch visits and messages logged in one place. Complaints stay open until someone closes them.',
  },
]

const SECURITY: { icon: IconName; title: string; text: string }[] = [
  {
    icon: 'connectors',
    title: 'A separate space for every bank',
    text: 'Each organization has its own database schema. One bank can never reach another bank’s customers.',
  },
  {
    icon: 'lock',
    title: 'Identity numbers encrypted',
    text: 'PAN and CKYC are encrypted and masked on screen. Aadhaar and account numbers keep only their last 4 digits.',
  },
  {
    icon: 'customers',
    title: 'Each role sees only its job',
    text: 'Front-line staff never see AML risk or sanctions, so nobody can tip off a customer by mistake.',
  },
  {
    icon: 'audit',
    title: 'Proof for every action',
    text: 'Showing a full number needs a reason. Every action is written to an append-only audit log.',
  },
]

const ROLES = [
  { title: 'Relationship managers', text: 'See the trusted profile and every product a customer holds, and suggest corrections.' },
  { title: 'Contact centre agents', text: 'Read the briefing before speaking, log the call, and record consent with masked details.' },
  { title: 'Data stewards', text: 'Merge duplicates, approve changes and keep every source system in sync.' },
  { title: 'Compliance officers', text: 'Track re-KYC, AML risk, PEP and sanctions, and read the full audit trail.' },
]

const NAV = [
  { href: '#how', label: 'How it works' },
  { href: '#features', label: 'Features' },
  { href: '#security', label: 'Security' },
  { href: '#roles', label: 'Who it’s for' },
]

// Public home page: what Lumina CRI is, shown before anyone signs in.
export function LandingPage() {
  useRevealOnScroll()
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    document.title = 'Lumina CRI · One trusted record for every customer'
    const onScroll = () => setScrolled(window.scrollY > 12)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <div className="lp">
      <header className={`lp-nav${scrolled ? ' is-scrolled' : ''}`}>
        <div className="lp-wrap lp-nav-inner">
          <a href="#top" className="lp-brand" aria-label="Lumina CRI home">
            <BrandMark size={32} />
            <span>Lumina CRI</span>
          </a>
          <nav className="lp-links" aria-label="Sections">
            {NAV.map((n) => (
              <a key={n.href} href={n.href}>
                {n.label}
              </a>
            ))}
          </nav>
          <a className="btn btn-primary lp-nav-cta" href="/sign-in">
            Organization sign-in
          </a>
        </div>
      </header>

      <main id="top">
        <section className="lp-hero">
          <div className="lp-hero-bg" aria-hidden="true">
            <i />
            <i />
            <i />
          </div>
          <div className="lp-wrap lp-hero-grid">
            <div className="lp-hero-copy">
              <span className="lp-eyebrow lp-in" style={{ animationDelay: '0.05s' }}>
                Customer data platform for banks
              </span>
              <h1 className="lp-in" style={{ animationDelay: '0.15s' }}>
                One trusted record for <span className="lp-grad">every customer</span>.
              </h1>
              <p className="lp-lead lp-in" style={{ animationDelay: '0.25s' }}>
                Lumina CRI reads customer data from every system your bank runs, finds the records that belong to the
                same person, and builds one golden record with a score that shows how far it can be trusted.
              </p>
              <div className="lp-cta lp-in" style={{ animationDelay: '0.35s' }}>
                <a className="btn btn-primary lp-btn-lg" href="/sign-in">
                  Organization sign-in
                </a>
                <a className="btn lp-btn-lg" href="#how">
                  See how it works
                </a>
              </div>
              <ul className="lp-proof lp-in" style={{ animationDelay: '0.45s' }}>
                <li>
                  <Icon name="check" size={16} /> Separate data for every bank
                </li>
                <li>
                  <Icon name="check" size={16} /> Encrypted identity numbers
                </li>
                <li>
                  <Icon name="check" size={16} /> Full audit trail
                </li>
              </ul>
            </div>
            <HeroVisual />
          </div>
        </section>

        <section id="how" className="lp-section">
          <div className="lp-wrap">
            <div className="lp-head reveal">
              <span className="lp-eyebrow">How it works</span>
              <h2>From scattered records to one customer, in four steps</h2>
            </div>
            <ol className="lp-steps">
              {STEPS.map((s, i) => (
                <li key={s.title} className="lp-step reveal" style={{ transitionDelay: `${i * 90}ms` }}>
                  <LogoArt kind={s.kind} size={56} animated />
                  <span className="lp-step-n">0{i + 1}</span>
                  <h3>{s.title}</h3>
                  <p>{s.text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="features" className="lp-section lp-alt">
          <div className="lp-wrap">
            <div className="lp-head reveal">
              <span className="lp-eyebrow">Features</span>
              <h2>Everything a bank needs to trust its customer data</h2>
            </div>
            <div className="lp-features">
              {FEATURES.map((f, i) => (
                <article key={f.title} className="lp-feature reveal" style={{ transitionDelay: `${(i % 3) * 90}ms` }}>
                  <span className="lp-icon">
                    <Icon name={f.icon} size={20} />
                  </span>
                  <h3>{f.title}</h3>
                  <p>{f.text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="security" className="lp-section lp-dark">
          <div className="lp-wrap lp-security">
            <div className="lp-head reveal">
              <span className="lp-eyebrow">Built for banks</span>
              <h2>Security and compliance are part of the design, not an add-on</h2>
              <p>
                Customer data is the most sensitive thing a bank holds. Lumina keeps each bank apart, hides what a role
                does not need, and records everything.
              </p>
            </div>
            <div className="lp-sec-grid">
              {SECURITY.map((s, i) => (
                <div key={s.title} className="lp-sec reveal" style={{ transitionDelay: `${i * 90}ms` }}>
                  <span className="lp-icon">
                    <Icon name={s.icon} size={20} />
                  </span>
                  <div>
                    <h3>{s.title}</h3>
                    <p>{s.text}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="roles" className="lp-section">
          <div className="lp-wrap">
            <div className="lp-head reveal">
              <span className="lp-eyebrow">Who it’s for</span>
              <h2>Every team sees exactly what its job needs</h2>
            </div>
            <div className="lp-roles">
              {ROLES.map((r, i) => (
                <div key={r.title} className="lp-role reveal" style={{ transitionDelay: `${i * 90}ms` }}>
                  <h3>{r.title}</h3>
                  <p>{r.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="lp-section">
          <div className="lp-wrap">
            <div className="lp-final reveal">
              <LogoArt kind="overlap" size={64} animated />
              <h2>Already using Lumina?</h2>
              <p>Sign in with the organization code your administrator gave you.</p>
              <a className="btn btn-primary lp-btn-lg" href="/sign-in">
                Organization sign-in
              </a>
            </div>
          </div>
        </section>
      </main>

      <footer className="lp-footer">
        <div className="lp-wrap lp-footer-inner">
          <span className="lp-brand">
            <BrandMark size={24} />
            <span>Lumina CRI</span>
          </span>
          <nav aria-label="Footer">
            {NAV.map((n) => (
              <a key={n.href} href={n.href}>
                {n.label}
              </a>
            ))}
            <a href="/sign-in">Sign in</a>
          </nav>
          <span className="muted text-sm">© 2026 Lumina CRI</span>
        </div>
      </footer>
    </div>
  )
}
