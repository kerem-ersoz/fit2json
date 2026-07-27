import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Sparkles, Square } from 'lucide-react'
import { api, streamAnalyze } from '../../lib/api'
import { Button } from '../../components/ui/Button'
import { Card, CardBody } from '../../components/ui/Card'
import { MarkdownView } from '../../components/ui/Markdown'
import { formatDateTime } from '../../lib/format'

const SUGGESTIONS = [
  "Give me a coach's summary of this workout.",
  'Analyze my pacing and heart-rate strategy.',
  'Chart my time in each heart-rate zone.',
  'Any signs of fatigue or overreaching here?',
]

function backendOptions(copilot: boolean) {
  const opts = [
    { v: 'ollama', label: 'Ollama (local)' },
    { v: 'lmstudio', label: 'LM Studio (local)' },
  ]
  if (copilot) opts.unshift({ v: 'copilot', label: 'Copilot CLI' })
  return opts
}

export function AnalysisPanel({ activityId }: { activityId: string }) {
  const queryClient = useQueryClient()
  const { data: config } = useQuery({ queryKey: ['config'], queryFn: api.config })
  const analysesQ = useQuery({
    queryKey: ['analyses', activityId],
    queryFn: () => api.analyses(activityId),
  })

  const [prompt, setPrompt] = useState('')
  const [backend, setBackend] = useState<string>('')
  const [running, setRunning] = useState(false)
  const [output, setOutput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!backend && config?.backends.default) setBackend(config.backends.default)
  }, [config, backend])

  useEffect(() => () => abortRef.current?.abort(), [])

  const run = async () => {
    if (!prompt.trim() || running) return
    setRunning(true)
    setError(null)
    setOutput('')
    const controller = new AbortController()
    abortRef.current = controller
    await streamAnalyze(
      { activity_id: activityId, prompt, backend: backend || undefined },
      {
        onDelta: (text) => setOutput((o) => o + text),
        onDone: (info) => {
          setRunning(false)
          if (info.saved) {
            setOutput('')
            queryClient.invalidateQueries({ queryKey: ['analyses', activityId] })
          }
        },
        onError: (msg) => {
          setRunning(false)
          setError(msg)
        },
      },
      controller.signal,
    )
  }

  const stop = () => {
    abortRef.current?.abort()
    setRunning(false)
  }

  const options = backendOptions(config?.backends.copilot ?? false)
  const past = analysesQ.data?.analyses ?? []

  return (
    <section className="space-y-4">
      <Card>
        <CardBody className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
              <Sparkles className="h-5 w-5 text-brand-600" /> Analyze this workout
            </h2>
            <select
              value={backend}
              onChange={(e) => setBackend(e.target.value)}
              disabled={running}
              className="h-9 rounded-lg border border-slate-200 bg-white px-2 text-xs focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              aria-label="Analysis backend"
            >
              {options.map((o) => (
                <option key={o.v} value={o.v}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Ask a coaching question about this workout…"
            rows={3}
            className="w-full resize-y rounded-lg border border-slate-200 p-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />

          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setPrompt(s)}
                disabled={running}
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600 hover:bg-slate-100 disabled:opacity-50"
              >
                {s}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3">
            {running ? (
              <Button variant="secondary" onClick={stop}>
                <Square className="h-4 w-4" /> Stop
              </Button>
            ) : (
              <Button onClick={run} disabled={!prompt.trim()}>
                <Sparkles className="h-4 w-4" /> Analyze
              </Button>
            )}
            {running && (
              <span className="flex items-center gap-1.5 text-sm text-slate-500">
                <Loader2 className="h-4 w-4 animate-spin" /> Thinking…
              </span>
            )}
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {(output || running) && (
            <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
              {output ? (
                <MarkdownView>{output}</MarkdownView>
              ) : (
                <p className="text-sm text-slate-400">Waiting for the model…</p>
              )}
            </div>
          )}
        </CardBody>
      </Card>

      <div>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Past analyses{past.length ? ` (${past.length})` : ''}
        </h3>
        {analysesQ.isLoading ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : past.length === 0 ? (
          <p className="text-sm text-slate-400">
            No analyses yet. Ask a question above to create your first one.
          </p>
        ) : (
          <div className="space-y-2">
            {past.map((a) => (
              <details key={a.entry_id} className="group rounded-xl border border-slate-200 bg-white">
                <summary className="flex cursor-pointer items-center justify-between gap-3 p-4 text-sm">
                  <span className="min-w-0 flex-1 truncate font-medium text-slate-800">
                    {a.prompt || 'Analysis'}
                  </span>
                  <span className="shrink-0 text-xs text-slate-400">
                    {formatDateTime(a.created_at)}
                  </span>
                </summary>
                <div className="border-t border-slate-100 p-4">
                  <div className="mb-2 text-xs text-slate-400">
                    {a.backend}
                    {a.model ? ` · ${a.model}` : ''}
                  </div>
                  <MarkdownView>{a.content ?? ''}</MarkdownView>
                </div>
              </details>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
