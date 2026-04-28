# /signals v2 — Stream · Component Spec

> Single source of truth for the `/signals` route rebuild. All tokens reference
> `frontend/src/app/globals.css` (design system v3, locked 2026-04-27). Sibling
> spec to `home-v2/SPEC.md` — same shell, same hover language, same legal boundaries.
> Do **not** introduce new colors, fonts, or radii.

---

## 0. Page-level shell

| Region | Element | Source / Notes |
|---|---|---|
| Top nav | `<TopBar/>` (existing in `components/layout/`) | unchanged; `Signals` nav item gets `.active` |
| Top ticker | `<TopTicker/>` (`components/terminal/top-ticker.tsx`) | **reuse** — full-bleed, hairline above + below |
| CFO status | `<LivingCFOStatusBar/>` (`components/dashboard/living-cfo-status.tsx`) | **reuse** — props extended (see §1.1 GAP) |
| Hero | `<SignalsHeroV2/>` | **NEW** — sibling of `TodayMemoHeroV2` from home-v2 |
| Filter bar | `<SignalsFilterBar/>` | **NEW** — sticky, 4-col grid |
| Top movers | `<SignalsMoversRail/>` | **NEW** — 5-card horizontal grid |
| Timeline | `<SignalsTimeline/>` with `<SignalRow/>` items, day-rule headings | **NEW** |
| Pagination | `<SignalsPager/>` (mono uppercase, page 1..N) | **NEW** |
| Disclaimer | `<DisclaimerBanner/>` (`components/ui/disclaimer-banner.tsx`) | **reuse** — already mounted by `(dashboard)/layout.tsx`; verify single instance |
| Foot | `<FootSignature/>` (`components/ui/editorial`) | **reuse**, eyebrow text "Signals · Stream" |

Container: `max-w-[1280px]` mx-auto, `px-6`. Body bg `--pq-ink` (Vantablack).

---

## 1. Hero — `SignalsHeroV2`

| Prop | Type | Source |
|---|---|---|
| `eyebrow` | `string` (always `"Signals · live"`) | static |
| `headline` | `string` w/ optional `<span class="br">…</span>` | derived client-side from filter state — see §1.2 |
| `body` | `string` | derived: counts of POSITIVE / NEGATIVE / NEUTRAL today |
| `counts` | `{ positive: number; negative: number; neutral: number; symbols: number }` | from `useSignals(filters)` aggregation |
| `loading` | `boolean` | combined SWR loading flag |

Visual rules (mockup §HERO):
- 80px top, 64px bottom padding. No card border — hairline-bottom seal only.
- H1 Playfair 500 / 48px / 1.05 line / `--pq-track-tight`.
- Bronze "br" italic: `observed`, `filtered`.
- Body: Source Serif 4, max-width 720px, color `rgba(245,240,232,0.82)`.
- Inline counts use `.num` (mono tabular) + `--pq-positive` / `--pq-negative` / `--pq-ivory-quiet`.
- CTAs: `pq-cta` "Jump to my book" + `pq-link` "Export today · CSV".

### 1.1 CFO status bar — extended segments

Existing `<LivingCFOStatusBar/>` segments suffice; copy override only:
- `seg 1`: `CFO ROOM · OPEN`
- `seg 2`: `Stream · LIVE`
- `seg 3`: `Last observation · ${humanizeAgo(latestSignalAt)}`
- `seg 4` (right-aligned): `Filtered to your book + watchlist · ${symbols} symbols`

If the component does not currently accept variant copy, this is a small **GAP** —
add a `variant: "home" | "signals" | "reports"` prop and switch text inside.

### 1.2 Headline construction

Static template, no AI:
```
The stream is <br>observed</br>,
not advised — <br>filtered</br> to what you own.
```
Always identical. Copy is locked editorial, not data-driven.

---

## 2. Filter bar — `SignalsFilterBar`

```tsx
<SignalsFilterBar
  value={filters}
  onChange={setFilters}
  counts={{ positive: 17, negative: 14, neutral: 11 }}
/>
```

Sticky (`position: sticky; top: 0; z-index: 10; background: var(--pq-ink)`).
4-column grid, `gap: 32px`.

| Col | Control | Notes |
|---|---|---|
| Label | 3 toggle chips (POS / NEG / NEU) | Bronze 1px border on `.active`. Counts append `· N`. |
| Strength | Range slider 0.00 → 1.00 | Two-handle. Bronze fill between thumbs. |
| Symbol | Autocomplete input | Pulls from `useWatchlist().items` + `usePortfolioPositions()` for hint set. |
| Time | 3 toggle chips (Today / 7d / 30d) | Single-select. Default `Today`. |

