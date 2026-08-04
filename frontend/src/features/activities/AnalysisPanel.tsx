import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Sparkles, Square } from 'lucide-react'
import { api, streamAnalyze, type ThinkingInfo } from '../../lib/api'
import { Button } from '../../components/ui/Button'
import { Card, CardBody } from '../../components/ui/Card'
import { MarkdownView } from '../../components/ui/Markdown'
import { ThinkingDisclosure } from '../../components/ui/ThinkingDisclosure'
import { AnalysisView } from './AnalysisView'
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

// Copilot CLI reasoning effort. '' = leave the model/CLI default untouched.
const EFFORT_OPTIONS = [
  { v: '', label: 'Reasoning: default' },
  { v: 'low', label: 'Reasoning: low' },
  { v: 'medium', label: 'Reasoning: medium' },
  { v: 'high', label: 'Reasoning: high' },
  { v: 'max', label: 'Reasoning: max' },
]

export function AnalysisPanel({ activityId }: { activityId: string }) {
  const queryClient = useQueryClient()
  const { data: config } = useQuery({ queryKey: ['config'], queryFn: api.config })
  const analysesQ = useQuery({
    queryKey: ['analyses', activityId],
    queryFn: () => api.analyses(activityId),
  })

  const [prompt, setPrompt] = useState('')
  const [backend, setBackend] = useState<string>('')
  const [effort, setEffort] = useState<string>('')
  const [running, setRunning] = useState(false)
  const [output, setOutput] = useState('')
  const [thinking, setThinking] = useState<ThinkingInfo>({ summary: '', text: '' })
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const committedOutputRef = useRef('')
  const streamBackendRef = useRef('')
  const sectionRef = useRef<HTMLElement>(null)
  const promptRef = useRef<HTMLTextAreaElement>(null)
  const [openIds, setOpenIds] = useState<Set<string>>(new Set())
  const seenNewestRef = useRef<string | null>(null)

  useEffect(() => {
    if (!backend && config?.backends.default) setBackend(config.backends.default)
  }, [config, backend])

  useEffect(() => () => abortRef.current?.abort(), [])

  // Deep-link from the Analyze page: scroll to the panel and focus the prompt.
  useEffect(() => {
    if (typeof window === 'undefined' || window.location.hash !== '#analyze-panel') return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    sectionRef.current?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
    const t = window.setTimeout(() => promptRef.current?.focus(), reduce ? 0 : 300)
    return () => window.clearTimeout(t)
  }, [])

  const run = async () => {
    if (!prompt.trim() || running) return
    setRunning(true)
    setError(null)
    setOutput('')
    setThinking({ summary: '', text: '' })
    committedOutputRef.current = ''
    streamBackendRef.current = backend
    const controller = new AbortController()
    abortRef.current = controller
    await streamAnalyze(
      {
        activity_id: activityId,
        prompt,
        backend: backend || undefined,
        reasoning_effort: backend === 'copilot' && effort ? effort : undefined,
      },
      {
        onStart: (value) => {
          streamBackendRef.current = value
        },
        onThinking: setThinking,
        onDelta: (text) =>
          setOutput((output) => {
            const next = output + text
            if (streamBackendRef.current !== 'copilot') committedOutputRef.current = next
            return next
          }),
        onReplace: (text) => {
          committedOutputRef.current = text
          setOutput(text)
        },
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
    setOutput(committedOutputRef.current)
    setRunning(false)
  }

  const options = backendOptions(config?.backends.copilot ?? false)
  const past = analysesQ.data?.analyses ?? []

  // Auto-expand the most recent analysis on open (and whenever a newer one is saved);
  // older ones stay collapsed.
  const newestId = past[0]?.entry_id
  useEffect(() => {
    if (newestId && seenNewestRef.current !== newestId) {
      seenNewestRef.current = newestId
      setOpenIds((prev) => new Set(prev).add(newestId))
    }
  }, [newestId])

  return (
    <section ref={sectionRef} id="analyze-panel" className="space-y-4">
      <Card>
        <CardBody className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
              <Sparkles className="h-5 w-5 text-brand-600" /> Analyze this workout
            </h2>
            <div className="flex items-center gap-2">
              {backend === 'copilot' && (
                <select
                  value={effort}
                  onChange={(e) => setEffort(e.target.value)}
                  disabled={running}
                  className="h-9 rounded-lg border border-slate-200 bg-white px-2 text-xs focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  aria-label="Reasoning effort"
                  title="Copilot reasoning effort. Higher = deeper, more thorough analysis."
                >
                  {EFFORT_OPTIONS.map((o) => (
                    <option key={o.v} value={o.v}>
                      {o.label}
                    </option>
                  ))}
                </select>
              )}
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
          </div>

          <textarea
            ref={promptRef}
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
          </div>

          <ThinkingDisclosure
            summary={thinking.summary}
            thinking={thinking.text}
            running={running}
          />

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {output && (
            <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
              <MarkdownView>{output}</MarkdownView>
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
              <details
                key={a.entry_id}
                open={openIds.has(a.entry_id)}
                onToggle={(e) => {
                  const open = e.currentTarget.open
                  setOpenIds((prev) => {
                    const next = new Set(prev)
                    if (open) next.add(a.entry_id)
                    else next.delete(a.entry_id)
                    return next
                  })
                }}
                className="group rounded-xl border border-slate-200 bg-white"
              >
                <summary className="flex cursor-pointer items-center justify-between gap-3 p-4 text-sm">
                  <span className="min-w-0 flex-1 truncate font-medium text-slate-800">
                    {a.prompt || 'Analysis'}
                  </span>
                  <span className="shrink-0 text-xs text-slate-400">
                    {formatDateTime(a.created_at)}
                  </span>
                </summary>
                <div className="border-t border-slate-100 p-4">
                  <AnalysisView
                    content={a.content ?? ''}
                    prompt={a.prompt}
                    meta={`${a.backend}${a.model ? ` · ${a.model}` : ''}`}
                    entryId={a.entry_id}
                  />
                </div>
              </details>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
