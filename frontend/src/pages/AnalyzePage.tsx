import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Paperclip, Sparkles } from 'lucide-react'
import { api } from '../lib/api'
import { sportMeta } from '../lib/sport'
import { sortActivities } from '../lib/library'
import { hrMaxProxy } from '../lib/intensity'
import { useWorkoutParams } from '../lib/useWorkoutParams'
import { useCardKeyboardNav } from '../lib/useCardKeyboardNav'
import { useChat } from '../features/chat/ChatProvider'
import { ChatWorkspace } from '../features/chat/ChatDock'
import { WorkoutBrowser } from '../features/analyze/WorkoutBrowser'
import { EmptyState, ErrorState } from '../components/ui/Feedback'
import { Sheet } from '../components/ui/Sheet'

export function AnalyzePage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['activities'],
    queryFn: api.activities,
  })

  const { search, sport, sort, setParam } = useWorkoutParams()
  // Selection lives in the chat: whatever is selected here is attached to the active
  // conversation, so the chat pane (and any resumed chat) stays in sync.
  const { activityIds, setActivityIds, toggleActivity, setOpen } = useChat()
  const [contextOpen, setContextOpen] = useState(false)
  const searchRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  useCardKeyboardNav(listRef, searchRef, contextOpen)

  useEffect(() => {
    setOpen(false)
  }, [setOpen])

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
    <div className="flex h-full min-h-0 flex-col overflow-hidden overscroll-none">
      <h1 className="sr-only">Analyze</h1>
      <ChatWorkspace
        className="min-h-0 flex-1"
        contextCount={selectedCount}
        contextOpen={contextOpen}
        onOpenContext={() => setContextOpen(true)}
      />

      {contextOpen && (
        <Sheet
          title="Workout context"
          subtitle={
            selectedCount > 0
              ? `${selectedCount} ${selectedCount === 1 ? 'workout' : 'workouts'} attached`
              : 'Choose workouts to focus the conversation'
          }
          icon={
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent-tint text-accent-strong">
              <Paperclip className="h-4 w-4" />
            </span>
          }
          onClose={() => setContextOpen(false)}
          contentClassName="min-h-0 flex-1 overflow-hidden bg-surface-muted p-4"
        >
          {isLoading && <ContextSkeleton />}

          {isError && (
            <ErrorState
              message={(error as Error)?.message ?? 'Failed to load activities.'}
              hint="Make sure the FitSift server is running and pointed at a workout library (--library)."
              onRetry={() => refetch()}
            />
          )}

          {data && !isLoading && data.length === 0 && (
            <EmptyState
              icon={<Sparkles className="h-8 w-8 text-disabled" />}
              title="No workouts yet"
              hint="You can still ask general questions, or add workouts from the Add tab."
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
              surface="sheet"
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
        </Sheet>
      )}
    </div>
  )
}

function ContextSkeleton() {
  return (
    <div className="rounded-xl border border-divider bg-surface p-4" aria-label="Loading workouts">
      <div className="animate-pulse space-y-3">
        <div className="h-9 rounded-lg bg-skeleton" />
        <div className="h-7 w-2/3 rounded bg-skeleton" />
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="flex items-center gap-3 border-t border-divider-soft pt-3">
            <div className="h-8 w-8 rounded-full bg-skeleton" />
            <div className="flex-1 space-y-2">
              <div className="h-3 rounded bg-skeleton" />
              <div className="h-2.5 w-2/3 rounded bg-skeleton" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
