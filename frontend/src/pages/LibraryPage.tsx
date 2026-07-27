import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, ListChecks } from 'lucide-react'
import { api } from '../lib/api'
import { sportMeta } from '../lib/sport'
import { ActivityCard } from '../features/activities/ActivityCard'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/Feedback'

export function LibraryPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['activities'],
    queryFn: api.activities,
  })

  const [sport, setSport] = useState('all')
  const [search, setSearch] = useState('')

  const sports = useMemo(() => {
    const set = new Set<string>()
    for (const a of data ?? []) if (a.sport) set.add(a.sport)
    return Array.from(set).sort()
  }, [data])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return (data ?? []).filter((a) => {
      if (sport !== 'all' && a.sport !== sport) return false
      if (!q) return true
      const hay = [a.sport, sportMeta(a.sport).label, a.start_time, a.source_file]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return hay.includes(q)
    })
  }, [data, sport, search])

  return (
    <div>
      <div className="mb-4 flex flex-col gap-3 sm:mb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Library</h1>
          <p className="text-sm text-slate-500">
            {data ? `${data.length} workout${data.length === 1 ? '' : 's'}` : 'Your workouts'}
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search workouts…"
              className="h-11 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 sm:w-56"
            />
          </div>
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
        </div>
      </div>

      {isLoading && <LoadingState label="Loading your workouts…" />}
      {isError && <ErrorState message={(error as Error)?.message ?? 'Failed to load activities.'} />}

      {data && !isLoading && filtered.length === 0 && (
        <EmptyState
          icon={<ListChecks className="h-8 w-8 text-slate-300" />}
          title={data.length === 0 ? 'No workouts yet' : 'No matching workouts'}
          hint={
            data.length === 0
              ? 'Add workouts from the Add tab, or point the server at an existing library with --library.'
              : 'Try a different sport or search term.'
          }
        />
      )}

      {filtered.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {filtered.map((a) => (
            <ActivityCard key={a.id} activity={a} />
          ))}
        </div>
      )}
    </div>
  )
}
