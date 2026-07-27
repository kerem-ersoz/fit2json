import { History } from 'lucide-react'
import { EmptyState } from '../components/ui/Feedback'

export function MemoryPage() {
  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold tracking-tight">Memory</h1>
      <EmptyState
        icon={<History className="h-8 w-8 text-slate-300" />}
        title="Training memory is coming in Phase 3"
        hint="Browse every past analysis, filtered by sport and date, so you can revisit how your training has trended over time."
      />
    </div>
  )
}
