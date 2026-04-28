# /portfolio v2 — "The Book" · Component Spec

> Single source of truth for implementation. Tokens reference
> `frontend/src/app/globals.css` (design system v3, locked 2026-04-27).
> No new colors, fonts, radii, or banned UI strings.
>
> **Hook accuracy note**: every hook listed below was confirmed by
> `grep -n "^export function use" frontend/src/lib/hooks.ts` on
> 2026-04-27. The home-v2 SPEC referenced 7 hooks that do not exist in
> `hooks.ts`. This document avoids that pattern: existing hooks are
> marked **EXISTS** and missing ones are listed in the GAP section.

---

## 0. Page-level shell

| Region | Element | Source / Notes |
|---|---|---|
| Top nav | `<TopBar/>` (`components/layout/`) | reuse |
| Top ticker | `<TopTicker/>` (`components/terminal/top-ticker.tsx`) | reuse — full-bleed, hairline above + below |
| CFO status | `<LivingCFOStatusBar/>` (`components/dashboard/living-cfo-status.tsx`) | reuse — sticky hairline under the ticker |
| Hero | `<PortfolioHeroV2/>` (NEW) | new editorial hero, mirrors home-v2 hero rhythm |
| Equity curve | `<EquityCurveBlock/>` (NEW) | wraps existing chart + new timeframe toggle |
| Positions table | `<PositionsTableV2/>` (NEW) | full-width Bloomberg-grade ledger |
| 3-col grid | `<SectorDonutCard/>` `<WatchlistMiniCard/>` `<TransactionsMiniCard/>` (each NEW) | inside `pq-card` shells |
| Add Position modal | `<AddPositionModalV2/>` (NEW) | dialog mounted at page root |
| Disclaimer | `<DisclaimerBanner/>` (`components/ui/disclaimer-banner.tsx`) | reuse — already mounted in `(dashboard)/layout.tsx` |
| Foot | `<FootSignature/>` (`components/ui/editorial`) | reuse |

Container: `max-w-[1280px]` mx-auto, `px-6`. Outer body is `--pq-ink` (Vantablack).

---

## 1. Hero — `PortfolioHeroV2`

| Prop | Type | Source |
|---|---|---|
| `eyebrow` | `string` | derived: `"Book · Volume ${weekIndex} · ${weekday}"` |
| `headline` | `string` (with `<span class="br">…</span>`) | static: `"Your <br>book.</br>"` |
| `body` | `string` (with bronze italic accents on `observed`/`reconciled`) | composed from `usePortfolioSummary()` |
| `positionCount` | `number` | `usePortfolioSummary()` → `summary.positionCount` (GAP — see §6) |
| `nav` | `number` | `usePortfolioSummary()` → `totalNav` (EXISTS) |
| `lastReconciledAt` | `string` (ISO) | `usePortfolioSummary()` → `observed_at` (EXISTS) |
| `cashPct` | `number` | (GAP — `usePortfolioSummary()` does not yet expose `cashPct`) |
| `onAddPosition` | `() => void` | opens `<AddPositionModalV2/>` |
| `onReconcile` | `() => void` | calls `/api/broker/{kis|alpaca}/sync` |

**Visual rules** (mockup §HERO):
- 80px top, 64px bottom padding. No card border — only `border-bottom: 1px solid var(--pq-hairline)`.
- H1 Playfair 500 / 48px / line-height 1.05 / `--pq-track-tight`.
- Bronze italic accents (`.br`) on the headline word "book." and inside the deck on "observed", "reconciled".
- Two CTAs side-by-side:
  - Primary `pq-cta` (bronze-filled) → "Add position →"
  - Secondary `pq-cta.outline` (bronze border, transparent) → "Reconcile from broker"

---

## 2. Equity curve block — `EquityCurveBlock`

| Prop | Type | Source |
|---|---|---|
| `range` | `'1mo' \| '3mo' \| '6mo' \| '1yr' \| 'all'` | local state, default `'6mo'` |
| `series` | `{ t: string; nav: number; benchmark: number }[]` | **GAP — needs `useEquityCurve(range)` hook (NOT EXISTING)** |
| `currentNav` | `number` | `usePortfolioSummary().totalNav` (EXISTS) |
| `rangeReturn` | `number` | derived from `series` |
| `benchmarkReturn` | `number` | derived from `series` (KOSPI200 default) |
| `loading` | `boolean` | combined SWR loading flag |

**Visual rules** (mockup §BLOCK 1):
- Section header with timeframe toggle on the right (mono uppercase pills).
- Inside `pq-card`: 3-up KPI strip (NAV / range return / benchmark) above SVG.
- SVG `viewBox="0 0 1200 280"`, two polylines:
  - Portfolio: `var(--pq-bronze)` solid 1.6px stroke + bronze fill gradient (`rgba(184,149,106,0.18)` → 0).
  - Benchmark: `rgba(245,240,232,0.32)` 1.2px **dashed** (`stroke-dasharray="3 4"`) + faint ivory fill.
