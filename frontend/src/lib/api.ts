// Typed client for the FitSift JSON API.
// API base derives from Vite's BASE_URL so it works at "/" locally and under a
// path prefix (e.g. /fitsift) later, with no code change.

const API_BASE = `${import.meta.env.BASE_URL.replace(/\/$/, '')}/api`

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
  base_path: string
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

export interface ActivitySummary {
  id: string
  sport: string | null
  start_time: string | null
  source_file: string
  file: string
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

export const api = {
  config: () => getJSON<AppConfig>('/config'),
  activities: () => getJSON<ActivitySummary[]>('/activities'),
  activity: (id: string) => getJSON<ActivityDetail>(`/activities/${encodeURIComponent(id)}`),
  streams: (id: string, maxPoints = 2000) =>
    getJSON<Streams>(
      `/activities/${encodeURIComponent(id)}/streams?max_points=${maxPoints}`,
    ),
  laps: (id: string) => getJSON<{ laps: Lap[] }>(`/activities/${encodeURIComponent(id)}/laps`),
  rawUrl: (id: string) => `${API_BASE}/activities/${encodeURIComponent(id)}/raw`,
}
