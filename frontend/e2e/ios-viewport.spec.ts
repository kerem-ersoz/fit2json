import { expect, test, type Locator, type Page } from '@playwright/test'

interface VisualViewportFrame {
  height: number
  offsetTop: number
}

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
    } else if (path.includes('/models')) {
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

async function emulateVisualViewport(page: Page) {
  await page.addInitScript(() => {
    type MutableFrame = { height?: number; offsetTop: number }

    const frame: MutableFrame = { offsetTop: 0 }
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
      value: (next: VisualViewportFrame) => {
        frame.height = next.height
        frame.offsetTop = next.offsetTop
        viewport.dispatchEvent(new Event('resize'))
        viewport.dispatchEvent(new Event('scroll'))
      },
    })
  })
}

async function setVisualViewport(page: Page, frame: VisualViewportFrame) {
  await page.evaluate((next) => {
    ;(
      window as typeof window & {
        __setEmulatedVisualViewport: (value: VisualViewportFrame) => void
      }
    ).__setEmulatedVisualViewport(next)
  }, frame)
}

async function keyboardFrame(page: Page): Promise<VisualViewportFrame> {
  const layoutHeight = await page.evaluate(() => window.innerHeight)
  const height = Math.min(430, layoutHeight - 160)
  return { height, offsetTop: layoutHeight - height }
}

async function expectVisualViewportFrame(locator: Locator, frame: VisualViewportFrame) {
  await expect
    .poll(() =>
      locator.evaluate((element) => {
        const style = getComputedStyle(element)
        return {
          height: Math.round(Number.parseFloat(style.height)),
          top: Math.round(Number.parseFloat(style.top)),
        }
      }),
    )
    .toEqual({
      height: frame.height,
      top: frame.offsetTop,
    })
}

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

test('publishes standalone Home Screen app metadata', async ({ page }) => {
  await page.goto('/')

  const metadata = await page.evaluate(async () => {
    const manifestLink = document.querySelector<HTMLLinkElement>('link[rel="manifest"]')
    const manifest = manifestLink
      ? await fetch(manifestLink.href).then((response) => response.json())
      : null
    return {
      appleCapable: document.querySelector<HTMLMetaElement>(
        'meta[name="apple-mobile-web-app-capable"]',
      )?.content,
      manifest,
      mobileCapable: document.querySelector<HTMLMetaElement>(
        'meta[name="mobile-web-app-capable"]',
      )?.content,
    }
  })

  expect(metadata.appleCapable).toBe('yes')
  expect(metadata.mobileCapable).toBe('yes')
  expect(metadata.manifest).toMatchObject({
    display: 'standalone',
    id: './',
    scope: './',
    start_url: './',
  })
})

test('restores touch surfaces after browser chrome changes between tabs', async ({ page }) => {
  await emulateVisualViewport(page)
  await page.goto('/analyze')

  const layoutHeight = await page.evaluate(() => window.innerHeight)
  const chromeFrame = {
    height: layoutHeight - 112,
    offsetTop: 56,
  }

  await page.getByRole('link', { name: 'Add' }).tap()
  await setVisualViewport(page, chromeFrame)
  await page.getByRole('link', { name: 'Analyze' }).tap()

  const shell = page.locator('#root > div')
  await expectVisualViewportFrame(shell, chromeFrame)

  const tabBar = page.locator('nav:visible').last()
  const tabBarBounds = await tabBar.boundingBox()
  expect(tabBarBounds).not.toBeNull()
  expect(tabBarBounds!.y).toBeGreaterThanOrEqual(chromeFrame.offsetTop)
  expect(tabBarBounds!.y + tabBarBounds!.height).toBeLessThanOrEqual(
    chromeFrame.offsetTop + chromeFrame.height,
  )

  await page.getByRole('link', { name: 'You' }).tap()
  await expect(page).toHaveURL(/\/you$/)
})

