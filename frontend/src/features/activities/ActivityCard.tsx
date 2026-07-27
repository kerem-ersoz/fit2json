import { Link } from 'react-router-dom'
import { MapPin } from 'lucide-react'
import type { ActivitySummary } from '../../lib/api'
import { sportMeta } from '../../lib/sport'
import {
  formatDate,
  formatDistance,
  formatDuration,
  formatHr,
  formatPaceOrSpeed,
} from '../../lib/format'
import { Card } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="truncate text-sm font-semibold text-slate-900">{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
    </div>
  )
}

export function ActivityCard({ activity }: { activity: ActivitySummary }) {
  const { label, Icon } = sportMeta(activity.sport)
  const m = activity.metrics

  return (
    <Link to={`/activities/${encodeURIComponent(activity.id)}`} className="block">
      <Card className="h-full transition-shadow hover:shadow-md">
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
          <Metric label="Distance" value={formatDistance(m.distance_m)} />
          <Metric label="Time" value={formatDuration(m.duration_s)} />
          <Metric
            label="Pace"
            value={formatPaceOrSpeed(m.avg_speed_mps, activity.sport)}
          />
          <Metric label="Avg HR" value={formatHr(m.avg_hr)} />
        </div>
      </Card>
    </Link>
  )
}
