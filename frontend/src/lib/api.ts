// Typed client for the FitSift JSON API.
// Remote builds can target a private tailnet URL; local and bundled builds retain
// the same-origin /api default.

const configuredApiBase = import.meta.env.VITE_API_BASE_URL?.trim()
const API_BASE = (
  configuredApiBase || `${import.meta.env.BASE_URL.replace(/\/$/, '')}/api`
).replace(/\/+$/, '')

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = body.detail
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail)
  }
  return (await res.json()) as T
}

export interface AppConfig {
  brand: { name: string; tagline: string }
  backends: { copilot: boolean; default: string }
  library_dir: string
  memory_dir: string
  chats_dir: string
  base_path: string
  workout_prompt_default: string
}

export interface ModelInfo {
  backend: string
  models: string[]
  efforts: string[]
  allow_custom: boolean
  reachable: boolean
}

export interface Metrics {
  distance_m?: number
  duration_s?: number
  avg_hr?: number
  max_hr?: number
  avg_speed_mps?: number
  avg_power_w?: number
  total_calories?: number
  ascent_m?: number
}

export interface SourceRef {
  platform: string
  label: string
  id: string
  url: string
}

export interface ActivitySummary {
  id: string
  sport: string | null
  start_time: string | null
  source_file: string
  source: string | null
  source_ref: SourceRef | null
  metrics: Metrics
  record_count: number
  available_series: string[]
  has_gps: boolean
}

export interface ActivityDetail {
  id: string
  sport: string | null
  start_time: string | null
  source_file: string
  source: string | null
  source_ref: SourceRef | null
  message_counts: Record<string, number>
  field_units: Record<string, string>
  metrics: Metrics
  session: Record<string, unknown>
  available_series: string[]
  has_gps: boolean
}

export interface Series {
  unit: string
  values: (number | null)[]
}

export interface Streams {
  total_records: number
  point_count: number
  stride: number
  time_s: (number | null)[]
  distance_m: (number | null)[]
  series: Record<string, Series>
  latlng: [number, number][]
}

export type Lap = Record<string, unknown>

export interface AnalysisEntry {
  entry_id: string
  prompt: string
  created_at: string
  backend: string
  model: string
  sport: string | null
  date: string | null
  metrics?: Metrics
  content?: string
}

export interface IngestResult {
  added: ActivitySummary[]
  skipped: number
  errors: { file: string; error: string }[]
}

export interface FetchResult {
  added: ActivitySummary[]
  skipped: number
  fetched: number
}

export interface AthleteProfile {
  name?: string | null
  sex?: string | null
  birth_year?: number | null
  height_cm?: number | null
  weight_kg?: number | null
  resting_hr?: number | null
  max_hr?: number | null
  lactate_threshold_hr?: number | null
  ftp_w?: number | null
  vo2max?: number | null
  goals?: string | null
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  thinking_summary?: string | null
  thinking?: string | null
  created_at?: string
}

export interface ChatSummary {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
  backend: string
  model: string
  activity_ids: string[]
}

export interface Chat {
  id: string
  title: string
  created_at: string
  updated_at: string
  backend: string
  model: string
  reasoning_effort: string
  activity_ids: string[]
  messages: ChatMessage[]
}

export interface ChatSaveBody {
  title?: string
  backend?: string
  model?: string
  reasoning_effort?: string
  activity_ids: string[]
  messages: ChatMessage[]
}

