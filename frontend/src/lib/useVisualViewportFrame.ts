import { useEffect, type RefObject } from 'react'

const MIN_USABLE_HEIGHT = 100

/**
 * Keep a fixed interactive surface inside the viewport iOS actually displays.
 * The layout viewport does not resize when Safari opens the keyboard.
 */
export function useVisualViewportFrame<T extends HTMLElement>(
  frameRef: RefObject<T>,
  enabled = true,
) {
  useEffect(() => {
    const frame = frameRef.current
    const viewport = window.visualViewport
    if (!enabled || !frame || !viewport || !window.matchMedia('(pointer: coarse)').matches) {
      return
    }

    const previousTop = frame.style.top
    const previousHeight = frame.style.height
    let animationFrame: number | null = null

    const sync = () => {
      if (animationFrame !== null) return
      animationFrame = window.requestAnimationFrame(() => {
        animationFrame = null
        if (
          !Number.isFinite(viewport.offsetTop) ||
          !Number.isFinite(viewport.height) ||
          viewport.height < MIN_USABLE_HEIGHT
        ) {
          return
        }
        frame.style.top = `${viewport.offsetTop}px`
        frame.style.height = `${viewport.height}px`
      })
    }

    sync()
    viewport.addEventListener('resize', sync)
    viewport.addEventListener('scroll', sync)

    return () => {
      if (animationFrame !== null) window.cancelAnimationFrame(animationFrame)
      viewport.removeEventListener('resize', sync)
      viewport.removeEventListener('scroll', sync)
      frame.style.top = previousTop
      frame.style.height = previousHeight
    }
  }, [enabled, frameRef])
}
