import { useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { api } from '../lib/api'
import { sportMeta } from '../lib/sport'
import { sortActivities } from '../lib/library'
import { hrMaxProxy } from '../lib/intensity'
import { useWorkoutParams } from '../lib/useWorkoutParams'
import { useCardKeyboardNav } from '../lib/useCardKeyboardNav'
import { WorkoutBrowser } from '../features/analyze/WorkoutBrowser'
import { ConversationPane } from '../features/analyze/ConversationPane'
import { ActivityGridSkeleton } from '../features/activities/ActivityGridSkeleton'
import { EmptyState, ErrorState } from '../components/ui/Feedback'

export function AnalyzePage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['activities'],
    queryFn: api.activities,
  })

  const { search, sport, sort, setParam } = useWorkoutParams()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const searchRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  useCardKeyboardNav(listRef, searchRef)

  const sports = useMemo(() => {
    const set = new Set<string>()
    for (const a of data ?? []) if (a.sport) set.add(a.sport)
    return Array.from(set).sort()
  }, [data])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    const base = (data ?? []).filter((a) => {
      if (sport !== 'all' && a.sport !== sport) return false
      if (!q) return true
      const hay = [a.sport, sportMeta(a.sport).label, a.start_time, a.source_file]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return hay.includes(q)
    })
    return sortActivities(base, sort)
  }, [data, sport, search, sort])

  // Selection persists across filter changes; the conversation sees every selected workout.
  const selectedActivities = useMemo(
    () => (data ?? []).filter((a) => selected.has(a.id)),
    [data, selected],
  )

  const hrMax = useMemo(() => hrMaxProxy(data ?? []), [data])

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const toggleAll = () => {
    const ids = filtered.map((a) => a.id)
    const allSelected = ids.length > 0 && ids.every((id) => selected.has(id))
    setSelected((prev) => {
      const next = new Set(prev)
      if (allSelected) ids.forEach((id) => next.delete(id))
      else ids.forEach((id) => next.add(id))
      return next
    })
  }

  return (
    <div>
      <div className="mb-4 sm:mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Analyze</h1>
        <p className="text-sm text-slate-500">Select workouts, then chat with the model about them.</p>
      </div>

      {isLoading && <ActivityGridSkeleton />}

      {isError && (
        <ErrorState
          message={(error as Error)?.message ?? 'Failed to load activities.'}
          hint="Make sure the FitSift server is running and pointed at a workout library (--library)."
          onRetry={() => refetch()}
        />
      )}

      {data && !isLoading && data.length === 0 && (
        <EmptyState
          icon={<Sparkles className="h-8 w-8 text-slate-300" />}
          title="Nothing to analyze yet"
          hint="Add workouts from the Add tab, then come back to analyze them."
        />
      )}

      {data && !isLoading && data.length > 0 && (
        <div className="lg:grid lg:grid-cols-[1fr_minmax(360px,26rem)] lg:items-start lg:gap-6">
          <WorkoutBrowser
            activities={filtered}
            selectedIds={selected}
            onToggle={toggle}
            onToggleAll={toggleAll}
            listRef={listRef}
            hrMax={hrMax}
            controls={{
              search,
              onSearch: (v) => setParam('q', v, ''),
              sport,
              sports,
              onSport: (v) => setParam('sport', v, 'all'),
              sort,
              onSort: (v) => setParam('sort', v, 'date'),
              searchRef,
            }}
          />
          <div className="mt-6 lg:mt-0 lg:sticky lg:top-8">
            <ConversationPane activities={selectedActivities} onDeselect={toggle} />
          </div>
        </div>
      )}
    </div>
  )
}
