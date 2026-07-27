---
name: FitSift
description: A calm, precise reading room for your own workout data.
colors:
  signal-green: "#059669"
  signal-green-hover: "#047857"
  signal-green-tint: "#ecfdf5"
  ink: "#0f172a"
  ink-soft: "#1e293b"
  slate-strong: "#334155"
  slate: "#475569"
  slate-muted: "#64748b"
  slate-faint: "#94a3b8"
  divider: "#e2e8f0"
  divider-soft: "#f1f5f9"
  mist: "#f8fafc"
  surface: "#ffffff"
  alert-red: "#b91c1c"
  alert-red-tint: "#fef2f2"
  alert-red-border: "#fecaca"
  caution-amber: "#d97706"
typography:
  display:
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.025em"
rounded:
  md: "6px"
  lg: "8px"
  xl: "12px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
components:
  button-primary:
    backgroundColor: "{colors.signal-green}"
    textColor: "{colors.surface}"
    typography: "{typography.body}"
    rounded: "{rounded.lg}"
    padding: "0 16px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.signal-green-hover}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.slate-strong}"
    rounded: "{rounded.lg}"
    height: "44px"
  button-ghost:
    textColor: "{colors.slate}"
    rounded: "{rounded.lg}"
    height: "44px"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.xl}"
    padding: "16px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    height: "44px"
    padding: "0 12px"
  chip:
    backgroundColor: "{colors.mist}"
    textColor: "{colors.slate}"
    rounded: "{rounded.full}"
    padding: "4px 12px"
  badge:
    backgroundColor: "{colors.divider-soft}"
    textColor: "{colors.slate}"
    rounded: "{rounded.full}"
    padding: "2px 10px"
  badge-brand:
    backgroundColor: "{colors.signal-green-tint}"
    textColor: "{colors.signal-green-hover}"
  nav-item-active:
    backgroundColor: "{colors.signal-green-tint}"
    textColor: "{colors.signal-green-hover}"
    rounded: "{rounded.lg}"
    padding: "10px 12px"
---

# Design System: FitSift

## 1. Overview

**Creative North Star: "The Quiet Instrument"**

FitSift is a precise measuring instrument for one athlete's training. The chassis
is calm matte chrome — near-white surfaces, hairline dividers, a single restrained
green — and the *readout* is the workout data itself: the metrics, the route, the
charts, the AI write-up. The interface never competes with the numbers. It holds
still so the data can speak, the way a good scale or a watchmaker's loupe
disappears in the hand and leaves only the reading.

Restraint is the default, but the instrument is not lifeless. Expression is
*rationed* and spent precisely where it aids comprehension: the sport glyph on an
activity card, the emerald focus ring answering a keystroke, the route map, and
the model's streamed analysis. These are the lit dials on an otherwise matte
panel. Everywhere else, chrome recedes to greyscale.

This system explicitly rejects the vocabulary of consumer-social fitness — no
feeds, kudos, likes, leaderboards, streaks, or confetti. There is no one to
perform for; this is a private tool for a single user. It equally rejects the
cluttered "pro dashboard" (everything on screen at once, nothing prioritised) and
generic AI-SaaS styling (cream/violet gradients, gradient text, hero-metric card
templates, tracked-uppercase eyebrows on every section).

**Key Characteristics:**
- Near-white greyscale chassis; one green accent, used sparingly.
- Border-driven, near-flat surfaces — depth is a *response* to state, not decoration.
- Mobile-first, thumb-friendly (44px minimum targets, safe-area aware).
- Data and insight are the only things allowed to be vivid.
- Light-only today; dark mode is a first-class, contrast-verified goal (see Colors).

## 2. Colors

A greyscale instrument panel lit by a single emerald signal. One accent hue does
all the "active / on / go" work; everything structural is slate.

### Primary
- **Signal Green** (`#059669`): the one voice of the system. Primary buttons,
  active-nav text and icon, links, focus rings, the sport-glyph and the "Analyze"
  spark. It marks *action* and *active state* — nothing decorative.
- **Signal Green — Pressed** (`#047857`): hover/active depth for Signal Green, and
  the text colour on tinted brand chips (contrast-safe on the tint).
- **Signal Green — Tint** (`#ecfdf5`): the quiet wash behind an active nav item,
  the sport-glyph disc, and the GPS badge. Signals "selected" without shouting.

### Neutral
- **Ink** (`#0f172a`, slate-900): primary text and headings. The default reading colour.
- **Ink Soft** (`#1e293b`, slate-800): strong-but-secondary text (list item titles).
- **Slate Strong** (`#334155`, slate-700): secondary-button label, empty-state titles.
- **Slate** (`#475569`, slate-600): resting navigation labels, medium-weight body.
- **Slate Muted** (`#64748b`, slate-500): captions and secondary metadata.
- **Slate Faint** (`#94a3b8`, slate-400): *decoration only* — placeholder glyphs,
  timestamps, unit labels. Below 4.5:1 on white; never use for text that must be read.
