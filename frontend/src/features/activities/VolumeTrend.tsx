import { useMemo } from 'react'
import { clsx } from 'clsx'
import { TrendingDown, TrendingUp } from 'lucide-react'
import type { ActivitySummary } from '../../lib/api'
import { useUnits } from '../../lib/units'
import { weeklyVolume } from '../../lib/library'

/**
 * A compact weekly-distance sparkline (last 8 weeks) with this week's total and the
 * change vs last week. The Library's expressive-data moment — on-brand and quiet.
 */
export function VolumeTrend({ activities }: { activities: ActivitySummary[] }) {
  const { fmt } = useUnits()
  const weeks = useMemo(() => weeklyVolume(activities, 8), [activities])

  const max = Math.max(1, ...weeks.map((w) => w.distanceM))
  const current = weeks[weeks.length - 1]
  const prev = weeks[weeks.length - 2]
  const hasData = weeks.some((w) => w.distanceM > 0)
  if (!hasData) return null

  const delta = prev && prev.distanceM > 0 ? (current.distanceM - prev.distanceM) / prev.distanceM : null
  const weekFmt = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' })

  return (
    <section
      aria-label={`Weekly distance for the last ${weeks.length} weeks`}
      className="rounded-xl border border-divider bg-surface p-4 sm:p-5"
    >
      <div className="mb-3 flex items-end justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-strong">This week</h2>
          <p className="mt-0.5 text-2xl font-bold tabular-nums tracking-tight text-ink">
            {fmt.distance(current?.distanceM ?? 0)}
          </p>
        </div>
        {delta !== null && (
          <span
            className={clsx(
              'inline-flex shrink-0 items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium tabular-nums',
              delta >= 0
                ? 'border-accent-divider bg-accent-tint text-accent-strong'
                : 'border-divider-soft bg-surface-subtle text-copy',
            )}
          >
            {delta >= 0 ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
            {Math.abs(Math.round(delta * 100))}% vs last week
          </span>
        )}
      </div>

      <div className="flex h-16 items-stretch gap-1.5">
        {weeks.map((w, i) => {
          const isCurrent = i === weeks.length - 1
          const pct = (w.distanceM / max) * 100
          const height = w.distanceM > 0 ? Math.max(6, pct) : 2
          return (
            <div
              key={w.weekStart}
              className="flex flex-1 flex-col justify-end"
              title={`Week of ${weekFmt.format(new Date(w.weekStart))} · ${fmt.distance(w.distanceM)}`}
            >
              <div
                className={clsx(
                  'w-full rounded-t',
                  isCurrent ? 'bg-action' : w.distanceM > 0 ? 'bg-accent-muted' : 'bg-divider',
                )}
                style={{ height: `${height}%` }}
              />
            </div>
          )
        })}
      </div>
      <p className="mt-2 text-xs text-faint">Last {weeks.length} weeks</p>
    </section>
  )
}
