import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertCircle, Check, Copy, Download, Layers, Loader2, RefreshCw, Square } from 'lucide-react'
import {
  infographicViewUrl,
  memoryInfographicRawUrl,
  memoryInfographicStatus,
  memoryInfographicViewUrl,
  streamInfographic,
  streamMemoryInfographic,
} from '../../lib/api'
import { Button } from '../../components/ui/Button'

/**
 * A visual rendering of an analysis, shown inside a sandboxed iframe. Two sources:
 *  - `ephemeral`: generated from raw analysis text (chat), served from a short-lived URL.
 *  - `entry`: a saved analysis, whose infographic is cached server-side by `entry_id`, so
 *    it loads instantly on return and is only (re)generated on request.
 *
 * The HTML is LLM-authored, so it's only ever loaded (by real URL — some webviews block
 * `srcdoc`/`blob:`) into `sandbox="allow-scripts"` (opaque origin, isolated from the app)
 * and served under a strict CSP. Height comes from the backend's nonced reporter via a
 * postMessage we accept only from this iframe's own window.
 */
export type InfographicSource =
  | { kind: 'ephemeral'; analysis: string; backend?: string; model?: string; reasoningEffort?: string }
  | { kind: 'entry'; entryId: string }

type Phase = 'checking' | 'empty' | 'loading' | 'ready' | 'error'

function extractHtml(raw: string): string {
  let s = raw.trim()
  const fenced = s.match(/^```[a-zA-Z]*\s*\n([\s\S]*?)\n?```$/)
  if (fenced) s = fenced[1].trim()
  const lower = s.toLowerCase()
  const docIdx = lower.indexOf('<!doctype')
  const htmlIdx = lower.indexOf('<html')
  const start = docIdx !== -1 ? docIdx : htmlIdx
  if (start > 0) s = s.slice(start)
  return s.trim()
}

