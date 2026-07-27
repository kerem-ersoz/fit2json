// Human-friendly formatting for workout metrics.

export type UnitSystem = 'metric' | 'imperial'

export function formatDistance(m?: number | null, system: UnitSystem = 'metric'): string {
  if (m == null) return '—'
  if (system === 'imperial') {
    const mi = m / 1609.344
    return mi >= 0.1 ? `${mi.toFixed(2)} mi` : `${Math.round(m * 3.28084)} ft`
  }
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

export function formatPaceOrSpeed(
  mps?: number | null,
  sport?: string | null,
  system: UnitSystem = 'metric',
): string {
  if (mps == null || mps <= 0) return '—'
  if (isPaceSport(sport)) {
    const perUnit = system === 'imperial' ? 1609.344 : 1000
    const sec = perUnit / mps
    let m = Math.floor(sec / 60)
    let s = Math.round(sec % 60)
    if (s === 60) {
      m += 1
      s = 0
    }
    return `${m}:${String(s).padStart(2, '0')} ${system === 'imperial' ? '/mi' : '/km'}`
  }
  return system === 'imperial'
    ? `${(mps * 2.236936).toFixed(1)} mph`
    : `${(mps * 3.6).toFixed(1)} km/h`
}

export function formatHr(bpm?: number | null): string {
  return bpm != null ? `${Math.round(bpm)} bpm` : '—'
}

export function formatPower(w?: number | null): string {
  return w != null ? `${Math.round(w)} W` : '—'
}

export function formatElevation(m?: number | null, system: UnitSystem = 'metric'): string {
  if (m == null) return '—'
  return system === 'imperial' ? `${Math.round(m * 3.28084)} ft` : `${Math.round(m)} m`
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
