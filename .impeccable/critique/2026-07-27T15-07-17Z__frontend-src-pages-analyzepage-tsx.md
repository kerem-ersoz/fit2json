---
target: analyze
total_score: 21
p0_count: 0
p1_count: 3
timestamp: 2026-07-27T15-07-17Z
slug: frontend-src-pages-analyzepage-tsx
---
# Critique — Analyze (`frontend/src/pages/AnalyzePage.tsx`, route `/analyze`)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | No signal of which workouts are already analyzed; error has no retry here |
| 2 | Match System / Real World | 3 | Clear copy, but the page promises "ask questions / streaming analysis" that actually happens two taps away |
| 3 | User Control and Freedom | 2 | No search / filter / sort on a picker of 80 items |
| 4 | Consistency and Standards | 1 | Duplicates the Library grid + destination; now strictly behind the improved Library |
| 5 | Error Prevention | 3 | Read-only picker, little destructive risk |
| 6 | Recognition vs Recall | 2 | Must recognize one workout in 80 unsorted cards |
| 7 | Flexibility and Efficiency | 1 | No search/sort/keyboard; no "recent" or re-analyze shortcut |
| 8 | Aesthetic & Minimalist | 3 | Visually clean, but minimal tips into empty — no analyze-specific content |
| 9 | Error Recovery | 2 | `ErrorState` rendered without retry/hint (component now supports both) |
| 10 | Help and Documentation | 2 | One-line hint + teaching empty state; no prompt examples or "how it works" |
| **Total** | | **21/40** | **Acceptable — works, but redundant and thin** |

## Anti-Patterns Verdict

**Looks AI-generated? Not visually — but conceptually, yes: this is a redundant page.** The `/analyze` route renders the *same* `ActivityCard` grid as Library and links each card to the *same* destination (`/activities/:id`). Two nav items, one behavior.

**LLM assessment:** No visual slop tells (shared clean components). The real anti-pattern is an **identical card grid that duplicates another route** with no added value. After the Library overhaul it's worse: Library now has search, sort, date grouping, a latest hero, a volume trend, skeletons, retry, keyboard nav and URL state — Analyze has none of it, while showing the identical 80 cards.

**Deterministic scan:** `detect.mjs` on `AnalyzePage.tsx` → **0 findings (clean)**.

**Live data (real evidence):** the running backend serves **80 activities** (walking 32, running 25, cycling 14, swimming 3, fitness_equipment 2, sport_57 4). So "scroll 80 unsorted cards to pick one to analyze" is the real experience, not a hypothetical.

**Visual overlay:** Not performed. The dev server + backend are up and the page renders in the browser canvas, but no scriptable browser automation is available to inject the detector overlay / read the console — so there is no user-visible overlay. Evidence = source review + live API data + CLI scan.

## Overall Impression

The page is clean and honest, but it barely earns its place: it's a second copy of the Library grid that routes to the same detail view where analysis actually lives. The single biggest question is strategic — **should "Analyze" be a destination at all, or an action on a workout?** If it stays, it must (a) give the user analyze-specific value the Library doesn't (what's analyzed, what isn't, jump straight into asking) and (b) at minimum match Library's findability, because picking one workout out of 80 with no search or sort is the core failure today.

## What's Working

1. **Honest, expectation-setting copy** — "Open a workout to ask coaching questions and get a saved, streaming analysis" tells the user what this leads to.
2. **Shared component vocabulary** — reuses `ActivityCard` / `EmptyState`, so it stays visually consistent and inherited the recent card a11y + tabular-figure fixes for free.
3. **States aren't forgotten** — loading, error, and a teaching empty state are all present.

## Priority Issues

- **[P1] The route duplicates Library.** Same grid, same click-through, no analyze-specific value — two nav items for one behavior. **Fix:** make it analyze-centric (surface "recently analyzed" vs "not yet analyzed," show a per-card analysis count, deep-link straight into the detail's analyze panel), or drop it as a separate destination and make "Analyze" an action on a workout. **Command:** `/impeccable shape`.
- **[P1] Can't find a workout among 80.** No search / filter / sort on the picker (Library now has all three). **Fix:** share Library's control bar (extract it once) or fold analyze into Library. **Command:** `/impeccable layout` (after `shape`).
- **[P1] Drifted behind the improved Library.** Identical content, none of Library's grouping / hero / trend / skeleton / retry / keyboard / URL state. **Fix:** share one list surface with two entry points so they can't diverge. **Command:** `/impeccable polish` (design-system alignment).
- **[P2] Error state is a dead end here.** `ErrorState` is rendered without `onRetry` / `hint`, though the component now supports both. **Fix:** pass `onRetry={refetch}` + a diagnosis hint. **Command:** `/impeccable harden`.
- **[P2] No analyze signal on cards.** Nothing shows which workouts already have saved analyses or how many (data exists at `/activities/:id/analyses`). **Fix:** an "Analyzed ×N" badge and/or sort "un-analyzed first." **Command:** `/impeccable delight`.

## Persona Red Flags

**Alex (Power User):** 80 cards, no search/sort/keyboard on this page. Analyzing yesterday's ride means scrolling; no re-analyze shortcut, no bulk action. Slow and rigid.

**Sam (Accessibility):** Cards now have focus rings (good), but the page is one long unstructured list of 80 links — no headings/landmarks to jump between (Library groups with `h2`s; this doesn't). Tedious via screen reader/keyboard.

**Casey (Mobile):** Picking one workout out of 80 by scrolling on a phone, with no search at the top and the real analyze action another tap away.

**Morgan (endurance athlete, project persona):** Expects "Analyze" to help reason across workouts and see what's already been analyzed. Gets a bare picker; the training-memory corpus the product is built around is invisible here.

## Minor Observations

- Uses the `LoadingState` spinner, not the skeleton the Library now uses — inconsistent loading vocabulary.
- The subtitle promises "streaming analysis," but that action is two navigations away with no preview.
- Cards carry a Garmin `source_ref.url` that's never surfaced (possible quick win elsewhere).

## Questions to Consider

- Should "Analyze" be a place, or an action on a workout?
- What would make this page worth visiting *instead of* Library?
- How should the user find the one workout to analyze among 80 — and see what they've already analyzed?
