import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Sparkles, Square } from 'lucide-react'
import {
  api,
  cancelAnalysisRun,
  newAnalysisRunId,
  startAnalysisRun,
  streamAnalysisRun,
  type AnalysisRunInfo,
  type ThinkingInfo,
} from '../../lib/api'
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

const runStorageKey = (activityId: string) => `fitsift-analysis-run:${activityId}`

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
  const [stopping, setStopping] = useState(false)
  const [output, setOutput] = useState('')
  const [thinking, setThinking] = useState<ThinkingInfo>({ summary: '', text: '' })
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const runIdRef = useRef<string | null>(null)
  const committedOutputRef = useRef('')
  const streamBackendRef = useRef('')
  const sectionRef = useRef<HTMLElement>(null)
  const promptRef = useRef<HTMLTextAreaElement>(null)
  const [openIds, setOpenIds] = useState<Set<string>>(new Set())
  const seenNewestRef = useRef<string | null>(null)

  useEffect(() => {
    if (!backend && config?.backends.default) setBackend(config.backends.default)
  }, [config, backend])

  const clearStoredRun = useCallback(
    (runId: string) => {
      try {
        if (localStorage.getItem(runStorageKey(activityId)) === runId) {
          localStorage.removeItem(runStorageKey(activityId))
        }
      } catch {
        /* local storage is an enhancement; the saved analysis remains server-side */
      }
    },
    [activityId],
  )

  const followRun = useCallback(
    async (runId: string, controller: AbortController) => {
      const isCurrent = () => runIdRef.current === runId
      await streamAnalysisRun(
        runId,
        {
          onStart: (value) => {
            streamBackendRef.current = value
          },
          onThinking: setThinking,
          onDelta: (text) => {
            if (!isCurrent()) return
            setOutput((current) => {
              const next = current + text
              if (streamBackendRef.current !== 'copilot') committedOutputRef.current = next
              return next
            })
          },
          onReplace: (text) => {
            if (!isCurrent()) return
            committedOutputRef.current = text
            setOutput(text)
          },
          onDone: (info) => {
            clearStoredRun(runId)
            if (info.saved) {
              queryClient.invalidateQueries({ queryKey: ['analyses', activityId] })
            }
            if (!isCurrent()) return
            setRunning(false)
            setStopping(false)
            setError(null)
            if (info.saved) setOutput('')
            committedOutputRef.current = ''
            runIdRef.current = null
          },
          onError: (message) => {
            clearStoredRun(runId)
            queryClient.invalidateQueries({ queryKey: ['analyses', activityId] })
            if (!isCurrent()) return
            setRunning(false)
            setStopping(false)
            setOutput(committedOutputRef.current)
            setError(message)
            runIdRef.current = null
          },
          onCancelled: () => {
            clearStoredRun(runId)
            if (!isCurrent()) return
            setRunning(false)
            setStopping(false)
            setOutput(committedOutputRef.current)
            runIdRef.current = null
          },
          onMissing: async () => {
            clearStoredRun(runId)
            await queryClient.invalidateQueries({ queryKey: ['analyses', activityId] })
            if (!isCurrent()) return
            setRunning(false)
            setStopping(false)
            setError(
              'The analysis was interrupted because the FitSift server restarted.',
            )
            runIdRef.current = null
          },
        },
        controller.signal,
      )
      if (abortRef.current === controller) abortRef.current = null
    },
    [activityId, clearStoredRun, queryClient],
  )

  useEffect(
    () => () => {
      abortRef.current?.abort()
      abortRef.current = null
      runIdRef.current = null
    },
    [activityId],
  )

  // Restore a detached run after navigation, reload, or mobile app suspension.
  useEffect(() => {
    let runId: string | null = null
    try {
      runId = localStorage.getItem(runStorageKey(activityId))
    } catch {
      runId = null
    }
    if (!runId) return

    const controller = new AbortController()
    abortRef.current = controller
    runIdRef.current = runId
    setRunning(true)
    setStopping(false)
    setError(null)
    setOutput('')
    void followRun(runId, controller)
    return () => controller.abort()
  }, [activityId, followRun])

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
    const runId = newAnalysisRunId()
    runIdRef.current = runId
    try {
      localStorage.setItem(runStorageKey(activityId), runId)
    } catch {
      /* the run still survives while this page remains mounted */
    }
    let started: AnalysisRunInfo
    try {
      started = await startAnalysisRun(
        {
          run_id: runId,
          analysis: {
            activity_id: activityId,
            prompt,
            backend: backend || undefined,
            reasoning_effort: backend === 'copilot' && effort ? effort : undefined,
          },
        },
        controller.signal,
      )
    } catch (cause) {
      if (controller.signal.aborted) return
      setRunning(false)
      setStopping(false)
      setError((cause as Error)?.message ?? 'Analysis could not be started.')
      clearStoredRun(runId)
      runIdRef.current = null
      if (abortRef.current === controller) abortRef.current = null
      return
    }
    if (
      started.status === 'completed' ||
      started.status === 'failed' ||
      started.status === 'cancelled'
    ) {
      clearStoredRun(runId)
      if (runIdRef.current === runId) {
        setRunning(false)
        setStopping(false)
        setError(
          started.status === 'failed' ? started.error || 'Analysis failed.' : null,
        )
        runIdRef.current = null
      }
      if (started.status === 'completed') {
        await queryClient.invalidateQueries({ queryKey: ['analyses', activityId] })
      }
      return
    }
    await followRun(runId, controller)
  }

  const stop = () => {
    const runId = runIdRef.current
    if (!runId || stopping) return
    setStopping(true)
    void cancelAnalysisRun(runId).catch((cause) => {
      if (runIdRef.current === runId) {
        setStopping(false)
        setError((cause as Error)?.message ?? 'The analysis could not be stopped.')
      }
    })
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
            <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
              <Sparkles className="h-5 w-5 text-accent" /> Analyze this workout
            </h2>
            <div className="flex items-center gap-2">
              {backend === 'copilot' && (
                <select
                  value={effort}
                  onChange={(e) => setEffort(e.target.value)}
                  disabled={running}
                  className="h-9 rounded-lg border border-divider bg-surface px-2 text-xs focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
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
                className="h-9 rounded-lg border border-divider bg-surface px-2 text-xs focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
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
            className="w-full resize-y rounded-lg border border-divider p-3 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />

          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setPrompt(s)}
                disabled={running}
                className="rounded-full border border-divider bg-surface-muted px-3 py-1 text-xs text-copy hover:bg-hover disabled:opacity-50"
              >
                {s}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3">
            {running ? (
              <Button variant="secondary" onClick={stop} disabled={stopping}>
                <Square className="h-4 w-4" /> {stopping ? 'Stopping…' : 'Stop'}
              </Button>
            ) : (
              <Button onClick={run} disabled={!prompt.trim()}>
                <Sparkles className="h-4 w-4" /> Analyze
              </Button>
            )}
            {running && (
              <span className="flex items-center gap-1.5 text-sm text-muted">
                <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" />
                {stopping ? 'Stopping analysis…' : 'Running in the background…'}
              </span>
            )}
          </div>

          <ThinkingDisclosure
            summary={thinking.summary}
            thinking={thinking.text}
            running={running}
          />

          {error && (
            <div className="rounded-lg border border-danger-divider bg-danger-tint p-3 text-sm text-danger-strong">
              {error}
            </div>
          )}

          {(output || running) && (
            <div className="rounded-lg border border-divider bg-surface-muted p-3">
              {output ? (
                <MarkdownView>{output}</MarkdownView>
              ) : (
                <p className="text-sm text-muted">
                  You can leave this screen while the model works.
                </p>
              )}
            </div>
          )}
        </CardBody>
      </Card>

      <div>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">
          Past analyses{past.length ? ` (${past.length})` : ''}
        </h3>
        {analysesQ.isLoading ? (
          <p className="text-sm text-faint">Loading…</p>
        ) : past.length === 0 ? (
          <p className="text-sm text-faint">
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
                className="group rounded-xl border border-divider bg-surface"
              >
                <summary className="flex cursor-pointer items-center justify-between gap-3 p-4 text-sm">
                  <span className="min-w-0 flex-1 truncate font-medium text-ink-soft">
                    {a.prompt || 'Analysis'}
                  </span>
                  <span className="shrink-0 text-xs text-faint">
                    {formatDateTime(a.created_at)}
                  </span>
                </summary>
                <div className="border-t border-divider-soft p-4">
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
