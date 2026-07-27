import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { Bike, CloudDownload, FileUp, Loader2, UploadCloud } from 'lucide-react'
import { api, type FetchResult, type IngestResult } from '../lib/api'
import { Button } from '../components/ui/Button'
import { Card, CardBody } from '../components/ui/Card'

function AddedSummary({ added, skipped }: { added: { id: string }[]; skipped: number }) {
  if (added.length === 0 && skipped === 0) return null
  return (
    <div className="rounded-lg border border-brand-200 bg-brand-50 p-3 text-sm text-brand-800">
      {added.length > 0 ? (
        <>
          Added <strong>{added.length}</strong> workout{added.length === 1 ? '' : 's'}.{' '}
          <Link to="/" className="font-medium underline">
            View in Library
          </Link>
        </>
      ) : (
        'No new workouts.'
      )}
      {skipped > 0 && <span className="text-brand-600"> · {skipped} already in library</span>}
    </div>
  )
}

function UploadCard() {
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<IngestResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const upload = async (files: FileList | File[]) => {
    const list = Array.from(files).filter((f) => f.name.toLowerCase().endsWith('.fit'))
    if (list.length === 0) {
      setError('Please choose .fit files.')
      return
    }
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.uploadFit(list)
      setResult(res)
      if (res.added.length > 0) {
        queryClient.invalidateQueries({ queryKey: ['activities'] })
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardBody className="space-y-3">
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
          <FileUp className="h-5 w-5 text-brand-600" /> Upload .fit files
        </h2>
        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            if (e.dataTransfer.files?.length) upload(e.dataTransfer.files)
          }}
          className={[
            'flex min-h-[132px] cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-6 text-center transition-colors',
            dragging ? 'border-brand-500 bg-brand-50' : 'border-slate-300 hover:border-brand-400',
          ].join(' ')}
        >
          <UploadCloud className="h-8 w-8 text-slate-400" />
          <div className="text-sm font-medium text-slate-700">
            Tap to choose, or drag &amp; drop
          </div>
          <div className="text-xs text-slate-400">.fit files from Garmin, Wahoo, etc.</div>
          <input
            ref={inputRef}
            type="file"
            accept=".fit"
            multiple
            className="hidden"
            onChange={(e) => e.target.files && upload(e.target.files)}
          />
        </div>

        {busy && (
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" /> Converting…
          </div>
        )}
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}
        {result && <AddedSummary added={result.added} skipped={result.skipped} />}
        {result && result.errors.length > 0 && (
          <ul className="space-y-1 text-xs text-amber-700">
            {result.errors.map((e) => (
              <li key={e.file}>
                {e.file}: {e.error}
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  )
}

function FetchCard({
  platform,
  title,
  hint,
  icon,
}: {
  platform: 'garmin' | 'strava'
  title: string
  hint: string
  icon: React.ReactNode
}) {
  const queryClient = useQueryClient()
  const [days, setDays] = useState(30)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<FetchResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const run = async () => {
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.fetchFrom(platform, days)
      setResult(res)
      if (res.added.length > 0) queryClient.invalidateQueries({ queryKey: ['activities'] })
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardBody className="space-y-3">
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
          {icon} {title}
        </h2>
        <p className="text-xs text-slate-500">{hint}</p>
        <div className="flex items-end gap-3">
          <label className="text-sm">
            <span className="mb-1 block text-xs text-slate-500">Days back</span>
            <input
              type="number"
              min={1}
              max={365}
              value={days}
              onChange={(e) => setDays(Math.max(1, Number(e.target.value) || 1))}
              className="h-11 w-24 rounded-lg border border-slate-200 px-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </label>
          <Button onClick={run} disabled={busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <CloudDownload className="h-4 w-4" />}
            {busy ? 'Fetching…' : 'Fetch'}
          </Button>
        </div>
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}
        {result && <AddedSummary added={result.added} skipped={result.skipped} />}
      </CardBody>
    </Card>
  )
}

export function IngestPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Add workouts</h1>
        <p className="text-sm text-slate-500">
          Upload .fit files, or pull recent activities from Garmin Connect or Strava.
        </p>
      </div>

      <UploadCard />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FetchCard
          platform="garmin"
          title="Garmin Connect"
          hint="Uses your cached Garmin session or GARMIN_EMAIL / GARMIN_PASSWORD. MFA logins must be seeded first."
          icon={<CloudDownload className="h-5 w-5 text-brand-600" />}
        />
        <FetchCard
          platform="strava"
          title="Strava"
          hint="Uses your STRAVA_CLIENT_ID / SECRET / REFRESH_TOKEN. Lower fidelity than .fit — bulk-export + upload for full detail."
          icon={<Bike className="h-5 w-5 text-brand-600" />}
        />
      </div>
    </div>
  )
}
