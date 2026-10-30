import { useRef, useState, type DragEvent, type ReactNode } from 'react'

import { api } from '../api/client'
import type { FileRemoval, Source, UploadResult, UploadedFile } from '../api/types'
import { useApi } from '../api/useApi'
import { formatDateTime } from '../format'
import { Icon } from './Icon'
import { Loader } from './Loader'
import { useToast } from './Toasts'
import { Card, EmptyState, ErrorAlert, StatusBadge } from './ui'

const MAX_FILES = 20
const MAX_BYTES = 5 * 1024 * 1024

// File-upload connector, step 1: every CSV uploaded to it. A sync reads all active files (the newest wins when
// the same customer ID is in several). Suspend hides the customers only those files hold; Resume brings them
// back with the same IDs; Remove deletes them after showing what goes.
export function UploadedFilesCard({ source, title, onChanged }: { source: Source; title: ReactNode; onChanged: () => void }) {
  const toast = useToast()
  const input = useRef<HTMLInputElement>(null)
  const files = useApi(() => api.connectorFiles(source.code), [source.code])
  const [selected, setSelected] = useState<number[]>([])
  const [busy, setBusy] = useState<'upload' | 'status' | 'look' | 'remove' | null>(null)
  const [refused, setRefused] = useState<UploadResult[]>([])
  const [notes, setNotes] = useState<UploadResult[]>([])
  const [removal, setRemoval] = useState<FileRemoval | null>(null)
  const [dragging, setDragging] = useState(false)

  const list = files.data ?? []
  const chosen = list.filter((f) => selected.includes(f.id))
  const allChosen = list.length > 0 && selected.length === list.length
  const active = list.filter((f) => f.status === 'active').length

  const reload = () => {
    files.reload()
    onChanged()
  }

  const upload = async (picked: File[]) => {
    if (picked.length === 0) return
    if (picked.length > MAX_FILES) {
      toast('error', `Upload at most ${MAX_FILES} files at a time.`)
      return
    }
    const tooBig = picked.filter((f) => f.size > MAX_BYTES)
    if (tooBig.length) {
      toast('error', `${tooBig.map((f) => f.name).join(', ')}: larger than 5 MB.`)
      return
    }
    setBusy('upload')
    setRefused([])
    try {
      const results = await api.uploadConnectorFiles(source.code, picked)
      const kept = results.filter((r) => r.ok)
      setRefused(results.filter((r) => !r.ok))
      setNotes(kept.filter((r) => r.missing?.length || r.new_columns?.length || r.lumina_ids))
      if (kept.length) {
        const rows = kept.reduce((n, r) => n + (r.rows ?? 0), 0)
        toast('success', `${kept.length} file${kept.length === 1 ? '' : 's'} uploaded, ${rows} rows.`)
      }
      reload()
    } catch (e) {
      toast('error', (e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const setStatus = async (status: UploadedFile['status']) => {
    setBusy('status')
    try {
      const out = await api.setFileStatus(source.code, selected, status)
      const n = `${out.changed} file${out.changed === 1 ? '' : 's'}`
      toast(
        'success',
        status === 'suspended'
          ? `${n} suspended. Customers found only there are hidden.`
          : `${n} resumed. Their customers are back, with the same IDs.`,
      )
      setSelected([])
      reload()
    } catch (e) {
      toast('error', (e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const look = async () => {
    setBusy('look')
    try {
      setRemoval(await api.fileRemovePreview(source.code, selected))
    } catch (e) {
      toast('error', (e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const remove = async () => {
    setBusy('remove')
    try {
      const out = await api.removeFiles(source.code, selected)
      toast('success', `${out.files} file${out.files === 1 ? '' : 's'} removed.`)
      setSelected([])
      setRemoval(null)
      reload()
    } catch (e) {
      toast('error', (e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const toggle = (id: number) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    upload(Array.from(e.dataTransfer.files).filter((f) => f.name.toLowerCase().endsWith('.csv')))
  }

  const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

  return (
    <Card
      title={title}
      description="CSV files with a header row, up to 20 at a time and 5 MB each. Every active file is read; when the same customer ID is in several, the newest file wins."
      flush
    >
      <div
        className={`dropzone${dragging ? ' is-over' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input
          ref={input}
          type="file"
          accept=".csv,text/csv"
          multiple
          hidden
          onChange={(e) => {
            const picked = Array.from(e.target.files ?? [])
            e.target.value = ''
            upload(picked)
          }}
        />
        <Icon name="file" size={20} />
        <span>
          Drop CSV files here, or{' '}
          <button type="button" className="link" disabled={busy !== null} onClick={() => input.current?.click()}>
            {busy === 'upload' ? 'uploading...' : 'choose files'}
          </button>
        </span>
        {list.length > 0 && (
          <span className="text-sm muted">
            {active} of {plural(list.length, 'file')} active
          </span>
        )}
      </div>

      {busy === 'upload' && <Loader kind="drop" label="Uploading the files" size={44} />}
      {!files.data && !files.error && busy !== 'upload' && <Loader kind="drop" label="Loading the files" size={44} />}

      {notes.length > 0 && (
        <div className="card-body">
          <div className="upload-notes" role="status">
            {notes.map((r) => (
              <div key={r.name} className="upload-note">
                <strong>{r.name}</strong>
                <ul>
                  {r.new_columns?.length ? (
                    <li>
                      New columns: {r.new_columns.join(', ')}. Map them in step 2; the column list there is already
                      up to date.
                    </li>
                  ) : null}
                  {r.missing?.length ? (
                    <li>
                      {r.missing.includes(source.mapping.id_column as string)
                        ? `It has no ${source.mapping.id_column} column (the record ID), so its rows are skipped until the ID column is changed in step 2.`
                        : `It has no ${r.missing.join(', ')} column${r.missing.length > 1 ? 's' : ''}. For customers also in earlier files, those values stay as the earlier files gave them.`}
                    </li>
                  ) : null}
                  {r.lumina_ids ? (
                    <li>
                      Its IDs look like Lumina's own customer IDs (like C-10168). A file is read as its own system, so
                      these rows join existing customers only through PAN, date of birth, email or mobile. Rows with
                      just a name become new customers.
                    </li>
                  ) : null}
                </ul>
              </div>
            ))}
            <button type="button" className="link text-sm" onClick={() => setNotes([])}>
              Dismiss
            </button>
          </div>
        </div>
      )}
      {refused.length > 0 && (
        <div className="card-body">
          <ErrorAlert message={`Not uploaded: ${refused.map((r) => `${r.name} (${r.error})`).join('; ')}`} />
        </div>
      )}
      {files.error && (
        <div className="card-body">
          <ErrorAlert message={files.error} />
        </div>
      )}

      {list.length === 0 && files.data && (
        <EmptyState icon="file" title="No files yet">
          Upload the branch spreadsheets saved as CSV. You can add more later.
        </EmptyState>
      )}

      {list.length > 0 && (
        <>
          <div className="files-toolbar">
            <span className="text-sm muted">
              {selected.length ? `${selected.length} selected` : 'Select files to suspend, resume or remove'}
            </span>
            <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
              <button
                type="button"
                className="btn btn-sm"
                disabled={busy !== null || !chosen.some((f) => f.status === 'active')}
                onClick={() => setStatus('suspended')}
              >
                <Icon name="power" size={14} /> Suspend
              </button>
              <button
                type="button"
                className="btn btn-sm"
                disabled={busy !== null || !chosen.some((f) => f.status === 'suspended')}
                onClick={() => setStatus('active')}
              >
                <Icon name="refresh" size={14} /> Resume
              </button>
              <button type="button" className="btn btn-sm btn-danger-ghost" disabled={busy !== null || !selected.length} onClick={look}>
                <Icon name="x" size={14} /> {busy === 'look' ? 'Checking...' : 'Remove...'}
              </button>
            </div>
          </div>

          {removal && (
            <div className="files-removal" role="alert">
              <p>
                Removing {plural(removal.files, 'file')} deletes {plural(removal.records, 'customer row')} found only
                there, and {plural(removal.customers, 'customer')} no other file or system knows, with their{' '}
                {plural(removal.conversations, 'conversation')} and {plural(removal.corrections, 'correction')}. This
                cannot be undone; Suspend can.
              </p>
              <div className="row" style={{ gap: 8, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                <button type="button" className="btn btn-sm" onClick={() => setRemoval(null)}>
                  Cancel
                </button>
                <button type="button" className="btn btn-sm btn-danger" disabled={busy !== null} onClick={remove}>
                  {busy === 'remove' ? 'Removing...' : 'Remove for good'}
                </button>
              </div>
            </div>
          )}

          <div className="table-wrap">
            <table className="table" style={{ minWidth: 620 }}>
              <thead>
                <tr>
                  <th style={{ width: 36 }}>
                    <input
                      type="checkbox"
                      aria-label="Select all files"
                      checked={allChosen}
                      onChange={() => setSelected(allChosen ? [] : list.map((f) => f.id))}
                    />
                  </th>
                  <th>File</th>
                  <th className="num">Rows</th>
                  <th>Status</th>
                  <th>Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {list.map((f) => (
                  <tr key={f.id} className={f.status === 'suspended' ? 'is-muted' : undefined}>
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Select ${f.name}`}
                        checked={selected.includes(f.id)}
                        onChange={() => toggle(f.id)}
                      />
                    </td>
                    <td className="mono">{f.name}</td>
                    <td className="num">{f.rows}</td>
                    <td>
                      <StatusBadge tone={f.status === 'active' ? 'good' : 'neutral'}>
                        {f.status === 'active' ? 'Active' : 'Suspended'}
                      </StatusBadge>
                    </td>
                    <td className="text-sm muted">
                      {formatDateTime(f.uploaded_at)}
                      {f.uploaded_by && ` · ${f.uploaded_by}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  )
}