- Hairline horizontal gridlines at y=56,112,168,224.
- Legend row at bottom with swatch + eyebrow labels + spread KPI.

**A11y**: chart wrapped in `<figure>` with `<figcaption class="sr-only">` describing the series and current spread.

---

## 3. Positions table — `PositionsTableV2`

| Prop | Type | Source |
|---|---|---|
| `positions` | `Position[]` | `usePortfolioPositions()` (EXISTS) |
| `sortKey` | `'name'\|'shares'\|'avgCost'\|'last'\|'plPct'\|'value'\|'weight'\|'sector'` | local state |
| `sortDir` | `'asc'\|'desc'` | local state |
| `onRowClick` | `(ticker: string) => void` | router push to `/detail/[ticker]` |
| `loading` | `boolean` | `swr.isLoading` |

**Columns** (left → right):

| # | Column | Width | Type | Notes |
|---|---|---|---|---|
| 1 | **Name** | flex | Playfair 500 / 18px ivory + ticker mono 10.5px dim below | **종목명 main pattern** — H3-class hierarchy, ticker is secondary. CEO directive 2026-04-26. |
| 2 | Shares | min-content | mono 13.5px tabular | right-aligned |
| 3 | Avg Cost | min-content | mono 13.5px ivory-quiet (muted) | right-aligned |
| 4 | Last | min-content | mono 13.5px ivory-soft | right-aligned |
| 5 | P/L % | min-content | mono 13.5px **KR positive/negative** color | `+` glyph forced for positive |
| 6 | Mkt Value | min-content | mono 13.5px ivory-soft | right-aligned |
| 7 | Weight | 96px | mono 13.5px + bronze gradient bar below | gauge-style mini bar |
| 8 | Sector | min-content | `.sector-tag` mono 10px uppercase, bronze border | eyebrow-style chip |

**Header row**: mono uppercase 10.5px ivory-mute, hover → bronze, click → sort. Tracking `0.22em`, padding `14px 12px`, hairline-bottom border.

**Body row hover**: `background: rgba(184,149,106,0.03)` (very subtle). Hairline-bottom only — no full border.

**Click target**: entire row navigates to `/detail/[ticker]` via `onRowClick`. The ticker mono small below the name does NOT need to be clickable separately — it's a secondary label, not a primary affordance.

**Empty state**: "No positions observed yet." in editorial-body, with a `pq-cta` to open Add Position modal.

---

## 4. 3-col grid — Sector / Watchlist / Transactions

Each card uses the `pq-card` shell (from home-v2). `min-height: 380px`. Corner CTA top-right (mono 9.5px ivory-mute, hover bronze).

### 4.1 `SectorDonutCard`

| Prop | Type | Source |
|---|---|---|
| `sectors` | `{ name: string; pct: number; color: string }[]` | derived from `usePortfolioPositions()` (EXISTS) |
| `count` | `number` | `sectors.length` |

- 160×160 SVG donut. 7 strokes drawn as `circle` segments rotated -90°.
- Color ramp: `--pq-bronze` → `--pq-bronze-light` → `--pq-bronze-deep` → 4 ivory tints (0.32 / 0.22 / 0.14 / 0.08).
- Center text: "SECTORS" eyebrow + count in Playfair 20px.
- Legend below: 12px swatch + serif label + mono pct, hairline-divided rows.

**Color is never the only signal**: legend always pairs swatch + text label.

### 4.2 `WatchlistMiniCard`

| Prop | Type | Source |
|---|---|---|
| `watchlist` | `WatchlistResponse['items']` | `useWatchlist()` (EXISTS) |
| `limit` | `number` | default `6` |

- `mini-row` markup from home-v2. **종목명 main pattern**: name in Playfair 15px ivory + ticker mono 10px dim small. Price right-aligned mono. Change % right-aligned with KR positive/negative.
- Footer: eyebrow dim "X more · N total" + `pq-link` "Open Watchlist ›" → `/watchlist`.

### 4.3 `TransactionsMiniCard`

| Prop | Type | Source |
|---|---|---|
| `transactions` | `Transaction[]` | **GAP — needs `useTransactions()` hook (NOT EXISTING)**. Backend already has `routes/portfolio.py` with `PORTFOLIO_TRADES = "/api/portfolio/trades"` (already in `endpoints.ts` line 240). |
| `limit` | `number` | default `7` |

