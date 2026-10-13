import { useRef, useState, type ChangeEvent } from 'react'
import { useParams } from 'react-router-dom'

import { api } from '../api/client'
import type { AccountField, AccountsMapping, ConnectorMapping, ConnectorType, Field, Source } from '../api/types'
import { useApi } from '../api/useApi'
import { useCan } from '../auth/AuthContext'
import { ConnectorFields } from '../components/ConnectorFields'
import { Icon } from '../components/Icon'
import { Loader, LoaderRow } from '../components/Loader'
import { useToast } from '../components/Toasts'
import { Card, ErrorAlert, PageHeader, StatusBadge } from '../components/ui'
import { FIELD_LABELS, FIELDS, formatDateTime } from '../format'

// Guesses which column feeds which Lumina field from its name ("MOB_NO" -> Mobile). Only a suggestion:
// the administrator confirms every choice before saving.
const GUESS: Record<Field | 'id' | 'updated', { has: string[]; not?: string[] }> = {
  name: { has: ['fullname', 'custname', 'customername', 'name'], not: ['father', 'first', 'last', 'user', 'file', 'branch'] },
  father_name: { has: ['father'] },
  dob: { has: ['dob', 'birth'] },
  gender: { has: ['gender', 'sex'] },
  pan: { has: ['pan'], not: ['company', 'span'] },
  aadhaar: { has: ['aadhaar', 'aadhar', 'uid'] },
  ckyc: { has: ['ckyc'] },
  mobile: { has: ['mobile', 'mob', 'phone', 'cell'] },
  email: { has: ['email', 'mail'] },
  address: { has: ['address', 'addr'], not: ['perm', 'email', 'mail'] },
  perm_address: { has: ['permaddr', 'permanent', 'perm'] },
  occupation: { has: ['occupation', 'job', 'title', 'profession'] },
  income: { has: ['income', 'salary'] },
  id: { has: ['custid', 'customerid', 'refno', 'ref', 'id', 'code'], not: ['pan', 'ckyc', 'aadhaar', 'email'] },
  updated: { has: ['updated', 'modified', 'lastupd', 'changed'] },
}

// The same kind of guess for the optional accounts table.
const ACCOUNT_GUESS: Record<AccountField | 'account' | 'customer' | 'updated', { has: string[]; not?: string[] }> = {
  account: { has: ['acctno', 'accountno', 'accountnumber', 'loanaccount', 'acct', 'account'], not: ['cust', 'type', 'status'] },
  customer: { has: ['custid', 'customerid', 'custno', 'cust', 'customer'] },
  product_type: { has: ['producttype', 'productcode', 'loantype', 'accttype', 'accounttype', 'type', 'code'], not: ['cust', 'branch'] },
  product_name: { has: ['productname', 'productdesc', 'scheme', 'description', 'desc', 'product'], not: ['code', 'type'] },
  status: { has: ['status', 'state'] },
  opened_on: { has: ['opendate', 'opened', 'open', 'disburs', 'startdate', 'since'] },
  balance: { has: ['balance', 'outstanding', 'principal', 'amount', 'amt'], not: ['emi', 'limit'] },
  updated: { has: ['updated', 'modified', 'lasttxn', 'lastupd', 'changed'] },
}
const ACCOUNT_LABELS: Record<AccountField, [string, string]> = {
  product_type: ['Product type', 'A code or word, e.g. SB, HL, Credit card'],
  product_name: ['Product name', "The bank's own name, e.g. Prime Savings"],
  status: ['Status', 'Active, overdue, dormant or closed'],
  opened_on: ['Opened on', ''],
  balance: ['Balance or amount owed', 'Rupees'],
}
const ACCOUNT_FIELDS = Object.keys(ACCOUNT_LABELS) as AccountField[]

function guess(key: keyof typeof GUESS, columns: string[]): string {
  return pick(GUESS[key], columns)
}

