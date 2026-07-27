import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Download } from 'lucide-react'
import { api } from '../lib/api'
import { sportMeta } from '../lib/sport'
import {
  formatCalories,
  formatDateTime,
  formatDistance,
  formatDuration,
  formatElevation,
  formatHr,
  formatPaceOrSpeed,
  formatPower,
} from '../lib/format'
import { ErrorState, LoadingState } from '../components/ui/Feedback'
import { Card } from '../components/ui/Card'
import { ActivityCharts } from '../features/activities/ActivityCharts'
import { ActivityMap } from '../features/activities/ActivityMap'
import { LapsTable } from '../features/activities/LapsTable'

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card className="p-3">
      <div className="text-lg font-bold leading-tight text-slate-900">{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
    </Card>
  )
}

export function ActivityDetailPage() {
  const { id = '' } = useParams()
  const detailQ = useQuery({ queryKey: ['activity', id], queryFn: () => api.activity(id), enabled: !!id })
  const streamsQ = useQuery({ queryKey: ['streams', id], queryFn: () => api.streams(id), enabled: !!id })
  const lapsQ = useQuery({ queryKey: ['laps', id], queryFn: () => api.laps(id), enabled: !!id })

  if (detailQ.isLoading) return <LoadingState label="Loading workout…" />
  if (detailQ.isError || !detailQ.data)
    return <ErrorState message={(detailQ.error as Error)?.message ?? 'Failed to load workout.'} />

  const d = detailQ.data
  const { label, Icon } = sportMeta(d.sport)
  const m = d.metrics

  const stats: { label: string; value: string }[] = []
  if (m.distance_m != null) stats.push({ label: 'Distance', value: formatDistance(m.distance_m) })
  if (m.duration_s != null) stats.push({ label: 'Time', value: formatDuration(m.duration_s) })
  if (m.avg_speed_mps != null)
    stats.push({ label: 'Avg Pace', value: formatPaceOrSpeed(m.avg_speed_mps, d.sport) })
  if (m.avg_hr != null) stats.push({ label: 'Avg HR', value: formatHr(m.avg_hr) })
  if (m.max_hr != null) stats.push({ label: 'Max HR', value: formatHr(m.max_hr) })
  if (m.avg_power_w != null) stats.push({ label: 'Avg Power', value: formatPower(m.avg_power_w) })
  if (m.ascent_m != null) stats.push({ label: 'Elev Gain', value: formatElevation(m.ascent_m) })
  if (m.total_calories != null)
    stats.push({ label: 'Calories', value: formatCalories(m.total_calories) })

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/"
          className="mb-3 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-800"
        >
          <ArrowLeft className="h-4 w-4" /> Library
        </Link>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
              <Icon className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight sm:text-2xl">{label}</h1>
              <p className="text-sm text-slate-500">{formatDateTime(d.start_time)}</p>
            </div>
          </div>
          <a
            href={api.rawUrl(d.id)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex min-h-[40px] items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-600 hover:bg-slate-50"
            title="Download lossless JSON"
          >
            <Download className="h-4 w-4" />
            <span className="hidden sm:inline">Raw JSON</span>
          </a>
        </div>
      </div>

      {stats.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {stats.map((s) => (
            <Stat key={s.label} label={s.label} value={s.value} />
          ))}
        </div>
      )}

      {d.has_gps && streamsQ.data && streamsQ.data.latlng.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Route</h2>
          <ActivityMap positions={streamsQ.data.latlng} />
        </section>
      )}

      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Charts</h2>
        {streamsQ.isLoading && <LoadingState label="Loading charts…" />}
        {streamsQ.data && streamsQ.data.point_count > 0 ? (
          <ActivityCharts streams={streamsQ.data} />
        ) : (
          !streamsQ.isLoading && (
            <p className="text-sm text-slate-400">No per-second data for this workout.</p>
          )
        )}
      </section>

      {lapsQ.data && lapsQ.data.laps.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Laps
          </h2>
          <LapsTable laps={lapsQ.data.laps} sport={d.sport} />
        </section>
      )}
    </div>
  )
}
