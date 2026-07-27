# Copilot instructions

## Design Context

This project has two root-level design documents that govern all UI/frontend work
(the frontend lives in `frontend/`, a React + Vite + Tailwind SPA called **FitSift**):

- **[PRODUCT.md](../PRODUCT.md)** — strategic: register (`product`), users, product
  purpose, brand personality, anti-references, design principles, and the
  accessibility bar.
- **[DESIGN.md](../DESIGN.md)** — the visual system (Stitch format): color tokens,
  typography, elevation, components, and do's/don'ts. `.impeccable/design.json` is
  its machine-readable sidecar.

When designing or changing any interface, read both first and stay on-brand.

**North Star:** *"The Quiet Instrument"* — a calm, precise, data-forward product.
The chrome recedes; the workout data and AI insight are the hero.

**Hard rules to respect:**
- Keep the single **Signal Green** (`#059669`) accent to ≤10% of any screen; build
  structure with slate + hairline borders, not color.
- Flat by default — shadows are a response to hover/focus/overlay, never decoration.
- No consumer-social patterns (feeds, likes, kudos, leaderboards, streaks).
- No generic AI-SaaS slop (gradient text, hero-metric templates, tracked-uppercase eyebrows).
- Dark mode is a first-class, contrast-verified goal (the app is currently light-only).
- Body text ≥4.5:1 contrast; every animation needs a `prefers-reduced-motion` alternative.
