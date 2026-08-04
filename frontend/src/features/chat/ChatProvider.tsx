import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, streamAnalyze, type ChatSummary, type MapStep } from '../../lib/api'

/** A single conversation turn as held in memory (map steps are live-only). */
export interface Msg {
  id: string
  role: 'user' | 'assistant'
  content: string
  thinkingSummary?: string
  thinking?: string
  steps?: MapStep[]
}

export const CUSTOM_MODEL = '__custom__'
const ACTIVE_KEY = 'fitsift-active-chat'

/** A frozen copy of the settings a turn was sent with, so a later save can't pick up
 *  state that changed (or belongs to another chat) while the request was in flight. */
interface SaveSnapshot {
  title: string
  backend: string
  model: string
  reasoning_effort: string
  activity_ids: string[]
}

let seq = 0
const uid = () => `m${++seq}`

function newChatId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `chat-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

interface ChatContextValue {
  // Panel visibility
  open: boolean
  setOpen: (open: boolean) => void
  toggleOpen: () => void

  // Active conversation
  chatId: string | null
  title: string
  messages: Msg[]
  running: boolean
  error: string | null

  // Attached workouts — the single source of truth, shared with the Analyze page.
  activityIds: string[]
  setActivityIds: (ids: string[]) => void
  toggleActivity: (id: string) => void

  // Per-chat settings (persisted so a resumed chat restores them).
  backend: string
  setBackend: (v: string) => void
  modelSel: string
  setModelSel: (v: string) => void
  customModel: string
  setCustomModel: (v: string) => void
  effort: string
  setEffort: (v: string) => void
  workoutPrompt: string | null
  setWorkoutPrompt: (v: string) => void
  effectiveModel: string

  // History
  chats: ChatSummary[]
  chatsLoading: boolean

  // Actions
  send: (text: string) => Promise<void>
  stop: () => void
  newChat: () => void
  resumeChat: (id: string, options?: { openPanel?: boolean }) => Promise<void>
  deleteChat: (id: string) => Promise<void>
  renameChat: (title: string) => Promise<void>
}

const ChatContext = createContext<ChatContextValue | null>(null)

export function ChatProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const { data: config } = useQuery({ queryKey: ['config'], queryFn: api.config })

  const [open, setOpen] = useState(false)
  const [chatId, setChatId] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [messages, setMessages] = useState<Msg[]>([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activityIds, setActivityIdsState] = useState<string[]>([])

  const [backend, setBackend] = useState('')
  const [modelSel, setModelSel] = useState('auto')
  const [customModel, setCustomModel] = useState('')
  const [effort, setEffort] = useState('')
  const [workoutPrompt, setWorkoutPrompt] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)
  const committedRef = useRef<{ messageId: string; content: string } | null>(null)
  // Tracks the currently-active chat so a background save that resolves after the user
  // switched chats doesn't write its result onto the wrong conversation.
  const chatIdRef = useRef<string | null>(null)
  useEffect(() => {
    chatIdRef.current = chatId
  }, [chatId])

  const { data: chatList, isLoading: chatsLoading } = useQuery({
    queryKey: ['chats'],
    queryFn: api.chats,
  })
  const chats = chatList?.chats ?? []

  // Seed defaults from server config once it arrives.
  useEffect(() => {
    if (!backend && config?.backends.default) setBackend(config.backends.default)
  }, [config, backend])
  useEffect(() => {
    if (workoutPrompt === null && config?.workout_prompt_default) {
      setWorkoutPrompt(config.workout_prompt_default)
    }
  }, [config, workoutPrompt])

  // Abort any in-flight stream on unmount.
  useEffect(() => () => abortRef.current?.abort(), [])

  const effectiveModel = modelSel === CUSTOM_MODEL ? customModel.trim() : modelSel

  const setActivityIds = useCallback((ids: string[]) => setActivityIdsState(ids), [])
  const toggleActivity = useCallback((id: string) => {
    setActivityIdsState((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }, [])

  const rememberActive = (id: string | null) => {
    try {
      if (id) localStorage.setItem(ACTIVE_KEY, id)
      else localStorage.removeItem(ACTIVE_KEY)
    } catch {
      /* ignore storage failures (private mode, etc.) */
    }
  }

  const persist = useCallback(
    async (id: string, msgs: Msg[], snap: SaveSnapshot) => {
      const cleaned = msgs.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        thinking_summary: m.thinkingSummary,
        thinking: m.thinking,
      }))
      const firstUser = cleaned.find((m) => m.role === 'user')?.content ?? ''
      try {
        const saved = await api.saveChat(id, {
          title: snap.title || firstUser || undefined,
          backend: snap.backend || undefined,
          model: snap.model || undefined,
          reasoning_effort: snap.reasoning_effort || undefined,
          activity_ids: snap.activity_ids,
          messages: cleaned,
        })
        // Only reflect the saved title if this chat is still the active one.
        if (chatIdRef.current === id) setTitle(saved.title)
        queryClient.invalidateQueries({ queryKey: ['chats'] })
      } catch {
        /* a failed save shouldn't disrupt the live conversation */
      }
    },
    [queryClient],
  )

  const send = useCallback(
    async (text: string) => {
      const q = text.trim()
      if (!q || running) return

      const id = chatId ?? newChatId()
      if (!chatId) {
        setChatId(id)
        rememberActive(id)
      }
      // Mark this chat active immediately so a fast-completing save targets it correctly.
      chatIdRef.current = id

      const prior = messages
      const userMsg: Msg = { id: uid(), role: 'user', content: q }
      const asstId = uid()
      committedRef.current = { messageId: asstId, content: '' }
      setMessages([...prior, userMsg, { id: asstId, role: 'assistant', content: '', steps: [] }])
      setRunning(true)
      setError(null)

      const controller = new AbortController()
      abortRef.current = controller

      // Freeze the settings this turn is sent with; the save uses these, not live state.
      const snap: SaveSnapshot = {
        title,
        backend,
        model: effectiveModel,
        reasoning_effort: effort,
        activity_ids: activityIds,
      }

      const transcript = prior.map((m) => `${m.role === 'user' ? 'Me' : 'Coach'}: ${m.content}`).join('\n\n')
      const prompt = transcript
        ? `Here is our conversation so far:\n\n${transcript}\n\nNow respond to my next message:\n\n${q}`
        : q
      const model = !effectiveModel || effectiveModel === 'auto' ? undefined : effectiveModel

      let asstContent = ''
      let asstThinkingSummary = ''
      let asstThinking = ''
      let resolvedBackend = backend
      await streamAnalyze(
        {
          activity_ids: activityIds,
          prompt,
          workout_prompt: workoutPrompt && workoutPrompt.trim() ? workoutPrompt : undefined,
          backend: backend || undefined,
          model,
          reasoning_effort: effort || undefined,
          no_memory: true,
        },
        {
          onStart: (value) => {
            resolvedBackend = value
          },
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
          onThinking: (info) => {
            asstThinkingSummary = info.summary
            asstThinking = info.text
            setMessages((m) =>
              m.map((x) =>
                x.id === asstId
                  ? {
                      ...x,
                      thinkingSummary: info.summary || undefined,
                      thinking: info.text || undefined,
                    }
                  : x,
              ),
            )
          },
          onDelta: (t) => {
            asstContent += t
            if (resolvedBackend !== 'copilot') {
              committedRef.current = { messageId: asstId, content: asstContent }
            }
            setMessages((m) => m.map((x) => (x.id === asstId ? { ...x, content: x.content + t } : x)))
          },
          onReplace: (text) => {
            asstContent = text
            committedRef.current = { messageId: asstId, content: text }
            setMessages((m) => m.map((x) => (x.id === asstId ? { ...x, content: text } : x)))
          },
          onDone: () => {
            setRunning(false)
            committedRef.current = null
            void persist(
              id,
              [
                ...prior,
                userMsg,
                {
                  id: asstId,
                  role: 'assistant',
                  content: asstContent,
                  thinkingSummary: asstThinkingSummary || undefined,
                  thinking: asstThinking || undefined,
                },
              ],
              snap,
            )
          },
          onError: (msg) => {
            setRunning(false)
            committedRef.current = null
            setError(msg)
            setMessages((m) => m.filter((x) => !(x.id === asstId && x.content === '' && !(x.steps && x.steps.length))))
            void persist(id, [...prior, userMsg], snap)
          },
        },
        controller.signal,
      )
    },
    [running, chatId, messages, activityIds, workoutPrompt, backend, effectiveModel, effort, title, persist],
  )

  const stop = useCallback(() => {
    abortRef.current?.abort()
    const committed = committedRef.current
    if (committed) {
      setMessages((messages) =>
        messages.map((message) =>
          message.id === committed.messageId ? { ...message, content: committed.content } : message,
        ),
      )
    }
    committedRef.current = null
    setRunning(false)
  }, [])

  const newChat = useCallback(() => {
    abortRef.current?.abort()
    committedRef.current = null
    setRunning(false)
    setChatId(null)
    setTitle('')
    setMessages([])
    setError(null)
    rememberActive(null)
    // Attachments and settings intentionally carry over, so it's easy to ask a fresh
    // question about the same workouts.
  }, [])

  const loadChat = useCallback(async (id: string, openPanel: boolean) => {
    abortRef.current?.abort()
    committedRef.current = null
    setRunning(false)
    setError(null)
    try {
      const chat = await api.chat(id)
      setChatId(chat.id)
      setTitle(chat.title)
      setMessages(
        chat.messages.map((m) => ({
          id: uid(),
          role: m.role,
          content: m.content,
          thinkingSummary: m.thinking_summary || undefined,
          thinking: m.thinking || undefined,
        })),
      )
      setActivityIdsState(chat.activity_ids ?? [])
      if (chat.backend) setBackend(chat.backend)
      setEffort(chat.reasoning_effort ?? '')
      setModelSel(chat.model || 'auto')
      setCustomModel('')
      rememberActive(chat.id)
      if (openPanel) setOpen(true)
    } catch {
      // The stored chat is gone — forget it.
      rememberActive(null)
    }
  }, [])

  const resumeChat = useCallback(
    (id: string, options?: { openPanel?: boolean }) => loadChat(id, options?.openPanel ?? true),
    [loadChat],
  )

  const deleteChat = useCallback(
    async (id: string) => {
      try {
        await api.deleteChat(id)
      } catch {
        /* ignore — refetch below reflects the true server state */
      }
      queryClient.invalidateQueries({ queryKey: ['chats'] })
      if (id === chatId) newChat()
    },
    [queryClient, chatId, newChat],
  )

  const renameChat = useCallback(
    async (next: string) => {
      const trimmed = next.trim()
      if (!chatId || !trimmed) return
      setTitle(trimmed)
      const cleaned = messages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        thinking_summary: m.thinkingSummary,
        thinking: m.thinking,
      }))
      try {
        await api.saveChat(chatId, {
          title: trimmed,
          backend: backend || undefined,
          model: effectiveModel || undefined,
          reasoning_effort: effort || undefined,
          activity_ids: activityIds,
          messages: cleaned,
        })
        queryClient.invalidateQueries({ queryKey: ['chats'] })
      } catch {
        /* ignore */
      }
    },
    [chatId, messages, backend, effectiveModel, effort, activityIds, queryClient],
  )

  // Restore the last active conversation on load (without popping the panel open),
  // so a refresh doesn't lose your place.
  const restoredRef = useRef(false)
  useEffect(() => {
    if (restoredRef.current) return
    restoredRef.current = true
    let last: string | null = null
    try {
      last = localStorage.getItem(ACTIVE_KEY)
    } catch {
      last = null
    }
    if (last) void loadChat(last, false)
  }, [loadChat])

  const value = useMemo<ChatContextValue>(
    () => ({
      open,
      setOpen,
      toggleOpen: () => setOpen((o) => !o),
      chatId,
      title,
      messages,
      running,
      error,
      activityIds,
      setActivityIds,
      toggleActivity,
      backend,
      setBackend,
      modelSel,
      setModelSel,
      customModel,
      setCustomModel,
      effort,
      setEffort,
      workoutPrompt,
      setWorkoutPrompt,
      effectiveModel,
      chats,
      chatsLoading,
      send,
      stop,
      newChat,
      resumeChat,
      deleteChat,
      renameChat,
    }),
    [
      open,
      chatId,
      title,
      messages,
      running,
      error,
      activityIds,
      setActivityIds,
      toggleActivity,
      backend,
      modelSel,
      customModel,
      effort,
      workoutPrompt,
      effectiveModel,
      chats,
      chatsLoading,
      send,
      stop,
      newChat,
      resumeChat,
      deleteChat,
      renameChat,
    ],
  )

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChat must be used within a ChatProvider')
  return ctx
}
