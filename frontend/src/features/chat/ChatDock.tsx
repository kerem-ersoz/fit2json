import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Check,
  ChevronLeft,
  Clock,
  Loader2,
  MessageSquare,
  Paperclip,
  Pencil,
  Plus,
  Search,
  Send,
  SlidersHorizontal,
  Sparkles,
  Square,
  Trash2,
  X,
} from 'lucide-react'
import { api, type MapStep } from '../../lib/api'
import { sportMeta } from '../../lib/sport'
import { formatDate } from '../../lib/format'
import { Button } from '../../components/ui/Button'
import { MarkdownView } from '../../components/ui/Markdown'
import { CUSTOM_MODEL, useChat, type Msg } from './ChatProvider'

const selectClass =
  'h-8 max-w-[10rem] rounded-lg border border-slate-200 bg-white px-2 text-xs text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 disabled:opacity-50'

function backendOptions(copilot: boolean) {
  const opts = [
    { v: 'ollama', label: 'Ollama (local)' },
    { v: 'lmstudio', label: 'LM Studio (local)' },
  ]
  if (copilot) opts.unshift({ v: 'copilot', label: 'Copilot CLI' })
  return opts
}

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const diff = Date.now() - then
  const min = Math.round(diff / 60000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min}m ago`
  const hr = Math.round(min / 60)
  if (hr < 24) return `${hr}h ago`
  const day = Math.round(hr / 24)
  if (day < 7) return `${day}d ago`
  return formatDate(iso)
}

interface ChatSummaryLite {
  id: string
  title: string
  updated_at: string
  message_count: number
  activity_ids: string[]
}

/** Bucket chats by recency so a long history stays scannable. Input is newest-first. */
function groupByRecency(chats: ChatSummaryLite[]) {
  const now = new Date()
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const startWeek = startToday - 6 * 86_400_000
  const buckets: Record<string, ChatSummaryLite[]> = { today: [], week: [], older: [] }
  for (const c of chats) {
    const t = new Date(c.updated_at).getTime()
    if (!Number.isNaN(t) && t >= startToday) buckets.today.push(c)
    else if (!Number.isNaN(t) && t >= startWeek) buckets.week.push(c)
    else buckets.older.push(c)
  }
  return [
    { key: 'today', label: 'Today', items: buckets.today },
    { key: 'week', label: 'Previous 7 days', items: buckets.week },
    { key: 'older', label: 'Older', items: buckets.older },
  ].filter((g) => g.items.length > 0)
}

/**
 * Global, resumable conversation pane. Lives above every tab as a right-side drawer.
 * Persistence, streaming, and attached-workout state come from {@link useChat}; this
 * component is the surface: header + settings + transcript + composer, plus a history
 * view for resuming past chats.
 */
export function ChatDock() {
  const chat = useChat()
  const { open, setOpen } = chat
  const [view, setView] = useState<'chat' | 'history'>('chat')
  const inputRef = useRef<HTMLTextAreaElement>(null)
  // `mounted` keeps the drawer in the DOM briefly while it animates out; `shown` drives
  // the slide/fade. When neither is set the drawer renders nothing at all — so a closed
  // pane can never affect layout, scroll width, or intercept clicks in any engine.
  const [mounted, setMounted] = useState(open)
  const [shown, setShown] = useState(open)

  useEffect(() => {
    if (open) {
      setMounted(true)
      // Next frame: flip to the on-screen state so the transition runs.
      const raf = requestAnimationFrame(() => setShown(true))
      return () => cancelAnimationFrame(raf)
    }
    setShown(false)
    const t = window.setTimeout(() => setMounted(false), 220) // after the 200ms transition
    return () => window.clearTimeout(t)
  }, [open])

  // Close on Escape; focus the composer when the drawer opens.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    const t = window.setTimeout(() => inputRef.current?.focus(), 60)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.clearTimeout(t)
    }
  }, [open, setOpen])

  useEffect(() => {
    if (open) setView('chat')
  }, [open])

  // Fully absent when closed — no fixed overlay left behind.
  if (!mounted && !open) return null

  return (
    <>
      {/* Scrim — dims the app and closes on click. */}
      <div
        onClick={() => setOpen(false)}
        aria-hidden="true"
        className={`fixed inset-0 z-40 bg-slate-900/20 transition-opacity duration-200 motion-reduce:transition-none ${
          shown ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Chat"
        className={`fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-slate-200 bg-white shadow-xl transition-transform duration-200 ease-out motion-reduce:transition-none sm:max-w-[30rem] ${
          shown ? 'translate-x-0' : 'translate-x-full'
        }`}
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      >
        {view === 'history' ? (
          <HistoryView onClose={() => setView('chat')} />
        ) : (
          <ChatView inputRef={inputRef} onShowHistory={() => setView('history')} />
        )}
      </aside>
    </>
  )
}

