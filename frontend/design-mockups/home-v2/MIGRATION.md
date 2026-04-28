# /home v2 — Migration & Risk Plan

> Scope: replace the current 1,139-line dense terminal layout in
> `frontend/src/app/(dashboard)/home/page.tsx` with the gallery layout
> specified in `SPEC.md`. **No code changes have been made yet** —
> this document is the contract for the implementation PR.

---

## 1. What survives, what moves, what dies

### KEEP (untouched, 1:1 reuse)

| Component | File | Role in v2 |
|---|---|---|
| `TopTicker` | `components/terminal/top-ticker.tsx` | Same — full-bleed ticker strip, top of page |
| `LivingCFOStatusBar` | `components/dashboard/living-cfo-status.tsx` | Same — sticky hairline below ticker |
| `KpiCard` | `components/terminal/kpi-card.tsx` | Reused in Snapshot card (size="sm") |
| `ArtifactQueue` | `components/home/artifact-queue.tsx` | Reused inside Companion · Archive card |
| `WeeklyPulseCard` | `components/dashboard/weekly-pulse.tsx` | Same — invisible Mon 07:00 KST trigger |
| `UpsellPlus` | `components/dashboard/upsell-plus.tsx` | **Moved below disclaimer**, conditional on free tier |
| `FootSignature`, `Fleuron` | `components/ui/editorial` | Same — page footer |
| `DisclaimerBanner` | `components/ui/disclaimer-banner.tsx` | Same — already mounted by `(dashboard)/layout.tsx` |
| `ErrorBoundary` | `components/ui/error-boundary` | Wraps page root |
| **All data hooks** in `lib/hooks.ts` | — | Zero changes to SWR keys (per AGENTS.md rule) |

### REWRITE (significant change, same name OK or new file)

| Component | File | Reason |
|---|---|---|
| `TodayMemoHero` → `TodayMemoHeroV2` | `components/home/today-memo-hero.tsx` | Was small. v2 is page-defining: 80px padding, 48px Playfair H1, bronze italic accents, two CTAs. Recommend new file `today-memo-hero-v2.tsx` and import switch on a feature flag (see §5). |

### NEW

| Component | Purpose | Est. effort |
|---|---|---|
| `HomeCard` | Generic gallery shell — bronze hover border, corner CTA, eyebrow kicker | S (1 file, ~80 lines) |
| `HomeCardSnapshot` | Card #1 — NAV + spark + 3 mini KPIs | S |
| `HomeCardRiskBoard` | Card #2 — 4 horizontal CSS gauges | S |
| `HomeCardEarningsBrief` | Card #3 — pre-brief + 7-day queue. **Requires backend hook** (see §3) | M |
| `HomeCardPositions` | Card #4 — top 5 weight rows | S |
| `HomeCardSignals` | Card #5 — top 3 POSITIVE/NEGATIVE/NEUTRAL | S |
| `HomeCardCompanion` | Card #6 — archive count + 3 recent | S |
| `useUpcomingBriefs()` SWR hook | Powers card #3 | XS (after backend) |

### DELETE (from home page only — components themselves can stay for other routes)

| Section | Lines (current page.tsx) | Where it goes |
|---|---|---|
| Row 1 dense triple-column "Today Brief / Snapshot / Risk Gauges" | 583–722 | Replaced by Snapshot + Risk Board cards |
| Row 2 Positions + Watchlist tables | 724–801 | Mini Positions card; Watchlist becomes its own route entry only (sidebar link) |
| Row 2.5 Equity Curve + Sector donut | 803–873 | Spark inside Snapshot card; sector mix moves to `/portfolio` page |
| Row 3 full-width Candlestick (top holding) | 875–975 | Moves to `/portfolio/[ticker]` (already exists at `/detail/[ticker]`) |
| Row 4 Signals + Pulse Activity dense tables | 977–1057 | Top 3 to Signals card; Pulse activity feed moves to `/activity` (new minor route) or sidebar dropdown |
| Row 5 Companion entry + Artifact queue | 1059–1121 | Folded into single Companion · Archive card |