export function InfographicView({ source }: { source: InfographicSource }) {
  const sourceKey =
    source.kind === 'entry'
      ? `entry:${source.entryId}`
      : `eph:${source.analysis}:${source.backend}:${source.model}:${source.reasoningEffort}`

  const [phase, setPhase] = useState<Phase>(source.kind === 'entry' ? 'checking' : 'empty')
  const [viewUrl, setViewUrl] = useState('')
  const [bytes, setBytes] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [iframeHeight, setIframeHeight] = useState(420)

  const abortRef = useRef<AbortController | null>(null)
  const htmlRef = useRef('') // cleaned HTML for copy/download (when generated this session)
  const iframeRef = useRef<HTMLIFrameElement>(null)

  // Entry sources: check for a cached infographic once, up front.
  useEffect(() => {
    htmlRef.current = ''
    setBytes(0)
    setError(null)
    setViewUrl('')
    setIframeHeight(420)
    if (source.kind !== 'entry') {
      setPhase('empty')
      return
    }
    const entryId = source.entryId
    let cancelled = false
    setPhase('checking')
    memoryInfographicStatus(entryId)
      .then((s) => {
        if (cancelled) return
        if (s.exists) {
          setViewUrl(`${memoryInfographicViewUrl(entryId)}?t=${encodeURIComponent(s.generated_at ?? '')}`)
          setPhase('ready')
        } else {
          setPhase('empty')
        }
      })
      .catch(() => !cancelled && setPhase('empty'))
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceKey])

  useEffect(() => () => abortRef.current?.abort(), [])

  // Size the iframe from height messages posted by the backend's reporter (this frame only).
  useEffect(() => {
    const onMsg = (e: MessageEvent) => {
      if (!iframeRef.current || e.source !== iframeRef.current.contentWindow) return
      const h = e.data && typeof e.data === 'object' ? (e.data as Record<string, unknown>).__fitsift_ig_height : undefined
      if (typeof h === 'number' && h > 0) setIframeHeight(Math.min(Math.max(h, 240), 20000))
    }
    window.addEventListener('message', onMsg)
    return () => window.removeEventListener('message', onMsg)
  }, [])

  const generate = useCallback(() => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setPhase('loading')
    setBytes(0)
    setError(null)
    setIframeHeight(420)
    let acc = ''
    const onDelta = (t: string) => {
      acc += t
      setBytes(acc.length)
    }
    const onError = (msg: string) => {
      if (controller.signal.aborted) return
      setError(msg)
      setPhase('error')
    }

    if (source.kind === 'entry') {
      const entryId = source.entryId
      void streamMemoryInfographic(
        entryId,
        {},
        {
          onDelta,
          onDone: () => {
            htmlRef.current = extractHtml(acc)
            setViewUrl(`${memoryInfographicViewUrl(entryId)}?t=${Date.now()}`)
            setPhase('ready')
          },
          onError,
        },
        controller.signal,
      )
    } else {
      void streamInfographic(
        {
          analysis: source.analysis,
          backend: source.backend,
          model: source.model,
          reasoning_effort: source.reasoningEffort,
        },
        {
          onDelta,
          onDone: (info) => {
            const cleaned = extractHtml(acc)
            if (!cleaned || !info.id) {
              setError('The model returned no HTML. Try again.')
              setPhase('error')
              return
            }
            htmlRef.current = cleaned
            setViewUrl(infographicViewUrl(info.id))
            setPhase('ready')
          },
          onError,
        },
        controller.signal,
      )
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceKey])

  const stop = () => abortRef.current?.abort()

  const ensureHtml = useCallback(async (): Promise<string> => {
    if (htmlRef.current) return htmlRef.current
    if (source.kind === 'entry') {
      try {
        const res = await fetch(memoryInfographicRawUrl(source.entryId))
        if (res.ok) htmlRef.current = await res.text()
      } catch {
        /* fall through */
      }
    }
    return htmlRef.current
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceKey])

  const copy = async () => {
    const html = await ensureHtml()
    if (!html) return
    try {
      await navigator.clipboard?.writeText(html)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard unavailable */
    }
  }

  const download = async () => {
    const html = await ensureHtml()
    if (!html) return
    const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'fitsift-infographic.html'
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 2000)
  }

  if (phase === 'checking') {
    return (
      <div className="flex min-h-[8rem] items-center justify-center text-sm text-slate-400">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Checking…
      </div>
    )
  }

  if (phase === 'empty') {
    return (
      <div className="flex min-h-[14rem] flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-slate-200 bg-white/60 p-6 text-center">
        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
          <Layers className="h-5 w-5" />
        </span>
        <div>
          <p className="text-sm font-medium text-slate-700">See this analysis as an infographic</p>
          <p className="mt-0.5 text-xs text-slate-400">A visual summary you can scan. Uses the model — takes a moment.</p>
        </div>
        <Button onClick={generate} className="min-h-0 py-2">
          <Layers className="h-4 w-4" /> Generate
        </Button>
      </div>
    )
  }

  if (phase === 'loading') {
    return (
      <div className="flex min-h-[14rem] flex-col items-center justify-center gap-3 text-center">
        <Loader2 className="h-6 w-6 animate-spin text-brand-600" />
        <p className="text-sm font-medium text-slate-700">Designing your infographic…</p>
        <p className="text-xs text-slate-400">
          Turning the analysis into visuals{bytes > 0 ? ` · ${(bytes / 1024).toFixed(1)} KB so far` : ''}
        </p>
        <button
          type="button"
          onClick={stop}
          className="mt-1 inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
        >
          <Square className="h-3.5 w-3.5" /> Stop
        </button>
      </div>
    )
  }

  if (phase === 'error') {
    return (
      <div className="flex min-h-[14rem] flex-col items-center justify-center gap-3 text-center">
        <AlertCircle className="h-6 w-6 text-red-500" />
        <p className="text-sm font-medium text-slate-700">Couldn’t build the infographic</p>
        {error && <p className="max-w-sm text-xs text-slate-500">{error}</p>}
        <Button variant="secondary" onClick={generate} className="min-h-0 py-2">
          <RefreshCw className="h-4 w-4" /> Try again
        </Button>
      </div>
    )
  }

  return (
    <div>
      <iframe
        ref={iframeRef}
        title="Workout infographic"
        sandbox="allow-scripts"
        src={viewUrl}
        className="w-full rounded-xl border border-slate-200 bg-white"
        style={{ height: iframeHeight }}
      />
      <div className="mt-2 flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={generate}
          className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Regenerate
        </button>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={copy}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-brand-600" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? 'Copied' : 'Copy HTML'}
          </button>
          <button
            type="button"
            onClick={download}
            className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-2 text-xs font-medium text-white hover:bg-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
          >
            <Download className="h-3.5 w-3.5" /> Download
          </button>
        </div>
      </div>
    </div>
  )
}
