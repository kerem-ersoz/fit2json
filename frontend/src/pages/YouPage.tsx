import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, HeartPulse, Loader2, Save, Target, User } from 'lucide-react'
import { api, type AthleteProfile } from '../lib/api'
import { Button } from '../components/ui/Button'
import { Card, CardBody } from '../components/ui/Card'
import { ErrorState, LoadingState } from '../components/ui/Feedback'
import { useUnits } from '../lib/units'
import type { UnitSystem } from '../lib/format'

// ── unit conversions (profile is stored canonically in metric: cm / kg) ──────────
const LB_PER_KG = 2.2046226218

function cmToFtIn(cm: number): { ft: number; inch: number } {
  const totalIn = cm / 2.54
  let ft = Math.floor(totalIn / 12)
  let inch = Math.round(totalIn - ft * 12)
  if (inch === 12) {
    ft += 1
    inch = 0
  }
  return { ft, inch }
}
const ftInToCm = (ft: number, inch: number) => (ft * 12 + inch) * 2.54
const round1 = (n: number) => Math.round(n * 10) / 10

// ── draft form state (all strings so partial/decimal typing is preserved) ────────
interface Draft {
  name: string
  sex: string
  birthYear: string
  heightCm: string
  heightFt: string
  heightIn: string
  weightKg: string
  weightLb: string
  restingHr: string
  maxHr: string
  lthr: string
  ftp: string
  vo2max: string
  goals: string
}

const numStr = (v: number | null | undefined) => (v == null ? '' : String(v))

function seed(p: AthleteProfile, system: UnitSystem): Draft {
  const d: Draft = {
    name: p.name ?? '',
    sex: p.sex ?? '',
    birthYear: numStr(p.birth_year),
    heightCm: '',
    heightFt: '',
    heightIn: '',
    weightKg: '',
    weightLb: '',
    restingHr: numStr(p.resting_hr),
    maxHr: numStr(p.max_hr),
    lthr: numStr(p.lactate_threshold_hr),
    ftp: numStr(p.ftp_w),
    vo2max: numStr(p.vo2max),
    goals: p.goals ?? '',
  }
  if (p.height_cm != null) {
    if (system === 'imperial') {
      const { ft, inch } = cmToFtIn(p.height_cm)
      d.heightFt = String(ft)
      d.heightIn = String(inch)
    } else {
      d.heightCm = String(round1(p.height_cm))
    }
  }
  if (p.weight_kg != null) {
    if (system === 'imperial') d.weightLb = String(round1(p.weight_kg * LB_PER_KG))
    else d.weightKg = String(round1(p.weight_kg))
  }
  return d
}

const toNum = (s: string): number | null => {
  const t = s.trim()
  if (!t) return null
  const n = Number(t)
  return Number.isFinite(n) ? n : null
}
const toInt = (s: string): number | null => {
  const n = toNum(s)
  return n == null ? null : Math.round(n)
}

function buildPayload(d: Draft, system: UnitSystem): AthleteProfile {
  let height_cm: number | null
  if (system === 'imperial') {
    const ft = toNum(d.heightFt)
    const inch = toNum(d.heightIn)
    height_cm = ft == null && inch == null ? null : round1(ftInToCm(ft ?? 0, inch ?? 0))
  } else {
    height_cm = toNum(d.heightCm)
  }

  let weight_kg: number | null
  if (system === 'imperial') {
    const lb = toNum(d.weightLb)
    weight_kg = lb == null ? null : round1(lb / LB_PER_KG)
  } else {
    weight_kg = toNum(d.weightKg)
  }

  return {
    name: d.name.trim() || null,
    sex: d.sex || null,
    birth_year: toInt(d.birthYear),
    height_cm,
    weight_kg,
    resting_hr: toInt(d.restingHr),
    max_hr: toInt(d.maxHr),
    lactate_threshold_hr: toInt(d.lthr),
    ftp_w: toInt(d.ftp),
    vo2max: toNum(d.vo2max),
    goals: d.goals.trim() || null,
  }
}

