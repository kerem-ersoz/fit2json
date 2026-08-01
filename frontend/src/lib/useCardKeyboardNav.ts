import { useEffect, type RefObject } from 'react'

/**
 * Power-user keyboard nav shared by the workout lists: "/" focuses the search input,
 * and j/k or ArrowDown/ArrowUp roves focus across elements marked [data-activity-card]
 * inside `listRef`. Native focus drives the visible focus ring and Enter-to-open.
 */
export function useCardKeyboardNav(
  listRef: RefObject<HTMLElement>,
  searchRef: RefObject<HTMLInputElement>,
  enabled = true,
) {
  useEffect(() => {
    if (!enabled) return

    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      const typing =
        !!target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable)

      if (e.key === '/' && !typing) {
        e.preventDefault()
        searchRef.current?.focus()
        return
      }
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return

      const forward = e.key === 'j' || e.key === 'ArrowDown'
      const backward = e.key === 'k' || e.key === 'ArrowUp'
      if (!forward && !backward) return

      const cards = Array.from(listRef.current?.querySelectorAll<HTMLElement>('[data-activity-card]') ?? [])
      if (cards.length === 0) return
      e.preventDefault()
      const idx = cards.indexOf(document.activeElement as HTMLElement)
      const nextIdx = idx === -1 ? 0 : Math.min(cards.length - 1, Math.max(0, idx + (forward ? 1 : -1)))
      cards[nextIdx]?.focus()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [enabled, listRef, searchRef])
}
