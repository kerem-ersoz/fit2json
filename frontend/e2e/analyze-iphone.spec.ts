import { expect, test, type Page } from '@playwright/test'

async function mockApi(page: Page) {
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    let json: unknown = {}

    if (path.endsWith('/config')) {
      json = {
        brand: { name: 'FitSift', tagline: 'Sift your workouts into insight' },
        backends: { copilot: false, default: 'ollama' },
        library_dir: '',
        memory_dir: '',
        chats_dir: '',
        base_path: '',
        workout_prompt_default: '',
      }
    } else if (path.endsWith('/activities')) {
      json = []
    } else if (path.endsWith('/chats')) {
      json = { chats: [] }
    } else if (path.endsWith('/models')) {
      json = {
        backend: 'ollama',
        models: ['auto'],
        efforts: [],
        allow_custom: false,
        reachable: true,
      }
    }

    await route.fulfill({ json })
  })
}

async function readViewportState(page: Page) {
  return page.evaluate(() => {
    const shell = document.querySelector<HTMLElement>('#root > div')
    const composer = document.querySelector<HTMLTextAreaElement>('textarea[aria-label="Message"]')
    const viewport = window.visualViewport
    if (!shell || !composer || !viewport) throw new Error('Analyze viewport elements are missing')

    const shellStyle = getComputedStyle(shell)
    return {
      bodyPosition: getComputedStyle(document.body).position,
      composerFontSize: getComputedStyle(composer).fontSize,
      documentOverflow: getComputedStyle(document.documentElement).overflow,
      documentScrollY: window.scrollY,
      pointerCoarse: window.matchMedia('(pointer: coarse)').matches,
      shellHeight: Number.parseFloat(shellStyle.height),
      shellTop: Number.parseFloat(shellStyle.top),
      viewportHeight: viewport.height,
      viewportOffsetTop: viewport.offsetTop,
      viewportScale: viewport.scale,
      viewportWidth: viewport.width,
    }
  })
}

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

test('keeps portrait composer focus at scale 1 without document movement', async ({ page }) => {
  await page.goto('/analyze')

  const composer = page.getByRole('textbox', { name: 'Message' })
  await expect(composer).toBeVisible()
  await composer.tap()
  await expect(composer).toBeFocused()
  await page.waitForTimeout(350)

  const state = await readViewportState(page)
  expect(state.viewportWidth).toBeLessThan(500)
  expect(state.pointerCoarse).toBe(true)
  expect(state.composerFontSize).toBe('16px')
  expect(state.viewportScale).toBeCloseTo(1, 5)
  expect(state.documentScrollY).toBe(0)
  expect(state.documentOverflow).toBe('hidden')
  expect(state.bodyPosition).toBe('fixed')
  expect(state.shellTop).toBeCloseTo(state.viewportOffsetTop, 1)
  expect(state.shellHeight).toBeCloseTo(state.viewportHeight, 1)
})

test('tracks the portrait keyboard visual viewport instead of panning the screen', async ({ page }) => {
  await page.addInitScript(() => {
    type Frame = { height?: number; offsetTop: number }

    const frame: Frame = { offsetTop: 0 }
    const viewport = new EventTarget()
    Object.defineProperties(viewport, {
      height: { get: () => frame.height ?? window.innerHeight },
      offsetTop: { get: () => frame.offsetTop },
      scale: { get: () => 1 },
      width: { get: () => window.innerWidth },
    })
    Object.defineProperty(window, 'visualViewport', {
      configurable: true,
      value: viewport,
    })
    Object.defineProperty(window, '__setEmulatedVisualViewport', {
      configurable: true,
      value: (next: Required<Frame>) => {
        frame.height = next.height
        frame.offsetTop = next.offsetTop
        viewport.dispatchEvent(new Event('resize'))
        viewport.dispatchEvent(new Event('scroll'))
      },
    })
  })

  await page.goto('/analyze')

  const composer = page.getByRole('textbox', { name: 'Message' })
  await expect(composer).toBeVisible()
  await composer.tap()

  const layoutHeight = await page.evaluate(() => window.innerHeight)
  const visibleHeight = 430
  const viewportOffsetTop = layoutHeight - visibleHeight

  await page.evaluate(
    ({ height, offsetTop }) => {
      ;(
        window as typeof window & {
          __setEmulatedVisualViewport: (frame: { height: number; offsetTop: number }) => void
        }
      ).__setEmulatedVisualViewport({ height, offsetTop })
    },
    { height: visibleHeight, offsetTop: viewportOffsetTop },
  )

  await expect
    .poll(async () => {
      const state = await readViewportState(page)
      return {
        documentScrollY: state.documentScrollY,
        shellHeight: Math.round(state.shellHeight),
        shellTop: Math.round(state.shellTop),
      }
    })
    .toEqual({
      documentScrollY: 0,
      shellHeight: visibleHeight,
      shellTop: viewportOffsetTop,
    })

  await page.evaluate(
    ({ height }) => {
      ;(
        window as typeof window & {
          __setEmulatedVisualViewport: (frame: { height: number; offsetTop: number }) => void
        }
      ).__setEmulatedVisualViewport({ height, offsetTop: 0 })
    },
    { height: layoutHeight },
  )

  await expect
    .poll(async () => {
      const state = await readViewportState(page)
      return {
        documentScrollY: state.documentScrollY,
        shellHeight: Math.round(state.shellHeight),
        shellTop: Math.round(state.shellTop),
      }
    })
    .toEqual({
      documentScrollY: 0,
      shellHeight: layoutHeight,
      shellTop: 0,
    })
})
