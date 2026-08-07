# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

FitSift primarily serves data-literate endurance athletes — runners, cyclists,
and triathletes — who want deep insight into their own complete training history
without giving up data ownership or privacy.

They browse their workout library, inspect an activity in depth, ask coaching
questions across one or many workouts, and revisit saved conversations and
analysis memory to understand progress over time. They use FitSift on a phone
soon after training and on a desktop for longer review sessions.

A paid multi-athlete tier for coaches is planned, not currently implemented.

## Product Purpose

fit2json turns raw workout files and provider exports into faithful, lossless
data. FitSift is the private reading and analysis surface for that archive. The
product exists to turn workouts into durable insight: understand one session
quickly, then see how it fits the larger arc of training.

Success means an athlete can trust the stored record, grasp a workout at a
glance, and get useful longitudinal coaching without ads, social pressure, or
engagement mechanics.

## Positioning

FitSift is a private AI coach built around a local, portable, lossless training
vault. Unlike social fitness networks and cloud-first AI summaries, it combines
full-fidelity history, durable analysis memory, and user-chosen inference: a
local model for maximum privacy or a user-controlled cloud model for frontier
capability.

The product promise is local-first and private by default. Hosted storage is a
future adapter, not the foundation of the current product.

## Operating Context

- Athletes import local `.fit` files or fetch activities from Garmin Connect or
  Strava, then retain raw files and lossless JSON in their own archive.
- The current local pipeline has three roles: poller, analyzer, and web UI. They
  coordinate through `~/.fit2json` rather than a hosted account.
- FitSift's web UI provides the Library, activity detail, Analyze conversation,
  saved memory, workout ingestion, and You profile surfaces.
- Chat sessions, athlete profile data, workout files, and analysis memory persist
  locally. Background polling and analysis are available through the current
  CLI/supervisor workflow.
- Phone use favors quick post-workout checks; desktop use favors detailed review,
  comparison, and longer coaching conversations.

## Capabilities and Constraints

**Current capabilities**

- Lossless FIT conversion and a portable archive of raw FIT, JSON, and Markdown.
- Garmin Connect and Strava ingestion, including incremental polling.
- Local activity browsing, maps, charts, filtering, profile personalization,
  resumable chat, and saved training-memory analysis.
- Analysis through GitHub Copilot CLI, Ollama, or LM Studio. Arbitrary
  OpenAI-compatible endpoints are available in the CLI but do not yet have a
  first-class web settings flow.
- The shipped experience is local and single-user. Multi-device E2EE sync,
  multi-athlete coaching, sharing, and hosted storage remain planned work.
- Automatic cloud-backed analysis must be explicit and cost-aware; it must not
  silently spend a user's model budget.
- Provider credentials are device-local secrets and must never enter synced
  training data.

## Brand Commitments

FitSift is calm, precise, data-forward, and quietly confident. Its voice is
plain, exact, and unhyped; it names pace, zones, splits, and uncertainty
directly. The product is local-first, private by design, and trusts athletes to
read their own data.

It must not adopt consumer-social fitness patterns such as feeds, likes, kudos,
leaderboards, follower counts, streaks, or social comparison. It also rejects
loud gamification, cluttered pro dashboards, and generic AI-SaaS conventions.

## Evidence on Hand

- `README.md` documents the implemented CLI, lossless archive, analysis backends,
  profile personalization, watch modes, and FitSift web UI.
- `ARCHITECTURE.md` documents the current poller/analyzer/web topology and local
  filesystem contract.
- `docs/product-direction.md` records the owner-approved local-first direction,
  current implementation boundaries, and phased roadmap.
- `frontend/src/` contains the implemented FitSift React application.
- The repository contains no customer testimonials, market benchmarks, press, or
  production adoption evidence; future product copy must not fabricate them.

## Product Principles

1. **The athlete owns the record.** Preserve full-fidelity, portable source data
   and keep local storage as the default.
2. **Privacy boundaries stay explicit.** State when data leaves the device and
   keep hosted behavior opt-in.
3. **Model choice belongs to the user.** Support local and user-controlled cloud
   inference without reselling tokens or hiding cost.
4. **Insight beats engagement.** Optimize for understanding and durable memory,
   never feeds, comparison, or dopamine mechanics.
5. **Ship honest layers.** Distinguish implemented capabilities from planned sync,
   coach, sharing, and hosted adapters.

## Accessibility & Inclusion

Working target: **practical WCAG AA.** Body text ≥4.5:1 contrast (large text
≥3:1), fully keyboard-operable with visible focus, and a genuine
`prefers-reduced-motion` alternative for every animation.

**Dark mode is first-class.** The app follows the system theme and uses a
true-black AMOLED canvas and surfaces in dark mode, with translucent white
hairlines instead of gray structural fills. Both themes are held to the same AA
bar. Charts, maps, and status colors must stay distinguishable for common
color-vision deficiencies (don't rely on hue alone).
