import { Skeleton } from '../../components/ui/Skeleton'

/** Loading placeholder that mirrors the ActivityCard grid. Shared by Library and Analyze. */
export function ActivityGridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2" aria-hidden>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-xl border border-divider bg-surface p-4">
          <div className="flex items-center gap-3 border-b border-divider-soft pb-4">
            <Skeleton className="h-11 w-11 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-3 w-32" />
            </div>
          </div>
          <div className="grid grid-cols-4 gap-3 pt-4">
            {Array.from({ length: 4 }).map((_, j) => (
              <div key={j} className="space-y-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-2 w-3/4" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
