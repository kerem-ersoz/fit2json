import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { clsx } from 'clsx'
import { Brain, History, ListChecks, Upload, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { api } from '../lib/api'

interface NavItem {
  to: string
  label: string
  Icon: LucideIcon
  end?: boolean
}

const NAV: NavItem[] = [
  { to: '/', label: 'Library', Icon: ListChecks, end: true },
  { to: '/analyze', label: 'Analyze', Icon: Brain },
  { to: '/memory', label: 'Memory', Icon: History },
  { to: '/ingest', label: 'Add', Icon: Upload },
]

function BrandMark({ compact = false }: { compact?: boolean }) {
  const { data: config } = useQuery({ queryKey: ['config'], queryFn: api.config })
  return (
    <div className="flex items-center gap-2.5">
      <img src={`${import.meta.env.BASE_URL}favicon.svg`} alt="" className="h-8 w-8" />
      <div className="leading-tight">
        <div className="text-lg font-bold tracking-tight text-slate-900">
          {config?.brand.name ?? 'FitSift'}
        </div>
        {!compact && (
          <div className="text-xs text-slate-500">
            {config?.brand.tagline ?? 'Sift your workouts into insight'}
          </div>
        )}
      </div>
    </div>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-full lg:flex">
      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="px-5 py-5">
          <BrandMark />
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {NAV.map(({ to, label, Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-brand-50 text-brand-700'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                )
              }
            >
              <Icon className="h-5 w-5" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-4 text-xs text-slate-400">Local · single-user</div>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-20 flex items-center border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur lg:hidden">
        <BrandMark compact />
      </header>

      {/* Main content */}
      <main className="min-w-0 flex-1">
        <div className="mx-auto max-w-5xl px-4 pb-24 pt-4 sm:px-6 lg:px-8 lg:pb-10 lg:pt-8">
          {children}
        </div>
      </main>

      {/* Mobile bottom tab bar */}
      <nav
        className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-slate-200 bg-white/95 backdrop-blur lg:hidden"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      >
        {NAV.map(({ to, label, Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              clsx(
                'flex min-h-[56px] flex-col items-center justify-center gap-1 text-[11px] font-medium',
                isActive ? 'text-brand-700' : 'text-slate-500',
              )
            }
          >
            <Icon className="h-5 w-5" />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
