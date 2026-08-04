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

test('expands model thinking from its one-sentence summary', async ({ page }) => {
  const summary = 'Reviewing pace and heart-rate evidence'
  const reasoning =
    'The opening pace was controlled while heart rate rose gradually. The finish stayed aerobic.'
  const frames = [
    `event: start\ndata: ${JSON.stringify({ backend: 'copilot' })}\n\n`,
    `event: thinking\ndata: ${JSON.stringify({ summary, text: reasoning })}\n\n`,
    `event: delta\ndata: ${JSON.stringify({ text: 'A controlled aerobic session.' })}\n\n`,
    `event: replace\ndata: ${JSON.stringify({ text: 'A controlled aerobic session.' })}\n\n`,
    `event: done\ndata: ${JSON.stringify({ chars: 29, saved: null, backend: 'copilot' })}\n\n`,
  ]
  await page.route('**/api/analyze', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: frames.join(''),
    }),
  )
  await page.goto('/analyze')

  const savedChat = page.waitForRequest(
    (request) => {
      if (request.method() !== 'PUT' || !new URL(request.url()).pathname.includes('/api/chats/')) {
        return false
      }
      const body = request.postDataJSON() as {
        messages?: { thinking_summary?: string }[]
      }
      return body.messages?.[1]?.thinking_summary === summary
    },
  )
  await page.getByRole('textbox', { name: 'Message' }).fill('How did this session go?')
  await page.getByRole('button', { name: 'Send' }).tap()

  const disclosure = page.locator('details').filter({ hasText: summary })
  const detail = page.getByText(reasoning)
  await expect(disclosure).toBeVisible()
  expect(await disclosure.evaluate((element) => (element as HTMLDetailsElement).open)).toBe(false)
  await expect(detail).toBeHidden()

  const trigger = disclosure.locator('summary')
  expect(await trigger.evaluate((element) => element.getBoundingClientRect().height)).toBeGreaterThanOrEqual(44)
  await trigger.tap()

  await expect(detail).toBeVisible()
  expect(await disclosure.evaluate((element) => (element as HTMLDetailsElement).open)).toBe(true)
  await expect(page.getByText('A controlled aerobic session.')).toBeVisible()

  const savedBody = (await savedChat).postDataJSON()
  expect(savedBody.messages[1].thinking_summary).toBe(summary)
  expect(savedBody.messages[1].thinking).toBe(reasoning)
})

test('discards provisional Copilot narration when stopped', async ({ page }) => {
  const narration = 'I will inspect the workout file.'
  await page.addInitScript(({ narration }) => {
    const originalFetch = window.fetch.bind(window)
    window.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : String(input)
      if (!url.includes('/api/analyze')) return originalFetch(input, init)

      const encoder = new TextEncoder()
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(
            encoder.encode(
              [
                `event: start\ndata: ${JSON.stringify({ backend: 'copilot' })}\n\n`,
                `event: delta\ndata: ${JSON.stringify({ text: narration })}\n\n`,
              ].join(''),
            ),
          )
          init?.signal?.addEventListener('abort', () => {
            controller.error(new DOMException('Aborted', 'AbortError'))
          })
        },
      })
      return Promise.resolve(
        new Response(body, {
          status: 200,
          headers: { 'Content-Type': 'text/event-stream' },
        }),
      )
    }) as typeof window.fetch
  }, { narration })
  await page.goto('/analyze')

  await page.getByRole('textbox', { name: 'Message' }).fill('Review this workout')
  await page.getByRole('button', { name: 'Send' }).tap()
  await expect(page.getByText(narration)).toBeVisible()

  await page.getByRole('button', { name: 'Stop' }).tap()
  await expect(page.getByText(narration)).toBeHidden()
})

test('recovers when an analysis stream closes without a terminal event', async ({ page }) => {
  let savedBeforeAnalysis = false

  await page.route('**/api/chats/*', async (route) => {
    const body = route.request().postDataJSON() as {
      title?: string
      backend?: string
      model?: string
      reasoning_effort?: string
      activity_ids: string[]
      messages: { id: string; role: string; content: string }[]
    }
    expect(body.messages).toHaveLength(1)
    savedBeforeAnalysis = true
    const id = new URL(route.request().url()).pathname.split('/').pop() ?? 'chat'
    await route.fulfill({
      json: {
        id,
        title: body.title ?? body.messages[0].content,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        backend: body.backend ?? '',
        model: body.model ?? '',
        reasoning_effort: body.reasoning_effort ?? '',
        activity_ids: body.activity_ids,
        messages: body.messages,
      },
    })
  })
  await page.route('**/api/analyze', async (route) => {
    expect(savedBeforeAnalysis).toBe(true)
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'event: start\ndata: {"backend":"copilot"}\n\n',
        'event: delta\ndata: {"text":"I will inspect the workout file."}\n\n',
        'event: ping\ndata: {}\n\n',
      ].join(''),
    })
  })

  await page.goto('/analyze')
  await page.getByRole('textbox', { name: 'Message' }).fill('Review my latest run')
  await page.getByRole('button', { name: 'Send' }).click()

  await expect(page.getByRole('alert')).toContainText(
    'The connection closed before the response finished.',
  )
  await expect(page.getByText('Thinking…')).toBeHidden()
  await expect(page.getByText('I will inspect the workout file.')).toBeHidden()
  await expect(page.getByRole('button', { name: 'Send' })).toBeVisible()
})
