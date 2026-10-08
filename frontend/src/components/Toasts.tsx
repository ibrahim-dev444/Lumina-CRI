import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'

import { Icon } from './Icon'

type Tone = 'success' | 'error'
interface Toast {
  id: number
  tone: Tone
  message: string
}

const ToastContext = createContext<(tone: Tone, message: string) => void>(() => {})

// Short messages in the bottom-right corner after an action ("Sync finished", "Merge failed").
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const show = useCallback((tone: Tone, message: string) => {
    const id = Date.now() + Math.random()
    setToasts((list) => [...list, { id, tone, message }])
    setTimeout(() => setToasts((list) => list.filter((t) => t.id !== id)), tone === 'error' ? 7000 : 4500)
  }, [])

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.tone}`}>
            <Icon name={t.tone === 'success' ? 'check' : 'alert'} size={18} className="toast-icon" />
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast() {
  return useContext(ToastContext)
}
