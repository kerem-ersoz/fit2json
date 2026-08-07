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

test('matches the system theme with true-black dark surfaces', async ({ page }) => {
  const theme = () =>
    page.evaluate(() => {
      const root = getComputedStyle(document.documentElement)
      const header = document.querySelector('header')
      return {
        canvas: root.getPropertyValue('--color-canvas').trim(),
        surface: root.getPropertyValue('--color-surface').trim(),
        divider: root.getPropertyValue('--color-divider').trim(),
        accent: root.getPropertyValue('--color-accent').trim(),
        body: getComputedStyle(document.body).backgroundColor,
        header: header ? getComputedStyle(header).backgroundColor : '',
      }
    })

  await page.emulateMedia({ colorScheme: 'dark' })
  await page.goto('/')
  await expect(page.locator('header')).toBeVisible()

  const dark = await theme()
  expect(dark).toMatchObject({
    canvas: '#000000',
    surface: '#000000',
    divider: 'rgb(255 255 255 / 0.22)',
    accent: '#34d399',
  })
  expect(dark.body).toMatch(/^rgb\(0,\s*0,\s*0\)$/)
  expect(dark.header).toMatch(/^rgba?\(0,\s*0,\s*0/)

  await page.emulateMedia({ colorScheme: 'light' })
  await expect.poll(theme).toMatchObject({
    canvas: '#f8fafc',
    surface: '#ffffff',
    divider: '#e2e8f0',
    accent: '#059669',
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

test('reconnects to background thinking without starting twice', async ({ page }) => {
  let runId = ''
  let startCalls = 0
  let eventConnections = 0
  const summary = 'Reviewing pace and heart-rate evidence'
  const reasoning =
    'The opening pace was controlled while heart rate rose gradually. The finish stayed aerobic.'

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
          'id: 1\nevent: start\ndata: {"backend":"copilot"}\n\n' +
          `id: 2\nevent: thinking\ndata: ${JSON.stringify({ summary, text: reasoning })}\n\n` +
          'id: 3\nevent: delta\ndata: {"text":"I will inspect the workout file."}\n\n',
      })
      return
    }
    expect(url.searchParams.get('after')).toBe('3')
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body:
        'id: 4\nevent: replace\ndata: {"text":"A controlled aerobic session."}\n\n' +
        'id: 5\nevent: done\ndata: {"chars":29,"saved":null,"backend":"copilot"}\n\n',
    })
  })

  await page.goto('/analyze')
  await page.getByRole('textbox', { name: 'Message' }).fill('Review my latest run')
  await page.getByRole('button', { name: 'Send' }).click()

  const disclosure = page.locator('details').filter({ hasText: summary })
  const detail = page.getByText(reasoning)
  await expect(disclosure).toBeVisible()
  await disclosure.locator('summary').tap()
  await expect(detail).toBeVisible()
  await expect(page.getByText('A controlled aerobic session.')).toBeVisible()
  await expect(page.getByText('I will inspect the workout file.')).toBeHidden()
  expect(startCalls).toBe(1)
  expect(eventConnections).toBe(2)
  await expect(page.getByText('Running in the background…')).toBeHidden()
  await expect(page.getByRole('button', { name: 'Send' })).toBeVisible()
})

test('switches away from a running chat without restoring it from summary polling', async ({
  page,
}) => {
  const timestamp = '2026-08-06T20:00:00Z'
  const runningChat = {
    id: 'chat-running',
    title: 'Current running chat',
    created_at: timestamp,
    updated_at: timestamp,
    backend: 'ollama',
    model: 'auto',
    reasoning_effort: '',
    activity_ids: [],
    messages: [
      { id: 'running-user', role: 'user', content: 'Current running question' },
      { id: 'running-assistant', role: 'assistant', content: 'Current partial answer' },
    ],
    analysis_run: {
      id: 'run-current',
      assistant_message_id: 'running-assistant',
      status: 'running',
      error: null,
      started_at: timestamp,
      finished_at: null,
    },
  }
  const savedChat = {
    id: 'chat-saved',
    title: 'Older saved chat',
    created_at: timestamp,
    updated_at: timestamp,
    backend: 'ollama',
    model: 'auto',
    reasoning_effort: '',
    activity_ids: [],
    messages: [
      { id: 'saved-user', role: 'user', content: 'Older saved question' },
      { id: 'saved-assistant', role: 'assistant', content: 'Older saved answer' },
    ],
    analysis_run: null,
  }
  let runningChatLoads = 0

  await page.addInitScript((chatId) => {
    localStorage.setItem('fitsift-active-chat', chatId)
  }, runningChat.id)
  await page.route('**/api/chats', async (route) => {
    await route.fulfill({
      json: {
        chats: [
          {
            ...runningChat,
            message_count: runningChat.messages.length,
            analysis_status: 'running',
          },
          {
            ...savedChat,
            message_count: savedChat.messages.length,
            analysis_status: null,
          },
        ],
      },
    })
  })
  await page.route('**/api/chats/*', async (route) => {
    const id = decodeURIComponent(new URL(route.request().url()).pathname.split('/').at(-1) ?? '')
    if (id === runningChat.id) {
      runningChatLoads += 1
      await route.fulfill({ json: runningChat })
      return
    }

    await new Promise((resolve) => setTimeout(resolve, 150))
    await route.fulfill({ json: savedChat })
  })
  await page.route('**/api/analysis-runs/run-current/events?*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: 'id: 1\nevent: start\ndata: {"backend":"ollama"}\n\n',
    })
  })

  await page.goto('/analyze')
  await expect(page.getByText('Current running question')).toBeVisible()

  await page.getByRole('button', { name: 'Chat history' }).tap()
  await page.getByRole('button', { name: /^Older saved chat/ }).tap()

  await expect(page.getByText('Older saved answer')).toBeVisible()
  await expect(page.getByText('Current running question')).toBeHidden()
  expect(runningChatLoads).toBe(1)
})

test('discards provisional Copilot narration when a background run is stopped', async ({ page }) => {
  const narration = 'I will inspect the workout file.'
  let runId = ''
  let releaseCancellation = () => {}
  const cancellation = new Promise<void>((resolve) => {
    releaseCancellation = resolve
  })

  await page.route('**/api/analysis-runs', async (route) => {
    runId = (route.request().postDataJSON() as { run_id: string }).run_id
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
  await page.route('**/api/analysis-runs/*/cancel', async (route) => {
    releaseCancellation()
    await route.fulfill({
      json: {
        id: runId,
        status: 'cancelling',
        error: null,
        last_event_id: 2,
        created_at: new Date().toISOString(),
        finished_at: null,
      },
    })
  })
  await page.route('**/api/analysis-runs/*/events?*', async (route) => {
    const after = new URL(route.request().url()).searchParams.get('after')
    if (after === '0') {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body:
          'id: 1\nevent: start\ndata: {"backend":"copilot"}\n\n' +
          `id: 2\nevent: delta\ndata: ${JSON.stringify({ text: narration })}\n\n`,
      })
      return
    }
    await cancellation
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: 'id: 3\nevent: cancelled\ndata: {}\n\n',
    })
  })

  await page.goto('/analyze')
  await page.getByRole('textbox', { name: 'Message' }).fill('Review this workout')
  await page.getByRole('button', { name: 'Send' }).tap()
  await expect(page.getByText(narration)).toBeVisible()

  await page.getByRole('button', { name: 'Stop' }).tap()
  await expect(page.getByText(narration)).toBeHidden()
  await expect(page.getByRole('button', { name: 'Send' })).toBeVisible()
})
