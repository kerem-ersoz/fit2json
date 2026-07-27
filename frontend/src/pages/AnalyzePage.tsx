import { Brain } from 'lucide-react'
import { EmptyState } from '../components/ui/Feedback'

export function AnalyzePage() {
  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold tracking-tight">Analyze</h1>
      <EmptyState
        icon={<Brain className="h-8 w-8 text-slate-300" />}
        title="Analysis is coming in Phase 3"
        hint="Pick a workout, write a prompt, and stream a coaching analysis from Copilot or a local model — with your training memory recalled for context."
      />
    </div>
  )
}
