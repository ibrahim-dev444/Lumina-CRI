import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api/client'
import type { Source } from '../api/types'
import { Icon } from './Icon'
import { useToast } from './Toasts'
import { Card, ErrorAlert } from './ui'

type Impact = Awaited<ReturnType<typeof api.connectorDeletePreview>>

// Connector setup, last card: delete the connector for good. Shows what goes first, offers Disconnect (which can
// be undone) instead, and asks for the connector's name before deleting.
export function DeleteConnectorCard({ source, onChanged }: { source: Source; onChanged: () => void }) {
  const toast = useToast()
  const navigate = useNavigate()
  const [impact, setImpact] = useState<Impact | null>(null)
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState<'look' | 'delete' | 'off' | null>(null)
  const [error, setError] = useState<string | null>(null)

  const look = async () => {
    setBusy('look')
    setError(null)
    try {
      setImpact(await api.connectorDeletePreview(source.code))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const disconnect = async () => {
    setBusy('off')
    try {
      await api.updateSource(source.code, { enabled: false })
      toast('success', `${source.name} disconnected. Customers found only there are hidden until you reconnect it.`)
      setImpact(null)
      onChanged()
    } catch (e) {
      toast('error', (e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const remove = async (e: FormEvent) => {
    e.preventDefault()
    setBusy('delete')
    setError(null)
    try {
      await api.deleteConnector(source.code, typed)
      toast('success', `${source.name} deleted. Customers were rebuilt from the remaining systems.`)
      navigate('/connectors')
    } catch (err) {
      setError((err as Error).message)
      setBusy(null)
    }
  }

  return (
    <Card
      className="danger-card"
      title="Delete connector"
      description="Removes this connector and everything Lumina read from it. This cannot be undone."
    >
      {error && <ErrorAlert message={error} />}
      {!impact ? (
        <button type="button" className="btn btn-danger" disabled={busy !== null} onClick={look}>
          <Icon name="x" size={16} /> {busy === 'look' ? 'Checking...' : 'Delete connector...'}
        </button>
      ) : (
        <form className="stack" style={{ gap: 14 }} onSubmit={remove}>
          <p>Deleting <strong>{source.name}</strong> removes:</p>
          <ul className="danger-list">
            <li>
              <strong>{impact.records}</strong> customer record{impact.records === 1 ? '' : 's'} and{' '}
              <strong>{impact.products}</strong> product{impact.products === 1 ? '' : 's'} read from it
            </li>
            <li>
              <strong>{impact.customers}</strong> customer{impact.customers === 1 ? '' : 's'} no other system knows,
              with their <strong>{impact.conversations}</strong> conversation{impact.conversations === 1 ? '' : 's'} and{' '}
              <strong>{impact.corrections}</strong> correction{impact.corrections === 1 ? '' : 's'}
            </li>
            <li>its stored password or API key and its sync history</li>
          </ul>
          <p className="text-sm muted">
            Customers that other systems also describe stay, rebuilt from those systems. The audit log keeps a record of
            this deletion.
          </p>
          {source.enabled && (
            <div className="notice" role="note">
              <Icon name="info" size={16} />
              <span>
                Only need it gone for now? <strong>Disconnect</strong> hides its customers and can be undone.{' '}
                <button type="button" className="link" disabled={busy !== null} onClick={disconnect}>
                  {busy === 'off' ? 'Disconnecting...' : 'Disconnect instead'}
                </button>
              </span>
            </div>
          )}
          <div className="form-field">
            <label htmlFor="delete-confirm">
              Type <strong>{source.name}</strong> to confirm
            </label>
            <input
              id="delete-confirm"
              className="input"
              autoComplete="off"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
            />
          </div>
          <div className="row" style={{ gap: 8, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
            <button type="button" className="btn" disabled={busy !== null} onClick={() => setImpact(null)}>
              Cancel
            </button>
            <button type="submit" className="btn btn-danger" disabled={busy !== null || typed.trim() !== source.name}>
              {busy === 'delete' ? 'Deleting...' : 'Delete for good'}
            </button>
          </div>
        </form>
      )}
    </Card>
  )
}
