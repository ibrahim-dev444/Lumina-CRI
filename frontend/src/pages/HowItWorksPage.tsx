import type { ReactNode } from 'react'

import { api } from '../api/client'
import type { Capability, Field } from '../api/types'
import { useApi } from '../api/useApi'
import { Icon, type IconName } from '../components/Icon'
import { Loader } from '../components/Loader'
import { Card, ErrorAlert, PageHeader, Skeleton } from '../components/ui'
import { FIELD_LABELS, FIELDS, formatScore } from '../format'

// "How Lumina works": a guide for new team members and staff. Numbers on this page (weights, trust,
// matching points, permissions) come from /api/reference/, so they always match the running system.

const CAPABILITY_LABELS: { key: Capability; label: string }[] = [
  { key: 'view_pii', label: 'See full mobile, email, date of birth' },
  { key: 'propose_corrections', label: 'Propose a correction' },
  { key: 'approve_corrections', label: "Approve someone else's correction" },
  { key: 'view_matches', label: 'See possible duplicates' },
  { key: 'decide_matches', label: 'Merge or keep apart duplicates' },
  { key: 'manage_sources', label: 'Sync or switch sources' },
  { key: 'export', label: 'Export customer list' },
  { key: 'record_consent', label: 'Record customer consent' },
  { key: 'view_compliance', label: 'See AML risk, PEP and sanctions' },
  { key: 'reveal_identity', label: 'Reveal full PAN or CKYC (with reason)' },
  { key: 'view_audit', label: 'Read the audit log' },
]

