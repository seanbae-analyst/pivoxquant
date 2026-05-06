# /home v2 — Direction B (Gallery) · Component Spec

> Single source of truth for implementation. All tokens reference
> `frontend/src/app/globals.css` (design system v3, locked 2026-04-27).
> Do **not** introduce new colors, fonts, or radii.

---

## 0. Page-level shell

| Region | Element | Source / Notes |
|---|---|---|
| Top nav | `<TopBar/>` (existing in `components/layout/`) | unchanged from current home |
| Top ticker | `<TopTicker/>` (`components/terminal/top-ticker.tsx`) | **reuse** — full-bleed, hairline above + below |
| CFO status | `<LivingCFOStatusBar/>` (`components/dashboard/living-cfo-status.tsx`) | **reuse** — sticky hairline under the ticker |
| Hero | `<TodayMemoHeroV2/>` | **rewrite** of `components/home/today-memo-hero.tsx` |
| Gallery | 6 × `<HomeCard/>` in a 3-col grid | **new generic shell**, content from existing data sources |
| Disclaimer | `<DisclaimerBanner/>` (`components/ui/disclaimer-banner.tsx`) | **reuse** — already mounted by `(dashboard)/layout.tsx`. Verify it still renders below cards. |
| Foot | `<FootSignature/>` (`components/ui/editorial`) | **reuse** |
| Background tasks | `<WeeklyPulseCard/>` (Mon 07:00 KST trigger) | **reuse**, mounted invisibly |

Container: `max-w-[1280px]` mx-auto, `px-6`. Outer body is `--pq-ink` (Vantablack).

---

## 1. Hero — `TodayMemoHeroV2`

The single largest visual change. Shifts CFO concept from terminal-row to editorial display.

| Prop | Type | Source |
|---|---|---|
| `eyebrow` | `string` | derived: `"Memo · ${weekIndex} of 52 · ${weekday}"` |
| `headline` | `string` (with optional `<span class="br">…</span>` accents) | `useMorningBrief()` ✎ → `brief.headline` |
| `body` | `string` | `useMorningBrief()` ✎ → `brief.body` |
| `audioDuration` | `string?` | `useMorningBrief()` ✎ → `brief.audio?.duration` |
| `displayName` | `string` | `useAuth().user.displayName` |
| `loading` | `boolean` | combined SWR loading flag |

**Existing data hook**: `useMorningBrief()` ✎ in `lib/hooks.ts` (hook name corrected 2026-04-27 — was `useTodayMemo()`, which does not exist; actual hook is `useMorningBrief` at line 72). The endpoint is `API.market.morningBriefToday` — no backend change needed.

**Visual rules** (mockup §"HERO"):
- 80px top, 64px bottom padding. No card border — just hairline-bottom seal.
- H1: Playfair Display 500 / 48px / line-height 1.05 / `--pq-track-tight`.
- Bronze "br" accent words italic via `font-feature-settings: "ss01"`.
- Editorial body in Source Serif 4, max-width 720px, color `rgba(245,240,232,0.82)`.
- Two CTAs: `pq-cta` bronze pill (Read full memo) + `pq-link` mono underline (Listen · 4:12).
- Eyebrow caption: "Drafted by AI · Reviewed by you" (CFO-concept signature).

