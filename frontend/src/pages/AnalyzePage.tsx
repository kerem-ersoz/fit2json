import { useMemo, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MessageSquare, Sparkles } from 'lucide-react'
import { api } from '../lib/api'
import { sportMeta } from '../lib/sport'
import { sortActivities } from '../lib/library'
import { hrMaxProxy } from '../lib/intensity'
import { useWorkoutParams } from '../lib/useWorkoutParams'
import { useCardKeyboardNav } from '../lib/useCardKeyboardNav'
import { useChat } from '../features/chat/ChatProvider'
import { WorkoutBrowser } from '../features/analyze/WorkoutBrowser'
import { ActivityGridSkeleton } from '../features/activities/ActivityGridSkeleton'
import { EmptyState, ErrorState } from '../components/ui/Feedback'
import { Button } from '../components/ui/Button'

export function AnalyzePage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['activities'],
    queryFn: api.activities,
  })

  const { search, sport, sort, setParam } = useWorkoutParams()
  // Selection lives in the chat: whatever is selected here is attached to the active
  // conversation, so the chat pane (and any resumed chat) stays in sync.
  const { activityIds, setActivityIds, toggleActivity, setOpen } = useChat()
  const searchRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  useCardKeyboardNav(listRef, searchRef)

  const selected = useMemo(() => new Set(activityIds), [activityIds])

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

  // Count only selections that still exist in the library (a resumed chat may reference
  // workouts that are no longer present).
  const selectedCount = useMemo(
    () => (data ?? []).filter((a) => selected.has(a.id)).length,
    [data, selected],
  )

  const hrMax = useMemo(() => hrMaxProxy(data ?? []), [data])

  const toggleAll = () => {
    const ids = filtered.map((a) => a.id)
    const next = new Set(activityIds)
    const allSelected = ids.length > 0 && ids.every((id) => next.has(id))
    if (allSelected) ids.forEach((id) => next.delete(id))
    else ids.forEach((id) => next.add(id))
    setActivityIds([...next])
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3 sm:mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Analyze</h1>
          <p className="text-sm text-slate-500">
            Select workouts, then chat about them. Conversations are saved and resumable.
          </p>
        </div>
        <Button
          variant={selectedCount > 0 ? 'primary' : 'secondary'}
          onClick={() => setOpen(true)}
          aria-haspopup="dialog"
        >
          <MessageSquare className="h-4 w-4" />
          {selectedCount > 0
            ? `Chat about ${selectedCount} ${selectedCount === 1 ? 'workout' : 'workouts'}`
            : 'Open chat'}
        </Button>
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
        <WorkoutBrowser
          activities={filtered}
          selectedIds={selected}
          onToggle={toggleActivity}
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
      )}
    </div>
  )
}
