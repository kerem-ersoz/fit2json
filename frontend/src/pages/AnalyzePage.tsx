import { useQuery } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { api } from '../lib/api'
import { ActivityCard } from '../features/activities/ActivityCard'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/Feedback'

export function AnalyzePage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['activities'],
    queryFn: api.activities,
  })

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Analyze</h1>
      <p className="mb-4 text-sm text-slate-500">
        Open a workout to ask coaching questions and get a saved, streaming analysis.
      </p>

      {isLoading && <LoadingState label="Loading your workouts…" />}
      {isError && <ErrorState message={(error as Error)?.message ?? 'Failed to load activities.'} />}
      {data && data.length === 0 && (
        <EmptyState
          icon={<Sparkles className="h-8 w-8 text-slate-300" />}
          title="Nothing to analyze yet"
          hint="Add workouts from the Add tab, then open one to analyze it."
        />
      )}
      {data && data.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {data.map((a) => (
            <ActivityCard key={a.id} activity={a} />
          ))}
        </div>
      )}
    </div>
  )
}