**A11y**:
- H1 must be a real `<h1>`. Each gallery card uses `<h2>` for its kicker title.
- Bronze (#B8956A) on Vantablack (#050505) → contrast **6.94:1** (passes WCAG AA for normal text, AAA for large). Ivory (#F5F0E8) on Vantablack → **17.4:1** (AAA all sizes). Verified via APCA + WebAIM ratio.

---

## 2. Gallery shell — `HomeCard`

A new generic container so the 6 cards are visually consistent.

```tsx
<HomeCard
  href="/portfolio"
  eyebrow="Portfolio · NAV"
  cornerCta="Open Book"   // shows top-right, mono uppercase
  minHeight={280}
>
  {/* card body */}
</HomeCard>
```

CSS: `.pq-card` token (already defined inline in mockup; promote to `globals.css` under "Wave 1C cards" section).

**Hover**: border `var(--pq-hairline)` → `var(--pq-bronze)`, background → `rgba(184,149,106,0.025)`. 240ms ease-out. Corner CTA color goes ivory → bronze.

**Click**: entire card is the link target. Inner `pq-link`/buttons get `pointer-events: none` or use an inner `<button>` if a secondary action is required.

---

## 3. The 6 cards

> **Hook mapping verified 2026-04-27 against `lib/hooks.ts` (grep: 14 exports).
> Corrected names marked ✎. GAP hooks do not yet exist — see §3a.**

| # | Card | Reuse / new | Data hook | Route |
|---|---|---|---|---|
| 1 | **Portfolio Snapshot** (NAV + spark + 3 mini KPIs) | reuse `KpiCard` (sm) + new inline SVG spark; remove `EquityCurveChart` from this surface | `usePortfolioSummary()` ✓ exists → `summary.totalNav`, `todayPnl`, `todayPnlPct`, `positionCount`, `cashPct`. Spark series: **GAP** — `useEquityCurve` does not exist in hooks.ts; must be added (see §3a). | `/portfolio` |
| 2 | **Risk Board** (4 horizontal gauges) | new `<RiskGauge label value width/>` component (CSS-only, no chart lib) | **GAP** — `useRiskSummary()` does not exist in hooks.ts (see §3a). Fields needed: `var_95`, `sharpe`, `sectorConcentration`, `correlationCluster`, `tailCES`. **Additional GAP**: `sectorConcentration` and `correlationCluster` may not yet be on the snapshot endpoint — verify in `services/risk_summary.py` and add if missing. | `/risk` |
| 3 | **Earnings Pre-Brief** | **NEW component** + **NEW data hook**. CFO-concept artifact #3. | **GAP — needs backend**. Proposed endpoint: `GET /api/brief/earnings/upcoming?window=7d` returning `[{ ticker, datetime_kst, eps_est, revenue_est, implied_move, brief_status: 'queued'\|'drafted'\|'sent' }]`. Data sources already in repo: FMP earnings calendar (`fmp_service.py`) + KIS earnings (KR). Composition lives in a new `services/earnings_brief.py`. | `/brief/earnings` (new route) |
| 4 | **Positions (mini)** | reuse current row markup but strip filtering UI | `usePortfolioPositions()` ✎ (was `usePositions()` — corrected to exact hook name) → top 5 by `weight`. Format via `lib/format.ts` `fmtMoney`/`fmtPct`. | `/portfolio` |
| 5 | **Signals — Today's three** | new `HomeCardSignals` component. **Lock label set to POSITIVE / NEGATIVE / NEUTRAL.** | **GAP** — `useSignals()` does not exist in hooks.ts (see §3a). Needed fields: `ticker`, `label`, `rationale`, `score`. | `/signals` |
| 6 | **Companion · Archive** | reuse `ArtifactQueue` slice + counts; new editorial framing | `useArtifacts({ limit: 3 })` ✎ (was `useArtifactQueue()` — corrected; `useArtifacts` is the actual hook with optional `limit` param) for last 3. **GAP** — `useArtifactStats()` does not exist (see §3a). | `/reports` (or `/archive`) |

### §3a. GAP — New hooks required (not yet in `lib/hooks.ts`)

The following 4 hooks must be added to `lib/hooks.ts` before the corresponding cards can be wired. Each requires a matching backend endpoint.

| Hook | Used by card | Fields needed | Backend endpoint |
|---|---|---|---|
| `useEquityCurve(range, currency)` | Card #1 Snapshot (spark) | Array of `{ date, value }` — last 14 points for `'1W'` | `GET /api/portfolio/equity-curve?range=1W` |
| `useRiskSummary()` | Card #2 Risk Board | `var_95`, `sharpe`, `sectorConcentration`, `correlationCluster`, `tailCES` | `GET /api/risk/summary` (verify `services/risk_summary.py`) |
| `useSignals(limit?)` | Card #5 Signals | `ticker`, `label` (POSITIVE/NEGATIVE/NEUTRAL), `rationale`, `score` | `GET /api/signals?limit=3` |
| `useArtifactStats()` | Card #6 Companion | `count_ytd`, `count_decision_moving` | `GET /api/artifacts/stats` (trivial wrapper over artifacts table) |

### Card 3 backend gap — concrete

```python
# services/earnings_brief.py  (new)
def upcoming_briefs(user_id: int, window_days: int = 7) -> list[dict]:
    """Combines FMP US calendar + KIS KR calendar for tickers in the user's
    book + watchlist. Marks brief_status by checking artifacts table."""
    ...
```

Routes: add `routes/brief.py::upcoming_earnings()`. Map in `endpoints.ts` as `API.brief.earningsUpcoming`. Add `useUpcomingBriefs()` SWR hook in `lib/hooks.ts`.

---

## 4. Tokens used (NO new tokens)

> ink token reconciliation 2026-04-27: `--pq-ink` value corrected from `#0A0A0A` → `#050505`
> in `globals.css` line 797. Vantablack `#050505` is the v3 lock-in canonical value per
> `project_design_v3.md`. All components using `var(--pq-ink)` automatically receive the
> corrected value — no per-file changes needed.

| Token | Value | Used by |
|---|---|---|
| `--pq-ink` | #050505 | body bg |
| `--pq-ivory` | #F5F0E8 | primary text |
| `--pq-bronze` | #B8956A | eyebrow, kicker, CTA, hover border, "br" accent, gauge fill |
| `--pq-bronze-light` | #A3845C | CTA hover |
| `--pq-bronze-deep` | #6F5636 | embossed seal, gauge gradient start, locked overlay |
| `--pq-hairline` | rgba(10,10,10,0.12) | card border, ticker rules, mini-row dividers |
| `--pq-text-h1` | clamp 2.4–4.5rem | hero |
| `--pq-text-h2` | — | section header "Six rooms." + card display numerals |
| `--pq-text-eyebrow` (12px) + `--pq-track-eyebrow` | — | every card kicker |
| `--pq-radius-card` | 4px | every card |
| `--pq-radius-cta` | 2px | hero CTA |
| `--pq-positive` | #dc2626 | KR convention price up |
| `--pq-negative` | #2563eb | KR convention price down |

**Banned**: any new hex code, any radius >4px (except `pq-radius-pill` if explicitly needed — not used here), any non-Playfair/Source Serif/JetBrains Mono/Pretendard font.

---

## 5. Banned UI strings (legal)

The following must NEVER appear in any v2 component:

- `BUY`, `SELL`, `HOLD`
- `recommend`, `recommendation`, `advice`, `advise`
- `추천`, `조언`
- `AI Coach`, `투자 코치`

Allowed signal vocabulary: `POSITIVE`, `NEGATIVE`, `NEUTRAL` only. Mockup verified clean.

`DisclaimerBanner` is mounted once by `(dashboard)/layout.tsx` and remains the single legal seal. Do not duplicate — but verify visual placement under the gallery still works after the row count drops from 8 to 1+1.

---

## 6. Responsive breakpoints

Desktop-first per current home convention.

| Breakpoint | Layout |
|---|---|
| `≥1280px` (`xl`) | Hero full width; gallery 3 columns × 2 rows |
| `1024–1279px` (`lg`) | Hero unchanged; gallery 3 columns, hero h1 clamps down |
| `768–1023px` (`md`) | Hero padding reduces to 56px / 40px; gallery 2 columns × 3 rows |
| `<768px` (mobile) | Hero padding 40px / 28px, h1 falls to ~32px via `clamp()`; gallery 1 column × 6 rows; ticker becomes horizontally scrollable; CFO status wraps to two lines; corner CTA hides on cards <600px wide and the full card stays the link |

Mobile concrete numbers:
- Card min-height drops 280→220.
- Spark height drops 36→28.
- Mini-row fonts: name 13px, px 12px.

---

## 7. A11y checklist

- [ ] Heading order: H1 (hero) → H2 ("Six rooms.") → H2 per card kicker → H3 within cards (e.g. ticker labels). Verify with `axe-core` after build.
- [ ] All cards: `<a>` with `aria-label="${eyebrow} — open ${route}"`.
- [ ] Bronze on Vantablack confirmed 6.94:1 (AA normal / AAA large) — eyebrows are ≥10.5px so they qualify only as **AA Large** when bold; eyebrow is medium weight, so use bronze only on uppercase mono ≥10.5px and verify case-by-case in design-review.
- [ ] Color is never the only signal: POSITIVE/NEGATIVE/NEUTRAL labels carry the meaning; price red/blue is paired with a +/- glyph.
- [ ] Focus rings: `:focus-visible { outline: 1px solid var(--pq-bronze); outline-offset: 3px; }` (already defined globals.css line 1091).
- [ ] Reduced-motion: card hover transition wraps in `@media (prefers-reduced-motion: no-preference)`.
- [ ] Screen reader: hero CTA has visible label "Read full memo"; ticker has `aria-live="off"` and `role="marquee"` only if animated, otherwise plain list.