- **Divider** (`#e2e8f0`, slate-200): the hairline that carries almost all structure.
- **Divider Soft** (`#f1f5f9`, slate-100): inner card dividers, neutral badge fill, hover wash.
- **Mist** (`#f8fafc`, slate-50): the body background and the tint behind subtle panels.
- **Surface** (`#ffffff`): cards, bars, inputs — the raised matte face of the panel.

### Semantic
- **Alert Red** (`#b91c1c` on `#fef2f2`, border `#fecaca`): error and failure states only.
- **Caution Amber** (`#d97706`): non-fatal warnings (e.g. a chart that failed to render).

### Named Rules
**The One Voice Rule.** Signal Green appears on ≤10% of any screen. It means
"active" or "act now." If two greens compete for attention on one view, one of
them is wrong — demote it to slate.

**The Greyscale-First Rule.** Structure is built in slate and dividers, never in
colour. A border, a tint, or a weight change carries hierarchy before any hue does.

**The Dark-Mode-Is-First-Class Rule.** The app ships light-only today
(`color-scheme: light`, `mist` body). Dark is a priority, not a filter: invert the
neutral ramp to a near-black/slate chassis, re-verify every pairing at AA, and
lift the accent toward `#34d399` (brand-400) for text/icons on dark so Signal
Green keeps ≥4.5:1. Both themes are held to the same bar; neither is the afterthought.

## 3. Typography

**Display / Body / Label Font:** Inter (with `system-ui, -apple-system, Segoe UI, Roboto` fallback).

**Character:** One family, worked in weight and size rather than contrast. Inter's
tall x-height and tabular figures make dense metrics legible at small sizes — the
right choice for an instrument readout. No serif, no second family: a measuring
tool does not need two voices.

### Hierarchy
- **Display** (700, `1.5rem`/text-2xl, line-height ~1.15, `-0.025em`): page titles
  ("Library"). The largest type in the app — this is a compact product UI, not a
  marketing page; it never shouts.
- **Title** (600, `1rem`–`1.125rem`, tight): section headings, card and brand marks.
- **Body** (400, `0.875rem`/text-sm, 1.5): the default — copy, controls, inputs,
  most metrics. Prose (AI analyses) renders at this size via the typography plugin.
- **Label** (600, `0.6875rem`/text-[11px], `0.025em`, UPPERCASE): metric captions
  under a value ("DISTANCE", "AVG HR") and the "Past analyses" section marker.

### Named Rules
**The Readout Rule.** Numbers lead, labels follow and shrink. A metric is a bold
`Ink` value with a small uppercase `Slate` label beneath it — value first, always.

**The Tabular Figures Rule.** Any column or grid of numbers uses tabular figures so
digits align vertically. Metrics that jitter as they update are a bug, not a style.

## 4. Elevation

Near-flat by conviction. Depth is drawn with **hairline `Divider` borders on
`Surface`**, not stacked shadows. Resting cards carry only the faintest ambient
shadow (`shadow-sm`); a real shadow is a *response to interaction*, never a default
coat of paint. Floating chrome (the sticky mobile top bar and bottom tab bar) uses
a translucent `Surface` with a backdrop blur so content scrolls softly beneath it.

### Shadow Vocabulary
- **Ambient rest** (`box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05)`): the barely-there
  lift under a resting card. Reads as "a physical face," not "a floating object."
- **Hover lift** (`box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)`):
  the response when a card becomes interactive (tappable activity cards).

### Named Rules
**The Flat-By-Default Rule.** Surfaces are flat at rest and separated by borders.
Shadow appears only on hover, focus, or genuine overlay (dialogs, popovers). If a
static screen needs a shadow to look structured, add a border instead.

**The Ghost-Border Rule.** If it looks like a 2014 app, the shadow is too dark and
the blur is too small — delete the shadow and reach for a `Divider` hairline.

## 5. Components

Every interactive element is at least **44px** tall — this is a phone-first tool
used with a thumb, often right after a workout.

### Buttons
- **Shape:** gently rounded (8px, `rounded-lg`); pill-shaped only for chips/badges.
- **Primary:** `Signal Green` fill, `Surface` text, 44px tall, `0 16px` padding.
  Hover deepens to `Signal Green — Pressed`.
- **Secondary:** `Surface` fill, `Divider` border, `Slate Strong` text; hover washes to `Mist`.
- **Ghost:** no fill or border, `Slate` text; hover washes to `Divider Soft`.
- **Focus:** a 2px `Signal Green` ring with a 2px offset (`focus-visible`), never a
  removed outline. Disabled drops to 50% opacity.