export function HowItWorksPage() {
  const { data, error } = useApi(() => api.reference(), [])

  return (
    <>
      <PageHeader title="How Lumina works" description="A guide to what Lumina does, step by step." />
      {error && <ErrorAlert message={error} />}

      <Section n={1} title="The problem Lumina solves">
        <p className="lead">
          A bank keeps the same customer in several systems, and they disagree. Lumina reads them all, decides which
          records are the same person, and keeps one trusted record per customer.
        </p>
        <div className="hiw-problem">
          <div className="hiw-sources">
            <SourceBox name="FLEXCUBE" note="Suresh Kumar · 9822104521" />
            <SourceBox name="Salesforce" note="Sooresh Kumar · 9822107788" />
            <SourceBox name="Branch upload" note="Suresh K · 9822107788" />
          </div>
          <Arrow />
          <div className="hiw-node accent">
            <strong>Lumina</strong>
            <span>collect · clean · match · decide</span>
          </div>
          <Arrow />
          <div className="hiw-node">
            <strong>Golden record</strong>
            <span>Suresh Kumar · 9822104521</span>
            <span className="hiw-score">Trust 85 · High</span>
          </div>
        </div>
      </Section>

      <Section n={2} title="What happens to the data">
        <ol className="hiw-steps">
          <Step icon="connectors" title="Collect" text="A connector reads each bank system. Lumina only reads." />
          <Step icon="file" title="Keep the raw copy" text="Each row is stored exactly as received, as proof." />
          <Step icon="check" title="Clean" text="+91 98221 04521 becomes 9822104521." />
          <Step icon="merge" title="Match" text="Records that belong to the same person are grouped." />
          <Step icon="shield" title="Decide" text="For each field, the most trusted source wins." />
          <Step icon="overview" title="Score" text="A trust score from 0 to 100 says how reliable the record is." />
        </ol>
        <p className="muted text-sm">
          Steps 1 to 6 run when someone clicks <strong>Sync</strong> on Connectors, or a developer runs{' '}
          <code>manage.py sync</code>.
        </p>
      </Section>

      <Section n={3} title="How records are matched">
        {data ? (
          <div className="hiw-two">
            <div>
              <p className="lead">Two records are only compared if they share a PAN, mobile, email or birth date. Then they earn points:</p>
              <table className="table hiw-table">
                <tbody>
                  <tr>
                    <td>Same PAN (compared by fingerprint, never decrypted)</td>
                    <td className="right mono">+{data.matching.points_pan}</td>
                  </tr>
                  <tr>
                    <td>Same mobile</td>
                    <td className="right mono">+{data.matching.points_mobile}</td>
                  </tr>
                  <tr>
                    <td>Same email</td>
                    <td className="right mono">+{data.matching.points_email}</td>
                  </tr>
                  <tr>
                    <td>Same date of birth</td>
                    <td className="right mono">+{data.matching.points_dob}</td>
                  </tr>
                  <tr>
                    <td>Similar name (scaled by similarity)</td>
                    <td className="right mono">up to +{data.matching.points_name_max}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="hiw-outcomes">
              <Outcome tone="good" title={`${data.matching.match_threshold} points or more`} text="Same person. Merged automatically." />
              <Outcome
                tone="warn"
                title={`${data.matching.review_threshold} to ${data.matching.match_threshold - 1} points`}
                text="Probably the same person. A data steward decides in Match review."
              />
              <Outcome tone="bad" title="Two different PANs" text="Never matched: a PAN belongs to one person." />
              <Outcome
                tone="bad"
                title={`Names under ${data.matching.min_name_similarity}% alike`}
                text="Never matched, whatever else agrees. Family members often share a phone or surname."
              />
            </div>
          </div>
        ) : (
          <Loader label="Loading the rules" />
        )}
      </Section>

      <Section n={4} title="How the trust score is calculated">
        {data ? (
          <TrustExample weights={data.weights} sources={data.sources} correctionTrust={data.correction_trust} />
        ) : (
          <Skeleton height={220} />
        )}
      </Section>

      <Section n={5} title="What happens when you open a customer">
        <ol className="hiw-vflow">
          <VStep title="You click a customer" text="The React app asks the server: GET /api/customers/7/" />
          <VStep title="Who are you?" text="Django checks you are signed in and have a role. If not, it refuses (403)." />
          <VStep title="Read the database" text="The golden record and every source record come from PostgreSQL." />
          <VStep
            title="Hide what your role must not see"
            text="A contact centre agent gets 98xxxx4521. The full number never leaves the server."
          />
          <VStep title="Write the audit log" text="Who opened which customer, when, and whether data was hidden." />
          <VStep title="Show the profile" text="The server sends JSON back and the page draws it." />
        </ol>
      </Section>

      <Section n={6} title="Who can do what">
        {data ? (
          <div className="table-wrap">
            <table className="table hiw-matrix">
              <thead>
                <tr>
                  <th>Permission</th>
                  {data.roles.map((r) => (
                    <th key={r.role} className="center">
                      {r.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {CAPABILITY_LABELS.map((c) => (
                  <tr key={c.key}>
                    <td>{c.label}</td>
                    {data.roles.map((r) => (
                      <td key={r.role} className="center">
                        {r.capabilities.includes(c.key) ? (
                          <Icon name="check" size={16} className="yes" label="Yes" />
                        ) : (
                          <Icon name="minus" size={16} className="no" label="No" />
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Skeleton height={260} />
        )}
        <p className="muted text-sm">
          Every role can open Overview, Customers and Connectors. The server enforces these rules; the screens only hide
          buttons you could not use.
        </p>
      </Section>

      <Section n={7} title="Fixing wrong data: two people, every time">
        <ol className="hiw-steps">
          <Step icon="edit" title="Propose" text="Someone enters the right value, an evidence reference and a reason." />
          <Step icon="approve" title="Check" text="A different person approves or rejects it. Nobody approves their own." />
          <Step icon="shield" title="Apply" text={`Approved values win at trust ${formatScore(data?.correction_trust ?? '1')} and the score is recalculated.`} />
          <Step icon="audit" title="Record" text="Proposal and decision are written to the audit log." />
        </ol>
      </Section>

      <Section n={8} title="Words used in Lumina">
        <dl className="hiw-glossary">
          <Term word="Source" meaning="A bank system Lumina reads from, such as FLEXCUBE or Salesforce." />
          <Term word="Source trust" meaning="How much a source is believed, from 0 to 100. Set by the bank." />
          <Term word="Golden record" meaning="The single best value for each field of a customer." />
          <Term word="Trust score" meaning="How reliable a customer's golden record is, from 0 to 100." />
          <Term word="Match review" meaning="Pairs of records that are probably the same person, waiting for a decision." />
          <Term word="Correction" meaning="A fix backed by evidence, applied only after a second person approves it." />
          <Term word="Masking" meaning="Hiding part of a value, like 98xxxx4521, from roles that do not need it." />
          <Term word="Audit log" meaning="The permanent list of who did what and when." />
        </dl>
      </Section>
    </>
  )
}

function Section({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <Card
      title={
        <span className="row" style={{ gap: 10 }}>
          <span className="hiw-n">{n}</span>
          {title}
        </span>
      }
    >
      <div className="stack" style={{ gap: 16 }}>
        {children}
      </div>
    </Card>
  )
}

function SourceBox({ name, note }: { name: string; note: string }) {
  return (
    <div className="hiw-node">
      <strong>{name}</strong>
      <span>{note}</span>
    </div>
  )
}

function Arrow() {
  return (
    <span className="hiw-arrow" aria-hidden="true">
      <Icon name="chevronRight" size={20} />
    </span>
  )
}

function Step({ icon, title, text }: { icon: IconName; title: string; text: string }) {
  return (
    <li className="hiw-step">
      <span className="hiw-step-icon">
        <Icon name={icon} size={18} />
      </span>
      <strong>{title}</strong>
      <span>{text}</span>
    </li>
  )
}

function VStep({ title, text }: { title: string; text: string }) {
  return (
    <li>
      <strong>{title}</strong>
      <span>{text}</span>
    </li>
  )
}

function Outcome({ tone, title, text }: { tone: 'good' | 'warn' | 'bad'; title: string; text: string }) {
  return (
    <div className={`hiw-outcome ${tone}`}>
      <strong>{title}</strong>
      <span>{text}</span>
    </div>
  )
}

function Term({ word, meaning }: { word: string; meaning: string }) {
  return (
    <div>
      <dt>{word}</dt>
      <dd>{meaning}</dd>
    </div>
  )
}

// A worked example using the live weights: every field supplied by the most trusted source.
function TrustExample({
  weights,
  sources,
  correctionTrust,
}: {
  weights: Partial<Record<Field, string>>
  sources: { code: string; name: string; trust: string }[]
  correctionTrust: string
}) {
  const best = sources[0]
  const rows = FIELDS.map((f) => {
    const w = Number(weights[f] ?? 0)
    return { f, w, adds: w * Number(best?.trust ?? 0) }
  })
  const total = rows.reduce((s, r) => s + r.adds, 0)

  return (
    <div className="hiw-two">
      <div className="stack" style={{ gap: 12 }}>
        <p className="lead">
          Each source has a trust level. For each field, the value from the most trusted source wins; on a tie, the
          newest value wins. An approved correction counts as trust {formatScore(correctionTrust)}.
        </p>
        <table className="table hiw-table">
          <thead>
            <tr>
              <th>Source</th>
              <th className="right">Trust</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((s) => (
              <tr key={s.code}>
                <td>{s.name}</td>
                <td className="right mono">{formatScore(s.trust)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="stack" style={{ gap: 12 }}>
        <p className="lead">
          Each field is worth some points (its weight). It earns that share of points matching its source's trust.
          Example: every field comes from{' '}
          {best?.name}:
        </p>
        <table className="table hiw-table">
          <thead>
            <tr>
              <th>Field</th>
              <th className="right">Worth</th>
              <th className="right">× Trust</th>
              <th className="right">Points</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.f}>
                <td>{FIELD_LABELS[r.f]}</td>
                <td className="right mono">{Math.round(r.w * 100)}</td>
                <td className="right mono">{best ? formatScore(best.trust) : '-'}%</td>
                <td className="right mono">{(r.adds * 100).toFixed(1)}</td>
              </tr>
            ))}
            <tr className="hiw-total">
              <td colSpan={3}>Trust score</td>
              <td className="right mono">{Math.round(total * 100)}</td>
            </tr>
          </tbody>
        </table>
        <p className="muted text-sm">Below 60 is Low, 60 to 79 is Medium, 80 and above is High.</p>
      </div>
    </div>
  )
}
