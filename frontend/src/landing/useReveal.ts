import { useEffect, useRef, useState } from 'react'

const reduceMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

// Marks every ".reveal" element inside the page as visible when it scrolls into view, so it can fade and
// rise in once. With "reduce motion" switched on, everything is shown straight away.
export function useRevealOnScroll() {
  useEffect(() => {
    const items = Array.from(document.querySelectorAll<HTMLElement>('.reveal'))
    if (reduceMotion() || !('IntersectionObserver' in window)) {
      items.forEach((el) => el.classList.add('is-visible'))
      return
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible')
            observer.unobserve(entry.target)
          }
        }
      },
      { threshold: 0.15, rootMargin: '0px 0px -40px 0px' },
    )
    items.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [])
}

// Counts from 0 to `target` once, starting after `delayMs`. Used for the trust score in the hero.
export function useCountUp(target: number, durationMs = 1400, delayMs = 0) {
  const [value, setValue] = useState(reduceMotion() ? target : 0)
  const frame = useRef(0)

  useEffect(() => {
    if (reduceMotion()) return
    let start = 0
    const timer = window.setTimeout(() => {
      const tick = (now: number) => {
        if (!start) start = now
        const t = Math.min(1, (now - start) / durationMs)
        const eased = 1 - Math.pow(1 - t, 3)
        setValue(Math.round(target * eased))
        if (t < 1) frame.current = requestAnimationFrame(tick)
      }
      frame.current = requestAnimationFrame(tick)
    }, delayMs)
    return () => {
      window.clearTimeout(timer)
      cancelAnimationFrame(frame.current)
    }
  }, [target, durationMs, delayMs])

  return value
}