export const api = {
  config: () => getJSON<AppConfig>('/config'),
  models: (backend: string) => getJSON<ModelInfo>(`/models?backend=${encodeURIComponent(backend)}`),
  activities: () => getJSON<ActivitySummary[]>('/activities'),
  activity: (id: string) => getJSON<ActivityDetail>(`/activities/${encodeURIComponent(id)}`),
  streams: (id: string, maxPoints = 2000) =>
    getJSON<Streams>(
      `/activities/${encodeURIComponent(id)}/streams?max_points=${maxPoints}`,
    ),
  laps: (id: string) => getJSON<{ laps: Lap[] }>(`/activities/${encodeURIComponent(id)}/laps`),
  analyses: (id: string) =>
    getJSON<{ analyses: AnalysisEntry[] }>(`/activities/${encodeURIComponent(id)}/analyses`),
  memory: (params?: { sport?: string; days?: number; limit?: number }) => {
    const q = new URLSearchParams()
    if (params?.sport) q.set('sport', params.sport)
    if (params?.days != null) q.set('days', String(params.days))
    if (params?.limit != null) q.set('limit', String(params.limit))
    const qs = q.toString()
    return getJSON<{ entries: AnalysisEntry[] }>(`/memory${qs ? `?${qs}` : ''}`)
  },
  memoryEntry: (entryId: string) =>
    getJSON<AnalysisEntry>(`/memory/${encodeURIComponent(entryId)}`),
  rawUrl: (id: string) => `${API_BASE}/activities/${encodeURIComponent(id)}/raw`,

  uploadFit: async (files: File[]): Promise<IngestResult> => {
    const form = new FormData()
    for (const f of files) form.append('files', f)
    const res = await fetch(`${API_BASE}/convert`, { method: 'POST', body: form })
    if (!res.ok) throw new Error(await errorText(res))
    return (await res.json()) as IngestResult
  },

  fetchFrom: async (platform: 'garmin' | 'strava', days: number): Promise<FetchResult> => {
    const res = await fetch(`${API_BASE}/fetch/${platform}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ days }),
    })
    if (!res.ok) throw new Error(await errorText(res))
    return (await res.json()) as FetchResult
  },

  profile: () => getJSON<AthleteProfile>('/profile'),

  saveProfile: async (profile: AthleteProfile): Promise<AthleteProfile> => {
    const res = await fetch(`${API_BASE}/profile`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profile),
    })
    if (!res.ok) throw new Error(await errorText(res))
    return (await res.json()) as AthleteProfile
  },

  chats: () => getJSON<{ chats: ChatSummary[] }>('/chats'),

  chat: (id: string) => getJSON<Chat>(`/chats/${encodeURIComponent(id)}`),

  saveChat: async (id: string, body: ChatSaveBody): Promise<Chat> => {
    const res = await fetch(`${API_BASE}/chats/${encodeURIComponent(id)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error(await errorText(res))
    return (await res.json()) as Chat
  },

  deleteChat: async (id: string): Promise<void> => {
    const res = await fetch(`${API_BASE}/chats/${encodeURIComponent(id)}`, { method: 'DELETE' })
    if (!res.ok) throw new Error(await errorText(res))
  },
}

async function errorText(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (body?.detail) return body.detail
  } catch {
    /* ignore */
  }
  return `${res.status} ${res.statusText}`
}

export interface AnalyzeBody {
  activity_id?: string
  activity_ids?: string[]
  prompt: string
  workout_prompt?: string | null
  backend?: string | null
  model?: string | null
  reasoning_effort?: string | null
  no_memory?: boolean
}

export interface MapStep {
  index: number
  total: number
  label: string
  reused?: boolean
  state: 'start' | 'done'
}

export interface ThinkingInfo {
  summary: string
  text: string
}

export interface StreamHandlers {
  onStart?: (backend: string) => void
  onStep?: (step: MapStep) => void
  onReduce?: (info: { count: number }) => void
  onThinking?: (info: ThinkingInfo) => void
  onDelta: (text: string) => void
  onReplace?: (text: string) => void
  onDone?: (info: { chars: number; saved: string | null; backend: string }) => void
  onError?: (message: string) => void
}

interface SseFrame {
  event: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any
}

function parseFrame(frame: string): SseFrame | null {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }
  if (dataLines.length === 0) return null
  try {
    return { event, data: JSON.parse(dataLines.join('\n')) }
  } catch {
    return null
  }
}

/** POST a JSON body and return the streaming Response, or an error message string. */
async function startSse(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<Response | string | null> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (e) {
    // An intentional abort (Stop, navigation, unmount) is not an error — stop silently.
    if ((e as Error)?.name === 'AbortError' || signal?.aborted) return null
    return (e as Error)?.message ?? 'Request failed'
  }
  if (!res.ok || !res.body) {
    let msg = `${res.status} ${res.statusText}`
    try {
      const b = await res.json()
      if (b?.detail) msg = b.detail
    } catch {
      /* ignore */
    }
    return msg
  }
  return res
}

/** Read an SSE Response body, dispatching each parsed frame. Stops silently when the
 *  request is aborted via its AbortController; other stream errors propagate. */
async function pumpSse(res: Response, onFrame: (frame: SseFrame) => void): Promise<void> {
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let sep: number
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        const parsed = parseFrame(frame)
        if (parsed) onFrame(parsed)
      }
    }
  } catch (e) {
    if ((e as Error)?.name === 'AbortError') return // cancelled via AbortController — expected
    throw e
  }
}

