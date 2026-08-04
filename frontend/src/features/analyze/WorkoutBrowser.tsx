import { Link } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'
import { clsx } from 'clsx'
import type { ComponentProps, RefObject } from 'react'
import type { ActivitySummary } from '../../lib/api'
import { sportMeta } from '../../lib/sport'
import { formatDate, formatDuration, formatHr } from '../../lib/format'
import { workoutZone } from '../../lib/intensity'
import { useUnits } from '../../lib/units'
import { WorkoutControls } from '../activities/WorkoutControls'

interface Props {
  activities: ActivitySummary[]
  selectedIds: Set<string>
  onToggle: (id: string) => void
  onToggleAll: () => void
  controls: ComponentProps<typeof WorkoutControls>
  listRef?: RefObject<HTMLUListElement>
  hrMax: number
  surface?: 'page' | 'sheet'
}

/** Filterable, multi-selectable list of workouts used as context for the Analyze workspace. */
export function WorkoutBrowser({
  activities,
  selectedIds,
  onToggle,
  onToggleAll,
  controls,
  listRef,
  hrMax,
  surface = 'page',
}: Props) {
  const allSelected = activities.length > 0 && activities.every((a) => selectedIds.has(a.id))

  return (
    <div
      className={clsx(
        'rounded-xl border border-divider bg-surface',
        surface === 'sheet' && 'flex h-full min-h-0 flex-col',
      )}
    >
      <div className="shrink-0 space-y-3 border-b border-divider-soft p-3 sm:p-4">
        <WorkoutControls {...controls} layout="stacked" />
        <div className="flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={onToggleAll}
            disabled={activities.length === 0}
            className="rounded text-xs font-medium text-accent-strong hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-40"
          >
            {allSelected ? 'Clear selection' : `Select all${activities.length ? ` (${activities.length})` : ''}`}
          </button>
          <span className="text-xs tabular-nums text-muted">{selectedIds.size} selected</span>
        </div>
      </div>
      {activities.length === 0 ? (
        <p className="p-6 text-center text-sm text-muted">No workouts match your filters.</p>
      ) : (
        <ul
          ref={listRef}
          className={clsx(
            'divide-y divide-divider-soft overflow-y-auto',
            surface === 'sheet'
              ? 'min-h-0 flex-1'
              : 'max-h-[22rem] lg:max-h-[calc(100vh-15rem)]',
          )}
        >
          {activities.map((a) => (
            <WorkoutRow key={a.id} activity={a} selected={selectedIds.has(a.id)} onToggle={onToggle} hrMax={hrMax} />
          ))}
        </ul>
      )}
    </div>
  )
}

function WorkoutRow({
  activity,
  selected,
  onToggle,
  hrMax,
}: {
  activity: ActivitySummary
  selected: boolean
  onToggle: (id: string) => void
  hrMax: number
}) {
  const { label, Icon } = sportMeta(activity.sport)
  const { fmt } = useUnits()
  const m = activity.metrics
  const z = workoutZone(activity, hrMax)
  const inputId = `select-${activity.id}`

  const title =
    m.distance_m && m.distance_m > 0
      ? `${fmt.distance(m.distance_m)} ${label}`
      : m.duration_s
        ? `${formatDuration(m.duration_s)} ${label}`
        : label

  const discTitle = z.zone
    ? `Zone ${z.zone} · ${z.label}${m.avg_hr ? ` · avg ${formatHr(m.avg_hr)}` : ''}${
        z.pctOfMax ? ` (~${Math.round(z.pctOfMax * 100)}% of max)` : ''
      }`
    : 'No heart-rate data'

  return (
    <li
      className={clsx(
        'flex items-center gap-3 px-3 py-2.5 transition-colors sm:px-4',
        selected ? 'bg-accent-tint' : 'hover:bg-hover',
      )}
    >
      <input
        id={inputId}
        type="checkbox"
        checked={selected}
        onChange={() => onToggle(activity.id)}
        data-activity-card
        aria-label={`Select ${title}${z.zone ? `, ${z.label} intensity` : ''}, ${formatDate(activity.start_time)}`}
        className="h-4 w-4 shrink-0 rounded border-divider-strong text-accent focus:ring-accent focus:ring-offset-0"
      />
      <label htmlFor={inputId} className="flex min-w-0 flex-1 cursor-pointer items-center gap-3">
        <span
          title={discTitle}
          className={clsx('flex h-8 w-8 shrink-0 items-center justify-center rounded-full', z.disc, z.icon)}
        >
          <Icon className="h-4 w-4" />
        </span>
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium text-ink">{title}</span>
          <span className="flex items-center gap-1.5 text-xs text-muted">
            {z.zone && <span className={clsx('h-2 w-2 shrink-0 rounded-full', z.dot)} aria-hidden />}
            {z.zone && <span className="shrink-0 text-copy">{z.label}</span>}
            {z.zone && <span aria-hidden>·</span>}
            <span className="truncate tabular-nums">
              {formatDate(activity.start_time)}
              {m.avg_hr ? ` · ${formatHr(m.avg_hr)}` : ''}
            </span>
          </span>
        </span>
      </label>
      <Link
        to={`/activities/${encodeURIComponent(activity.id)}#analyze-panel`}
        aria-label={`Open ${label}`}
        title="Open workout"
        className="shrink-0 rounded p-1 text-faint transition-colors hover:text-accent-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        <ArrowUpRight className="h-4 w-4" />
      </Link>
    </li>
  )
}
