import { Upload } from 'lucide-react'
import { EmptyState } from '../components/ui/Feedback'

export function IngestPage() {
  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold tracking-tight">Add workouts</h1>
      <EmptyState
        icon={<Upload className="h-8 w-8 text-slate-300" />}
        title="Ingest is coming in Phase 2"
        hint="Drag-and-drop .fit files to convert them, or pull recent activities straight from Garmin Connect or Strava."
      />
    </div>
  )
}