test('keeps Analyze interactive through iOS keyboard viewport changes', async ({ page }) => {
  await emulateVisualViewport(page)
  await page.goto('/analyze')

  const shell = page.locator('#root > div')
  const composer = page.getByRole('textbox', { name: 'Message' })
  await expect(composer).toBeVisible()
  await composer.tap()

  const keyboard = await keyboardFrame(page)
  await setVisualViewport(page, keyboard)
  await expectVisualViewportFrame(shell, keyboard)

  const layoutHeight = await page.evaluate(() => window.innerHeight)
  await setVisualViewport(page, { height: layoutHeight, offsetTop: 0 })
  await expectVisualViewportFrame(shell, { height: layoutHeight, offsetTop: 0 })

  await page.getByRole('button', { name: 'Add workout context' }).tap()
  const contextDialog = page.getByRole('dialog', { name: 'Workout context' })
  await expect(contextDialog).toBeVisible()

  await setVisualViewport(page, keyboard)
  await expectVisualViewportFrame(contextDialog.locator('..'), keyboard)
  await page.getByRole('button', { name: 'Close' }).tap()
  await expect(contextDialog).toBeHidden()

  await setVisualViewport(page, { height: layoutHeight, offsetTop: 0 })
  await page.getByRole('link', { name: 'Add' }).tap()
  await expect(page).toHaveURL(/\/ingest$/)
})

test('keeps the chat drawer interactive through iOS keyboard viewport changes', async ({ page }) => {
  await emulateVisualViewport(page)
  await page.goto('/')

  await page.getByRole('button', { name: 'Chat' }).tap()
  const drawer = page.getByRole('dialog', { name: 'Chat' })
  await expect(drawer).toBeVisible()

  const keyboard = await keyboardFrame(page)
  await setVisualViewport(page, keyboard)
  await expectVisualViewportFrame(drawer, keyboard)

  await page.getByRole('button', { name: 'Close chat' }).tap()
  await expect(drawer).toBeHidden()

  const layoutHeight = await page.evaluate(() => window.innerHeight)
  await setVisualViewport(page, { height: layoutHeight, offsetTop: 0 })
  await page.getByRole('link', { name: 'Analyze' }).tap()
  await expect(page).toHaveURL(/\/analyze$/)
})

test('keeps touch form controls above the iOS focus-zoom threshold', async ({ page }) => {
  await page.setViewportSize({ width: 852, height: 393 })
  await page.goto('/analyze')

  const controls = page.locator('input, textarea, select')
  await expect(controls.first()).toBeVisible()
  const fontSizes = await controls.evaluateAll((elements) =>
    elements.map((element) => Number.parseFloat(getComputedStyle(element).fontSize)),
  )

  expect(fontSizes.length).toBeGreaterThan(0)
  expect(fontSizes.every((size) => size >= 16)).toBe(true)
})

test('reconnects to a background analysis without starting it twice', async ({ page }) => {
  let runId = ''
  let startCalls = 0
  let eventConnections = 0

  await page.route('**/api/analysis-runs', async (route) => {
    const body = route.request().postDataJSON() as {
      run_id: string
      chat: { messages: { role: string; content: string }[] }
    }
    startCalls += 1
    runId = body.run_id
    expect(body.chat.messages).toHaveLength(1)
    await route.fulfill({
      json: {
        id: runId,
        status: 'running',
        error: null,
        last_event_id: 0,
        created_at: new Date().toISOString(),
        finished_at: null,
      },
    })
  })
  await page.route('**/api/analysis-runs/*/events?*', async (route) => {
    eventConnections += 1
    const url = new URL(route.request().url())
    expect(url.pathname).toContain(runId)
    if (eventConnections === 1) {
      expect(url.searchParams.get('after')).toBe('0')
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body:
          'id: 1\nevent: start\ndata: {"backend":"ollama"}\n\n' +
          'id: 2\nevent: delta\ndata: {"text":"Part one "}\n\n',
      })
      return
    }
    expect(url.searchParams.get('after')).toBe('2')
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body:
        'id: 3\nevent: delta\ndata: {"text":"part two."}\n\n' +
        'id: 4\nevent: done\ndata: {"chars":18,"saved":null,"backend":"ollama"}\n\n',
    })
  })

  await page.goto('/analyze')
  await page.getByRole('textbox', { name: 'Message' }).fill('Review my latest run')
  await page.getByRole('button', { name: 'Send' }).click()

  await expect(page.getByText('Part one part two.')).toBeVisible()
  expect(startCalls).toBe(1)
  expect(eventConnections).toBe(2)
  await expect(page.getByText('Running in the background…')).toBeHidden()
  await expect(page.getByRole('button', { name: 'Send' })).toBeVisible()
})
