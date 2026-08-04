// Heart-rate intensity zones for at-a-glance workout scanning.
//
// We don't have the athlete's true HRmax, so we approximate it from the highest HR seen
// across the library and bucket each workout's *average* HR into a 5-zone model with the
// conventional colour ramp (gray → blue → green → orange → red). This is a visual cue, not
// a medical zone calculation.
import type { ActivitySummary } from './api'

// Full literal Tailwind classes (so the JIT scanner keeps them).
const COLORS = {
  gray: { disc: 'bg-surface-subtle', icon: 'text-muted', dot: 'bg-faint' },
  blue: { disc: 'bg-zone-blue-tint', icon: 'text-zone-blue', dot: 'bg-zone-blue' },
  green: { disc: 'bg-zone-green-tint', icon: 'text-zone-green', dot: 'bg-zone-green' },
  orange: { disc: 'bg-zone-orange-tint', icon: 'text-zone-orange', dot: 'bg-zone-orange' },
  red: { disc: 'bg-danger-tint', icon: 'text-danger', dot: 'bg-danger-soft' },
  none: { disc: 'bg-surface-subtle', icon: 'text-faint', dot: 'bg-divider-strong' },
} as const

// Ordered high → low; the first threshold an activity clears wins.
const LEVELS = [
  { min: 0.9, zone: 5, label: 'Max', color: 'red' },
  { min: 0.8, zone: 4, label: 'Threshold', color: 'orange' },
  { min: 0.7, zone: 3, label: 'Tempo', color: 'green' },
  { min: 0.6, zone: 2, label: 'Easy', color: 'blue' },
  { min: 0.0, zone: 1, label: 'Recovery', color: 'gray' },
] as const

export interface WorkoutZone {
  zone: number | null
  label: string
  pctOfMax: number | null
  disc: string
  icon: string
  dot: string
}

/** Approximate the athlete's HRmax from the highest HR recorded across the library. */
export function hrMaxProxy(activities: ActivitySummary[]): number {
  let max = 0
  for (const a of activities) {
    const h = a.metrics.max_hr ?? a.metrics.avg_hr ?? 0
    if (h > max) max = h
  }
  return Math.max(max, 150)
}

/** Bucket a workout's average HR into a coloured intensity zone (or "none" if no HR data). */
export function workoutZone(activity: ActivitySummary, hrMax: number): WorkoutZone {
  const hr = activity.metrics.avg_hr
  if (!hr || hr <= 0 || !hrMax) {
    return { zone: null, label: '', pctOfMax: null, ...COLORS.none }
  }
  const pct = hr / hrMax
  const level = LEVELS.find((l) => pct >= l.min) ?? LEVELS[LEVELS.length - 1]
  const c = COLORS[level.color]
  return { zone: level.zone, label: level.label, pctOfMax: pct, disc: c.disc, icon: c.icon, dot: c.dot }
}