**Net**: 8 dense rows → 1 hero + 1 gallery (3×2). Removes ~600 lines from `home/page.tsx`. Final v2 page should land ~350–450 lines.

---

## 2. Reuse ratio

| Bucket | Count |
|---|---|
| Existing components reused as-is | **9** (TopTicker, LivingCFOStatusBar, KpiCard, ArtifactQueue, WeeklyPulseCard, UpsellPlus, FootSignature, ErrorBoundary, DisclaimerBanner) |
| Existing component rewritten (same domain) | 1 (TodayMemoHero → V2) |
| New components | 7 (HomeCard + 6 specialized cards) |
| Existing data hooks reused | See hook reuse breakdown below |
| New data hook | 5 (`useUpcomingBriefs` + 4 GAP hooks — see §3a in SPEC.md) |

Reuse ratio: **9 of 17 components reused as-is = 53%.**

**Hook reuse breakdown (verified 2026-04-27 against `lib/hooks.ts` — 14 hooks total):**

| Hook | Status | Notes |
|---|---|---|
| `usePortfolioSummary()` | Exact match | Card #1 Snapshot — confirmed at hooks.ts line 192 |
| `usePortfolioPositions()` | Name-corrected | Card #4 Positions — was `usePositions()` in draft SPEC |
| `useMorningBrief()` | Name-corrected | Hero — was `useTodayMemo()` in draft SPEC |
| `useArtifacts({ limit: 3 })` | Name-corrected | Card #6 Companion — was `useArtifactQueue()` in draft SPEC |
| `useDiscover()` | Available (not yet mapped) | Not wired to any home-v2 card; available if needed |
| `useWatchlist()` | Available (not yet mapped) | Not wired to any home-v2 card |
| `useAlerts()` | Available (not yet mapped) | Not wired to any home-v2 card |
| `useMacro()` | Available (not yet mapped) | Not wired to any home-v2 card |
| `useBrokerConnections()` | Available (not yet mapped) | Not wired to any home-v2 card |
| `useEquityCurve()` | **GAP — does not exist** | Card #1 spark — must be added |
| `useRiskSummary()` | **GAP — does not exist** | Card #2 Risk Board — must be added |
| `useSignals()` | **GAP — does not exist** | Card #5 Signals — must be added |
| `useArtifactStats()` | **GAP — does not exist** | Card #6 stats count — must be added |
| `useUpcomingBriefs()` | **New — to be added** | Card #3 Earnings Pre-Brief |

**Corrected hook reuse rate: 9 of 14 existing hooks = 64%** (4 exact/name-corrected matches wired to home-v2 + 5 available but not mapped to home-v2 cards). The prior claim of "≥17 of 18 = 94%" was incorrect — hooks.ts contains exactly 14 hooks, and 4 hooks referenced in the draft SPEC did not exist under those names.

Backend churn: 1 new endpoint + 1 new service file (`services/earnings_brief.py`) + 4 additional endpoints for GAP hooks.

---

## 3. Backend gaps to close before v2 ships

| Gap | Severity | Owner / file |
|---|---|---|
| `GET /api/brief/earnings/upcoming?window=7d` does not exist | **BLOCKS card #3** | new `routes/brief.py` action + `services/earnings_brief.py` |
| `useRiskSummary()` snapshot may not include `sectorConcentration` and `correlationCluster` | Medium — card #2 falls back to "—" if missing, still ships | `services/risk_summary.py` (verify; expand if absent) |
| `usePortfolioSummary().cashPct` — verify present | Low — easy fallback to compute client-side from positions | `services/portfolio_summary.py` |

None of these touch `engine.py`, `quant_models.py`, `risk_defense.py`, or `portfolio_models.py` — backend invariants from CLAUDE.md preserved.

