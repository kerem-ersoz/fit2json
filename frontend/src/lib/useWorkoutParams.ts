import { useSearchParams } from 'react-router-dom'
import { isSortKey, type SortKey } from './library'

export type WorkoutParamKey = 'q' | 'sport' | 'sort'

export interface WorkoutParams {
  search: string
  sport: string
  sort: SortKey
  isFiltering: boolean
  setParam: (key: WorkoutParamKey, value: string, defaultValue: string) => void
  clearFilters: () => void
}

/**
 * Shared URL-backed filter/sort state for the workout lists (Library + Analyze), so the
 * two surfaces behave identically and stay bookmarkable / navigation-stable.
 */
export function useWorkoutParams(): WorkoutParams {
  const [params, setParams] = useSearchParams()
  const search = params.get('q') ?? ''
  const sport = params.get('sport') ?? 'all'
  const sortRaw = params.get('sort')
  const sort: SortKey = isSortKey(sortRaw) ? sortRaw : 'date'

  const setParam = (key: WorkoutParamKey, value: string, defaultValue: string) => {
    const next = new URLSearchParams(params)
    if (!value || value === defaultValue) next.delete(key)
    else next.set(key, value)
    setParams(next, { replace: true })
  }

  const clearFilters = () => {
    const next = new URLSearchParams(params)
    next.delete('q')
    next.delete('sport')
    setParams(next, { replace: true })
  }

  return { search, sport, sort, isFiltering: search.trim() !== '' || sport !== 'all', setParam, clearFilters }
}
