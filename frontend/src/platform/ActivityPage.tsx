import { useApi } from '../api/useApi'
import { formatDateTime } from '../format'
import { LoaderRow } from '../components/Loader'
import { Card, ErrorAlert, PageHeader, StatusBadge } from '../components/ui'
import { platformApi } from './api'

const ACTIONS: Record<string, { label: string; tone: 'good' | 'warn' | 'bad' | 'neutral' }> = {
  login: { label: 'Signed in', tone: 'neutral' },
  login_failed: { label: 'Sign-in failed', tone: 'bad' },
  logout: { label: 'Signed out', tone: 'neutral' },
  org_created: { label: 'Added organization', tone: 'good' },
  org_updated: { label: 'Changed organization', tone: 'neutral' },
  org_suspended: { label: 'Suspended organization', tone: 'bad' },
  org_resumed: { label: 'Resumed organization', tone: 'good' },
}

// The platform team's own activity. Each organization's audit log stays inside that organization.
export function ActivityPage() {
  const { data, error, loading } = useApi(() => platformApi.events(), [])
  return (
    <>
      <PageHeader title="Platform activity" description="What the platform team did, newest first. Nobody can edit it." />
      {error && <ErrorAlert message={error} />}
      <Card flush footer={data && <span>{data.length} events (latest 200)</span>}>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Who</th>
                <th>What</th>
                <th>Organization</th>
              </tr>
            </thead>
            {loading && !data ? (
              <LoaderRow kind="trail" label="Loading activity" columns={4} />
            ) : (
              <tbody>
                {data?.map((e) => {
                  const a = ACTIONS[e.action] ?? { label: e.action, tone: 'neutral' as const }
                  return (
                    <tr key={e.id}>
                      <td className="text-sm">{formatDateTime(e.at)}</td>
                      <td className="mono text-sm">{e.actor}</td>
                      <td>
                        <StatusBadge tone={a.tone}>{a.label}</StatusBadge>
                      </td>
                      <td className="mono text-sm">{e.target || '-'}</td>
                    </tr>
                  )
                })}
              </tbody>
            )}
          </table>
        </div>
      </Card>
    </>
  )
}
