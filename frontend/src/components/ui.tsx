// Small presentational pieces used across pages.

import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import type { Band } from '../api/types'
import { BAND_CLASS, BAND_LABELS, formatScore, initials, nameHue, sourceHue, sourceLabel } from '../format'
import { Icon, type IconName } from './Icon'

export function PageHeader({
  title,
  description,
  crumbs,
  actions,
}: {
  title: ReactNode
  description?: ReactNode
  crumbs?: { label: string; to?: string }[]
  actions?: ReactNode
}) {
  return (
    <header className="page-header">
      <div className="page-header-text">
        {crumbs && (
          <nav className="breadcrumb" aria-label="Breadcrumb">
            {crumbs.map((c, i) => (
              <span key={c.label} className="row" style={{ gap: 6 }}>
                {i > 0 && <Icon name="chevronRight" size={14} />}
                {c.to ? <Link to={c.to}>{c.label}</Link> : <span aria-current="page">{c.label}</span>}
              </span>
            ))}
          </nav>
        )}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="row">{actions}</div>}
    </header>
  )
}

export function Card({
  title,
  description,
  actions,
  footer,
  children,
  flush = false,
  glass = false,
  className = '',
}: {
  title?: ReactNode
  description?: ReactNode
  actions?: ReactNode
  footer?: ReactNode
  children: ReactNode
  flush?: boolean // no padding: for tables and lists that run edge to edge
  glass?: boolean // frosted look, for panels with little text (charts, summaries)
  className?: string
}) {
  return (
    <section className={`card${glass ? ' glass' : ''} ${className}`}>
      {title && (
        <div className="card-header">
          <div className="stack">
            <h2>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          {actions}
        </div>
      )}
      {flush ? children : <div className="card-body">{children}</div>}
      {footer && <div className="card-footer">{footer}</div>}
    </section>
  )
}

export function BandBadge({ band }: { band: Band }) {
  return (
    <span className={`badge ${BAND_CLASS[band]}`}>
      <span className="badge-dot" />
      {BAND_LABELS[band]}
    </span>
  )
}

export function StatusBadge({ tone, children }: { tone: 'good' | 'warn' | 'bad' | 'neutral'; children: ReactNode }) {
  return (
    <span className={`badge ${tone}`}>
      <span className="badge-dot" />
      {children}
    </span>
  )
}

export function TrustCell({ score, band }: { score: string | null; band: Band }) {
  return (
    <span className="trust-dot">
      <i style={{ background: `var(--band-${band})` }} aria-hidden="true" />
      <span className="mono">{formatScore(score)}</span>
      <span className="band-word">{BAND_LABELS[band]}</span>
    </span>
  )
}

export function Avatar({ name, large = false }: { name: string; large?: boolean }) {
  return (
    <span className={`avatar ${nameHue(name)}${large ? ' lg' : ''}`} aria-hidden="true">
      {initials(name)}
    </span>
  )
}

export function SourceChips({ codes }: { codes: string[] }) {
  return (
    <span className="chips">
      {codes.map((c) => (
        <span key={c} className={`chip hued ${sourceHue(c)}`}>
          {sourceLabel(c)}
        </span>
      ))}
    </span>
  )
}

export function EmptyState({ icon, title, children }: { icon: IconName; title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Icon name={icon} size={20} />
      </span>
      <strong>{title}</strong>
      {children && <span className="text-sm">{children}</span>}
    </div>
  )
}

export function ErrorAlert({ message }: { message: string }) {
  return (
    <div className="alert" role="alert">
      <Icon name="alert" size={18} />
      <span>{message}</span>
    </div>
  )
}

export function Skeleton({ width = '100%', height = 12 }: { width?: string | number; height?: number }) {
  return <span className="skeleton" style={{ width, height }} />
}