Tokens: `--pq-bronze-08` for active chip background, `--pq-hairline` for inactive border, `--pq-bronze` for active border. Chip text mono 10.5px uppercase `--pq-track-eyebrow`.

State shape:
```ts
interface SignalFilters {
  labels: Set<"POSITIVE" | "NEGATIVE" | "NEUTRAL">;
  strengthMin: number;   // 0..1
  strengthMax: number;   // 0..1
  symbol: string | null; // exact ticker or null
  window: "today" | "7d" | "30d";
}
```

---

## 3. Top movers — `SignalsMoversRail`

5 cards in a `grid-cols-5 gap-3.5` rail. On `<lg` it scrolls horizontally with snap.

Each card composition (top → bottom):
1. **Name main** — `name-main` Playfair 17px, weight 500, ivory. 종목명 main (CEO directive 2026-04-26).
2. **Ticker sub** — `ticker-sub` mono 10px `rgba(245,240,232,0.45)` letter-spacing 0.14em. Format: `AAPL · NASDAQ` or `005930.KS · KOSPI`.
3. **Label pill** — POSITIVE / NEGATIVE / NEUTRAL, KR convention colors (red / blue / ivory-mute).
4. **Strength bar** — 3px gauge, bronze gradient fill width = `strength * 100%`.
5. **Rationale** — Source Serif 4 12.5px, line-height 1.5, ivory-soft. Single sentence.
6. **Footer** — mono `+/-X.XX%` (KR color) + ivory-mute price.

Hover: border `--pq-hairline` → `--pq-bronze`.

Source: top 5 by `Math.abs(strength)` from `useSignals({ window: "today" })`.

---

## 4. Timeline — `SignalsTimeline` + `SignalRow`

Vertical list, grouped by day with a `day-rule` heading (`<h3>` Playfair 22px + meta + hairline).

`SignalRow` grid: `1fr 280px 120px` columns.

**Left column (1fr):**
- `name-main` Playfair 22px ivory — 종목명 main.
- `ticker-sub` mono 11px dim — `AAPL · NASDAQ`.
- `rationale` Source Serif 4 14px ivory-soft, 2-3 sentences max.

**Middle column (280px):**
- Label pill + strength text `strength 0.91`.
- Strength bar (3px bronze gradient).
- Price line: `$118.74 +2.81%` mono with KR color.

**Right column (120px):**
- Timestamp `09:42 KST` mono 11px ivory-mute.
- Subline `3h ago` letter-spacing 0.06em.

Whole row is `<a href="/detail/{ticker}?signal={id}">`. Hover: border bronze, bg `rgba(184,149,106,0.025)`.

A11y: `aria-label="${name} · ${label} · strength ${strength} · ${timestamp}"`.

### 4.1 Day rule

Renders before each day group:
```html
<div class="day-rule">
  <h3>Friday</h3>
  <span class="meta">27 Apr · 21 observations</span>
  <span class="line"></span>
</div>
```

Localized weekday via `lib/locale.tsx` (existing).

---

## 5. Pagination — `SignalsPager`

Mono uppercase numerals. Active page: ivory text + bronze underline.
Page size: 20 signals per page (configurable). On infinite scroll mode, hide pager and replace with `<IntersectionObserver/>` sentinel — either is acceptable per the page spec.

---

## 6. Hooks — verified against `lib/hooks.ts` (2026-04-27 grep)

### Existing hooks reused
- `useWatchlist()` — for autocomplete hints.
- `usePortfolioPositions<Position[]>()` — for autocomplete hints + "your book" filter.

### NEW hooks required (GAP)

```ts
// frontend/src/lib/hooks.ts — append

import type { SignalFilters } from "./types"; // add type

export interface SignalEntry {
  id: number;
  ticker: string;          // "AAPL", "005930.KS"
  name: string;            // "Apple Inc.", "Samsung Electronics" — for 종목명 main
  exchange?: string | null;
  label: "POSITIVE" | "NEGATIVE" | "NEUTRAL";
  strength: number;        // 0..1
  rationale: string;       // single sentence; backend already returns this
  observed_at: string;     // ISO 8601 KST
  price?: number | null;
  change_pct?: number | null;
}

export interface SignalsResponse {
  signals: SignalEntry[];
  total: number;
  counts: { positive: number; negative: number; neutral: number };
  symbols_filtered: number;
}

export function useSignals(filters: Partial<SignalFilters> = {}) {
  const qs = new URLSearchParams();
  if (filters.labels?.size) qs.set("labels", Array.from(filters.labels).join(","));
  if (filters.strengthMin != null) qs.set("strength_min", String(filters.strengthMin));
  if (filters.strengthMax != null) qs.set("strength_max", String(filters.strengthMax));
  if (filters.symbol) qs.set("symbol", filters.symbol);
  if (filters.window) qs.set("window", filters.window);
  const qsStr = qs.toString();
  const key = qsStr.length ? `${API.signals.all}?${qsStr}` : API.signals.all;

  return useSWR<SignalsResponse>(key, fetcher, {
    refreshInterval: () => liveRefresh(5_000, 60_000),
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    dedupingInterval: 4_000,
    errorRetryCount: 2,
  });
}
```

