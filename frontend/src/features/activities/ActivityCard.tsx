import { Link } from 'react-router-dom'
import { MapPin } from 'lucide-react'
import type { ActivitySummary } from '../../lib/api'
import { sportMeta } from '../../lib/sport'
import { formatDate, formatDuration, formatHr } from '../../lib/format'
import { useUnits } from '../../lib/units'
import { Card } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="truncate text-sm font-semibold tabular-nums text-slate-900">{value}</div>
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  )
}

export function ActivityCard({ activity, linkHash }: { activity: ActivitySummary; linkHash?: string }) {
  const { label, Icon } = sportMeta(activity.sport)
  const { fmt } = useUnits()
  const m = activity.metrics

  return (
    <Link
      to={`/activities/${encodeURIComponent(activity.id)}${linkHash ? `#${linkHash}` : ''}`}
      data-activity-card
      className="group block rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
    >
      <Card className="h-full transition-shadow group-hover:shadow-md">
        <div className="flex items-center gap-3 border-b border-slate-100 p-4">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
            <Icon className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate font-semibold text-slate-900">{label}</span>
              {activity.has_gps && (
                <Badge className="bg-brand-50 text-brand-700">
                  <MapPin className="h-3 w-3" /> GPS
                </Badge>
              )}
            </div>
            <div className="truncate text-sm text-slate-500">
              {formatDate(activity.start_time)}
            </div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-4">
          <Metric label="Distance" value={fmt.distance(m.distance_m)} />
          <Metric label="Time" value={formatDuration(m.duration_s)} />
          <Metric
            label="Pace"
            value={fmt.paceOrSpeed(m.avg_speed_mps, activity.sport)}
          />
          <Metric label="Avg HR" value={formatHr(m.avg_hr)} />
        </div>
      </Card>
    </Link>
  )
}
