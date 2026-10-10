import { useCallback, useEffect, useRef, useState } from 'react'

// The first load of a screen shows a logo loader. Keep it up long enough for its parts to merge and the core
// to light up (about 1.8 s), so it reads as a moment rather than a flicker. Later reloads (filters, saves) and
// people who ask their system to reduce motion get the data as soon as it arrives.
export const LOADER_MIN_MS = 1800

const reduceMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

export function atLeast<T>(work: Promise<T>, ms: number): Promise<T> {
  if (reduceMotion()) return work
  const wait = new Promise((resolve) => setTimeout(resolve, ms))
  return Promise.all([work, wait]).then(([result]) => result)
}

// Load data when a page opens (and again when `deps` change). `reload()` fetches again after a change.
export function useApi<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [version, setVersion] = useState(0)
  const firstLoad = useRef(true)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const stableLoad = useCallback(load, deps)

  useEffect(() => {
    let cancelled = false // ignore a slow old response that arrives after a newer one
    setLoading(true)
    const work = firstLoad.current ? atLeast(stableLoad(), LOADER_MIN_MS) : stableLoad()
    work
      .then((result) => {
        if (!cancelled) {
          firstLoad.current = false
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
