import { useMemo } from 'react'
import { MarkdownView } from '../../components/ui/Markdown'
import { AnalysisLens } from '../analyze/AnalysisLens'

/**
 * Strips the redundant front-matter-derived header a saved analysis carries — the
 * `# Sport — date` line and the `**Prompt:** …` echo — so the body renders as just the
 * analysis. The prompt is surfaced separately as a small collapsible preview.
 */
function stripEcho(content: string, prompt?: string): string {
  let body = content ?? ''
  body = body.replace(/^\s*#\s+.*(?:\r?\n)+/, '') // "# Sport — date"
  if (prompt) {
    const echo = `**Prompt:** ${prompt}`
    const idx = body.indexOf(echo)
    if (idx !== -1) body = body.slice(0, idx) + body.slice(idx + echo.length)
  }
  body = body.replace(/^\s*\*\*Prompt:\*\*.*(?:\r?\n)+/, '') // fallback if prompt didn't match verbatim
  return body.trim()
}

export function AnalysisView({
  content,
  prompt,
  meta,
  entryId,
}: {
  content: string
  prompt?: string
  meta?: string
  entryId?: string
}) {
  const body = useMemo(() => stripEcho(content, prompt), [content, prompt])
  const preview = prompt ? (prompt.length > 100 ? `${prompt.slice(0, 100)}…` : prompt) : ''

  return (
    <div>
      {(prompt || meta) && (
        <details className="mb-3 rounded-lg border border-slate-100 bg-slate-50/70">
          <summary className="flex cursor-pointer items-center gap-1.5 px-2.5 py-1.5 text-xs text-slate-500">
            <span className="shrink-0 font-medium text-slate-600">Prompt</span>
            {preview && <span className="min-w-0 flex-1 truncate text-slate-400">{preview}</span>}
          </summary>
          <div className="space-y-1 px-2.5 pb-2.5 text-xs text-slate-500">
            {prompt && <p className="whitespace-pre-wrap">{prompt}</p>}
            {meta && <p className="text-slate-400">{meta}</p>}
          </div>
        </details>
      )}
      <AnalysisLens
        surface="inline"
        source={entryId ? { kind: 'entry', entryId } : { kind: 'ephemeral', analysis: body }}
        text={<MarkdownView>{body}</MarkdownView>}
      />
    </div>
  )
}