- 2-col `mini-row` (`grid-template-columns: 1fr auto`) — name + meta line on the left, signed amount on the right.
- Meta line: `${action} · ${shares} sh @ ${price} · ${date}` in serif 12px ivory-quiet.
- Action vocabulary (legal-safe): **Add / Trim / Close / Deposit / Withdraw**. Never "Buy / Sell".
- Amount: forced sign (`+` / `−`) and KR positive/negative color.
- Footer: `pq-link` "Open Ledger ›" → `/portfolio/transactions` (route GAP — see §6).

---

## 5. Add Position modal — `AddPositionModalV2`

The modal is the **CRITICAL bug fix** half of this page (Add Position currently 404s).

| Prop | Type | Source |
|---|---|---|
| `open` | `boolean` | parent state |
| `onClose` | `() => void` | parent state |
| `onSubmit` | `(payload: AddPositionPayload) => Promise<void>` | calls `POST /api/portfolio/position` (EXISTS via `API.portfolio.addPosition`) |

**Payload shape** (mirrors backend `routes/portfolio.py::add_position`):
```ts
interface AddPositionPayload {
  symbol: string;        // ticker, normalized server-side (KR may include suffix)
  shares: number;
  avg_cost: number;
  acquired_at: string;   // ISO date
  currency: 'USD' | 'KRW';
  memo?: string;
}
```

**Visual rules** (mockup §BLOCK 4):
- Centered card max-width 560px, `padding: 40px 36px`, `background: rgba(184,149,106,0.025)`, hairline border.
- Hero block inside modal: eyebrow "Observation · New entry" + Playfair display-h2 32px "Record a *new position.*" + editorial-body deck.
- Form fields use `.form-field` with mono uppercase bronze label + transparent input with hairline-bottom (focus → bronze underline). No box borders.
- 2 form-rows of 2-col fields (Shares/Avg cost, Date/Currency) + single Symbol field on top + single Memo at bottom.
- Footer: `pq-cta` "Save observation →" + `pq-link` "Cancel" + eyebrow dim "Saved to your book · not sent to broker" (legal disclaimer inline).
- Legal language: **"observation"** / **"record"** — never "buy", "sell", "execute", "place".

**A11y**: dialog with `role="dialog"`, `aria-modal="true"`, `aria-labelledby` pointing at the H2. Focus trap on open (use `lib/useFocusTrap.ts`, EXISTS). Escape key closes.

---

## 6. Hook & endpoint mapping

### Hooks that EXIST (verified in `hooks.ts` 2026-04-27)

| Hook | Used by | Returns |
|---|---|---|
| `usePortfolioSummary()` | Hero, Equity block | `PortfolioSummary` (totalNav, todayPnl, todayPnlPct, unrealized, realizedYtd, fxRate, observed_at) |
| `usePortfolioPositions<T>()` | Positions table, Sector donut | generic `T` — caller provides shape |
| `useWatchlist()` | Watchlist card | `WatchlistResponse` |
| `useBrokerConnections()` | Hero "Reconcile" CTA enable/disable | `BrokerConnectionsResponse` |
| `useRealtimeContext()` | Positions table live prices | SSE prices |

### Hooks that DO NOT EXIST — must be added (GAP)

| Hook (proposed) | Endpoint (proposed) | Notes |
|---|---|---|
| `useEquityCurve(range)` | `GET /api/portfolio/history?period=${range}` (EXISTS in `endpoints.ts` line 18 as `API.portfolio.history(period)`) | Wrap with SWR. Backend already serves the data — only frontend hook missing. |
| `useTransactions(limit?)` | `GET /api/portfolio/trades` (EXISTS as `PORTFOLIO_TRADES` const, line 240 of `endpoints.ts`) | Wrap with SWR. Verify response shape with `routes/portfolio.py` before typing. |

### Field gaps on existing endpoints

`PortfolioSummary` interface (lines 179–187 of `hooks.ts`) does NOT currently expose `positionCount` or `cashPct`. The hero deck depends on both. **Resolution**: add these fields to `services/portfolio_summary.py` response, then extend the interface — no breaking change since fields are optional.

### Routes referenced

| Route | Exists? |
|---|---|
| `/portfolio` | NO — page itself is 404 (CRITICAL bug) |
| `/portfolio/transactions` | NO — proposed sub-route for full ledger |
| `/detail/[ticker]` | YES |
| `/watchlist` | YES |
| `/api/portfolio/position` (POST) | YES (`API.portfolio.addPosition`) |
| `/api/portfolio/history?period=` | YES (`API.portfolio.history(period)`) |
| `/api/portfolio/trades` | YES (`PORTFOLIO_TRADES`) |
| `/api/broker/kis/sync`, `/api/broker/alpaca/sync` | YES |

---

## 7. Tokens used (NO new tokens)