**No backend change required if `/api/signals` already returns this shape.**
Verify in `routes/signals.py::all()` — endpoint exists at `API.signals.all = "/api/signals"`.
If the backend returns a different envelope (e.g. raw `BUY/SELL` strings from legacy
`engine.py`), a small **mapper** is required in `routes/signals.py` or in the hook:
- `BUY` / `STRONG_BUY` → `POSITIVE`
- `SELL` / `STRONG_SELL` → `NEGATIVE`
- `HOLD` / `NEUTRAL` / null → `NEUTRAL`

This mapping must happen before the response leaves the API layer so the wire
format itself never carries banned vocabulary (legal-guard CI rule).

### Mistakes to avoid (home-v2 SPEC errata)

- ❌ `useTodayMemo()` — does **not** exist. Real name: `useMorningBrief()`.
- ❌ `useArtifactQueue()` — does **not** exist. Real name: `useArtifacts({ limit: N })`.
- ❌ `useArtifactStats()` — does **not** exist. Either compute from `useArtifacts({ limit: 9999 })` or add as new GAP.
- ❌ `useEquityCurve(range, currency)` — does **not** exist. New hook required.
- ❌ `useRiskSummary()` — does **not** exist. Endpoint `RISK_SUMMARY` exists but no SWR wrapper. New hook required.
- ❌ `usePositions()` — real name: `usePortfolioPositions<T>()`.
- ❌ `useUpcomingBriefs()` — does **not** exist. Backend endpoint also missing.
- ❌ `useSignals()` — does **not** exist. **This page introduces it.**

---

## 7. Endpoints — verified against `lib/endpoints.ts` (2026-04-27 read)

| Use | Constant | Resolved URL |
|---|---|---|
| Stream list | `API.signals.all` | `/api/signals` |
| Per-ticker (detail-row click target) | `API.signals.one(ticker)` | `/api/signals/${ticker}` |
| Force refresh button (admin only) | `API.signals.refresh` | `/api/signals/refresh` |
| Watchlist (autocomplete + filter) | `API.watchlist.list` | `/api/watchlist` |
| Positions (autocomplete + filter) | `PORTFOLIO_POSITIONS` | `/api/portfolio/positions` |

Verified the constants exist at lines 27–39 (`signals` group), 98–103 (`watchlist`), 238 (`PORTFOLIO_POSITIONS`).

---

## 8. Tokens used (NO new tokens)

