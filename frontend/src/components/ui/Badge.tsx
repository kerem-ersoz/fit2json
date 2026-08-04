import { clsx } from 'clsx'
import type { HTMLAttributes } from 'react'

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-full border border-divider-soft bg-surface-subtle px-2.5 py-0.5 text-xs font-medium text-copy',
        className,
      )}
      {...props}
    />
  )
}
