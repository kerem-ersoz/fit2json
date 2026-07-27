import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Check, Loader2, MessageSquare, Send, SlidersHorizontal, Sparkles, Square, X } from 'lucide-react'
import { api, streamAnalyze, type ActivitySummary, type MapStep } from '../../lib/api'
import { sportMeta } from '../../lib/sport'
import { formatDate } from '../../lib/format'
import { Button } from '../../components/ui/Button'
import { MarkdownView } from '../../components/ui/Markdown'

interface Msg {
  id: string
  role: 'user' | 'assistant'
  content: string
  steps?: MapStep[]
}

let seq = 0
const uid = () => `m${++seq}`

const CUSTOM = '__custom__'

function backendOptions(copilot: boolean) {
  const opts = [
    { v: 'ollama', label: 'Ollama (local)' },
    { v: 'lmstudio', label: 'LM Studio (local)' },
  ]
  if (copilot) opts.unshift({ v: 'copilot', label: 'Copilot CLI' })
  return opts
}

const selectClass =
  'h-8 max-w-[10rem] rounded-lg border border-slate-200 bg-white px-2 text-xs text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 disabled:opacity-50'

/**
 * Multi-turn conversation about workouts. Works two ways:
 *  - with workouts selected on the left (single analysis, or a map-reduce for 2+), or
 *  - freeform with nothing selected — describe the workouts in the question and the agent
 *    finds them in the library itself.
 * The per-workout building-block prompt used by the map step is adjustable (Advanced).
 */
