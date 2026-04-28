# /portfolio v2 — Migration Plan

> Companion to `mockup.html` and `SPEC.md`. This document covers the
> file diff: what's new, what's touched, what's preserved, and how the
> rollout is gated so v1 routes never break.

---

## 1. Page status before this work

| Path | State |
|---|---|
| `/portfolio` | **404 page-not-found** (CRITICAL CEO-flagged bug, qa_bug_log.md item #1) |
| Add Position modal | Does not exist. No way to record holdings. |
| Buy / Trim / Close modals | Do not exist. |
| Reconcile-from-broker affordance | Does not exist (despite `useBrokerConnections()` hook + KIS/Alpaca sync endpoints being live). |

Effectively: the page that the entire product depends on is missing. Every other surface (home cards, risk, signals) cites positions that the user has no way to enter.

---

## 2. New files (frontend)

```
frontend/src/app/(dashboard)/portfolio/
  page.tsx                     # NEW — server component, gated by NEXT_PUBLIC_PORTFOLIO_V2
  layout.tsx                   # NEW — page-local metadata, mounts AddPositionModalV2 portal
  loading.tsx                  # NEW — skeleton matching v2 hero + table heights
  error.tsx                    # NEW — editorial-tone error card

frontend/src/components/portfolio-v2/
  PortfolioHeroV2.tsx          # NEW — hero block (§1 of SPEC)
  EquityCurveBlock.tsx         # NEW — equity curve + timeframe toggle (§2)
  TimeframeToggle.tsx          # NEW — reusable mono pill toggle, will graft into Risk timeline too
  PositionsTableV2.tsx         # NEW — full-width Bloomberg-grade ledger (§3)
  PositionRowV2.tsx            # NEW — sub-component, encapsulates 종목명 main pattern
  SectorDonutCard.tsx          # NEW — 160×160 SVG donut + legend (§4.1)
  WatchlistMiniCard.tsx        # NEW — wraps useWatchlist with v2 styling (§4.2)
  TransactionsMiniCard.tsx     # NEW — needs useTransactions() — see §3
  AddPositionModalV2.tsx       # NEW — CRITICAL bug fix (§5 of SPEC)
  AddPositionForm.tsx          # NEW — sub-component, handles validation
  WeightBar.tsx                # NEW — bronze gradient gauge inline-bar
  SectorTag.tsx                # NEW — bronze-bordered eyebrow chip

frontend/src/lib/portfolio-v2/
  hooks.ts                     # NEW — useEquityCurve(range), useTransactions(limit?)
  types.ts                     # NEW — Transaction, AddPositionPayload, EquityPoint
```

---

## 3. Modified existing files

| File | Change | Reason |
|---|---|---|
| `frontend/src/lib/hooks.ts` | **No edits.** New hooks live in `lib/portfolio-v2/hooks.ts`. | Avoid touching the shared dedupe / refresh logic of `usePortfolioSummary` + `usePortfolioPositions` — those are documented to have a 10s dedupe window and we must not destabilize home, risk, etc. |
| `frontend/src/lib/endpoints.ts` | **Add only**, no removals: `API.portfolio.history` already exists; `PORTFOLIO_TRADES` already exists. No changes needed. | `endpoints.ts` is 1:1 with backend routes; everything required is already mapped. |
| `frontend/src/lib/types.ts` | **Extend** `PortfolioSummary` with optional `positionCount?: number`, `cashPct?: number`, `cashKrw?: number`. No removals. | Hero deck needs these. Backend `services/portfolio_summary.py` must add them — small backend task, additive only. |
| `frontend/src/app/(dashboard)/layout.tsx` | **No edits.** `DisclaimerBanner` already mounted there. Verify it still renders below the new long-scroll content (it should, since it's positioned by the layout, not the page). | Don't break v1. |
| `frontend/src/components/layout/sidebar.tsx` | **Verify** "Book" / "Portfolio" link points to `/portfolio` — already does. No edit. | |

---

## 4. Backend touch points

The backend changes are **additive only**. No existing endpoint changes shape.

| File | Change |
|---|---|
| `services/portfolio_summary.py` | **Add** `position_count` and `cash_pct` to the JSON response. Existing fields untouched. |
| `routes/portfolio.py::get_history` | **Verify** the response shape matches `EquityPoint[] = { t: ISO, nav: number, benchmark: number }`. If the current shape lacks `benchmark`, add it (KOSPI200 series joined by date) — this is a small additive change. |
| `routes/portfolio.py::list_trades` | **Verify** the response includes the action vocabulary (`add`/`trim`/`close`/`deposit`/`withdraw`). If it currently uses `buy`/`sell`, **map** to the legal-safe set on serialization — do not rename DB columns to keep migration scope zero. |
| `routes/portfolio.py::add_position` (POST) | No change. Modal POSTs the existing payload shape. |

If `services/portfolio_summary.py` cannot be edited in this wave (frozen surface), the hero shows ` — ` placeholders for `positionCount` / `cashPct` and the page still ships. No blocking dependency.

---

## 5. Feature-flag rollout

Mirror the home-v2 pattern (`NEXT_PUBLIC_HOME_V2`):

```ts
// frontend/src/app/(dashboard)/portfolio/page.tsx
import { redirect } from 'next/navigation';

export default function PortfolioPage() {
  if (process.env.NEXT_PUBLIC_PORTFOLIO_V2 !== 'true') {
    // v1 currently returns 404 — keep that behaviour rather than render a half-built page.
    // Render a holding-state component instead so users at least see something while the flag flips.
    return <PortfolioHoldingState />;
  }
  return <PortfolioV2 />;
}
```

**Vercel envs**:
- `production` — `NEXT_PUBLIC_PORTFOLIO_V2=false` initially. Flip to `true` after CEO sign-off.
- `preview` — `NEXT_PUBLIC_PORTFOLIO_V2=true` so PR preview deploys show the new surface.
- `development` — `true` by default in `.env.local`.

**Rollback**: flip the prod env back to `false`. No data migration to undo because backend changes are additive optional fields.

---

## 6. v1 routes preserved

No existing route changes. The full list of routes the user can currently hit is unchanged:

- `/home` (v2 home — unaffected)
- `/portfolio` — was 404; under flag, becomes the new page; without flag, stays 404 (or the holding-state component above, which is friendlier than a 404)
- `/detail/[ticker]` — unchanged; positions table rows link here
- `/watchlist` — unchanged; watchlist mini card "Open Watchlist ›" links here
- `/risk` — unchanged in this wave (covered by Wave 2 sibling spec `risk-v2/`)
- `/signals` — unchanged
- `/reports` — unchanged

API endpoint URLs unchanged (`endpoints.ts` is the immutable contract).

---

## 7. Component reuse from home-v2

When home-v2 lands first (it should — CEO-approved), the following components become shared:

| Shared component | First defined in | Reused by portfolio-v2 |
|---|---|---|
| `<TopBar/>` | `components/layout/` | yes |
| `<TopTicker/>` | `components/terminal/top-ticker.tsx` | yes |
| `<LivingCFOStatusBar/>` | `components/dashboard/living-cfo-status.tsx` | yes |
| `<DisclaimerBanner/>` | `components/ui/disclaimer-banner.tsx` | yes (already mounted via dashboard layout) |
| `<FootSignature/>` | `components/ui/editorial/` | yes |
| `pq-card`, `pq-cta`, `pq-link`, `eyebrow`, `display-h1`, `editorial-body`, `.br` | `globals.css` (after home-v2 promotion) | yes — do NOT redefine inline |
| `mini-row` | `globals.css` (after home-v2 promotion) | yes |

**Gating**: portfolio-v2 cannot ship before the home-v2 CSS tokens are promoted from inline `<style>` to `globals.css`. This is a hard dependency. If home-v2 hasn't promoted yet, portfolio-v2 PR includes the same promotion as a prerequisite commit — not an inline duplicate.

---

## 8. Component touch list (regressions to watch)

| Component | Why it's at risk |
|---|---|
| `<KpiCard/>` (existing) | Not used in v2 layout — but if it shares a CSS class with the new hero KPIs, verify no ambient styling leaks. |
| `<PositionsList/>` (existing v1, in `components/dashboard/`) | If still imported anywhere (verify with `grep -rn "from.*positions-list"` before merge), keep working. v2 introduces `<PositionsTableV2/>` as a separate component, no rename. |
| `<EquityCurveChart/>` (existing) | Not reused — v2 uses inline SVG. Leave intact for any v1 callers. |
| `useFocusTrap` (existing) | Reused by Add Position modal. No change. |
| `RealtimeProvider` SSE | Not changed. v2 positions table subscribes via `useRealtimeContext()`. Verify the realtime updates correctly merge into the v2 row. |

---

## 9. Tests

| Test type | What |
|---|---|
| Unit | `PositionRowV2` formats KR currency vs USD correctly via `lib/format.ts`. P/L sign forced. Sector tag renders. |
| Unit | `AddPositionForm` validates required fields, rejects negative shares, requires currency, parses date. |
| Integration | `/portfolio` (with flag on) renders all 4 blocks and reaches an idle SWR state with mocked endpoints. |
| Integration | Add Position submit POSTs to `/api/portfolio/position` and refetches `usePortfolioPositions`. |
| E2E (browse skill) | Click "Add position" → fill modal → save → row appears in table. Screenshot before/after. |
| Visual | Diff vs `mockup.html` desktop screenshot at 1280px. Tolerance ≤2% pixel diff. |
| Legal guard | Extend `tests/test_no_hardcoded_samples.py` to scan `app/(dashboard)/portfolio/**` for banned strings. |

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Backend `add_position` payload shape drifts from modal | Generate TS types from a single Pydantic-style schema, or add a smoke test that POSTs a fake payload pre-merge. |
| `usePortfolioPositions` returns shape varies between users (KR-only vs US-only vs mixed) | Defensive `?.` chaining + empty-state copy ("No positions observed yet."). Use `lib/format.ts` for currency dispatch. |
| Realtime SSE flickers on row hover | The row hover changes background only; price re-render does not change layout (mono tabular nums prevent shift). Verify under slow 3G in browse skill. |
| Modal traps focus but tab key escapes to main page | `useFocusTrap` + `inert` on the page main while modal is open. |
| Currency mismatch (record in USD, display KRW header) | Hero NAV uses the user's display currency from `useInvestmentProfile()` (EXISTS); table cells render in the position's native currency. Spread on equity curve is in display currency only. |

---

## 11. Definition of done

- [ ] CEO-approved screenshot match (1280px desktop) ≥ 98%.
- [ ] `pytest tests/test_no_hardcoded_samples.py -v` green.
- [ ] `axe-core` zero violations on `/portfolio` (under flag).
- [ ] Add Position end-to-end: open → submit → row visible. Verified in browse skill.
- [ ] `useEquityCurve` + `useTransactions` hooks added with SWR-style dedupe (60s).
- [ ] Feature flag rollout doc updated in `HANDOVER.md`.
- [ ] No banned UI strings (BUY/SELL/HOLD/recommend/advice/AI Coach/추천/조언) anywhere in portfolio-v2 source.
- [ ] `종목명 main` pattern verified by visual review on table, watchlist mini, transactions mini, hero text.
