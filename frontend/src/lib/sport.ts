import {
  Activity,
  Bike,
  Dumbbell,
  Footprints,
  Mountain,
  Waves,
  type LucideIcon,
} from 'lucide-react'

interface SportMeta {
  label: string
  Icon: LucideIcon
}

const SPORTS: Record<string, SportMeta> = {
  running: { label: 'Run', Icon: Footprints },
  trail_running: { label: 'Trail Run', Icon: Footprints },
  walking: { label: 'Walk', Icon: Footprints },
  hiking: { label: 'Hike', Icon: Mountain },
  cycling: { label: 'Ride', Icon: Bike },
  swimming: { label: 'Swim', Icon: Waves },
  rowing: { label: 'Row', Icon: Waves },
  strength_training: { label: 'Strength', Icon: Dumbbell },
  fitness_equipment: { label: 'Gym', Icon: Dumbbell },
}

export function sportMeta(sport?: string | null): SportMeta {
  if (sport && SPORTS[sport]) return SPORTS[sport]
  const label = sport
    ? sport.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : 'Activity'
  return { label, Icon: Activity }
}
