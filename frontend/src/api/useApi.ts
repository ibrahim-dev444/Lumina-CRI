import { useCallback, useEffect, useState } from 'react'

// Load data when a page opens (and again when `deps` change). `reload()` fetches again after a change.
export function useApi<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [version, setVersion] = useState(0)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const stableLoad = useCallback(load, deps)

  useEffect(() => {
    let cancelled = false // ignore a slow old response that arrives after a newer one
    setLoading(true)
    stableLoad()
      .then((result) => {
        if (!cancelled) {
          setData(result)
          setError(null)
        }
      })
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [stableLoad, version])

  const reload = useCallback(() => setVersion((v) => v + 1), [])
  return { data, error, loading, reload }
}