/** POST /analyze and stream the Server-Sent Events back through the handlers. */
export async function streamAnalyze(
  body: AnalyzeBody,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const started = await startSse('/analyze', body, signal)
  if (started === null) return // aborted — stop silently
  if (typeof started === 'string') {
    handlers.onError?.(started)
    return
  }
  await pumpSse(started, (parsed) => {
    if (parsed.event === 'start') handlers.onStart?.(parsed.data.backend)
    else if (parsed.event === 'step') handlers.onStep?.(parsed.data)
    else if (parsed.event === 'reduce') handlers.onReduce?.(parsed.data)
    else if (parsed.event === 'thinking')
      handlers.onThinking?.({
        summary: parsed.data.summary ?? '',
        text: parsed.data.text ?? '',
      })
    else if (parsed.event === 'delta') handlers.onDelta(parsed.data.text ?? '')
    else if (parsed.event === 'replace') handlers.onReplace?.(parsed.data.text ?? '')
    else if (parsed.event === 'done') handlers.onDone?.(parsed.data)
    else if (parsed.event === 'error') handlers.onError?.(parsed.data.message ?? 'Analysis failed')
  })
}

export interface InfographicBody {
  analysis: string
  backend?: string | null
  model?: string | null
  reasoning_effort?: string | null
}

export interface InfographicHandlers {
  onStart?: (backend: string) => void
  onDelta: (text: string) => void
  onDone?: (info: { chars: number; backend: string; id: string }) => void
  onError?: (message: string) => void
}

/** URL that serves a finished infographic as a standalone page (for the iframe `src`). */
export function infographicViewUrl(id: string): string {
  return `${API_BASE}/infographic/view/${encodeURIComponent(id)}`
}

/** POST /infographic and stream the generated HTML back through the handlers. */
export async function streamInfographic(
  body: InfographicBody,
  handlers: InfographicHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const started = await startSse('/infographic', body, signal)
  if (started === null) return // aborted — stop silently
  if (typeof started === 'string') {
    handlers.onError?.(started)
    return
  }
  await pumpSse(started, (parsed) => {
    if (parsed.event === 'start') handlers.onStart?.(parsed.data.backend)
    else if (parsed.event === 'delta') handlers.onDelta(parsed.data.text ?? '')
    else if (parsed.event === 'done') handlers.onDone?.(parsed.data)
    else if (parsed.event === 'error') handlers.onError?.(parsed.data.message ?? 'Infographic failed')
  })
}

// ── Persisted infographics for saved analyses (keyed by memory entry_id) ──────

export interface InfographicOptions {
  backend?: string | null
  model?: string | null
  reasoning_effort?: string | null
}

export interface MemoryInfographicHandlers {
  onStart?: (backend: string) => void
  onDelta: (text: string) => void
  onDone?: (info: { chars: number; backend: string; generated_at: string | null }) => void
  onError?: (message: string) => void
}

/** Whether a saved analysis already has a cached infographic. */
export function memoryInfographicStatus(entryId: string) {
  return getJSON<{ exists: boolean; generated_at: string | null }>(
    `/memory/${encodeURIComponent(entryId)}/infographic`,
  )
}

/** URL that serves a saved analysis's cached infographic (for the iframe `src`). */
export function memoryInfographicViewUrl(entryId: string): string {
  return `${API_BASE}/memory/${encodeURIComponent(entryId)}/infographic/view`
}

/** URL of the stored infographic HTML as-is (for copy / download). */
export function memoryInfographicRawUrl(entryId: string): string {
  return `${API_BASE}/memory/${encodeURIComponent(entryId)}/infographic/raw`
}

/** POST to (re)generate and persist a saved analysis's infographic; streams progress. */
export async function streamMemoryInfographic(
  entryId: string,
  body: InfographicOptions,
  handlers: MemoryInfographicHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const started = await startSse(
    `/memory/${encodeURIComponent(entryId)}/infographic`,
    body,
    signal,
  )
  if (started === null) return // aborted — stop silently
  if (typeof started === 'string') {
    handlers.onError?.(started)
    return
  }
  await pumpSse(started, (parsed) => {
    if (parsed.event === 'start') handlers.onStart?.(parsed.data.backend)
    else if (parsed.event === 'delta') handlers.onDelta(parsed.data.text ?? '')
    else if (parsed.event === 'done') handlers.onDone?.(parsed.data)
    else if (parsed.event === 'error') handlers.onError?.(parsed.data.message ?? 'Infographic failed')
  })
}