---

## 4. Estimated work

| Phase | Effort | Sequencing |
|---|---|---|
| 1. Promote `.pq-card` and gallery utility classes from mockup → `globals.css` | 0.5h | first, blocks all card work |
| 2. Build `HomeCard` shell + Storybook entry | 1h | second |
| 3. Build cards 1, 4, 5, 6 (no backend gap) | 3h total | parallel |
| 4. Backend: `services/earnings_brief.py` + route + endpoint constant + hook | 3h | parallel with #3 |
| 5. Build cards 2, 3 against new hooks | 2h | after #4 |
| 6. Build `TodayMemoHeroV2` | 1.5h | parallel with cards |
| 7. Wire `home/page.tsx` v2 (behind flag) | 1.5h | last |
| 8. axe + Lighthouse + screenshot diff vs mockup | 1h | last |

**Total: ~12–14h focused work.** Single-day if uninterrupted; realistic two-day for a part-time founder.

---

## 5. Rollout / rollback strategy

**Recommendation: feature flag, NOT separate route.**

A separate `/home-v2` route splits the user's mental model and forks state. Use a flag instead.

```ts
// lib/flags.ts
export const FLAGS = {
  homeGalleryV2: process.env.NEXT_PUBLIC_HOME_V2 === "1"
                 || (typeof window !== "undefined"
                     && window.localStorage.getItem("pq.flag.homeV2") === "1"),
};
```

```tsx
// app/(dashboard)/home/page.tsx
import HomeV1 from "./_v1/page";
import HomeV2 from "./_v2/page";
export default function HomePage() {
  return FLAGS.homeGalleryV2 ? <HomeV2 /> : <HomeV1 />;
}
```

Implementation steps:
1. Move current `page.tsx` → `_v1/page.tsx` (no edit, just path move). Verify build.
2. Author `_v2/page.tsx` greenfield against `SPEC.md`.
3. Ship behind `NEXT_PUBLIC_HOME_V2=0` (default off). Founder dogfoods via localStorage toggle for 3–5 days.
4. Flip default to `=1` in production env. Keep `_v1/` for one release.
5. Delete `_v1/` after one week of zero-rollback.

**Rollback**: flip the env var. No code revert needed. localStorage opt-out works for any user who reports issues.

---

## 6. Risks & mitigations

| Risk | Probability | Mitigation |
|---|---|---|
| Earnings calendar source returns sparse data for KR tickers (KIS) | Medium | Card #3 gracefully degrades: if 0 upcoming, show "Queue empty — next print outside 7-day window" with no CTA |
| Founder dogfoods v2 and misses a row he relied on (e.g. dense watchlist) | Medium | The deleted dense surfaces are reachable in 1 click via the ticker/sidebar; sit with it 3 days before flipping default |
| Bronze hover border feels noisy when 6 cards all light up at once | Low | Mockup uses subtle `rgba(184,149,106,0.025)` bg + 1px border, not full bronze fill. Reviewed; ships as designed |
| Disclaimer placement after a single gallery row looks orphaned | Low | Confirmed in mockup — disclaimer + foot signature anchor the bottom and read as one editorial seal |
| `Pulse Activity` table users will lose their feed | Medium | Add to top-bar "Activity" dropdown (small follow-up task, not v2-blocking) |
| FMP 402 (already known per CLAUDE.md) breaks earnings card | Medium | `useUpcomingBriefs` returns `{data: [], status: 'unavailable'}` on 402 → card shows neutral empty state, not error |

---

## 7. CEO sign-off gate

Before merging the implementation PR, the founder confirms (in writing in the PR description):

- [ ] Mockup HTML matches what was approved in this design round
- [ ] No row has been silently re-added during implementation
- [ ] DisclaimerBanner still renders below the gallery
- [ ] Build is green; axe-core has 0 critical/serious violations on /home v2
- [ ] Old `_v1/` is preserved for 1 release
