// Heart-rate intensity zones for at-a-glance workout scanning.
//
// We don't have the athlete's true HRmax, so we approximate it from the highest HR seen
// across the library and bucket each workout's *average* HR into a 5-zone model with the
// conventional colour ramp (gray → blue → green → orange → red). This is a visual cue, not
// a medical zone calculation.
import type { ActivitySummary } from './api'

// Full literal Tailwind classes (so the JIT scanner keeps them).
const COLORS = {
  gray: { disc: 'bg-slate-100', icon: 'text-slate-500', dot: 'bg-slate-400' },
  blue: { disc: 'bg-blue-50', icon: 'text-blue-600', dot: 'bg-blue-500' },
  green: { disc: 'bg-green-50', icon: 'text-green-600', dot: 'bg-green-500' },
  orange: { disc: 'bg-orange-50', icon: 'text-orange-600', dot: 'bg-orange-500' },
  red: { disc: 'bg-red-50', icon: 'text-red-600', dot: 'bg-red-500' },
  none: { disc: 'bg-slate-100', icon: 'text-slate-400', dot: 'bg-slate-300' },
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
