import { useEffect, useRef } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'

export interface ChartSeries {
  label: string
  values: (number | null)[]
  stroke: string
  fill?: string
  unit?: string
}

interface Props {
  x: number[] // elapsed seconds (monotonic)
  series: ChartSeries[]
  height?: number
}

function fmtClock(sec: number): string {
  const s = Math.max(0, Math.round(sec))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = s % 60
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}`
  return `${m}:${String(ss).padStart(2, '0')}`
}

/**
 * Thin React wrapper around uPlot. Handles responsive width via ResizeObserver
 * (important for mobile) and rebuilds the chart when data changes.
 */
export function UPlotChart({ x, series, height = 190 }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const data: uPlot.AlignedData = [x, ...series.map((s) => s.values)]

    const opts: uPlot.Options = {
      width: el.clientWidth || 600,
      height,
      cursor: { drag: { x: true, y: false }, points: { size: 6 } },
      legend: { show: true },
      scales: { x: { time: false } },
      axes: [
        {
          values: (_u, vals) => vals.map((v) => fmtClock(v as number)),
          grid: { show: true, stroke: '#eef2f7' },
          ticks: { stroke: '#e2e8f0' },
          stroke: '#94a3b8',
          size: 36,
        },
        {
          grid: { show: true, stroke: '#eef2f7' },
          ticks: { stroke: '#e2e8f0' },
          stroke: '#94a3b8',
          size: 46,
        },
      ],
      series: [
        { label: 'time', value: (_u, v) => (v == null ? '' : fmtClock(v)) },
        ...series.map((s) => ({
          label: s.unit ? `${s.label} (${s.unit})` : s.label,
          stroke: s.stroke,
          fill: s.fill,
          width: 1.5,
          points: { show: false },
          spanGaps: false,
        })),
      ],
    }

    const chart = new uPlot(opts, data, el)
    const ro = new ResizeObserver(() => {
      chart.setSize({ width: el.clientWidth || 600, height })
    })
    ro.observe(el)

    return () => {
      ro.disconnect()
      chart.destroy()
    }
  }, [x, series, height])

  return <div ref={ref} className="w-full" />
}
