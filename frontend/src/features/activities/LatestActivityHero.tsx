import { Link } from 'react-router-dom'
import { MapPin } from 'lucide-react'
import type { ActivitySummary } from '../../lib/api'
import { sportMeta } from '../../lib/sport'
import { formatDateTime, formatDuration, isPaceSport } from '../../lib/format'
import { useUnits } from '../../lib/units'
import { Badge } from '../../components/ui/Badge'

/**
 * The one "lit dial" of the Library: the most recent workout, promoted to a full-width
 * hero with a larger readout. Restrained by default, expressive where it counts.
 */
export function LatestActivityHero({ activity }: { activity: ActivitySummary }) {
  const { label, Icon } = sportMeta(activity.sport)
  const { fmt } = useUnits()
  const m = activity.metrics
  const metrics = [
    { label: 'Distance', value: fmt.distance(m.distance_m) },
    { label: 'Time', value: formatDuration(m.duration_s) },
    { label: isPaceSport(activity.sport) ? 'Pace' : 'Speed', value: fmt.paceOrSpeed(m.avg_speed_mps, activity.sport) },
    { label: 'Avg HR', value: fmt.hr(m.avg_hr) },
  ]

  return (
    <Link
      to={`/activities/${encodeURIComponent(activity.id)}`}
      data-activity-card
      aria-label={`Latest workout: ${label}, ${formatDateTime(activity.start_time)}`}
      className="group block rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
    >
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow group-hover:shadow-md sm:p-6">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
              <Icon className="h-7 w-7" />
            </div>
            <div className="min-w-0">
              <div className="mb-1 flex items-center gap-2">
                <Badge className="bg-brand-600 text-white">Latest</Badge>
                {activity.has_gps && (
                  <Badge className="bg-brand-50 text-brand-700">
                    <MapPin className="h-3 w-3" /> GPS
                  </Badge>
                )}
              </div>
              <h2 className="truncate text-xl font-bold tracking-tight text-slate-900">{label}</h2>
              <p className="truncate text-sm text-slate-500">{formatDateTime(activity.start_time)}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-x-8 gap-y-3 sm:flex sm:gap-8">
            {metrics.map((mt) => (
              <div key={mt.label} className="min-w-0">
                <div className="truncate text-lg font-semibold tabular-nums text-slate-900">{mt.value}</div>
                <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{mt.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Link>
  )
}
