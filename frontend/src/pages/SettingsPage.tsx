import { useRef, useState, type ChangeEvent } from 'react'

import { api } from '../api/client'
import type { Field, TrustSettings } from '../api/types'
import { useApi } from '../api/useApi'
import { Icon } from '../components/Icon'
import { Loader } from '../components/Loader'
import { OrgLogo } from '../components/OrgLogo'
import { useToast } from '../components/Toasts'
import { Card, ErrorAlert, PageHeader } from '../components/ui'
import { FIELD_LABELS } from '../format'
import { useOrganization } from '../organization'

const MAX_LOGO_BYTES = 256 * 1024
const LOGO_TYPES = ['image/png', 'image/jpeg', 'image/webp']

// The organization administrator's settings: the bank's logo, how much it trusts each source system, and
// how many points each field adds to the trust score. Saving trust settings recalculates every customer.
export function SettingsPage() {
  const org = useOrganization()
  return (
    <>
      <PageHeader
        title="Organization settings"
        description={`Settings for ${org.name} only. Other organizations are not affected.`}
      />
      <LogoCard />
      <TrustCard />
    </>
  )
}

function LogoCard() {
  const org = useOrganization()
  const toast = useToast()
  const input = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)

  const save = async (logo: string, done: string) => {
    setBusy(true)
    try {
      await api.saveLogo(logo)
      toast('success', done)
      // The logo appears across the app; a reload shows it everywhere at once.
      window.setTimeout(() => window.location.reload(), 700)
    } catch (e) {
      toast('error', (e as Error).message)
      setBusy(false)
    }
  }

  const pick = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (!LOGO_TYPES.includes(file.type)) {
      toast('error', 'Choose a PNG, JPEG or WebP image.')
      return
    }
    if (file.size > MAX_LOGO_BYTES) {
      toast('error', 'The logo must be 256 KB or smaller.')
      return
    }
    const reader = new FileReader()
    reader.onload = () => save(String(reader.result), 'Logo saved.')
    reader.readAsDataURL(file)
  }

  return (
    <Card
      title="Logo"
      description="Shown on your sign-in page and in the top bar. Lumina keeps its own look everywhere else."
    >
      <div className="logo-setting">
        <OrgLogo org={org} size={64} />
        <div className="stack" style={{ gap: 4 }}>
          <strong>{org.logo ? 'Your logo' : 'Initials badge (no logo yet)'}</strong>
          <span className="text-sm muted">PNG, JPEG or WebP, square works best, up to 256 KB.</span>
        </div>
        <div className="row" style={{ gap: 8, marginLeft: 'auto' }}>
          <input ref={input} type="file" accept={LOGO_TYPES.join(',')} hidden onChange={pick} />
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => input.current?.click()}>
            {org.logo ? 'Replace' : 'Upload logo'}
          </button>
          {org.logo && (
            <button type="button" className="btn" disabled={busy} onClick={() => save('', 'Logo removed.')}>
              Remove
            </button>
          )}
        </div>
      </div>
    </Card>
  )
}

function TrustCard() {
  const toast = useToast()
  const { data, error, loading } = useApi(() => api.trustSettings(), [])
  // Unsaved edits; until the first edit the page shows the saved settings.
  const [edits, setDraft] = useState<TrustSettings | null>(null)
  const [busy, setBusy] = useState(false)
  const draft = edits ?? data

  if (error) return <ErrorAlert message={error} />
  if (loading || !draft || !data) {
    return (
      <div className="card">
        <Loader kind="converge" label="Loading trust settings" />
      </div>
    )
  }

  const total = draft.weights.reduce((sum, w) => sum + w.points, 0)
  const changed = JSON.stringify(draft) !== JSON.stringify(data)

  const setTrust = (code: string, value: number) =>
    setDraft({ ...draft, sources: draft.sources.map((s) => (s.code === code ? { ...s, trust: value } : s)) })
  const setPoints = (field: string, value: number) =>
    setDraft({ ...draft, weights: draft.weights.map((w) => (w.field === field ? { ...w, points: value } : w)) })

  const save = async () => {
    setBusy(true)
    try {
      const saved = await api.saveTrustSettings({
        sources: Object.fromEntries(draft.sources.map((s) => [s.code, s.trust])),
        weights: Object.fromEntries(draft.weights.map((w) => [w.field, w.points])),
      })
      setDraft(saved)
      toast('success', 'Saved. Every customer’s golden record and trust score has been recalculated.')
      window.setTimeout(() => window.location.reload(), 900)
    } catch (e) {
      toast('error', (e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card
      title="Trust score"
      description="How much you trust each system, and how many points each detail adds. Saving recalculates every customer."
      footer={
        <>
          <span className={total === 100 ? 'text-sm muted' : 'text-sm'} style={total === 100 ? undefined : { color: 'var(--bad-text)' }}>
            Field points: <strong className="num">{total}</strong> of 100
            {total !== 100 && ` (${total > 100 ? 'remove' : 'add'} ${Math.abs(100 - total)})`}
          </span>
          <div className="row" style={{ gap: 8 }}>
            <button type="button" className="btn" disabled={!changed || busy} onClick={() => setDraft(null)}>
              Undo changes
            </button>
            <button type="button" className="btn btn-primary" disabled={!changed || busy || total !== 100} onClick={save}>
              <Icon name="check" size={16} /> {busy ? 'Recalculating...' : 'Save and recalculate'}
            </button>
          </div>
        </>
      }
    >
      <div className="settings-grid">
        <section>
          <h3 className="settings-title">Source trust</h3>
          <p className="text-sm muted">The system with the highest trust wins each detail. 0 = never trusted, 100 = fully.</p>
          {draft.sources.map((s) => (
            <label key={s.code} className="slider-row">
              <span>
                <strong>{s.name}</strong>
                <span className="text-xs muted">{s.category}</span>
              </span>
              <input
                type="range"
                min={0}
                max={100}
                value={s.trust}
                onChange={(e) => setTrust(s.code, Number(e.target.value))}
                aria-label={`Trust for ${s.name}`}
              />
              <span className="num slider-value">{s.trust}</span>
            </label>
          ))}
        </section>
        <section>
          <h3 className="settings-title">Field points</h3>
          <p className="text-sm muted">How much each detail counts. All points together must make 100.</p>
          <div className="points-grid">
            {draft.weights.map((w) => (
              <label key={w.field} className="points-row">
                <span>{FIELD_LABELS[w.field as Field] ?? w.label}</span>
                <input
                  className="input input-sm num"
                  type="number"
                  min={0}
                  max={100}
                  step={1}
                  value={w.points}
                  onChange={(e) => setPoints(w.field, Math.max(0, Math.min(100, Math.round(Number(e.target.value) || 0))))}
                  aria-label={`Points for ${FIELD_LABELS[w.field as Field] ?? w.label}`}
                />
              </label>
            ))}
          </div>
        </section>
      </div>
    </Card>
  )
}