### Chips
- **Suggestion / prompt chips:** pill (`rounded-full`), `Mist` fill, `Divider`
  border, `Slate` text, `4px 12px`; hover washes to `Divider Soft`. Used for the
  canned analysis prompts and as tap-to-fill affordances.
- **Segmented toggle** (metric/imperial units): a `Mist` track with a `Divider`
  border; the selected segment is a `Surface` pill with `Signal Green — Pressed`
  text and a soft shadow. The unselected segment is `Slate Muted`.

### Cards / Containers
- **Corner Style:** 12px (`rounded-xl`).
- **Background:** `Surface`, over a `Mist` page.
- **Border:** always a `Divider` hairline — the primary structure device.
- **Shadow Strategy:** ambient rest by default; interactive cards add hover lift (see Elevation).
- **Internal Padding:** `16px` mobile, `20px` from `sm` up. Inner sections split by a `Divider Soft` rule.

### Inputs / Fields
- **Style:** `Surface` fill, `Divider` border, 8px radius, 44px tall (`h-11`; a
  compact `h-9` variant exists for inline selectors).
- **Focus:** border shifts to `Signal Green` with a 1px `Signal Green` ring — the
  emerald "the instrument is listening" cue. Outline is never simply removed.
- **Placeholder / adornments:** `Slate Faint` — decorative only, not load-bearing text.

### Navigation
- **Desktop:** a fixed 256px left rail on `Surface`. Items are `rounded-lg`,
  `Slate` at rest; active is `Signal Green — Pressed` text on a `Signal Green —
  Tint` fill; hover washes to `Divider Soft`. 20px icons.
- **Mobile:** a sticky translucent top bar (brand mark + units) and a fixed
  bottom tab bar of four items, each ≥56px, `Slate Muted` at rest and `Signal
  Green — Pressed` when active. Safe-area inset padding on the bottom bar.

### Signature Components
- **Activity Card:** a `Surface` card headed by a `Signal Green — Tint` disc
  holding the sport glyph, the sport name, an optional GPS badge, and the date;
  below a hairline, a 2×2 → 1×4 grid of **Readout** metrics (Distance / Time /
  Pace / Avg HR). This is the atom of the Library and the clearest expression of
  the Readout Rule.
- **Analysis Panel:** the app's one "lit" surface. A `Sparkles` spark in `Signal
  Green`, a prompt textarea, tap-to-fill suggestion chips, a backend selector, and
  a live-streaming Markdown readout. The model may emit fenced `fitsift-chart`
  (Vega-Lite) blocks that render inline as bordered `Surface` charts — the sanctioned
  place for expressive data-viz colour beyond the core palette.

## 6. Do's and Don'ts

### Do:
- **Do** build structure with `Divider` hairlines on `Surface` first; add a shadow
  only as a hover/focus/overlay *response* (The Flat-By-Default Rule).
- **Do** keep `Signal Green` to ≤10% of a screen and reserve it for action and
  active state (The One Voice Rule).
- **Do** lead metrics with a bold `Ink` value and a small uppercase `Slate` label
  beneath, using tabular figures so numbers align (The Readout Rule).
- **Do** keep body text at `Slate Muted` (`#64748b`) or darker; put primary reading
  copy in `Ink`. Verify ≥4.5:1 (large text ≥3:1).
- **Do** treat dark mode as first-class: build it, invert the neutral ramp, lift the
  accent toward `#34d399`, and re-verify contrast in both themes.
- **Do** give every animation a `prefers-reduced-motion: reduce` alternative
  (currently missing — the spinner and transitions need one).
- **Do** keep every tap target ≥44px and honour safe-area insets.

### Don't:
- **Don't** import consumer-social patterns — no feeds, likes, kudos, follower
  counts, leaderboards, streaks, or confetti. This is a private, single-user tool.
- **Don't** reach for gamification or dopamine mechanics to drive "engagement";
  optimise for insight, not time-on-app.
- **Don't** use `Slate Faint` (`#94a3b8`) for text that must be read — it fails AA
  on white. It's for placeholders and non-essential metadata only.
- **Don't** ship generic AI-SaaS styling: no cream/violet gradients, no gradient
  text (`background-clip: text`), no hero-metric card template, no tracked-uppercase
  eyebrow above every section.
- **Don't** use `border-left`/`border-right` >1px as a coloured accent stripe on
  cards or callouts. Use a full border or a tint.
- **Don't** let a second accent colour creep in. If something needs emphasis and
  isn't an action, use weight, size, or `Ink` — not a new hue.
- **Don't** stack decorative shadows to fake depth ("2014 app" tell). Reach for a `Divider`.