| Token | Used by |
|---|---|
| `--pq-ink` (#050505) | body bg, modal-card text |
| `--pq-ivory` (#F5F0E8) | primary text, table name |
| `--pq-ivory-soft` (rgba 0.82) | editorial body, table prices |
| `--pq-ivory-quiet` (rgba 0.55) | avg cost (muted), meta lines |
| `--pq-ivory-mute` (rgba 0.40) | corner CTA, table headers |
| `--pq-bronze` (#B8956A) | eyebrow, kicker, CTA, hover border, "br" accent, donut primary, weight bar tip, sector tag border |
| `--pq-bronze-light` (#A3845C) | CTA hover, donut secondary |
| `--pq-bronze-deep` (#6F5636) | donut tertiary, weight bar base of gradient |
| `--pq-hairline` | card border, ticker rules, mini-row dividers, table row dividers |
| `--pq-hairline-2` | dashed dividers, modal stage, form input underline |
| `--pq-positive` (#dc2626) | KR positive (P/L %, change %, deposits) |
| `--pq-negative` (#2563eb) | KR negative (P/L %, change %) |
| `--pq-text-h1` (48px) | hero |
| `--pq-text-h2` (40px) | display-h2, modal headline |
| `--pq-radius-card` (4px) | every card, modal-card |
| `--pq-radius-cta` (2px) | hero CTA, sector tag, tf-toggle |

**Banned**: any new hex code, any radius >4px, any non-Playfair/Source-Serif/JetBrains-Mono/Pretendard font.

---

## 8. Banned UI strings (legal — automated guard)

| Banned | Replacement |
|---|---|
| `BUY` / `SELL` / `HOLD` | (none — never label rows or actions this way) |
| `recommend` / `recommendation` | (none — surface is record-keeping) |
| `advice` / `advise` / `advisory` | `observation` / `record` |
| `추천` / `조언` / `투자 코치` | `관찰` / `기록` |
| `AI Coach` | (no equivalent — feature does not exist on this surface) |

Action vocabulary in transactions ledger: **Add / Trim / Close / Deposit / Withdraw**. Never "Buy / Sell / Place / Execute".

CI guard: `tests/test_no_hardcoded_samples.py` already enforces template files. Extend to cover `frontend/src/app/(dashboard)/portfolio/**` once shipped.

---

## 9. Responsive breakpoints

Desktop-first per current home convention.

| Breakpoint | Layout |
|---|---|
| `≥1280px` (`xl`) | Full layout as mocked. Equity curve full width. Positions table 8 columns visible. 3-col grid. |
| `1024–1279px` (`lg`) | Hero unchanged; positions table same 8 cols; 3-col grid stays 3 columns but each card narrows. |
| `768–1023px` (`md`) | Hero padding 56px / 40px. Positions table hides Sector column (8 → 7). 3-col grid → 2-col + 1-row at bottom. |
| `<768px` (mobile) | Hero h1 clamps to ~32px. Positions table collapses to vertical card list (one row per position, name + P/L primary, other fields stacked under). 3-col grid → 1 column × 3 rows. Add Position modal becomes full-screen sheet. |

Mobile concrete numbers:
- Equity curve height drops 280 → 180.
- Donut size drops 160 → 120.
- Mini-row name 13px / px 12px (per home-v2 convention).

---

## 10. A11y checklist

- [ ] H1 for hero, H2 for each section header, H3 for each card kicker. Verify with `axe-core`.
- [ ] Equity SVG inside `<figure>`; `<figcaption class="sr-only">` describes series.
- [ ] Positions table: `<th scope="col">` on every header. Sortable headers have `aria-sort="ascending|descending|none"`.
- [ ] Row click: row is wrapped in or contains a `<button>` (or use `tabindex="0"` + keyboard handler) — never naked `<tr onClick>`.
- [ ] Bronze (#B8956A) on Vantablack confirmed 6.94:1 (AA normal / AAA large).
- [ ] KR positive/negative paired with `+`/`−` glyph — never color alone.
- [ ] Focus rings: `:focus-visible { outline: 1px solid var(--pq-bronze); outline-offset: 3px; }`.
- [ ] Modal: focus trap, escape closes, restore focus to trigger.
- [ ] Reduced-motion: card hover transitions wrapped in `@media (prefers-reduced-motion: no-preference)`.

---

## 11. Feature flag

```ts
// next.config / env
process.env.NEXT_PUBLIC_PORTFOLIO_V2 === 'true'
```

While `false`, the existing `/portfolio` route (currently 404) keeps its current behaviour so we do not regress further. While `true`, the new layout in this spec is rendered.

Toggle is server-rendered to avoid hydration flash. See `MIGRATION.md` §4 for rollout plan.
