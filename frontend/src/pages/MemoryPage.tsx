import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { History } from 'lucide-react'
import { api, type AnalysisEntry } from '../lib/api'
import { sportMeta } from '../lib/sport'
import { formatDate } from '../lib/format'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/Feedback'
import { AnalysisView } from '../features/activities/AnalysisView'

function MemoryEntryItem({ entry }: { entry: AnalysisEntry }) {
  const [open, setOpen] = useState(false)
  const { data, isLoading } = useQuery({
    queryKey: ['memory', entry.entry_id],
    queryFn: () => api.memoryEntry(entry.entry_id),
    enabled: open,
  })
  const { label, Icon } = sportMeta(entry.sport)

  return (
    <details
      className="rounded-xl border border-slate-200 bg-white"
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
    >
      <summary className="flex cursor-pointer items-center gap-3 p-4 text-sm">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate font-semibold text-slate-900">
            {label} · {formatDate(entry.date ?? entry.created_at)}
          </div>
          {entry.prompt && (
            <div className="truncate text-xs text-slate-400">{entry.prompt}</div>
          )}
        </div>
      </summary>
      <div className="border-t border-slate-100 p-4">
        {isLoading || !data ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : (
          <AnalysisView
            content={data.content ?? ''}
            prompt={data.prompt}
            meta={`${data.backend ?? ''}${data.model ? ` · ${data.model}` : ''}`}
            entryId={entry.entry_id}
          />
        )}
      </div>
    </details>
  )
}

export function MemoryPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['memory-list'],
    queryFn: () => api.memory({ limit: 200 }),
  })
  const [sport, setSport] = useState('all')

  const entries = data?.entries ?? []
  const sports = useMemo(() => {
    const set = new Set<string>()
    for (const e of entries) if (e.sport) set.add(e.sport)
    return Array.from(set).sort()
  }, [entries])

  const filtered = sport === 'all' ? entries : entries.filter((e) => e.sport === sport)

  return (
    <div>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Memory</h1>
          <p className="text-sm text-slate-500">Every analysis you've saved, newest first.</p>
        </div>
        {sports.length > 0 && (
          <select
            value={sport}
            onChange={(e) => setSport(e.target.value)}
            className="h-11 rounded-lg border border-slate-200 bg-white px-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="all">All sports</option>
            {sports.map((s) => (
              <option key={s} value={s}>
                {sportMeta(s).label}
              </option>
            ))}
          </select>
        )}
      </div>

      {isLoading && <LoadingState label="Loading memory…" />}
      {isError && <ErrorState message={(error as Error)?.message ?? 'Failed to load memory.'} />}
      {data && filtered.length === 0 && (
        <EmptyState
          icon={<History className="h-8 w-8 text-slate-300" />}
          title="No analyses yet"
          hint="Open a workout and run an analysis — it'll be saved here for trend context over time."
        />
      )}
      {filtered.length > 0 && (
        <div className="space-y-2">
          {filtered.map((e) => (
            <MemoryEntryItem key={e.entry_id} entry={e} />
          ))}
        </div>
      )}
    </div>
  )
}
