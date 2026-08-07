import { AlertCircle, Loader2, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'
import { clsx } from 'clsx'
import { Button } from './Button'

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={clsx('animate-spin text-accent', className)} />
}

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted">
      <Spinner className="h-6 w-6" />
      <p className="text-sm">{label}</p>
    </div>
  )
}

export function ErrorState({
  message,
  hint,
  onRetry,
}: {
  message: string
  hint?: string
  onRetry?: () => void
}) {
  return (
    <div
      role="alert"
      className="mx-auto max-w-md rounded-xl border border-danger-divider bg-danger-tint p-5 text-center"
    >
      <AlertCircle className="mx-auto mb-2 h-6 w-6 text-danger" aria-hidden />
      <p className="text-sm font-medium text-danger-deep">{message}</p>
      {hint && <p className="mx-auto mt-1 max-w-xs text-sm text-danger-strong">{hint}</p>}
      {onRetry && (
        <div className="mt-4 flex justify-center">
          <Button variant="secondary" onClick={onRetry}>
            <RefreshCw className="h-4 w-4" /> Try again
          </Button>
        </div>
      )}
    </div>
  )
}

export function EmptyState({
  title,
  hint,
  icon,
  action,
}: {
  title: string
  hint?: string
  icon?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center text-muted">
      {icon}
      <p className="text-base font-medium text-strong">{title}</p>
      {hint && <p className="max-w-sm text-sm">{hint}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}