| Token | Used by |
|---|---|
| `--pq-ink` (#050505) | body, sticky filter bg |
| `--pq-ivory` (#F5F0E8) | name-main, active chip text, pager active |
| `--pq-ivory-soft` (rgba .82) | rationale body, ticker sub-line caption |
| `--pq-ivory-quiet` (rgba .55) | NEUTRAL count, secondary numerics |
| `--pq-ivory-mute` (rgba .40) | timestamps, day-rule meta, ticker-sub price |
| `--pq-bronze` (#B8956A) | eyebrow, "br" italic accent, active chip border, hover border, strength gradient end, pager active underline |
| `--pq-bronze-deep` (#6F5636) | strength gradient start |
| `--pq-bronze-08` | active chip bg |
| `--pq-bronze-15` | pq-link border-bottom |
| `--pq-hairline` (rgba .08) | inactive chip border, signal-row border, mover border, day-rule line |
| `--pq-hairline-2` (rgba .14) | NEUTRAL pill border, disclaimer dashed border |
| `--pq-positive` (#dc2626) | POSITIVE pill text/border, +N% mono |
| `--pq-negative` (#2563eb) | NEGATIVE pill text/border, -N% mono |
| `--pq-text-h1` (48px) | hero |
| `--pq-text-h2` (40px → 30px clamp) | "Loudest five." / "Today's observations." |
| `--pq-text-eyebrow` + `--pq-track-eyebrow` | every kicker |
| `--pq-radius-card` (4px) | every card / row |
| `--pq-radius-cta` (2px) | hero CTA, chip, label pill |

Banned: any new hex, any radius >4px, any non-Playfair/Source Serif/JetBrains Mono/Pretendard font.

---

## 9. Banned UI strings (legal — same as home-v2)

The following must NEVER appear in any v2 component or in API response bodies:

- `BUY`, `SELL`, `HOLD`
- `recommend`, `recommendation`, `advice`, `advise`, `advisory`
- `추천`, `조언`
- `AI Coach`, `투자 코치`

Allowed signal vocabulary: **`POSITIVE`, `NEGATIVE`, `NEUTRAL` only.**

`DisclaimerBanner` already mounts via `(dashboard)/layout.tsx`. Verify visual placement
under the timeline + pager still renders. Custom copy used here:

> "Signals are observations of model state, not actions. POSITIVE / NEGATIVE / NEUTRAL
> describe the system's read of price, volume, and structure — they are not buy, sell,
> or hold instructions, and PivoxQuant does not provide investment advice or solicitation."

---

## 10. Responsive breakpoints

Desktop-first per current home convention.

| Breakpoint | Layout |
|---|---|
| `≥1280px` (`xl`) | 4-col filter, 5-card mover grid, signal-row 1fr 280 120 |
| `1024–1279px` (`lg`) | 4-col filter, 4-card mover grid + horizontal scroll, row unchanged |
| `768–1023px` (`md`) | filter wraps to 2×2; mover grid 3 cards w/ snap-x scroll; row 1fr 220 100 |
| `<768px` (mobile) | filter collapses to bottom-sheet trigger; movers full-width snap carousel; row stacks vertically (name → label/strength → timestamp) |

Mobile concrete numbers:
- name-main 18px (was 22).
- rationale 13px (was 14).
- timestamp moves to top-right inline with name on row.

---

## 11. A11y checklist

- [ ] Heading order: H1 (hero) → H2 ("Loudest five.") → H2 ("Today's observations.") → H3 day rule (`Friday`).
- [ ] Filter chips are real `<button>` with `aria-pressed`.
- [ ] Range slider implements WAI-ARIA `slider` role with min/max/now and keyboard support.
- [ ] Each `SignalRow` is `<a>` with `aria-label="${name} · ${ticker} · ${label} · strength ${strength} · ${timestamp}"`.
- [ ] Color is never the only signal: label text (POSITIVE/NEGATIVE/NEUTRAL) carries the meaning; price red/blue is paired with `+`/`-` glyph.
- [ ] Strength bar has visible numeric value next to it (`strength 0.91`) — bar is decorative.
- [ ] Bronze on Vantablack confirmed 6.94:1 (AA normal / AAA large) per home-v2 verification.
- [ ] Focus rings: `:focus-visible { outline: 1px solid var(--pq-bronze); outline-offset: 3px; }` (already in globals.css line ~1091).
- [ ] Reduced-motion: row hover transition wrapped in `@media (prefers-reduced-motion: no-preference)`. Auto-refresh still updates content but without visual fade.
- [ ] Live region: stream container gets `aria-live="polite"` so SR announces new signal arrivals.
- [ ] Pause-on-hover: stream auto-refresh pauses while pointer is inside the timeline (also helps reduced-motion users).

---

## 12. GAP summary (action items for engineering)

Order of magnitude: low. None require backend schema changes; one needs a backend label-mapper.

1. **`useSignals(filters)` hook** — new in `lib/hooks.ts`. Wraps `API.signals.all` with SWR.
2. **`SignalEntry` / `SignalsResponse` types** — new in `lib/types.ts`.
3. **Backend label mapper** — verify `routes/signals.py::all()` returns `POSITIVE/NEGATIVE/NEUTRAL` strings, never legacy `BUY/SELL/HOLD`. If not, add mapper inside the route serializer (one-line dict map).
4. **`<LivingCFOStatusBar variant="signals">`** — copy variant. Trivial.
5. **`<SignalsFilterBar/>`, `<SignalsMoversRail/>`, `<SignalsTimeline/>`, `<SignalRow/>`, `<SignalsPager/>`** — net-new components, all CSS-only (no chart lib).
6. **CSV export endpoint** — `GET /api/signals/export?format=csv&window=today` for the hero CTA. Backend addition. Optional in V2.0; can ship without and grey-out the CTA.

Backend touchpoint (label mapper, exact location):
```python
# routes/signals.py — inside all()
LABEL_MAP = {
    "BUY": "POSITIVE", "STRONG_BUY": "POSITIVE",
    "SELL": "NEGATIVE", "STRONG_SELL": "NEGATIVE",
    "HOLD": "NEUTRAL", "NEUTRAL": "NEUTRAL", None: "NEUTRAL",
}
for s in signals:
    s["label"] = LABEL_MAP.get(s.get("recommendation") or s.get("label"), "NEUTRAL")
    s.pop("recommendation", None)  # strip banned vocab from wire format
```