// Re-express only the height/weight display fields when the unit system changes, so
// switching units mid-edit converts those values in place and preserves every other field.
function convertUnits(d: Draft, from: UnitSystem, to: UnitSystem): Draft {
  if (from === to) return d

  let cm: number | null
  if (from === 'imperial') {
    const ft = toNum(d.heightFt)
    const inch = toNum(d.heightIn)
    cm = ft == null && inch == null ? null : ftInToCm(ft ?? 0, inch ?? 0)
  } else {
    cm = toNum(d.heightCm)
  }

  const kg =
    from === 'imperial'
      ? (() => {
          const lb = toNum(d.weightLb)
          return lb == null ? null : lb / LB_PER_KG
        })()
      : toNum(d.weightKg)

  const next: Draft = {
    ...d,
    heightCm: '',
    heightFt: '',
    heightIn: '',
    weightKg: '',
    weightLb: '',
  }
  if (cm != null) {
    if (to === 'imperial') {
      const { ft, inch } = cmToFtIn(cm)
      next.heightFt = String(ft)
      next.heightIn = String(inch)
    } else {
      next.heightCm = String(round1(cm))
    }
  }
  if (kg != null) {
    if (to === 'imperial') next.weightLb = String(round1(kg * LB_PER_KG))
    else next.weightKg = String(round1(kg))
  }
  return next
}

// ── small field primitives ───────────────────────────────────────────────────
const inputCls =
  'h-11 w-full rounded-lg border border-divider px-3 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent'

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: ReactNode
  children: ReactNode
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-muted">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-faint">{hint}</span>}
    </label>
  )
}

function NumberField({
  label,
  value,
  onChange,
  suffix,
  hint,
  min,
  max,
  step,
  placeholder,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  suffix?: string
  hint?: ReactNode
  min?: number
  max?: number
  step?: number
  placeholder?: string
}) {
  return (
    <Field label={label} hint={hint}>
      <div className="relative">
        <input
          type="number"
          inputMode="decimal"
          value={value}
          min={min}
          max={max}
          step={step}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
          className={suffix ? `${inputCls} pr-12` : inputCls}
        />
        {suffix && (
          <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-xs text-faint">
            {suffix}
          </span>
        )}
      </div>
    </Field>
  )
}

function SectionCard({
  icon,
  title,
  description,
  children,
}: {
  icon: ReactNode
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <Card>
      <CardBody className="space-y-4">
        <div>
          <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
            {icon} {title}
          </h2>
          {description && <p className="mt-1 text-xs text-muted">{description}</p>}
        </div>
        {children}
      </CardBody>
    </Card>
  )
}

