// Human-friendly formatting for workout metrics.

export function formatDistance(m?: number | null): string {
  if (m == null) return '—'
  return m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${Math.round(m)} m`
}

export function formatDuration(s?: number | null): string {
  if (s == null) return '—'
  const t = Math.round(s)
  const h = Math.floor(t / 3600)
  const m = Math.floor((t % 3600) / 60)
  const sec = t % 60
  const mm = String(m).padStart(2, '0')
  const ss = String(sec).padStart(2, '0')
  return h > 0 ? `${h}:${mm}:${ss}` : `${m}:${ss}`
}

const PACE_SPORTS = new Set(['running', 'walking', 'hiking', 'trail_running', 'track_running'])

export function isPaceSport(sport?: string | null): boolean {
  return sport ? PACE_SPORTS.has(sport) : false
}

export function formatPaceOrSpeed(mps?: number | null, sport?: string | null): string {
  if (mps == null || mps <= 0) return '—'
  if (isPaceSport(sport)) {
    const secPerKm = 1000 / mps
    const m = Math.floor(secPerKm / 60)
    const s = Math.round(secPerKm % 60)
    return `${m}:${String(s).padStart(2, '0')} /km`
  }
  return `${(mps * 3.6).toFixed(1)} km/h`
}

export function formatHr(bpm?: number | null): string {
  return bpm != null ? `${Math.round(bpm)} bpm` : '—'
}

export function formatPower(w?: number | null): string {
  return w != null ? `${Math.round(w)} W` : '—'
}

export function formatElevation(m?: number | null): string {
  return m != null ? `${Math.round(m)} m` : '—'
}

export function formatCalories(kcal?: number | null): string {
  return kcal != null ? `${Math.round(kcal)} kcal` : '—'
}

export function formatDateTime(iso?: string | null): string {
  if (!iso) return 'Unknown date'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function formatDate(iso?: string | null): string {
  if (!iso) return 'Unknown'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso.slice(0, 10)
  return d.toLocaleDateString(undefined, { dateStyle: 'medium' })
}

export function formatClock(totalSeconds?: number | null): string {
  if (totalSeconds == null) return ''
  const t = Math.max(0, Math.round(totalSeconds))
  const h = Math.floor(t / 3600)
  const m = Math.floor((t % 3600) / 60)
  const s = t % 60
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}
