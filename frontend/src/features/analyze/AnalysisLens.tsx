import { useState, type ReactNode } from 'react'
import { FileText, Layers } from 'lucide-react'
import { Sheet } from '../../components/ui/Sheet'
import { InfographicView, type InfographicSource } from './InfographicView'

/**
 * Presents an analysis as two peer lenses — the written **Text** and a visual
 * **Infographic** — with a consistent affordance across the app.
 *
 * `surface="inline"` (wide surfaces: activity detail, Memory) swaps the two views in
 * place via a segmented control. `surface="sheet"` (the narrow chat rail) keeps the text
 * visible and opens the infographic in a slide-over, since it needs more width than the
 * rail offers. Same label + icon vocabulary either way.
 */
export function AnalysisLens({
  text,
  source,
  surface,
}: {
  text: ReactNode
  source: InfographicSource
  surface: 'inline' | 'sheet'
}) {
  if (surface === 'sheet') return <SheetLens text={text} source={source} />
  return <InlineLens text={text} source={source} />
}

function InlineLens({ text, source }: { text: ReactNode; source: InfographicSource }) {
  const [view, setView] = useState<'text' | 'visual'>('text')
  return (
    <div>
      <div className="mb-3">
        <Segmented value={view} onChange={setView} />
      </div>
      {view === 'text' ? text : <InfographicView source={source} />}
    </div>
  )
}

function SheetLens({ text, source }: { text: ReactNode; source: InfographicSource }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      {text}
      <div className="mt-2">
        <button
          type="button"
          onClick={() => setOpen(true)}
          title="See this analysis as a visual infographic"
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
        >
          <Layers className="h-3.5 w-3.5 text-brand-600" /> Visual
        </button>
      </div>
      {open && (
        <Sheet
          title="Infographic"
          subtitle="A visual take on your analysis"
          icon={
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
              <Layers className="h-4 w-4" />
            </span>
          }
          onClose={() => setOpen(false)}
        >
          <InfographicView source={source} />
        </Sheet>
      )}
    </>
  )
}

function Segmented({
  value,
  onChange,
}: {
  value: 'text' | 'visual'
  onChange: (v: 'text' | 'visual') => void
}) {
  const seg = (active: boolean) =>
    `inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
      active ? 'bg-white text-slate-900' : 'text-slate-500 hover:text-slate-700'
    }`
  return (
    <div
      role="tablist"
      aria-label="Analysis view"
      className="inline-flex items-center gap-0.5 rounded-lg border border-slate-200 bg-slate-50 p-0.5"
    >
      <button type="button" role="tab" aria-selected={value === 'text'} onClick={() => onChange('text')} className={seg(value === 'text')}>
        <FileText className="h-3.5 w-3.5" /> Text
      </button>
      <button type="button" role="tab" aria-selected={value === 'visual'} onClick={() => onChange('visual')} className={seg(value === 'visual')}>
        <Layers className={`h-3.5 w-3.5 ${value === 'visual' ? 'text-brand-600' : ''}`} /> Visual
      </button>
    </div>
  )
}
