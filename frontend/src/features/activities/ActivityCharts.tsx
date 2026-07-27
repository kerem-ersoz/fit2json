import type { Streams } from '../../lib/api'
import { UPlotChart, type ChartSeries } from './UPlotChart'
import { Card } from '../../components/ui/Card'

interface Style {
  label: string
  stroke: string
  fill?: string
  unit?: string
  transform?: (v: number) => number
}

const SERIES_STYLE: Record<string, Style> = {
  heart_rate: { label: 'Heart rate', stroke: '#ef4444', fill: 'rgba(239,68,68,0.08)' },
  speed: {
    label: 'Speed',
    stroke: '#0ea5e9',
    fill: 'rgba(14,165,233,0.08)',
    unit: 'km/h',
    transform: (v) => v * 3.6,
  },
  power: { label: 'Power', stroke: '#f59e0b', fill: 'rgba(245,158,11,0.08)' },
  cadence: { label: 'Cadence', stroke: '#8b5cf6' },
  altitude: { label: 'Elevation', stroke: '#10b981', fill: 'rgba(16,185,129,0.10)' },
  temperature: { label: 'Temperature', stroke: '#64748b' },
}

const ORDER = ['heart_rate', 'speed', 'power', 'cadence', 'altitude', 'temperature']

export function ActivityCharts({ streams }: { streams: Streams }) {
  if (!streams.point_count) return null

  const hasTime = streams.time_s.every((v) => typeof v === 'number')
  const x = hasTime
    ? (streams.time_s as number[])
    : streams.time_s.map((_, i) => i)

  const names = ORDER.filter((k) => streams.series[k])
  if (names.length === 0) return null

  return (
    <div className="space-y-4">
      {names.map((name) => {
        const s = streams.series[name]
        const style = SERIES_STYLE[name] ?? { label: name, stroke: '#059669' }
        const values = style.transform
          ? s.values.map((v) => (v == null ? null : style.transform!(v)))
          : s.values
        const chartSeries: ChartSeries[] = [
          {
            label: style.label,
            values,
            stroke: style.stroke,
            fill: style.fill,
            unit: style.unit ?? s.unit,
          },
        ]
        return (
          <Card key={name} className="p-3 sm:p-4">
            <div className="mb-1 px-1 text-sm font-semibold text-slate-700">{style.label}</div>
            <UPlotChart x={x} series={chartSeries} height={180} />
          </Card>
        )
      })}
    </div>
  )
}