export function ConversationPane({
  activities,
  onDeselect,
}: {
  activities: ActivitySummary[]
  onDeselect: (id: string) => void
}) {
  const { data: config } = useQuery({ queryKey: ['config'], queryFn: api.config })
  const [backend, setBackend] = useState('')
  const [modelSel, setModelSel] = useState('auto')
  const [customModel, setCustomModel] = useState('')
  const [effort, setEffort] = useState('')
  const [workoutPrompt, setWorkoutPrompt] = useState<string | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!backend && config?.backends.default) setBackend(config.backends.default)
  }, [config, backend])
  useEffect(() => {
    if (workoutPrompt === null && config?.workout_prompt_default) setWorkoutPrompt(config.workout_prompt_default)
  }, [config, workoutPrompt])
  useEffect(() => () => abortRef.current?.abort(), [])
  useEffect(() => {
    const reduce = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
    endRef.current?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'end' })
  }, [messages])

  const { data: modelInfo } = useQuery({
    queryKey: ['models', backend],
    queryFn: () => api.models(backend),
    enabled: !!backend,
  })

  useEffect(() => {
    if (!modelInfo) return
    setModelSel((cur) => {
      if (cur === CUSTOM) return cur
      if (modelInfo.models.includes(cur)) return cur
      return modelInfo.models[0] ?? (modelInfo.allow_custom ? CUSTOM : '')
    })
  }, [modelInfo])

  const hasSelection = activities.length > 0
  const efforts = modelInfo?.efforts ?? []
  const effectiveModel = modelSel === CUSTOM ? customModel.trim() : modelSel

  const suggestions = useMemo(() => {
    if (activities.length > 1)
      return ['Compare these workouts — what stands out?', 'How is my fitness trending across these?', 'Which was the hardest effort, and why?']
    if (activities.length === 1)
      return ["Give me a coach's summary.", 'Analyze my pacing and heart-rate strategy.', 'Any signs of fatigue or overreaching?']
    return ['Compare my last 3 long runs', 'How did my running go this month?', 'Summarize this week of training']
  }, [activities.length])

  const send = async (text: string) => {
    const q = text.trim()
    if (!q || running) return
    const prior = messages
    const userMsg: Msg = { id: uid(), role: 'user', content: q }
    const asstId = uid()
    setMessages((m) => [...m, userMsg, { id: asstId, role: 'assistant', content: '', steps: [] }])
    setInput('')
    setRunning(true)
    setError(null)
    const controller = new AbortController()
    abortRef.current = controller
    const transcript = prior.map((m) => `${m.role === 'user' ? 'Me' : 'Coach'}: ${m.content}`).join('\n\n')
    const prompt = transcript
      ? `Here is our conversation so far:\n\n${transcript}\n\nNow respond to my next message:\n\n${q}`
      : q
    const model = !effectiveModel || effectiveModel === 'auto' ? undefined : effectiveModel
    await streamAnalyze(
      {
        activity_ids: activities.map((a) => a.id),
        prompt,
        workout_prompt: workoutPrompt && workoutPrompt.trim() ? workoutPrompt : undefined,
        backend: backend || undefined,
        model,
        reasoning_effort: effort || undefined,
        no_memory: true,
      },
      {
        onStep: (s) =>
          setMessages((m) =>
            m.map((x) => {
              if (x.id !== asstId) return x
              const steps = [...(x.steps ?? [])]
              const i = steps.findIndex((p) => p.index === s.index)
              if (i === -1) steps.push(s)
              else steps[i] = s
              steps.sort((a, b) => a.index - b.index)
              return { ...x, steps }
            }),
          ),
        onDelta: (t) =>
          setMessages((m) => m.map((x) => (x.id === asstId ? { ...x, content: x.content + t } : x))),
        onDone: () => setRunning(false),
        onError: (msg) => {
          setRunning(false)
          setError(msg)
          setMessages((m) => m.filter((x) => !(x.id === asstId && x.content === '' && !(x.steps && x.steps.length))))
        },
      },
      controller.signal,
    )
  }

  const stop = () => {
    abortRef.current?.abort()
    setRunning(false)
  }
  const reset = () => {
    abortRef.current?.abort()
    setRunning(false)
    setMessages([])
    setError(null)
  }

  return (
    <div className="flex h-[32rem] flex-col overflow-hidden rounded-xl border border-slate-200 bg-white lg:h-[calc(100vh-9rem)]">
      <div className="space-y-2 border-b border-slate-100 px-4 py-3">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <Sparkles className="h-4 w-4 text-brand-600" /> Conversation
          </h2>
          {messages.length > 0 && (
            <button
              type="button"
              onClick={reset}
              className="rounded text-xs font-medium text-slate-500 hover:text-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            >
              New chat
            </button>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={backend}
            onChange={(e) => setBackend(e.target.value)}
            disabled={running}
            aria-label="Model backend"
            className={selectClass}
          >
            {backendOptions(config?.backends.copilot ?? false).map((o) => (
              <option key={o.v} value={o.v}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            value={modelSel}
            onChange={(e) => setModelSel(e.target.value)}
            disabled={running || !modelInfo}
            aria-label="Model"
            className={selectClass}
          >
            {(modelInfo?.models ?? ['auto']).map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
            {modelInfo?.allow_custom && <option value={CUSTOM}>Custom…</option>}
          </select>
          {modelSel === CUSTOM && (
            <input
              value={customModel}
              onChange={(e) => setCustomModel(e.target.value)}
              disabled={running}
              placeholder="model id"
              aria-label="Custom model id"
              className="h-8 w-32 rounded-lg border border-slate-200 bg-white px-2 text-xs text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          )}
          {efforts.length > 0 && (
            <select
              value={effort}
              onChange={(e) => setEffort(e.target.value)}
              disabled={running}
              aria-label="Reasoning effort"
              title="Analyses are reused only across the same model + effort, so quality stays consistent."
              className={selectClass}
            >
              <option value="">Effort: auto</option>
              {efforts.map((e) => (
                <option key={e} value={e}>
                  Effort: {e}
                </option>
              ))}
            </select>
          )}
          <button
            type="button"
            onClick={() => setShowAdvanced((v) => !v)}
            aria-expanded={showAdvanced}
            className="inline-flex items-center gap-1 rounded text-xs font-medium text-slate-500 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <SlidersHorizontal className="h-3.5 w-3.5" /> Analysis prompt
          </button>
          {modelInfo && !modelInfo.reachable && (
            <span className="text-xs font-medium text-amber-600">
              {backend === 'copilot' ? 'Copilot CLI not found' : `${backend} not reachable`}
            </span>
          )}
        </div>
        {showAdvanced && (
          <div className="space-y-1">
            <textarea
              value={workoutPrompt ?? ''}
              onChange={(e) => setWorkoutPrompt(e.target.value)}
              rows={3}
              aria-label="Per-workout analysis prompt"
              className="w-full resize-y rounded-lg border border-slate-200 p-2 text-xs text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
            <div className="flex items-center justify-between gap-2">
              <p className="text-[11px] text-slate-400">
                Prompt for each per-workout analysis when comparing 2+ workouts. Changing it regenerates building blocks.
              </p>
              {config?.workout_prompt_default && workoutPrompt !== config.workout_prompt_default && (
                <button
                  type="button"
                  onClick={() => setWorkoutPrompt(config.workout_prompt_default)}
                  className="shrink-0 rounded text-[11px] font-medium text-brand-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                >
                  Reset
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {hasSelection && (
        <div className="flex flex-wrap gap-1.5 border-b border-slate-100 px-4 py-2.5">
          {activities.map((a) => {
            const { label } = sportMeta(a.sport)
            return (
              <span
                key={a.id}
                className="inline-flex items-center gap-1 rounded-full bg-brand-50 py-0.5 pl-2 pr-1 text-xs font-medium text-brand-700"
              >
                {label} · {formatDate(a.start_time)}
                <button
                  type="button"
                  onClick={() => onDeselect(a.id)}
                  aria-label={`Remove ${label}`}
                  className="rounded-full p-0.5 text-brand-700/70 hover:bg-brand-100 hover:text-brand-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            )
          })}
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-600">
              <MessageSquare className="h-6 w-6" />
            </div>
            {hasSelection ? (
              <>
                <p className="text-sm font-medium text-slate-700">
                  {activities.length === 1 ? 'Ask about this workout' : `Ask about these ${activities.length} workouts`}
                </p>
                <p className="max-w-xs text-sm text-slate-500">
                  {activities.length > 1
                    ? 'Each workout is analyzed on its own (reused from memory when possible), then compared. This chat isn’t saved.'
                    : 'Answers stream in below. This chat is exploratory and isn’t saved to memory.'}
                </p>
              </>
            ) : (
              <>
                <p className="text-sm font-medium text-slate-700">Ask about your training</p>
                <p className="max-w-xs text-sm text-slate-500">
                  Describe the workouts in your question, or select some on the left. Chats aren’t saved.
                </p>
              </>
            )}
            <div className="mt-1 flex flex-wrap justify-center gap-2">
              {suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((m) => (
              <MessageBubble key={m.id} msg={m} running={running} />
            ))}
            {error && (
              <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {error}
              </div>
            )}
            <div ref={endRef} />
          </div>
        )}
      </div>

      <div className="border-t border-slate-100 p-3">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault()
                send(input)
              }
            }}
            rows={1}
            placeholder={hasSelection ? 'Ask a question…  (⌘/Ctrl+Enter)' : 'Ask anything — e.g. “compare my last 3 long runs”'}
            aria-label="Message"
            className="max-h-32 min-h-[44px] flex-1 resize-y rounded-lg border border-slate-200 p-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          {running ? (
            <Button variant="secondary" onClick={stop} aria-label="Stop">
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <Button onClick={() => send(input)} disabled={!input.trim()} aria-label="Send">
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>
        {running && (
          <p className="mt-1.5 flex items-center gap-1.5 text-xs text-slate-500">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Thinking…
          </p>
        )}
      </div>
    </div>
  )
}

function StepList({ steps, running }: { steps: MapStep[]; running: boolean }) {
  const allDone = steps.length > 0 && steps.every((s) => s.state === 'done')
  return (
    <div className="mb-2 space-y-1 rounded-lg border border-slate-100 bg-slate-50/70 p-2.5">
      {steps.map((s) => (
        <div key={s.index} className="flex items-center gap-2 text-xs">
          {s.state === 'done' ? (
            <Check className="h-3.5 w-3.5 shrink-0 text-brand-600" />
          ) : (
            <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-slate-400" />
          )}
          <span className="truncate text-slate-600">
            {s.state === 'done' ? (s.reused ? 'Reused' : 'Analyzed') : 'Analyzing'} {s.label}
          </span>
        </div>
      ))}
      {allDone && running && (
        <div className="flex items-center gap-2 text-xs">
          <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-slate-400" />
          <span className="text-slate-600">Synthesizing across {steps.length} workouts…</span>
        </div>
      )}
    </div>
  )
}

function MessageBubble({ msg, running }: { msg: Msg; running: boolean }) {
  if (msg.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-xl rounded-br-sm bg-brand-600 px-3.5 py-2 text-sm text-white">
          {msg.content}
        </div>
      </div>
    )
  }
  return (
    <div className="min-w-0">
      {msg.steps && msg.steps.length > 0 && <StepList steps={msg.steps} running={running} />}
      {msg.content ? (
        <MarkdownView>{msg.content}</MarkdownView>
      ) : !msg.steps?.length && running ? (
        <p className="text-sm text-slate-400">Waiting for the model…</p>
      ) : null}
    </div>
  )
}
