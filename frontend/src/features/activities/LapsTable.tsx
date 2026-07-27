import type { Lap } from '../../lib/api'
import {
  formatDistance,
  formatDuration,
  formatHr,
  formatPaceOrSpeed,
} from '../../lib/format'
import { Card } from '../../components/ui/Card'

function num(v: unknown): number | undefined {
  return typeof v === 'number' ? v : undefined
}

interface Row {
  i: number
  distance?: number
  time?: number
  speed?: number
  hr?: number
  ascent?: number
}

function toRows(laps: Lap[]): Row[] {
  return laps.map((lap, i) => ({
    i: i + 1,
    distance: num(lap.total_distance),
    time: num(lap.total_timer_time) ?? num(lap.total_elapsed_time),
    speed: num(lap.enhanced_avg_speed) ?? num(lap.avg_speed),
    hr: num(lap.avg_heart_rate),
    ascent: num(lap.total_ascent),
  }))
}

function ascent(m?: number) {
  return m != null ? `${Math.round(m)} m` : '—'
}

export function LapsTable({ laps, sport }: { laps: Lap[]; sport?: string | null }) {
  if (!laps.length) return null
  const rows = toRows(laps)

  return (
    <div>
      {/* Desktop / tablet table */}
      <div className="hidden overflow-hidden rounded-xl border border-slate-200 sm:block">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2.5 font-medium">Lap</th>
              <th className="px-4 py-2.5 font-medium">Distance</th>
              <th className="px-4 py-2.5 font-medium">Time</th>
              <th className="px-4 py-2.5 font-medium">Pace</th>
              <th className="px-4 py-2.5 font-medium">Avg HR</th>
              <th className="px-4 py-2.5 font-medium">Ascent</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((r) => (
              <tr key={r.i} className="hover:bg-slate-50">
                <td className="px-4 py-2.5 font-medium">{r.i}</td>
                <td className="px-4 py-2.5">{formatDistance(r.distance)}</td>
                <td className="px-4 py-2.5">{formatDuration(r.time)}</td>
                <td className="px-4 py-2.5">{formatPaceOrSpeed(r.speed, sport)}</td>
                <td className="px-4 py-2.5">{formatHr(r.hr)}</td>
                <td className="px-4 py-2.5">{ascent(r.ascent)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile card-stack (no clipped columns) */}
      <div className="space-y-2 sm:hidden">
        {rows.map((r) => (
          <Card key={r.i} className="p-3">
            <div className="mb-2 text-sm font-semibold">Lap {r.i}</div>
            <div className="grid grid-cols-3 gap-y-2 text-sm">
              <Cell label="Dist" value={formatDistance(r.distance)} />
              <Cell label="Time" value={formatDuration(r.time)} />
              <Cell label="Pace" value={formatPaceOrSpeed(r.speed, sport)} />
              <Cell label="Avg HR" value={formatHr(r.hr)} />
              <Cell label="Ascent" value={ascent(r.ascent)} />
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="text-slate-800">{value}</div>
    </div>
  )
}