function pick(rule: { has: string[]; not?: string[] }, columns: string[]): string {
  const norm = (c: string) => c.toLowerCase().replace(/[^a-z0-9]/g, '')
  for (const word of rule.has) {
    const hit = columns.find((c) => norm(c).includes(word) && !(rule.not ?? []).some((n) => norm(c).includes(n)))
    if (hit) return hit
  }
  return ''
}

export function ConnectorSetupPage() {
  const { code = '' } = useParams()
  const source = useApi(() => api.sources().then((p) => p.results.find((s) => s.code === code) ?? null), [code])
  const catalog = useApi(() => api.connectorCatalog(), [])

  const s = source.data
  const type = catalog.data?.find((t) => t.type === s?.connector_type)

  return (
    <>
      <PageHeader
        title={s?.name ?? 'Connector'}
        description={
          type?.type === 'push_api'
            ? 'Your own systems send customers to Lumina with an API key.'
            : type
              ? `${type.label} connector. Lumina only reads, and only the columns you map.`
              : undefined
        }
        crumbs={[{ label: 'Connectors', to: '/connectors' }, { label: s?.name ?? '...' }]}
      />
      {(source.error || catalog.error) && <ErrorAlert message={source.error ?? catalog.error ?? ''} />}
      {source.data === null && <ErrorAlert message="No connector with this code." />}
      {!s || !catalog.data ? (
        source.data !== null && (
          <div className="card">
            <Loader kind="orbit" label="Loading the connector" />
          </div>
        )
      ) : s.is_demo || !type ? (
        <Card title="Built-in demo connector">
          <p className="muted">This demo connector reads Lumina&apos;s sample data and cannot be reconfigured.</p>
        </Card>
      ) : (
        <SetupSteps source={s} type={type} onChanged={source.reload} />
      )}
    </>
  )
}

function SetupSteps({ source, type, onChanged }: { source: Source; type: ConnectorType; onChanged: () => void }) {
  if (type.type === 'push_api') {
    return (
      <>
        <ApiKeyStep source={source} onChanged={onChanged} />
        <SyncStep source={source} onChanged={onChanged} push />
      </>
    )
  }
  return (
    <>
      {type.type === 'file_upload' ? (
        <UploadStep source={source} onChanged={onChanged} />
      ) : (
        <ConnectionStep source={source} type={type} onChanged={onChanged} />
      )}
      <MappingStep source={source} type={type} onChanged={onChanged} />
      {type.type !== 'file_upload' && <AccountsStep source={source} type={type} onChanged={onChanged} />}
      <SyncStep source={source} onChanged={onChanged} n={type.type === 'file_upload' ? 3 : 4} />
    </>
  )
}

function StepTitle({ n, text }: { n: number; text: string }) {
  return (
    <span className="row" style={{ gap: 10 }}>
      <span className="step-n">{n}</span>
      {text}
    </span>
  )
}

