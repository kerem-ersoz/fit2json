import { Search } from 'lucide-react'
import type { RefObject } from 'react'
import { sportMeta } from '../../lib/sport'
import { SORT_LABELS, type SortKey } from '../../lib/library'
import { Select } from '../../components/ui/Select'

interface Props {
  search: string
  onSearch: (value: string) => void
  sport: string
  sports: string[]
  onSport: (value: string) => void
  sort: SortKey
  onSort: (value: SortKey) => void
  searchRef?: RefObject<HTMLInputElement>
}

/** The shared search + sport + sort control bar used by Library and Analyze. */
export function WorkoutControls({ search, onSearch, sport, sports, onSport, sort, onSort, searchRef }: Props) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
      <div className="relative w-full sm:w-auto">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
          aria-hidden
        />
        <input
          ref={searchRef}
          type="search"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              onSearch('')
              e.currentTarget.blur()
            }
          }}
          placeholder="Search workouts…"
          aria-label="Search workouts"
          className="h-11 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-9 text-sm text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 sm:w-56"
        />
        {!search && (
          <kbd className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[11px] font-medium text-slate-400 sm:block">
            /
          </kbd>
        )}
      </div>
      <Select aria-label="Filter by sport" value={sport} onChange={(e) => onSport(e.target.value)} className="sm:w-40">
        <option value="all">All sports</option>
        {sports.map((s) => (
          <option key={s} value={s}>
            {sportMeta(s).label}
          </option>
        ))}
      </Select>
      <Select
        aria-label="Sort workouts"
        value={sort}
        onChange={(e) => onSort(e.target.value as SortKey)}
        className="sm:w-36"
      >
        {(Object.keys(SORT_LABELS) as SortKey[]).map((k) => (
          <option key={k} value={k}>
            {SORT_LABELS[k]}
          </option>
        ))}
      </Select>
    </div>
  )
}
