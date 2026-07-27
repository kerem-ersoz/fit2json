import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  formatCalories,
  formatDistance,
  formatDuration,
  formatElevation,
  formatHr,
  formatPaceOrSpeed,
  formatPower,
  type UnitSystem,
} from './format'

interface UnitsContextValue {
  system: UnitSystem
  setSystem: (s: UnitSystem) => void
  fmt: {
    distance: (m?: number | null) => string
    paceOrSpeed: (mps?: number | null, sport?: string | null) => string
    elevation: (m?: number | null) => string
    duration: typeof formatDuration
    hr: typeof formatHr
    power: typeof formatPower
    calories: typeof formatCalories
  }
}

const UnitsContext = createContext<UnitsContextValue | null>(null)
const STORAGE_KEY = 'fitsift-units'

function initialSystem(): UnitSystem {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'imperial' ? 'imperial' : 'metric'
  } catch {
    return 'metric'
  }
}

export function UnitsProvider({ children }: { children: ReactNode }) {
  const [system, setSystemState] = useState<UnitSystem>(initialSystem)

  const setSystem = (s: UnitSystem) => {
    setSystemState(s)
    try {
      localStorage.setItem(STORAGE_KEY, s)
    } catch {
      /* ignore */
    }
  }

  const fmt = useMemo(
    () => ({
      distance: (m?: number | null) => formatDistance(m, system),
      paceOrSpeed: (mps?: number | null, sport?: string | null) =>
        formatPaceOrSpeed(mps, sport, system),
      elevation: (m?: number | null) => formatElevation(m, system),
      duration: formatDuration,
      hr: formatHr,
      power: formatPower,
      calories: formatCalories,
    }),
    [system],
  )

  const value = useMemo(() => ({ system, setSystem, fmt }), [system, fmt])
  return <UnitsContext.Provider value={value}>{children}</UnitsContext.Provider>
}

export function useUnits(): UnitsContextValue {
  const ctx = useContext(UnitsContext)
  if (!ctx) throw new Error('useUnits must be used within a UnitsProvider')
  return ctx
}
