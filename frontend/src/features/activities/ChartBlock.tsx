import { useMemo, useState } from 'react'
import { VegaLite } from 'react-vega'

/* eslint-disable @typescript-eslint/no-explicit-any */

/**
 * Renders one LLM-authored Vega-Lite spec (from a ```fitsift-chart block).
 * Loaded lazily (Vega is heavy) so it only ships when an analysis has a chart.
 * Width is forced to "container" for responsiveness; remote data is refused.
 */
export default function ChartBlock({ spec }: { spec: string }) {
  const [renderError, setRenderError] = useState<string | null>(null)

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

  const responsiveSpec: any = {
    $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
    ...parsed.obj,
    width: 'container',
    autosize: { type: 'fit', contains: 'padding' },
  }
  if (typeof responsiveSpec.height !== 'number') responsiveSpec.height = 240

  return (
    <div className="my-4 w-full overflow-hidden rounded-xl border border-slate-200 bg-white p-2">
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
      <div className="mb-1 text-xs font-medium text-amber-600">{message}</div>
      <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">{raw}</pre>
    </div>
  )
}
