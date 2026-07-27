import { clsx } from 'clsx'

/** A neutral loading placeholder. Pulse is disabled under prefers-reduced-motion (see index.css). */
export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-slate-200/80', className)} />
}
