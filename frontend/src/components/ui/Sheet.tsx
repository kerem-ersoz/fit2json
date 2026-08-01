import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { usePrefersReducedMotion } from '../../lib/usePrefersReducedMotion'

/**
 * A focused overlay surface: a right-anchored slide-over on desktop, a bottom sheet on
 * mobile. Used where content needs more room than its host column offers (e.g. an
 * infographic in the narrow chat rail) without a hard, centered-modal context switch.
 *
 * Handles backdrop + Escape close, initial focus, background scroll-lock, focus
 * restoration, and a `prefers-reduced-motion` alternative (no slide).
 */
export function Sheet({
  title,
  subtitle,
  icon,
  onClose,
  children,
  footer,
  labelledById = 'sheet-title',
}: {
  title: string
  subtitle?: string
  icon?: ReactNode
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  labelledById?: string
}) {
  const [mounted, setMounted] = useState(false)
  const closeRef = useRef<HTMLButtonElement>(null)
  const reduced = usePrefersReducedMotion()

  useEffect(() => {
    setMounted(true)
    closeRef.current?.focus()
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const prevFocus = document.activeElement as HTMLElement | null
    return () => {
      document.body.style.overflow = prevOverflow
      prevFocus?.focus?.()
    }
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const shown = mounted || reduced

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-stretch sm:justify-end">
      <button
        type="button"
        aria-hidden="true"
        tabIndex={-1}
        onClick={onClose}
        className={`absolute inset-0 cursor-default bg-slate-900/40 transition-opacity duration-200 motion-reduce:transition-none ${
          mounted ? 'opacity-100' : 'opacity-0'
        }`}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledById}
        className={[
          'relative z-10 flex w-full max-h-[92vh] flex-col overflow-hidden border-slate-200 bg-white shadow-xl',
          'rounded-t-2xl border sm:h-full sm:max-h-none sm:w-full sm:max-w-xl sm:rounded-none sm:rounded-l-2xl sm:border-l',
          reduced ? '' : 'transition-transform duration-200 ease-out',
          shown ? 'translate-y-0 sm:translate-x-0' : 'translate-y-6 sm:translate-y-0 sm:translate-x-8',
        ].join(' ')}
      >
        <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
          <div className="flex min-w-0 items-center gap-2">
            {icon}
            <div className="min-w-0">
              <h2 id={labelledById} className="text-sm font-semibold text-slate-900">
                {title}
              </h2>
              {subtitle && <p className="truncate text-xs text-slate-500">{subtitle}</p>}
            </div>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto bg-slate-50/60 p-4">{children}</div>

        {footer && (
          <div className="border-t border-slate-100 px-4 py-3">{footer}</div>
        )}
      </div>
    </div>,
    document.body,
  )
}
