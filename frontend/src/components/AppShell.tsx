import { NavLink, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { clsx } from 'clsx'
import { Brain, History, ListChecks, MessageSquare, Upload, User, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { api } from '../lib/api'
import { useUnits } from '../lib/units'
import { ErrorBoundary } from './ErrorBoundary'
import { useChat } from '../features/chat/ChatProvider'
import { ChatDock } from '../features/chat/ChatDock'

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
  { to: '/you', label: 'You', Icon: User },
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

function UnitsToggle() {
  const { system, setSystem } = useUnits()
  return (
    <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs font-medium">
      {(['metric', 'imperial'] as const).map((s) => (
        <button
          key={s}
          type="button"
          onClick={() => setSystem(s)}
          className={clsx(
            'rounded-md px-2.5 py-1 capitalize transition-colors',
            system === s ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500',
          )}
        >
          {s}
        </button>
      ))}
    </div>
  )
}

/** Sidebar entry that opens the global chat pane. Not a route — it toggles the drawer. */
function ChatSidebarButton() {
  const { toggleOpen, open, messages } = useChat()
  return (
    <button
      type="button"
      onClick={toggleOpen}
      aria-haspopup="dialog"
      aria-expanded={open}
      className={clsx(
        'flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
        open ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
      )}
    >
      <MessageSquare className="h-5 w-5" />
      <span className="flex-1 text-left">Chat</span>
      {messages.length > 0 && !open && (
        <span className="h-1.5 w-1.5 rounded-full bg-brand-500" aria-hidden="true" />
      )}
    </button>
  )
}

/** Compact chat toggle for the mobile top bar. */
function ChatHeaderButton() {
  const { toggleOpen, open, messages } = useChat()
  return (
    <button
      type="button"
      onClick={toggleOpen}
      aria-label="Chat"
      aria-haspopup="dialog"
      aria-expanded={open}
      className="relative rounded-lg p-2 text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
    >
      <MessageSquare className="h-5 w-5" />
      {messages.length > 0 && !open && (
        <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-brand-500" aria-hidden="true" />
      )}
    </button>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation()
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
        <div className="border-t border-slate-100 px-3 py-2">
          <ChatSidebarButton />
        </div>
        <div className="space-y-3 px-5 py-4">
          <UnitsToggle />
          <div className="text-xs text-slate-400">Local · single-user</div>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur lg:hidden">
        <BrandMark compact />
        <div className="flex items-center gap-2">
          <UnitsToggle />
          <ChatHeaderButton />
        </div>
      </header>

      {/* Main content */}
      <main className="min-w-0 flex-1">
        <div className="mx-auto max-w-5xl px-4 pb-24 pt-4 sm:px-6 lg:px-8 lg:pb-10 lg:pt-8">
          <ErrorBoundary resetKey={location.pathname}>{children}</ErrorBoundary>
        </div>
      </main>

      {/* Mobile bottom tab bar */}
      <nav
        className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-slate-200 bg-white/95 backdrop-blur lg:hidden"
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

      <ErrorBoundary compact label="The chat pane hit an error">
        <ChatDock />
      </ErrorBoundary>
    </div>
  )
}
