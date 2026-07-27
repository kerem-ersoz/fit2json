import { useMemo, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ListChecks, X } from 'lucide-react'
import { api } from '../lib/api'
import { sportMeta } from '../lib/sport'
import { groupByDate, sortActivities } from '../lib/library'
import { useWorkoutParams } from '../lib/useWorkoutParams'
import { useCardKeyboardNav } from '../lib/useCardKeyboardNav'
import { ActivityCard } from '../features/activities/ActivityCard'
import { LatestActivityHero } from '../features/activities/LatestActivityHero'
import { VolumeTrend } from '../features/activities/VolumeTrend'
import { WorkoutControls } from '../features/activities/WorkoutControls'
import { ActivityGridSkeleton } from '../features/activities/ActivityGridSkeleton'
import { Button } from '../components/ui/Button'
import { EmptyState, ErrorState } from '../components/ui/Feedback'

export function LibraryPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['activities'],
    queryFn: api.activities,
  })

  const { search, sport, sort, isFiltering, setParam, clearFilters } = useWorkoutParams()
  const searchRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
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

  // Hero, trend, and date grouping only make sense in the default newest-first, unfiltered view.
  const showFeatured = !isFiltering && sort === 'date'

  const subtitle = !data
    ? 'Your workouts'
    : isFiltering
      ? `${filtered.length} of ${data.length} workout${data.length === 1 ? '' : 's'}`
      : `${data.length} workout${data.length === 1 ? '' : 's'}`

  return (
    <div>
      <div className="mb-4 flex flex-col gap-3 sm:mb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Library</h1>
          <p className="text-sm text-slate-500">{subtitle}</p>
        </div>
        <WorkoutControls
          search={search}
          onSearch={(v) => setParam('q', v, '')}
          sport={sport}
          sports={sports}
          onSport={(v) => setParam('sport', v, 'all')}
          sort={sort}
          onSort={(v) => setParam('sort', v, 'date')}
          searchRef={searchRef}
        />
      </div>

      {isLoading && <ActivityGridSkeleton />}

      {isError && (
        <ErrorState
          message={(error as Error)?.message ?? 'Failed to load activities.'}
          hint="Make sure the FitSift server is running and pointed at a workout library (--library)."
          onRetry={() => refetch()}
        />
      )}

      {data && !isLoading && filtered.length === 0 &&
        (isFiltering ? (
          <EmptyState
            icon={<ListChecks className="h-8 w-8 text-slate-300" />}
            title="No matching workouts"
            hint="Try a different sport or search term."
            action={
              <Button variant="secondary" onClick={clearFilters}>
                <X className="h-4 w-4" /> Clear filters
              </Button>
            }
          />
        ) : (
          <EmptyState
            icon={<ListChecks className="h-8 w-8 text-slate-300" />}
            title="No workouts yet"
            hint="Add workouts from the Add tab, or point the server at an existing library with --library."
          />
        ))}

      {data && !isLoading && filtered.length > 0 && (
        <div ref={listRef} className="space-y-6">
          {showFeatured ? (
            <>
              {data.length >= 3 && <VolumeTrend activities={data} />}
              <LatestActivityHero activity={filtered[0]} />
              {groupByDate(filtered.slice(1)).map((group) => (
                <section key={group.key} className="space-y-3">
                  <div className="flex items-baseline justify-between">
                    <h2 className="text-sm font-semibold text-slate-700">{group.label}</h2>
                    <span className="text-xs tabular-nums text-slate-400">{group.items.length}</span>
                  </div>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {group.items.map((a) => (
                      <ActivityCard key={a.id} activity={a} />
                    ))}
                  </div>
                </section>
              ))}
            </>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {filtered.map((a) => (
                <ActivityCard key={a.id} activity={a} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
