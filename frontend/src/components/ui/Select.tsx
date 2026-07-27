import { clsx } from 'clsx'
import { ChevronDown } from 'lucide-react'
import type { SelectHTMLAttributes } from 'react'

/**
 * A native <select> styled to match FitSift's inputs (consistent control vocabulary),
 * with a custom chevron. `className` targets the wrapper (use it for width, e.g. sm:w-40).
 * Pass an `aria-label` for accessibility since these selects have no visible <label>.
 */
export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className={clsx('relative', className)}>
      <select
        className="h-11 w-full appearance-none rounded-lg border border-slate-200 bg-white pl-3 pr-9 text-sm text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
        aria-hidden
      />
    </div>
  )
}
