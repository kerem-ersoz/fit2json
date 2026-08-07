import { lazy, Suspense } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'

/**
 * Languages reserved for LLM-authored visuals on the analysis page.
 *
 * The analysis prompt invites the model to emit bespoke charts (HR-vs-pace
 * scatter, HR/pace decoupling, time-in-zone, week-over-week load) as fenced
 * ```fitsift-chart / ```vega-lite blocks containing a Vega-Lite spec. The `pre`
 * override routes those to a lazily-loaded Vega renderer; everything else is
 * normal markdown.
 */
const CHART_LANGUAGES = new Set(['fitsift-chart', 'vega-lite', 'vegalite'])

const ChartBlock = lazy(() => import('../../features/activities/ChartBlock'))

function codeText(children: unknown): string {
  if (Array.isArray(children)) return children.map(codeText).join('')
  if (children == null) return ''
  return String(children)
}

/* eslint-disable @typescript-eslint/no-explicit-any */
const components: Components = {
  pre({ children }) {
    const child: any = Array.isArray(children) ? children[0] : children
    const className: string = child?.props?.className || ''
    const lang = /language-([\w-]+)/.exec(className)?.[1]
    if (lang && CHART_LANGUAGES.has(lang)) {
      const spec = codeText(child?.props?.children)
      return (
        <Suspense fallback={<div className="my-3 text-xs text-faint">Rendering chart…</div>}>
          <ChartBlock spec={spec} />
        </Suspense>
      )
    }
    return <pre>{children}</pre>
  },
}
/* eslint-enable @typescript-eslint/no-explicit-any */

export function MarkdownView({ children }: { children: string }) {
  return (
    <div className="prose prose-sm prose-slate max-w-none prose-pre:bg-code prose-pre:text-code-text prose-headings:font-semibold prose-a:text-accent-strong dark:prose-invert">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