export function YouPage() {
  const queryClient = useQueryClient()
  const { system } = useUnits()
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['profile'],
    queryFn: api.profile,
  })

  const [draft, setDraft] = useState<Draft | null>(null)
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [errMsg, setErrMsg] = useState<string | null>(null)
  const prevSystem = useRef(system)

  // Full (re)seed only when the saved profile loads or changes (initial load / after save),
  // showing canonical values in the athlete's current units.
  useEffect(() => {
    if (!data) return
    setDraft(seed(data, system))
    prevSystem.current = system
    // Intentionally keyed on `data` only: a units toggle must not wipe in-progress edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data])

  // On a units toggle, convert only height/weight in place and keep every other edit.
  useEffect(() => {
    if (prevSystem.current === system) return
    const from = prevSystem.current
    prevSystem.current = system
    setDraft((d) => (d ? convertUnits(d, from, system) : d))
  }, [system])

  if (isLoading || !draft) return <LoadingState label="Loading your profile…" />
  if (isError) return <ErrorState message={(error as Error)?.message ?? 'Failed to load profile.'} />

  const set = (k: keyof Draft) => (v: string) => {
    setDraft((d) => (d ? { ...d, [k]: v } : d))
    if (status !== 'idle') setStatus('idle')
  }

  const save = async () => {
    if (!draft) return
    setStatus('saving')
    setErrMsg(null)
    try {
      const saved = await api.saveProfile(buildPayload(draft, system))
      queryClient.setQueryData(['profile'], saved)
      setStatus('saved')
    } catch (e) {
      setStatus('error')
      setErrMsg((e as Error).message)
    }
  }

  const age = toInt(draft.birthYear) ? new Date().getFullYear() - toInt(draft.birthYear)! : null
  const estMaxHr = age != null ? 220 - age : null

  return (
    <div className="flex flex-col gap-6">
      <h1 className="sr-only">You</h1>
      <SectionCard
        icon={<User className="h-5 w-5 text-accent" />}
        title="About you"
        description={`Physical measurements are shown in ${system} units — switch units in the sidebar.`}
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Name">
            <input
              type="text"
              value={draft.name}
              placeholder="Optional"
              onChange={(e) => set('name')(e.target.value)}
              className={inputCls}
            />
          </Field>
          <Field label="Sex">
            <select
              value={draft.sex}
              onChange={(e) => set('sex')(e.target.value)}
              className={inputCls}
            >
              <option value="">Prefer not to say</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other</option>
            </select>
          </Field>

          <NumberField
            label="Birth year"
            value={draft.birthYear}
            onChange={set('birthYear')}
            min={1900}
            max={new Date().getFullYear()}
            step={1}
            placeholder="e.g. 1990"
            hint={age != null ? `${age} years old` : undefined}
          />

          {system === 'imperial' ? (
            <Field label="Height">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <input
                    type="number"
                    inputMode="numeric"
                    value={draft.heightFt}
                    min={0}
                    max={8}
                    step={1}
                    placeholder="ft"
                    onChange={(e) => set('heightFt')(e.target.value)}
                    className={`${inputCls} pr-8`}
                  />
                  <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-xs text-faint">
                    ft
                  </span>
                </div>
                <div className="relative flex-1">
                  <input
                    type="number"
                    inputMode="numeric"
                    value={draft.heightIn}
                    min={0}
                    max={11}
                    step={1}
                    placeholder="in"
                    onChange={(e) => set('heightIn')(e.target.value)}
                    className={`${inputCls} pr-8`}
                  />
                  <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-xs text-faint">
                    in
                  </span>
                </div>
              </div>
            </Field>
          ) : (
            <NumberField
              label="Height"
              value={draft.heightCm}
              onChange={set('heightCm')}
              suffix="cm"
              min={1}
              max={300}
              step={0.5}
            />
          )}

          <NumberField
            label="Weight"
            value={system === 'imperial' ? draft.weightLb : draft.weightKg}
            onChange={system === 'imperial' ? set('weightLb') : set('weightKg')}
            suffix={system === 'imperial' ? 'lb' : 'kg'}
            min={1}
            step={0.1}
          />
        </div>
      </SectionCard>

      <SectionCard
        icon={<HeartPulse className="h-5 w-5 text-accent" />}
        title="Performance benchmarks"
        description="Used to compute heart-rate / power zones and gauge effort in each workout."
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <NumberField
            label="Resting HR"
            value={draft.restingHr}
            onChange={set('restingHr')}
            suffix="bpm"
            min={20}
            max={120}
            step={1}
          />
          <NumberField
            label="Max HR"
            value={draft.maxHr}
            onChange={set('maxHr')}
            suffix="bpm"
            min={100}
            max={250}
            step={1}
            hint={
              !draft.maxHr && estMaxHr
                ? `Leave blank to estimate ≈ ${estMaxHr} bpm (220 − age)`
                : undefined
            }
          />
          <NumberField
            label="Lactate threshold HR"
            value={draft.lthr}
            onChange={set('lthr')}
            suffix="bpm"
            min={100}
            max={230}
            step={1}
            hint="Threshold / anaerobic-threshold heart rate, if you know it."
          />
          <NumberField
            label="FTP"
            value={draft.ftp}
            onChange={set('ftp')}
            suffix="W"
            min={1}
            max={2000}
            step={1}
            hint="Functional threshold power (cycling)."
          />
          <NumberField
            label="VO₂max"
            value={draft.vo2max}
            onChange={set('vo2max')}
            suffix="ml/kg/min"
            min={10}
            max={100}
            step={0.1}
          />
        </div>
      </SectionCard>

      <SectionCard
        icon={<Target className="h-5 w-5 text-accent" />}
        title="Goals & notes"
        description="Anything the coach should keep in mind — target races, injuries, training focus."
      >
        <textarea
          value={draft.goals}
          onChange={(e) => set('goals')(e.target.value)}
          rows={4}
          placeholder="e.g. Training for a sub-3:30 marathon in the spring; recovering from a calf strain."
          className="w-full resize-y rounded-lg border border-divider p-3 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        />
      </SectionCard>

      <div className="sticky bottom-0 -mx-4 flex items-center gap-3 border-t border-divider bg-chrome px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-xl sm:border sm:px-5">
        <Button onClick={save} disabled={status === 'saving'}>
          {status === 'saving' ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          {status === 'saving' ? 'Saving…' : 'Save profile'}
        </Button>
        {status === 'saved' && (
          <span className="flex items-center gap-1.5 text-sm font-medium text-accent-strong">
            <Check className="h-4 w-4" /> Saved
          </span>
        )}
        {status === 'error' && (
          <span className="text-sm text-danger">{errMsg ?? 'Could not save.'}</span>
        )}
      </div>
    </div>
  )
}
