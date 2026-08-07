import { Component, type ErrorInfo, type ReactNode } from 'react'
import { RotateCcw } from 'lucide-react'

interface Props {
  children: ReactNode
  /** When this value changes, the boundary clears a caught error and retries. */
  resetKey?: unknown
  /** Compact variant for smaller surfaces (e.g. the chat pane). */
  compact?: boolean
  label?: string
}

interface State {
  error: Error | null
}

/**
 * Contains render-time crashes so one broken surface can't white-screen the whole app.
 * Recovers automatically when `resetKey` changes (e.g. on route navigation) and shows the
 * underlying error so it can be reported.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surface it for diagnosis (visible in the browser console).
    console.error('UI crash caught by ErrorBoundary:', error, info.componentStack)
  }

  componentDidUpdate(prev: Props) {
    if (this.state.error && prev.resetKey !== this.props.resetKey) {
      this.setState({ error: null })
    }
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div
        role="alert"
        className={`flex flex-col items-center justify-center gap-3 text-center ${
          this.props.compact ? 'h-full p-6' : 'min-h-[50vh] p-8'
        }`}
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-danger-tint text-danger">
          <RotateCcw className="h-6 w-6" />
        </div>
        <div>
          <p className="text-sm font-semibold text-ink">
            {this.props.label ?? 'Something went wrong'}
          </p>
          <p className="mx-auto mt-1 max-w-sm text-sm text-muted">
            This view hit an unexpected error. You can retry or reload the app.
          </p>
        </div>
        <p className="max-w-md break-words rounded-lg border border-danger-divider bg-danger-tint px-3 py-2 font-mono text-xs text-danger-strong">
          {error.message || String(error)}
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            className="inline-flex min-h-[36px] items-center gap-1.5 rounded-lg border border-divider bg-surface px-3 text-sm font-medium text-strong hover:bg-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            Try again
          </button>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="inline-flex min-h-[36px] items-center gap-1.5 rounded-lg bg-action px-3 text-sm font-medium text-on-action hover:bg-action-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            Reload
          </button>
        </div>
      </div>
    )
  }
}
