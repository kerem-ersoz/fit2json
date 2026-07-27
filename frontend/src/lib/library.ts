// Sorting, date-grouping, and weekly-volume helpers for the Library view.
import type { ActivitySummary } from './api'

export type SortKey = 'date' | 'distance' | 'duration'

export const SORT_LABELS: Record<SortKey, string> = {
  date: 'Newest',
  distance: 'Distance',
  duration: 'Duration',
}

export function isSortKey(v: string | null): v is SortKey {
  return v === 'date' || v === 'distance' || v === 'duration'
}

function timeOf(a: ActivitySummary): number {
  if (!a.start_time) return Number.NEGATIVE_INFINITY
  const t = new Date(a.start_time).getTime()
  return Number.isNaN(t) ? Number.NEGATIVE_INFINITY : t
}

/** Returns a new array sorted for the given key (all descending: newest / farthest / longest first). */
export function sortActivities(list: ActivitySummary[], key: SortKey): ActivitySummary[] {
  const arr = [...list]
  arr.sort((a, b) => {
    if (key === 'distance') return (b.metrics.distance_m ?? -1) - (a.metrics.distance_m ?? -1)
    if (key === 'duration') return (b.metrics.duration_s ?? -1) - (a.metrics.duration_s ?? -1)
    return timeOf(b) - timeOf(a)
  })
  return arr
}

export interface ActivityGroup {
  key: string
  label: string
  items: ActivitySummary[]
}

/**
 * Buckets a date-sorted list into "This week" / "This month" / "Month YYYY" / "Undated".
 * Assumes `sorted` is already newest-first so encounter order yields the right group order.
 */
export function groupByDate(sorted: ActivitySummary[], now: Date = new Date()): ActivityGroup[] {
  const weekAgo = now.getTime() - 7 * 24 * 3600 * 1000
  const monthFmt = new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric' })
  const groups: ActivityGroup[] = []
  const index = new Map<string, ActivityGroup>()

  for (const a of sorted) {
    const t = a.start_time ? new Date(a.start_time).getTime() : NaN
    let key: string
    let label: string
    if (!a.start_time || Number.isNaN(t)) {
      key = 'undated'
      label = 'Undated'
    } else if (t >= weekAgo) {
      key = 'week'
      label = 'This week'
    } else {
      const d = new Date(t)
      if (d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth()) {
        key = 'month'
        label = 'This month'
      } else {
        label = monthFmt.format(d)
        key = label
      }
    }
    let g = index.get(key)
    if (!g) {
      g = { key, label, items: [] }
      index.set(key, g)
      groups.push(g)
    }
    g.items.push(a)
  }
  return groups
}

export interface WeekBucket {
  weekStart: number
  distanceM: number
  durationS: number
  count: number
}

function startOfWeek(d: Date): number {
  const x = new Date(d)
  x.setHours(0, 0, 0, 0)
  const mondayIndex = (x.getDay() + 6) % 7 // 0 = Monday
  x.setDate(x.getDate() - mondayIndex)
  return x.getTime()
}

/** Totals per ISO week (Monday-based) for the last `weeks` weeks, oldest-first. */
export function weeklyVolume(list: ActivitySummary[], weeks = 8, now: Date = new Date()): WeekBucket[] {
  const weekMs = 7 * 24 * 3600 * 1000
  const thisWeek = startOfWeek(now)
  const buckets: WeekBucket[] = []
  const index = new Map<number, WeekBucket>()
  for (let i = weeks - 1; i >= 0; i--) {
    const weekStart = thisWeek - i * weekMs
    const bucket: WeekBucket = { weekStart, distanceM: 0, durationS: 0, count: 0 }
    buckets.push(bucket)
    index.set(weekStart, bucket)
  }
  for (const a of list) {
    if (!a.start_time) continue
    const t = new Date(a.start_time).getTime()
    if (Number.isNaN(t)) continue
    const bucket = index.get(startOfWeek(new Date(t)))
    if (!bucket) continue
    bucket.distanceM += a.metrics.distance_m ?? 0
    bucket.durationS += a.metrics.duration_s ?? 0
    bucket.count += 1
  }
  return buckets
}
