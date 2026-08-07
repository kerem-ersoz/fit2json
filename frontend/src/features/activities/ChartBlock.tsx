import { useMemo, useState } from 'react'
import { VegaLite } from 'react-vega'
import { usePrefersDarkMode } from '../../lib/usePrefersDarkMode'
import { withReadableLineScales } from './chartSpec'

/* eslint-disable @typescript-eslint/no-explicit-any */

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function objectOrEmpty(value: unknown): Record<string, unknown> {
  return isObject(value) ? value : {}
}

/**
 * Renders one LLM-authored Vega-Lite spec (from a ```fitsift-chart block).
 * Loaded lazily (Vega is heavy) so it only ships when an analysis has a chart.
 * Width is forced to "container" for responsiveness; line-chart Y scales are
 * kept readable without changing explicit domains; remote data is refused.
 */
export default function ChartBlock({ spec }: { spec: string }) {
  const [renderError, setRenderError] = useState<string | null>(null)
  const dark = usePrefersDarkMode()

  const parsed = useMemo(() => {
    try {
      return { obj: JSON.parse(spec) as any, error: null as string | null }
    } catch (e) {
      return { obj: null, error: (e as Error).message }
    }
  }, [spec])

  if (parsed.error || !parsed.obj || typeof parsed.obj !== 'object') {
    return <ChartError message="Couldn't parse this chart." raw={spec} />
  }
  const data = parsed.obj.data
  if (data && typeof data === 'object' && 'url' in data) {
    return <ChartError message="Remote chart data isn't allowed." raw={spec} />
  }
  if (renderError) {
    return <ChartError message="Couldn't render this chart." raw={spec} />
  }

  const normalizedSpec = withReadableLineScales(parsed.obj)
  const authoredConfig = objectOrEmpty(normalizedSpec.config)
  const darkConfig = {
    axis: dark
      ? {
          domainColor: 'rgba(255, 255, 255, 0.34)',
          gridColor: 'rgba(255, 255, 255, 0.14)',
          labelColor: '#cbd5e1',
          tickColor: 'rgba(255, 255, 255, 0.22)',
          titleColor: '#f8fafc',
        }
      : {},
    legend: dark ? { labelColor: '#cbd5e1', titleColor: '#f8fafc' } : {},
    title: dark ? { color: '#f8fafc', subtitleColor: '#94a3b8' } : {},
    view: dark ? { stroke: 'rgba(255, 255, 255, 0.22)' } : {},
  }
  const responsiveSpec: any = {
    $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
    ...normalizedSpec,
    ...(dark ? { background: '#000000' } : {}),
    width: 'container',
    autosize: { type: 'fit', contains: 'padding' },
    config: {
      ...authoredConfig,
      ...darkConfig,
      axis: { ...objectOrEmpty(authoredConfig.axis), ...darkConfig.axis },
      legend: { ...objectOrEmpty(authoredConfig.legend), ...darkConfig.legend },
      title: { ...objectOrEmpty(authoredConfig.title), ...darkConfig.title },
      view: { ...objectOrEmpty(authoredConfig.view), ...darkConfig.view },
    },
  }
  if (typeof responsiveSpec.height !== 'number') responsiveSpec.height = 240

  return (
    <div className="my-4 w-full overflow-hidden rounded-xl border border-divider bg-surface p-2">
      <VegaLite
        spec={responsiveSpec}
        actions={false}
        renderer="svg"
        style={{ width: '100%' }}
        onError={(e) => setRenderError(String(e))}
      />
    </div>
  )
}

function ChartError({ message, raw }: { message: string; raw: string }) {
  return (
    <div className="my-3">
      <div className="mb-1 text-xs font-medium text-warning">{message}</div>
      <pre className="overflow-x-auto rounded-lg bg-code p-3 text-xs text-code-text">{raw}</pre>
    </div>
  )
}