function ChatView({
  inputRef,
  onShowHistory,
}: {
  inputRef: React.RefObject<HTMLTextAreaElement>
  onShowHistory: () => void
}) {
  const chat = useChat()
  const { data: config } = useQuery({ queryKey: ['config'], queryFn: api.config })
  const { data: activities } = useQuery({ queryKey: ['activities'], queryFn: api.activities })

  const { data: modelInfo } = useQuery({
    queryKey: ['models', chat.backend],
    queryFn: () => api.models(chat.backend),
    enabled: !!chat.backend && chat.open,
  })

  const [input, setInput] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

  // Keep the model selection valid for the chosen backend.
  useEffect(() => {
    if (!modelInfo) return
    if (chat.modelSel === CUSTOM_MODEL) return
    if (modelInfo.models.includes(chat.modelSel)) return
    chat.setModelSel(modelInfo.models[0] ?? (modelInfo.allow_custom ? CUSTOM_MODEL : ''))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelInfo])

  useEffect(() => {
    const reduce =
      typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
    endRef.current?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'end' })
  }, [chat.messages])

  const attached = useMemo(
    () => (activities ?? []).filter((a) => chat.activityIds.includes(a.id)),
    [activities, chat.activityIds],
  )
  const attachedCount = chat.activityIds.length
  const efforts = modelInfo?.efforts ?? []

  const suggestions = useMemo(() => {
    if (attachedCount > 1)
      return ['Compare these workouts — what stands out?', 'How is my fitness trending across these?', 'Which was the hardest effort, and why?']
    if (attachedCount === 1)
      return ["Give me a coach's summary.", 'Analyze my pacing and heart-rate strategy.', 'Any signs of fatigue or overreaching?']
    return ['Compare my last 3 long runs', 'How did my running go this month?', 'Summarize this week of training']
  }, [attachedCount])

  const submit = (text: string) => {
    if (chat.running) return // don't clear/drop a follow-up typed mid-stream
    if (!text.trim()) return
    setInput('')
    void chat.send(text)
  }

  const commitTitle = () => {
    setEditingTitle(false)
    if (titleDraft.trim() && titleDraft.trim() !== chat.title) void chat.renameChat(titleDraft)
  }

  return (
    <>
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-slate-100 px-3 py-2.5">
        <MessageSquare className="h-4 w-4 shrink-0 text-brand-600" />
        {editingTitle ? (
          <input
            value={titleDraft}
            autoFocus
            onChange={(e) => setTitleDraft(e.target.value)}
            onBlur={commitTitle}
            onKeyDown={(e) => {
              if (e.key === 'Enter') commitTitle()
              if (e.key === 'Escape') setEditingTitle(false)
            }}
            aria-label="Chat title"
            className="min-w-0 flex-1 rounded border border-slate-200 px-1.5 py-0.5 text-sm font-semibold text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        ) : (
          <button
            type="button"
            onClick={() => {
              if (!chat.chatId) return
              setTitleDraft(chat.title)
              setEditingTitle(true)
            }}
            disabled={!chat.chatId}
            title={chat.chatId ? 'Rename chat' : undefined}
            className="group flex min-w-0 flex-1 items-center gap-1.5 rounded text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <span className="truncate text-sm font-semibold text-slate-900">
              {chat.title || 'New chat'}
            </span>
            {chat.chatId && (
              <Pencil className="h-3 w-3 shrink-0 text-slate-300 group-hover:text-slate-500" />
            )}
          </button>
        )}
        <IconButton label="Chat history" onClick={onShowHistory}>
          <Clock className="h-4 w-4" />
        </IconButton>
        <IconButton label="New chat" onClick={() => chat.newChat()}>
          <Plus className="h-4 w-4" />
        </IconButton>
        <IconButton label="Close chat" onClick={() => chat.setOpen(false)}>
          <X className="h-4 w-4" />
        </IconButton>
      </div>

      {/* Settings */}
      <div className="space-y-2 border-b border-slate-100 px-3 py-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={chat.backend}
            onChange={(e) => chat.setBackend(e.target.value)}
            disabled={chat.running}
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
            value={chat.modelSel}
            onChange={(e) => chat.setModelSel(e.target.value)}
            disabled={chat.running || !modelInfo}
            aria-label="Model"
            className={selectClass}
          >
            {(modelInfo?.models ?? ['auto']).map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
            {modelInfo?.allow_custom && <option value={CUSTOM_MODEL}>Custom…</option>}
          </select>
          {chat.modelSel === CUSTOM_MODEL && (
            <input
              value={chat.customModel}
              onChange={(e) => chat.setCustomModel(e.target.value)}
              disabled={chat.running}
              placeholder="model id"
              aria-label="Custom model id"
              className="h-8 w-32 rounded-lg border border-slate-200 bg-white px-2 text-xs text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          )}
          {efforts.length > 0 && (
            <select
              value={chat.effort}
              onChange={(e) => chat.setEffort(e.target.value)}
              disabled={chat.running}
              aria-label="Reasoning effort"
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
              {chat.backend === 'copilot' ? 'Copilot CLI not found' : `${chat.backend} not reachable`}
            </span>
          )}
        </div>
        {showAdvanced && (
          <div className="space-y-1">
            <textarea
              value={chat.workoutPrompt ?? ''}
              onChange={(e) => chat.setWorkoutPrompt(e.target.value)}
              rows={3}
              aria-label="Per-workout analysis prompt"
              className="w-full resize-y rounded-lg border border-slate-200 p-2 text-xs text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
            <div className="flex items-center justify-between gap-2">
              <p className="text-[11px] text-slate-400">
                Prompt for each per-workout analysis when comparing 2+ workouts.
              </p>
              {config?.workout_prompt_default && chat.workoutPrompt !== config.workout_prompt_default && (
                <button
                  type="button"
                  onClick={() => chat.setWorkoutPrompt(config.workout_prompt_default)}
                  className="shrink-0 rounded text-[11px] font-medium text-brand-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                >
                  Reset
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Attached workouts */}
      {attachedCount > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 border-b border-slate-100 px-3 py-2">
          {attached.map((a) => {
            const { label } = sportMeta(a.sport)
            return (
              <span
                key={a.id}
                className="inline-flex items-center gap-1 rounded-full bg-brand-50 py-0.5 pl-2 pr-1 text-xs font-medium text-brand-700"
              >
                {label} · {formatDate(a.start_time)}
                <button
                  type="button"
                  onClick={() => chat.toggleActivity(a.id)}
                  aria-label={`Detach ${label}`}
                  className="rounded-full p-0.5 text-brand-700/70 hover:bg-brand-100 hover:text-brand-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            )
          })}
          {/* Ids whose activity summary isn't loaded still count as attached. */}
          {attachedCount > attached.length && (
            <span className="text-xs text-slate-400">
              +{attachedCount - attached.length} more
            </span>
          )}
        </div>
      )}

      {/* Transcript */}
      <div className="flex-1 overflow-y-auto px-3 py-4">
        {chat.messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-600">
              <Sparkles className="h-6 w-6" />
            </div>
            <p className="text-sm font-medium text-slate-700">
              {attachedCount > 0
                ? attachedCount === 1
                  ? 'Ask about this workout'
                  : `Ask about these ${attachedCount} workouts`
                : 'Ask about your training'}
            </p>
            <p className="max-w-xs text-sm text-slate-500">
              {attachedCount > 0
                ? 'Answers stream in below. This conversation is saved so you can pick it up later.'
                : 'Describe workouts in your question, or select some on the Analyze tab. Saved for later.'}
            </p>
            <div className="mt-1 flex flex-wrap justify-center gap-2">
              {suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => submit(s)}
                  className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {chat.messages.map((m) => (
              <MessageBubble key={m.id} msg={m} running={chat.running} />
            ))}
            {chat.error && (
              <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {chat.error}
              </div>
            )}
            <div ref={endRef} />
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="border-t border-slate-100 p-3">
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault()
                submit(input)
              }
            }}
            rows={1}
            placeholder={attachedCount > 0 ? 'Ask a question…  (⌘/Ctrl+Enter)' : 'Ask anything — e.g. “compare my last 3 long runs”'}
            aria-label="Message"
            className="max-h-32 min-h-[44px] flex-1 resize-y rounded-lg border border-slate-200 p-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          {chat.running ? (
            <Button variant="secondary" onClick={() => chat.stop()} aria-label="Stop">
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <Button onClick={() => submit(input)} disabled={!input.trim()} aria-label="Send">
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>
        {chat.running && (
          <p className="mt-1.5 flex items-center gap-1.5 text-xs text-slate-500">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Thinking…
          </p>
        )}
      </div>
    </>
  )
}

function HistoryView({ onClose }: { onClose: () => void }) {
  const chat = useChat()
  const [query, setQuery] = useState('')
  const [confirmId, setConfirmId] = useState<string | null>(null)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? chat.chats.filter((c) => c.title.toLowerCase().includes(q)) : chat.chats
  }, [chat.chats, query])

  const groups = useMemo(() => groupByRecency(filtered), [filtered])
  const showSearch = chat.chats.length > 5

  const del = (id: string) => {
    setConfirmId(null)
    void chat.deleteChat(id)
  }

  return (
    <>
      <div className="flex items-center gap-1 border-b border-slate-100 px-2 py-2.5">
        <IconButton label="Back to conversation" onClick={onClose}>
          <ChevronLeft className="h-4 w-4" />
        </IconButton>
        <span className="flex-1 text-sm font-semibold text-slate-900">Saved chats</span>
        <IconButton
          label="New chat"
          onClick={() => {
            chat.newChat()
            onClose()
          }}
        >
          <Plus className="h-4 w-4" />
        </IconButton>
      </div>

      {showSearch && (
        <div className="border-b border-slate-100 px-3 py-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search chats…"
              aria-label="Search saved chats"
              className="h-9 w-full rounded-lg border border-slate-200 bg-white pl-8 pr-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        {chat.chatsLoading ? (
          <div className="space-y-2 p-3">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded-lg bg-slate-100" />
            ))}
          </div>
        ) : chat.chats.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-8 text-center">
            <div className="flex h-11 w-11 items-center justify-center rounded-full bg-slate-100 text-slate-400">
              <MessageSquare className="h-5 w-5" />
            </div>
            <p className="text-sm font-medium text-slate-700">No saved chats yet</p>
            <p className="text-sm text-slate-500">
              Every conversation you start is saved here automatically so you can pick it up later.
            </p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-1 px-8 text-center">
            <p className="text-sm font-medium text-slate-700">No matches</p>
            <p className="text-sm text-slate-500">No saved chats contain “{query.trim()}”.</p>
          </div>
        ) : (
          <div className="pb-3">
            {groups.map((g) => (
              <section key={g.key}>
                <h3 className="sticky top-0 z-10 bg-white/90 px-3 pb-1 pt-3 text-xs font-medium text-slate-500 backdrop-blur">
                  {g.label}
                </h3>
                <ul className="divide-y divide-slate-100">
                  {g.items.map((c) => (
                    <ChatRow
                      key={c.id}
                      chat={c}
                      active={c.id === chat.chatId}
                      confirming={confirmId === c.id}
                      onResume={() => {
                        chat.resumeChat(c.id)
                        onClose() // return to the conversation view, not just load it in the background
                      }}
                      onAskDelete={() => setConfirmId(c.id)}
                      onCancelDelete={() => setConfirmId(null)}
                      onConfirmDelete={() => del(c.id)}
                    />
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
      </div>
    </>
  )
}

function ChatRow({
  chat: c,
  active,
  confirming,
  onResume,
  onAskDelete,
  onCancelDelete,
  onConfirmDelete,
}: {
  chat: ChatSummaryLite
  active: boolean
  confirming: boolean
  onResume: () => void
  onAskDelete: () => void
  onCancelDelete: () => void
  onConfirmDelete: () => void
}) {
  return (
    <li className={active ? 'bg-brand-50/50' : ''}>
      <div className="group flex items-stretch transition-colors hover:bg-slate-50 motion-reduce:transition-none">
        <button
          type="button"
          onClick={onResume}
          className="min-w-0 flex-1 px-3 py-2.5 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-500"
        >
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium text-slate-800">{c.title}</span>
            {active && (
              <span className="shrink-0 rounded-full bg-brand-100 px-1.5 py-px text-[10px] font-semibold text-brand-700">
                Current
              </span>
            )}
          </div>
          <div className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500">
            <span>{relativeTime(c.updated_at)}</span>
            <span aria-hidden="true">·</span>
            <span>
              {c.message_count} {c.message_count === 1 ? 'message' : 'messages'}
            </span>
            {c.activity_ids.length > 0 && (
              <span className="inline-flex items-center gap-0.5" title={`${c.activity_ids.length} workouts attached`}>
                <Paperclip className="h-3 w-3" />
                {c.activity_ids.length}
              </span>
            )}
          </div>
        </button>

        <div className="flex shrink-0 items-center pr-2">
          {confirming ? (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={onConfirmDelete}
                className="rounded-md px-2 py-1 text-xs font-semibold text-red-600 hover:bg-red-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
              >
                Delete
              </button>
              <button
                type="button"
                onClick={onCancelDelete}
                className="rounded-md px-2 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={onAskDelete}
              aria-label={`Delete chat: ${c.title}`}
              className="rounded-md p-1.5 text-slate-300 transition-colors hover:bg-slate-100 hover:text-red-600 focus:text-red-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 motion-reduce:transition-none"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </li>
  )
}

function IconButton({
  label,
  onClick,
  children,
}: {
  label: string
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
    >
      {children}
    </button>
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