function ConnectionStep({ source, type, onChanged }: { source: Source; type: ConnectorType; onChanged: () => void }) {
  const toast = useToast()
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(type.fields.map((f) => [f.name, f.secret ? '' : (source.config[f.name] ?? f.default)])),
  )
  const [busy, setBusy] = useState<'save' | 'test' | null>(null)
  const [result, setResult] = useState<{ ok: boolean; detail: string } | null>(null)

  const save = async () => {
    setBusy('save')
    try {
      await api.updateConnector(source.code, { settings: values })
      setValues((v) => Object.fromEntries(Object.entries(v).map(([k, val]) => [k, type.fields.find((f) => f.name === k)?.secret ? '' : val])))
      toast('success', 'Connection details saved.')
      onChanged()
    } catch (e) {
      toast('error', (e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const test = async () => {
    setBusy('test')
    setResult(null)
    try {
      setResult(await api.testConnector(source.code))
    } catch (e) {
      setResult({ ok: false, detail: (e as Error).message })
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card
      title={<StepTitle n={1} text="Connection" />}
      description="Use a read-only login that can see only the customer table or view."
      footer={
        <>
          {result ? (
            <span className="row text-sm" style={{ gap: 8, color: result.ok ? 'var(--good-text)' : 'var(--bad-text)' }}>
              <Icon name={result.ok ? 'check' : 'alert'} size={16} /> {result.detail}
            </span>
          ) : (
            <span className="text-sm muted">Save, then test the connection.</span>
          )}
          <div className="row" style={{ gap: 8 }}>
            <button type="button" className="btn" disabled={busy !== null} onClick={save}>
              {busy === 'save' ? 'Saving...' : 'Save'}
            </button>
            <button type="button" className="btn btn-primary" disabled={busy !== null} onClick={test}>
              <Icon name="refresh" size={16} className={busy === 'test' ? 'spin' : undefined} />
              {busy === 'test' ? 'Testing...' : 'Test connection'}
            </button>
          </div>
        </>
      }
    >
      <div className="form-grid">
        <ConnectorFields fields={type.fields} values={values} onChange={setValues} secretStored={source.has_secret} />
      </div>
    </Card>
  )
}

function UploadStep({ source, onChanged }: { source: Source; onChanged: () => void }) {
  const toast = useToast()
  const input = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)

  const pick = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setBusy(true)
    try {
      const done = await api.uploadConnectorFile(source.code, file)
      toast('success', `${done.name} uploaded: ${done.rows} rows. Now map its columns.`)
      onChanged()
    } catch (err) {
      toast('error', (err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title={<StepTitle n={1} text="File" />} description="A CSV file with a header row, up to 5 MB. A new upload replaces the old one at the next sync.">
      <div className="row" style={{ gap: 12 }}>
        <input ref={input} type="file" accept=".csv,text/csv" hidden onChange={pick} />
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => input.current?.click()}>
          <Icon name="file" size={16} /> {busy ? 'Uploading...' : 'Upload CSV'}
        </button>
        {source.mapping && 'object' in source.mapping && (
          <span className="text-sm muted">Mapped file: {source.mapping.object}</span>
        )}
      </div>
    </Card>
  )
}

function MappingStep({ source, type, onChanged }: { source: Source; type: ConnectorType; onChanged: () => void }) {
  const toast = useToast()
  const saved = 'object' in source.mapping ? (source.mapping as ConnectorMapping) : null
  const [objects, setObjects] = useState<string[] | null>(null)
  const [object, setObject] = useState(saved?.object ?? '')
  const [columns, setColumns] = useState<string[] | null>(null)
  const [mapping, setMapping] = useState<ConnectorMapping>(
    saved ?? { object: '', id_column: '', updated_column: '', fields: {} },
  )
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const run = async (label: string, work: () => Promise<void>) => {
    setBusy(label)
    setError(null)
    try {
      await work()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const discover = () =>
    run('objects', async () => {
      const found = (await api.discoverObjects(source.code)).objects
      setObjects(found)
      if (!object && found.length === 1) setObject(found[0])
    })

  const loadColumns = (target = object) =>
    run('columns', async () => {
      const cols = (await api.discoverColumns(source.code, target)).columns
      setColumns(cols)
      setMapping((m) => {
        const sameObject = m.object === target
        const fields: Partial<Record<Field, string>> = sameObject ? { ...m.fields } : {}
        for (const f of FIELDS) if (!fields[f]) fields[f] = guess(f, cols)
        return {
          object: target,
          id_column: (sameObject && m.id_column) || guess('id', cols),
          updated_column: (sameObject && m.updated_column) || guess('updated', cols),
          fields,
        }
      })
    })

  const save = () =>
    run('save', async () => {
      await api.saveMapping(source.code, mapping)
      toast('success', 'Mapping saved. Sync to read the customers.')
      onChanged()
    })

  const setField = (f: Field, column: string) => setMapping((m) => ({ ...m, fields: { ...m.fields, [f]: column } }))
  const columnSelect = (value: string, onChange: (v: string) => void, label: string, emptyText: string) => (
    <select className="select select-sm" aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{emptyText}</option>
      {columns?.map((c) => (
        <option key={c} value={c}>
          {c}
        </option>
      ))}
    </select>
  )

  return (
    <Card
      title={<StepTitle n={2} text="What to read" />}
      description="Choose where customers are, then match its columns to Lumina's fields. Unmapped columns are never read."
      footer={
        columns && (
          <>
            <span className="text-sm muted">
              {Object.values(mapping.fields).filter(Boolean).length} of {FIELDS.length} fields mapped
            </span>
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy !== null || !mapping.id_column || !mapping.fields.name}
              onClick={save}
            >
              <Icon name="check" size={16} /> {busy === 'save' ? 'Saving...' : 'Save mapping'}
            </button>
          </>
        )
      }
    >
      <div className="stack" style={{ gap: 16 }}>
        {error && <ErrorAlert message={error} />}
        <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
          <button type="button" className="btn" disabled={busy !== null} onClick={discover}>
            <Icon name="search" size={16} /> {busy === 'objects' ? 'Looking...' : 'Discover'}
          </button>
          {(objects || object) && (
            <select
              className="select"
              aria-label={type.object_label}
              value={object}
              onChange={(e) => {
                setObject(e.target.value)
                setColumns(null)
              }}
            >
              <option value="">Choose {type.object_label.toLowerCase()}</option>
              {(objects ?? [object]).map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          )}
          {object && (
            <button type="button" className="btn" disabled={busy !== null} onClick={() => loadColumns()}>
              {busy === 'columns' ? 'Reading columns...' : columns ? 'Reload columns' : 'Show columns'}
            </button>
          )}
        </div>

        {busy === 'columns' && <Loader kind="pair" label="Reading the columns" size={44} />}

        {columns && (
          <div className="mapping-grid">
            <div className="mapping-row is-key">
              <span>
                <strong>Record ID</strong>
                <span className="text-xs muted">Required. Never changes for a customer.</span>
              </span>
              {columnSelect(mapping.id_column, (v) => setMapping((m) => ({ ...m, id_column: v })), 'Record ID column', 'Choose...')}
            </div>
            <div className="mapping-row is-key">
              <span>
                <strong>Last updated</strong>
                <span className="text-xs muted">Optional. The newest value wins a tie.</span>
              </span>
              {columnSelect(mapping.updated_column, (v) => setMapping((m) => ({ ...m, updated_column: v })), 'Last updated column', 'Not available')}
            </div>
            {FIELDS.map((f) => (
              <div key={f} className="mapping-row">
                <span>
                  {FIELD_LABELS[f]}
                  {f === 'name' && <span className="muted"> (required)</span>}
                </span>
                {columnSelect(mapping.fields[f] ?? '', (v) => setField(f, v), `Column for ${FIELD_LABELS[f]}`, 'Not in this source')}
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  )
}

function AccountsStep({ source, type, onChanged }: { source: Source; type: ConnectorType; onChanged: () => void }) {
  const toast = useToast()
  const customers = 'object' in source.mapping ? (source.mapping as ConnectorMapping) : null
  const saved = customers?.accounts ?? null
  const empty: AccountsMapping = { object: '', id_column: '', customer_column: '', updated_column: '', fields: {} }
  const [open, setOpen] = useState(Boolean(saved))
  const [objects, setObjects] = useState<string[] | null>(null)
  const [columns, setColumns] = useState<string[] | null>(null)
  const [mapping, setMapping] = useState<AccountsMapping>(saved ?? empty)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const run = async (label: string, work: () => Promise<void>) => {
    setBusy(label)
    setError(null)
    try {
      await work()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const discover = () =>
    run('objects', async () => {
      const found = (await api.discoverObjects(source.code)).objects
      setObjects(found.filter((o) => o !== customers?.object))
    })

  const loadColumns = (target = mapping.object) =>
    run('columns', async () => {
      const cols = (await api.discoverColumns(source.code, target)).columns
      setColumns(cols)
      setMapping((m) => {
        const same = m.object === target
        const fields: Partial<Record<AccountField, string>> = same ? { ...m.fields } : {}
        for (const f of ACCOUNT_FIELDS) if (!fields[f]) fields[f] = pick(ACCOUNT_GUESS[f], cols)
        return {
          object: target,
          id_column: (same && m.id_column) || pick(ACCOUNT_GUESS.account, cols),
          customer_column: (same && m.customer_column) || pick(ACCOUNT_GUESS.customer, cols),
          updated_column: (same && m.updated_column) || pick(ACCOUNT_GUESS.updated, cols),
          fields,
        }
      })
    })

  const save = () =>
    run('save', async () => {
      await api.saveAccountsMapping(source.code, mapping)
      toast('success', 'Accounts mapping saved. Sync to read the products.')
      onChanged()
    })

  const remove = () =>
    run('remove', async () => {
      await api.removeAccountsMapping(source.code)
      setMapping(empty)
      setColumns(null)
      setOpen(false)
      toast('success', 'Lumina no longer reads accounts from this connector. Its products were removed.')
      onChanged()
    })

  const columnSelect = (value: string, onChange: (v: string) => void, label: string, emptyText: string) => (
    <select className="select select-sm" aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{emptyText}</option>
      {columns?.map((c) => (
        <option key={c} value={c}>
          {c}
        </option>
      ))}
    </select>
  )

  const ready = Boolean(
    mapping.id_column && mapping.customer_column && (mapping.fields.product_type || mapping.fields.product_name),
  )

  return (
    <Card
      title={<StepTitle n={3} text="Accounts and products (optional)" />}
      description="If this system also keeps accounts, deposits, loans or cards, choose that table. Each row needs the customer's ID from step 2."
      actions={
        saved && (
          <button type="button" className="btn btn-sm" disabled={busy !== null} onClick={remove}>
            {busy === 'remove' ? 'Removing...' : 'Stop reading accounts'}
          </button>
        )
      }
      footer={
        columns && (
          <>
            <span className="text-sm muted">Account numbers are kept as their last four only.</span>
            <button type="button" className="btn btn-primary" disabled={busy !== null || !ready} onClick={save}>
              <Icon name="check" size={16} /> {busy === 'save' ? 'Saving...' : 'Save accounts mapping'}
            </button>
          </>
        )
      }
    >
      {!customers ? (
        <p className="muted">Map the customers first.</p>
      ) : !open ? (
        <button type="button" className="btn" onClick={() => setOpen(true)}>
          <Icon name="file" size={16} /> Add an accounts table
        </button>
      ) : (
        <div className="stack" style={{ gap: 16 }}>
          {error && <ErrorAlert message={error} />}
          {saved && !columns && (
            <p className="text-sm">
              Reading <span className="mono">{saved.object}</span>. Show its columns to change the mapping.
            </p>
          )}
          <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
            <button type="button" className="btn" disabled={busy !== null} onClick={discover}>
              <Icon name="search" size={16} /> {busy === 'objects' ? 'Looking...' : 'Discover'}
            </button>
            {(objects || mapping.object) && (
              <select
                className="select"
                aria-label={`Accounts ${type.object_label.toLowerCase()}`}
                value={mapping.object}
                onChange={(e) => {
                  setMapping({ ...empty, object: e.target.value })
                  setColumns(null)
                }}
              >
                <option value="">Choose {type.object_label.toLowerCase()}</option>
                {(objects ?? [mapping.object]).map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            )}
            {mapping.object && (
              <button type="button" className="btn" disabled={busy !== null} onClick={() => loadColumns()}>
                {busy === 'columns' ? 'Reading columns...' : columns ? 'Reload columns' : 'Show columns'}
              </button>
            )}
          </div>

          {busy === 'columns' && <Loader kind="pair" label="Reading the columns" size={44} />}

          {columns && (
            <div className="mapping-grid">
              <div className="mapping-row is-key">
                <span>
                  <strong>Account number</strong>
                  <span className="text-xs muted">Required. One per account.</span>
                </span>
                {columnSelect(mapping.id_column, (v) => setMapping((m) => ({ ...m, id_column: v })), 'Account number column', 'Choose...')}
              </div>
              <div className="mapping-row is-key">
                <span>
                  <strong>Customer ID</strong>
                  <span className="text-xs muted">Required. The same ID as the customer&apos;s record ID.</span>
                </span>
                {columnSelect(mapping.customer_column, (v) => setMapping((m) => ({ ...m, customer_column: v })), 'Customer ID column', 'Choose...')}
              </div>
              <div className="mapping-row is-key">
                <span>
                  <strong>Last updated</strong>
                  <span className="text-xs muted">Optional.</span>
                </span>
                {columnSelect(mapping.updated_column, (v) => setMapping((m) => ({ ...m, updated_column: v })), 'Accounts last updated column', 'Not available')}
              </div>
              {ACCOUNT_FIELDS.map((f) => (
                <div key={f} className="mapping-row">
                  <span>
                    {ACCOUNT_LABELS[f][0]}
                    {ACCOUNT_LABELS[f][1] && <span className="text-xs muted"> {ACCOUNT_LABELS[f][1]}</span>}
                  </span>
                  {columnSelect(
                    mapping.fields[f] ?? '',
                    (v) => setMapping((m) => ({ ...m, fields: { ...m.fields, [f]: v } })),
                    `Column for ${ACCOUNT_LABELS[f][0]}`,
                    'Not in this table',
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

function SyncStep({
  source,
  onChanged,
  push = false,
  n = 3,
}: {
  source: Source
  onChanged: () => void
  push?: boolean
  n?: number
}) {
  const toast = useToast()
  const canSync = useCan('manage_sources')
  const runs = useApi(() => api.connectorRuns(source.code), [source.code])
  const [busy, setBusy] = useState(false)
  const ready = 'object' in source.mapping

  const setSchedule = async (hours: number) => {
    try {
      await api.updateSource(source.code, { sync_every_hours: hours as Source['sync_every_hours'] })
      toast('success', hours ? `Lumina will sync this every ${hours} hours.` : 'Automatic sync turned off.')
      onChanged()
    } catch (e) {
      toast('error', (e as Error).message)
    }
  }

  const sync = async () => {
    setBusy(true)
    try {
      const r = await api.syncSource(source.code)
      const products = r.accounts === null ? '' : ` and ${r.accounts} products`
      toast('success', `Read ${r.fetched} rows: ${r.created} new, ${r.updated} updated${products}. Customers rebuilt.`)
      onChanged()
    } catch (e) {
      toast('error', (e as Error).message)
    } finally {
      setBusy(false)
      runs.reload()
    }
  }

  return (
    <Card
      title={<StepTitle n={push ? 2 : n} text={push ? 'Received data' : 'Sync'} />}
      description={
        push
          ? 'Every batch your systems sent, newest first.'
          : 'Read the mapped columns, then match and score the customers. Every attempt is listed below.'
      }
      actions={
        canSync &&
        !push && (
          <div className="row" style={{ gap: 8 }}>
            <select
              className="select select-sm"
              aria-label="Sync automatically"
              value={source.sync_every_hours}
              onChange={(e) => setSchedule(Number(e.target.value))}
            >
              <option value={0}>Sync by hand only</option>
              <option value={6}>Every 6 hours</option>
              <option value={12}>Every 12 hours</option>
              <option value={24}>Every day</option>
            </select>
            <button type="button" className="btn btn-primary" disabled={busy || !ready || !source.enabled} onClick={sync}>
              <Icon name="refresh" size={16} className={busy ? 'spin' : undefined} /> {busy ? 'Syncing...' : 'Sync now'}
            </button>
          </div>
        )
      }
      flush
    >
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>When</th>
              <th>Result</th>
              <th className="right">Rows read</th>
              <th className="right col-sm">New</th>
              <th className="right col-sm">Updated</th>
              <th className="col-md">By</th>
            </tr>
          </thead>
          {runs.loading && !runs.data ? (
            <LoaderRow kind="trail" label="Loading sync history" columns={6} />
          ) : (
            <tbody>
              {runs.data?.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted text-sm">
                    {push ? 'Nothing received yet.' : 'No syncs yet.'}
                  </td>
                </tr>
              )}
              {runs.data?.map((r) => (
                <tr key={r.id}>
                  <td className="text-sm">{formatDateTime(r.started_at)}</td>
                  <td>
                    {r.status === 'ok' ? (
                      <StatusBadge tone="good">Succeeded</StatusBadge>
                    ) : (
                      <span className="stack" style={{ gap: 2 }}>
                        <StatusBadge tone="bad">Failed</StatusBadge>
                        <span className="text-xs muted">{r.error}</span>
                      </span>
                    )}
                  </td>
                  <td className="right num">{r.fetched}</td>
                  <td className="right num col-sm">{r.created}</td>
                  <td className="right num col-sm">{r.updated}</td>
                  <td className="mono text-sm col-md">{r.started_by || '-'}</td>
                </tr>
              ))}
            </tbody>
          )}
        </table>
      </div>
    </Card>
  )
}

function ApiKeyStep({ source, onChanged }: { source: Source; onChanged: () => void }) {
  const toast = useToast()
  const [key, setKey] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const prefix = source.config.key_prefix
  const endpoint = `${window.location.origin}/t/${window.location.pathname.split('/')[2]}/api/ingest/${source.code}/`
  const continued = ' \\' // shell line continuation
  const example = [
    `curl -X POST ${endpoint}${continued}`,
    `  -H "Authorization: Bearer ${key ?? 'YOUR_API_KEY'}"${continued}`,
    `  -H "Content-Type: application/json"${continued}`,
    `  -d '{"records": [{"id": "C-1001", "name": "Asha Rao", "mobile": "9000000001", "pan": "ABCPR1234K", "updated_at": "2026-10-01T10:00:00"}]}'`,
  ].join('\n')

  const create = async () => {
    if (prefix && !window.confirm('Create a new key? The current key stops working immediately.')) return
    setBusy(true)
    try {
      setKey((await api.createApiKey(source.code)).api_key)
      toast('success', 'New API key created. Copy it now: it is shown only once.')
      onChanged()
    } catch (e) {
      toast('error', (e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card
      title={<StepTitle n={1} text="API key" />}
      description="Your systems send customers to Lumina with this key. Lumina keeps only a scrambled copy, so a lost key can be replaced, not shown again."
      actions={
        <button type="button" className={`btn${prefix ? '' : ' btn-primary'}`} disabled={busy} onClick={create}>
          {prefix ? 'Replace key' : 'Create API key'}
        </button>
      }
    >
      <div className="stack" style={{ gap: 16 }}>
        {key ? (
          <div className="issued" role="status">
            <Icon name="key" size={18} />
            <div className="issued-text">
              <strong>Copy this key now</strong>
              <span className="text-sm">It is shown only once. Keep it in your system&apos;s secret settings, never in code.</span>
            </div>
            <code className="issued-pw">{key}</code>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => navigator.clipboard?.writeText(key).then(() => toast('success', 'Copied.'))}
            >
              Copy
            </button>
          </div>
        ) : prefix ? (
          <span className="text-sm">
            Active key starts with <code className="mono">{prefix}…</code>
          </span>
        ) : (
          <span className="text-sm muted">No key yet.</span>
        )}
        <div className="stack" style={{ gap: 6 }}>
          <strong className="text-sm">How your system sends customers</strong>
          <pre className="code-block">{example}</pre>
          <span className="text-xs muted">
            Up to 1,000 records per request. Each needs id and name; other fields: father_name, dob, gender, pan, aadhaar,
            ckyc, mobile, email, address, perm_address, occupation, income, updated_at. PAN and CKYC are encrypted on
            arrival; only the last 4 digits of Aadhaar are kept.
          </span>
        </div>
      </div>
    </Card>
  )
}
