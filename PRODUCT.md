# Product

## Register

product

## Users

Data-literate endurance athletes — runners, cyclists, triathletes — who want to make sense of
their *own* training and keep it private. They value data ownership and calm over social feeds
and engagement mechanics. FitSift is **local-first**: the workout library and training memory
live in a local database the athlete owns, and analysis runs on the model of their choice —
fully local, or their own cloud key. A one-time import seeds history; after that it stays in
sync in the background (no CLI required).

**Also served:** coaches who follow several athletes' training over time — the paid,
multi-athlete tier.

Their job: make sense of their training. They open FitSift to browse their
workout library, inspect a single activity in depth (splits, HR, map, charts),
run an LLM analysis against a custom prompt, and revisit a growing "training
memory" corpus to reason about progress over time. Context is split between
**phone** (right after a workout, on the go) and **desktop** (longer, focused
review sessions).

## Product Purpose

fit2json turns raw workout files into faithful, **lossless** data; FitSift is the
calm reading room for that data. It exists to convert a pile of `.fit` files and
API pulls into **durable insight** — one workout understood at a glance, and
long-term trends surfaced through accumulated analysis.

Success looks like: the athlete quickly grasps what a single session was, then
just as quickly sees how it fits the larger arc of their training — without ads,
noise, engagement mechanics, or social pressure. The interface earns trust by
being accurate, legible, and quiet.

## Brand Personality

Calm, precise, data-forward. Quiet confidence rather than hype. The chrome
recedes so the data is the hero — restraint in the Linear / Things tradition.

Crucially: **calm core, with earned moments of delight.** Restrained by default,
but expressive exactly where it aids comprehension — the charts, the route map,
and the AI insight write-up. Delight always serves understanding; it is never
decoration for its own sake.

Voice: plain, exact, unhyped. Names things precisely (pace, HR zones, splits) and
trusts the user to read data.

## Anti-references

- **Consumer-social fitness** (the primary anti-reference): feeds, likes, kudos,
  leaderboards, follower counts, social comparison. FitSift is private and
  personal; it must never borrow social-network patterns.
- **Loud gamification:** streaks, confetti, badges, dopamine mechanics.
- **Cluttered "pro" dashboards:** every widget on screen at once, nothing
  prioritized.
- **Generic AI-SaaS slop:** cream/violet gradients, gradient text, hero-metric
  card templates, tracked-uppercase eyebrows above every section.

## Design Principles

1. **Data is the hero.** Chrome recedes; numbers, charts, and the route lead.
   Layout and color exist to make the data legible, not to decorate it.
2. **Calm over loud.** Optimize for insight, not engagement. No gamification, no
   dopamine tricks, no attention-grabbing motion.
3. **Private by design.** Local-first by default — your data lives with you, and
   you choose where analysis runs (fully local, or your own cloud key). Never reach
   for social, comparison, or feed patterns — they contradict what this tool is.
4. **Legible at a glance, deep on demand.** Summary first, detail when asked.
   Progressive disclosure keeps each screen quiet while depth stays one tap away.
5. **Restraint by default, expression where it counts.** The interface is
   understated; the charts, map, and AI insights are where craft and delight are
   allowed to concentrate.
6. **Every theme first-class.** Light and dark are treated as equals, each with
   verified contrast — craft must hold in both.

## Accessibility & Inclusion

Working target: **practical WCAG AA.** Body text ≥4.5:1 contrast (large text
≥3:1), fully keyboard-operable with visible focus, and a genuine
`prefers-reduced-motion` alternative for every animation.

**First-class dark mode is a priority.** The app is currently light-only
(`color-scheme: light`); dark should become a fully-supported, contrast-verified
theme rather than an afterthought — both themes held to the same AA bar. Charts,
maps, and status colors must stay distinguishable for common color-vision
deficiencies (don't rely on hue alone).
