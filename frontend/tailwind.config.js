import typography from '@tailwindcss/typography'

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'media',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: 'var(--color-canvas)',
        surface: {
          DEFAULT: 'var(--color-surface)',
          muted: 'var(--color-surface-muted)',
          subtle: 'var(--color-surface-subtle)',
          translucent: 'var(--color-surface-translucent)',
        },
        chrome: 'var(--color-chrome)',
        hover: 'var(--color-hover)',
        divider: {
          DEFAULT: 'var(--color-divider)',
          soft: 'var(--color-divider-soft)',
          strong: 'var(--color-divider-strong)',
        },
        skeleton: 'var(--color-skeleton)',
        backdrop: {
          DEFAULT: 'var(--color-backdrop)',
          subtle: 'var(--color-backdrop-subtle)',
        },
        ink: {
          DEFAULT: 'var(--color-ink)',
          soft: 'var(--color-ink-soft)',
        },
        strong: 'var(--color-strong)',
        copy: 'var(--color-copy)',
        muted: 'var(--color-muted)',
        faint: 'var(--color-faint)',
        disabled: 'var(--color-disabled)',
        accent: {
          DEFAULT: 'var(--color-accent)',
          strong: 'var(--color-accent-strong)',
          deep: 'var(--color-accent-deep)',
          subdued: 'var(--color-accent-subdued)',
          tint: 'var(--color-accent-tint)',
          'tint-strong': 'var(--color-accent-tint-strong)',
          muted: 'var(--color-accent-muted)',
          divider: 'var(--color-accent-divider)',
        },
        action: {
          DEFAULT: 'var(--color-action)',
          hover: 'var(--color-action-hover)',
        },
        'on-action': 'var(--color-on-action)',
        'focus-neutral': 'var(--color-ring-neutral)',
        danger: {
          DEFAULT: 'var(--color-danger)',
          soft: 'var(--color-danger-soft)',
          strong: 'var(--color-danger-strong)',
          deep: 'var(--color-danger-deep)',
          tint: 'var(--color-danger-tint)',
          divider: 'var(--color-danger-divider)',
        },
        warning: {
          DEFAULT: 'var(--color-warning)',
          strong: 'var(--color-warning-strong)',
        },
        code: {
          DEFAULT: 'var(--color-code)',
          text: 'var(--color-code-text)',
        },
        'zone-blue': 'var(--color-zone-blue)',
        'zone-blue-tint': 'var(--color-zone-blue-tint)',
        'zone-green': 'var(--color-zone-green)',
        'zone-green-tint': 'var(--color-zone-green-tint)',
        'zone-orange': 'var(--color-zone-orange)',
        'zone-orange-tint': 'var(--color-zone-orange-tint)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [typography],
}
