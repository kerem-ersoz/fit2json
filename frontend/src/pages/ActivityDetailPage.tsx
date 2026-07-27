import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Download, ExternalLink } from 'lucide-react'
import { api } from '../lib/api'
import { sportMeta } from '../lib/sport'
import { formatCalories, formatDateTime, formatDuration, formatHr } from '../lib/format'
import { useUnits } from '../lib/units'
import { ErrorState, LoadingState } from '../components/ui/Feedback'
import { Card } from '../components/ui/Card'
import { ActivityMap } from '../features/activities/ActivityMap'
import { AnalysisPanel } from '../features/activities/AnalysisPanel'

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
  // Streams are fetched only for the small orientation map (GPS polyline), not charts.
  const streamsQ = useQuery({
    queryKey: ['map', id],
    queryFn: () => api.streams(id, 600),
    enabled: !!id && !!detailQ.data?.has_gps,
  })

  if (detailQ.isLoading) return <LoadingState label="Loading workout…" />
  if (detailQ.isError || !detailQ.data)
    return <ErrorState message={(detailQ.error as Error)?.message ?? 'Failed to load workout.'} />

  const d = detailQ.data
  const { label, Icon } = sportMeta(d.sport)
  const { fmt } = useUnits()
  const m = d.metrics

  const stats: { label: string; value: string }[] = []
  if (m.distance_m != null) stats.push({ label: 'Distance', value: fmt.distance(m.distance_m) })
  if (m.duration_s != null) stats.push({ label: 'Time', value: formatDuration(m.duration_s) })
  if (m.avg_speed_mps != null)
    stats.push({ label: 'Avg Pace', value: fmt.paceOrSpeed(m.avg_speed_mps, d.sport) })
  if (m.avg_hr != null) stats.push({ label: 'Avg HR', value: formatHr(m.avg_hr) })
  if (m.max_hr != null) stats.push({ label: 'Max HR', value: formatHr(m.max_hr) })
  if (m.avg_power_w != null) stats.push({ label: 'Avg Power', value: fmt.power(m.avg_power_w) })
  if (m.ascent_m != null) stats.push({ label: 'Elev Gain', value: fmt.elevation(m.ascent_m) })
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
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
              <Icon className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight sm:text-2xl">{label}</h1>
              <p className="text-sm text-slate-500">{formatDateTime(d.start_time)}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {d.source_ref && (
              <a
                href={d.source_ref.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex min-h-[40px] items-center gap-1.5 rounded-lg bg-brand-600 px-3 text-sm font-medium text-white hover:bg-brand-700"
                title={`Open the original activity on ${d.source_ref.label}`}
              >
                <ExternalLink className="h-4 w-4" />
                View on {d.source_ref.label}
              </a>
            )}
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
      </div>

      {stats.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {stats.map((s) => (
            <Stat key={s.label} label={s.label} value={s.value} />
          ))}
        </div>
      )}

      {/* Analysis is the point of this page — not a rehash of Connect/Strava graphs. */}
      <AnalysisPanel activityId={d.id} />

      {d.has_gps && streamsQ.data && streamsQ.data.latlng.length > 0 && (
        <section>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Route</h2>
            {d.source_ref && (
              <a
                href={d.source_ref.url}
                target="_blank"
                rel="noreferrer"
                className="text-xs font-medium text-brand-700 hover:underline"
              >
                Full map &amp; charts on {d.source_ref.label} →
              </a>
            )}
          </div>
          <ActivityMap positions={streamsQ.data.latlng} />
        </section>
      )}
    </div>
  )
}
