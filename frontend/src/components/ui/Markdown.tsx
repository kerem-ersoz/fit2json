import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'

/**
 * Languages reserved for LLM-authored visuals on the analysis page.
 *
 * Roadmap: the analysis prompt will invite the model to emit bespoke charts
 * (e.g. HR-vs-pace scatter, HR drift, zone distribution, week-over-week trends)
 * as fenced ```fitsift-chart / ```vega-lite blocks. The `pre` override below is
 * the single drop-in point — swap ChartPlaceholder for a real renderer
 * (e.g. Vega-Lite via react-vega) and nothing else needs to change.
 */
const CHART_LANGUAGES = new Set(['fitsift-chart', 'vega-lite', 'vegalite'])

function ChartPlaceholder({ lang }: { lang: string; spec: string }) {
  return (
    <div className="my-3 rounded-lg border border-dashed border-brand-300 bg-brand-50/60 p-3 text-xs font-medium text-brand-700">
      Visual ({lang}) — chart rendering coming soon.
    </div>
  )
}

/* eslint-disable @typescript-eslint/no-explicit-any */
const components: Components = {
  pre({ children }) {
    const child: any = Array.isArray(children) ? children[0] : children
    const className: string = child?.props?.className || ''
    const lang = /language-([\w-]+)/.exec(className)?.[1]
    if (lang && CHART_LANGUAGES.has(lang)) {
      return <ChartPlaceholder lang={lang} spec={String(child?.props?.children ?? '')} />
    }
    return <pre>{children}</pre>
  },
}
/* eslint-enable @typescript-eslint/no-explicit-any */

export function MarkdownView({ children }: { children: string }) {
  return (
    <div className="prose prose-sm prose-slate max-w-none prose-pre:bg-slate-900 prose-pre:text-slate-100 prose-headings:font-semibold prose-a:text-brand-700">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
