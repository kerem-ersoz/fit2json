---
target: library
total_score: 28
p0_count: 0
p1_count: 3
timestamp: 2026-07-27T14-44-12Z
slug: frontend-src-pages-librarypage-tsx
---
# Critique — Library (`frontend/src/pages/LibraryPage.tsx`)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Loading/error/empty all present; but header count shows total, not filtered, and loading is a center spinner (no skeleton) |
| 2 | Match System / Real World | 4 | Speaks the athlete's language fluently (Run/Ride/Swim, Pace, Avg HR, metric/imperial) |
| 3 | User Control and Freedom | 2 | No clear-filters affordance, no sort, filter/search state not in URL |
| 4 | Consistency and Standards | 4 | Cohesive component vocabulary, palette, focus rings, radii |
| 5 | Error Prevention | 3 | Constrained filters; little destructive risk on a read-only list |
| 6 | Recognition Rather Than Recall | 3 | Labeled nav, visible filter/search; searchable fields not obvious |
| 7 | Flexibility and Efficiency | 2 | No keyboard shortcuts, no sort, no bulk/multi-select, no URL state |
| 8 | Aesthetic and Minimalist Design | 3 | Clean and uncluttered, but undifferentiated — no focal point / "lit dial" |
| 9 | Error Recovery | 2 | Error state prints the message but offers no retry and no diagnosis |
| 10 | Help and Documentation | 2 | Great teaching empty state; otherwise no contextual help |
| **Total** | | **28/40** | **Good (bottom of band) — solid foundation, clear weak areas** |

## Anti-Patterns Verdict

**Does this look AI-generated? No.** It reads as a competent, restrained product UI in the Linear/Things tradition — exactly the "Quiet Instrument" the design docs call for.

**LLM assessment:** No slop tells. No gradient text, no hero-metric template, no tracked-uppercase eyebrows, no glassmorphism, no side-stripe borders. Component vocabulary is consistent and on-brand. The one watch-item is the *identical card grid*: every ActivityCard is the same weight with no focal point, and the page carries none of the "moments of delight / expressive data" the brand reserves for charts and insights. It's clean, but flat.

**Deterministic scan:** `detect.mjs` over 7 Library-surface files (LibraryPage, ActivityCard, AppShell, Feedback, Card, Button, Badge) returned **0 findings (exit 0, clean)**. Note: the static scan reads JSX/Tailwind markup and cannot resolve utility classes to computed contrast, so it did **not** catch the `slate-400` label contrast issue — that's an LLM-only find below.

**Visual overlays:** Not performed. No browser automation was available for this run (`frontend/node_modules` is not installed and no injectable browser/console is wired up), so there is **no** user-visible overlay. Evidence here is source review + the deterministic CLI scan only. To inspect live, run `cd frontend && npm install && npm run dev`, then `/impeccable live`.

## Overall Impression

A clean, trustworthy, mobile-first list that gets the fundamentals right and stays on-brand. It's competent but *quiet to a fault*: it treats a 3-year archive exactly like today, gives the eye no focal point, and offers a data-literate athlete almost no efficiency or control (no sort, no shortcuts, no shareable filter state). The single biggest opportunity: make the Library *structured and scannable over time* — surface the latest effort, sort by recency, and give power users real controls — so it delivers on PRODUCT.md's "understand one workout AND long-term progress" promise.

## What's Working

1. **A teaching empty state.** When there are no workouts it names the exact next action *and* the `--library` flag — textbook product empty state, not a dead "Nothing here."
2. **Earned, on-brand restraint.** Consistent Button/Card/Badge vocabulary, recognizable sport iconography, a persistent metric/imperial toggle (localStorage), and one disciplined green accent. The tool disappears into the task.
3. **Mobile-first done properly.** 1→2 column grid, sticky top bar + bottom tab nav, ≥44px targets, and safe-area insets. This genuinely works one-handed.

## Priority Issues

- **[P1] No sort or recency structure in a "library."** Cards render in raw API order with no user sort (date / distance / duration) and no date grouping. As workouts accumulate, "find my last long run" becomes a scroll hunt. **Fix:** default newest-first, add a sort control, group by month or add a "This week" band. **Command:** `/impeccable layout`.
- **[P1] Thin power-user efficiency.** No keyboard shortcuts (`/` to focus search, arrow/`j`/`k` between cards, `Enter` to open), no multi-select, and filter/search state isn't in the URL (can't bookmark or share "all runs"). The target user is a data-literate athlete with a large archive. **Command:** `/impeccable shape` (interaction model), then build.
- **[P1] The error state is a dead end.** `ErrorState` prints the API message but offers no "Try again" (React Query can `refetch`) and no diagnosis (server down vs. empty `--library`). **Command:** `/impeccable harden`.
- **[P2] Contrast + unlabeled controls (a11y).** Metric labels use `slate-400` (~2.6:1 on white — fails AA); the search input and sport `<select>` have no programmatic `<label>` (placeholder / "All sports" only). **Fix:** move labels to `slate-500`+, add visually-hidden labels. **Command:** `/impeccable audit`.
- **[P2] All chrome, no "lit dial."** The brand reserves delight for expressive data, but the landing page has none — no latest-activity highlight, no weekly-volume sparkline, uniform cards with no focal point. **Command:** `/impeccable delight` (or `/impeccable bolder`).

## Persona Red Flags

**Alex (Impatient Power User):** No keyboard shortcuts anywhere — can't `/`-focus search or arrow between cards. No sort, no bulk actions, no URL-encoded filters to bookmark. With hundreds of workouts this feels hand-held and slow. High "I'll just grep the JSON myself" risk.

**Sam (Accessibility-Dependent):** Search field is icon-only with no `<label>`; the sport `<select>` has no visible/programmatic label — a screen reader announces an unlabeled combobox. Metric labels fail 4.5:1 contrast. Each card is a full `<Link>` with no explicit `focus-visible` ring (relies on UA default), so keyboard focus is easy to lose in a 2-column grid.

**Casey (Distracted Mobile User):** Strong on targets/thumb-nav, but the search + filter live at the *top* of the screen (out of the thumb zone) and require typing, and their state is lost on navigation — returning after an interruption resets the view. Units do persist (good).

**Morgan (Data-literate endurance athlete — project persona):** Wants to see the latest effort and sense trends at a glance. The Library shows neither — no recency grouping, no PR/highlight, no trend. PRODUCT.md's "reason about progress over time" doesn't appear on the surface the athlete lands on first.

## Minor Observations

- Header count shows **total** (`data.length`), not the **filtered** count — filter to 3 of 50 and it still says "50 workouts."
- Sport filter is a native unstyled `<select>` sitting beside a custom-styled search input — slightly mixed control vocabulary.
- Loading is a centered spinner; the product register prefers **skeletons** for content areas.
- Card hover lifts (`hover:shadow-md`) but there's no matching keyboard focus treatment on the card link.

## Questions to Consider

- What if the *latest* workout were a hero, not just card #1?
- Does a 3-year archive deserve the same flat grid as today's single run?
- What would a keyboard-first Library feel like for someone with 500 workouts?
