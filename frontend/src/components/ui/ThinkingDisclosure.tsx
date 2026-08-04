import { ChevronRight, Loader2 } from 'lucide-react'

function sentenceSummary(summary: string, thinking: string): string {
  const source = (summary || thinking)
    .replace(/^[\s#>*_`-]+/, '')
    .replace(/\s+/g, ' ')
    .trim()
  if (!source) return 'Model thinking'

  const sentence = source.match(/^.*?[.!?](?=\s|$)/)?.[0] ?? source
  return sentence.length > 160 ? `${sentence.slice(0, 157).trimEnd()}…` : sentence
}

export function ThinkingDisclosure({
  summary = '',
  thinking = '',
  running = false,
  className = '',
}: {
  summary?: string | null
  thinking?: string | null
  running?: boolean
  className?: string
}) {
  const detail = thinking?.trim() ?? ''
  const label = sentenceSummary(summary?.trim() ?? '', detail)

  if (!detail) {
    if (!running) return null
    return (
      <p
        role="status"
        className={`flex min-h-11 items-center gap-2 text-sm text-copy ${className}`}
      >
        <Loader2 className="h-4 w-4 shrink-0 animate-spin text-faint" />
        <span>{summary?.trim() || 'Thinking…'}</span>
      </p>
    )
  }

  return (
    <details className={`group rounded-lg border border-divider bg-surface-muted ${className}`}>
      <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 rounded-lg px-3 py-2 text-sm text-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 [&::-webkit-details-marker]:hidden">
        {running ? (
          <Loader2 className="h-4 w-4 shrink-0 animate-spin text-faint" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-faint group-open:rotate-90" />
        )}
        <span aria-live="polite" className="min-w-0 flex-1">
          {label}
        </span>
        <span className="shrink-0 text-xs text-muted">
          <span className="group-open:hidden">Show thinking</span>
          <span className="hidden group-open:inline">Hide thinking</span>
        </span>
      </summary>
      <div className="border-t border-divider px-3 py-3">
        <p className="whitespace-pre-wrap text-sm leading-6 text-strong">{detail}</p>
      </div>
    </details>
  )
}
