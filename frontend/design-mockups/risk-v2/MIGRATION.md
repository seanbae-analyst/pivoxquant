# /risk v2 — Migration Plan

> Companion to `mockup.html` and `SPEC.md`. Covers what's new, what's
> touched, what's preserved, and how the rollout is gated.

---

## 1. Page status before this work

| Path | State |
|---|---|
| `/risk` | **Empty page** — route exists but renders nothing meaningful (CEO-flagged HIGH bug, qa_bug_log.md item #4) |
| 7-Layer Risk Defense backend | **Complete** (`risk_defense.py`, `risk_models.py`) |
| Risk endpoints | Already wired: `RISK_SUMMARY`, `RISK_LAYERS`, `RISK_CORRELATION`, `RISK_ROLLING_VAR` (lines 252–255 of `endpoints.ts`); plus `API.risk.var`, `drawdown`, `stressTest`, `volatility`, `componentEs`, `defenseStatus` (lines 124–131) |
| Frontend hooks for risk | **None** — `hooks.ts` has zero risk hooks (verified by grep on 2026-04-27) |

Effectively: full backend, full URL mapping, zero UI. Pure plumbing job.

---

## 2. New files (frontend)

```
frontend/src/app/(dashboard)/risk/
  page.tsx                     # NEW — server component, gated by NEXT_PUBLIC_RISK_V2
  layout.tsx                   # NEW — page-local metadata
  loading.tsx                  # NEW — skeleton matching v2 hero + 4 gauges
  error.tsx                    # NEW — editorial-tone error card

frontend/src/components/risk-v2/
  RiskHeroV2.tsx               # NEW — hero block (§1 of SPEC)
  BigGaugeCard.tsx             # NEW — reusable 240px gauge card (§2)
  DefenseLayerList.tsx         # NEW — 7-row defense table (§3)
  DefenseLayerRow.tsx          # NEW — sub-component, single row
  ConcentrationTable.tsx       # NEW — top-5 positions (§4) — uses 종목명 main pattern
  SectorDonutLg.tsx            # NEW — 220px donut (§5.1)
  SectorLeaderTable.tsx        # NEW — sector + leader name table (§5.2) — 종목명 main pattern
  RiskTimelineChart.tsx        # NEW — 30-day composite SVG line (§6)
  RiskKpiStrip.tsx             # NEW — 4-up mini KPIs under the timeline

frontend/src/lib/risk-v2/
  hooks.ts                     # NEW — useRiskSummary, useRiskLayers, useConcentration, useRiskTimeline, useSectorExposure
  derive.ts                    # NEW — pure helpers: groupBySector, top5ByWeight, computeCompositeScore
  types.ts                     # NEW — RiskSummary, DefenseLayer, ConcentrationEntry, SectorExposure, RiskTimelinePoint
```

---

## 3. Modified existing files

| File | Change | Reason |
|---|---|---|
| `frontend/src/lib/hooks.ts` | **No edits.** New risk hooks live in `lib/risk-v2/hooks.ts`. | Avoid touching the shared dedupe / refresh logic of `usePortfolioSummary` + `usePortfolioPositions`. |
| `frontend/src/lib/endpoints.ts` | **No edits.** `RISK_SUMMARY`, `RISK_LAYERS`, `RISK_CORRELATION`, `RISK_ROLLING_VAR` already exist (lines 252–255). | Endpoint URLs unchanged. |
| `frontend/src/lib/types.ts` | **Add only**: `PortfolioSummary.cashPct?` (shared with portfolio-v2). | Hero deck dependency. |
| `frontend/src/app/(dashboard)/layout.tsx` | **No edits.** `DisclaimerBanner` already mounted. The risk page extends the disclaimer copy via a prop or a page-local override (decide during impl). | |
| `frontend/src/components/layout/sidebar.tsx` | **Verify** Risk link — already exists. | |

---

## 4. Backend touch points

Most likely **zero backend work required** — the risk engine is complete. Two open questions to verify during impl:

| File | Verification |
|---|---|
| `routes/risk.py` (assumed file) | Confirm `/api/risk/summary` returns the aggregate shape used by `<RiskHeroV2/>` (posture string, last observed, count of layers under strain). If not, **add** the aggregate — pure read. |
| `routes/risk.py::layers` | Confirm `/api/risk/layers` returns 7 layers with `{num, name, status, value, threshold, observedAtKst}`. If today's response is unstructured, **map** the `risk_defense.py` model output to this shape on serialization. |
| `routes/risk.py::timeline` | NEW endpoint may be needed for the composite 0–100 score over 30 days. If `RISK_ROLLING_VAR` already returns a series compatible with rendering as a composite, reuse it; otherwise add `/api/risk/timeline?days=30`. |

**Frozen surfaces**: `risk_defense.py` and `risk_models.py` — do not modify. Only the route serializers may change.

---

## 5. Feature-flag rollout

Mirror home-v2 / portfolio-v2:

```ts
// frontend/src/app/(dashboard)/risk/page.tsx
import { redirect } from 'next/navigation';

export default function RiskPage() {
  if (process.env.NEXT_PUBLIC_RISK_V2 !== 'true') {
    return <RiskHoldingState />;  // friendlier than the current empty page
  }
  return <RiskV2 />;
}
```

**Vercel envs**:
- `production` — `NEXT_PUBLIC_RISK_V2=false` initially. Flip after CEO sign-off.
- `preview` — `NEXT_PUBLIC_RISK_V2=true`.
- `development` — `true` in `.env.local`.

**Rollback**: flip env to `false`. No data migration to undo since all backend changes are read-only serializer mappings.

---

## 6. v1 routes preserved

No existing route changes. Full route list unchanged:

- `/home` (v2 home — unaffected by this work)
- `/portfolio` (covered by sibling Wave 1 spec — independent rollout)
- `/risk` — was empty; under flag becomes the new page; without flag becomes the holding-state component
- `/detail/[ticker]` — unchanged; concentration table rows MAY link here in a future iteration (out of scope this wave)
- `/watchlist`, `/signals`, `/reports` — unchanged

API endpoint URLs unchanged.

---

## 7. Component reuse from home-v2 / portfolio-v2

| Shared component | First defined in | Reused by risk-v2 |
|---|---|---|
| `<TopBar/>`, `<TopTicker/>`, `<LivingCFOStatusBar/>`, `<DisclaimerBanner/>`, `<FootSignature/>` | layout / dashboard / ui | yes |
| `pq-card`, `pq-cta`, `pq-link`, `eyebrow`, `display-h1`, `display-h2`, `editorial-body`, `.br`, `.gauge` | `globals.css` (after home-v2 promotion) | yes |
| `종목명 main` table-row primitive | portfolio-v2 (`PositionRowV2.tsx`) | yes — concentration table + sector leader table both use the same Playfair+ticker-dim pattern. Refactor candidate: extract `<NameWithTickerCell/>` once both pages ship. |
| `<TimeframeToggle/>` | portfolio-v2 (proposed) | yes — risk timeline can offer 30/90/180-day toggle later |
| `<SectorDonutCard/>` (small 160px) vs `<SectorDonutLg/>` (220px) | portfolio-v2 small / risk-v2 large | size variant; consolidate via `size?: 'sm'\|'lg'` prop |

**Gating**: risk-v2 cannot ship before home-v2's CSS tokens are promoted to `globals.css`. Same dependency as portfolio-v2.

---

## 8. Components touched (regression watch)

| Component | Why at risk |
|---|---|
| `<DefenseStatusWidget/>` (if exists in current `components/dashboard/`) | If the v1 risk page or home page imports it, leave it functional. v2 introduces `<DefenseLayerList/>` as a separate name. Verify with `grep -rn "defense-status" frontend/src/`. |
| `<RiskCard/>` (home-v2 Card 2) | Already wired via home-v2 spec. The risk page hero echoes its eyebrow ("Risk · 7-Layer Defense") — the strings should match. |
| `useMacro()` | Used by VIX cross-reference if `risk_defense.vix` doesn't include the spot value. No changes to the hook. |

---

## 9. Tests

| Type | What |
|---|---|
| Unit | `BigGaugeCard` renders posture + value + bar width. Snapshot for each posture color. |
| Unit | `DefenseLayerRow` renders correct status color and observation timestamp formatting (uses `lib/format.ts`). |
| Unit | `derive.ts::groupBySector` correctly groups positions across mixed currencies. |
| Unit | `derive.ts::top5ByWeight` handles ties stably (stable sort by name as tiebreaker). |
| Integration | `/risk` (flag on) renders all 5 blocks at idle SWR with mocked endpoints. |
| Integration | Status colors map correctly when backend returns POSITIVE/NEGATIVE/NEUTRAL. |
| E2E (browse skill) | Open page → all 7 layers render, no console errors, no FOUC. Screenshot diff against mockup ≤2%. |
| Legal guard | Extend `tests/test_no_hardcoded_samples.py` to scan `app/(dashboard)/risk/**` for banned strings. Special check: zero occurrences of "BUY/SELL/HOLD/recommend/advice/AI Coach/추천/조언/reduce/exit". |

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Backend `risk_layers` shape doesn't match `DefenseLayer` interface | First impl PR adds a serializer test in `tests/test_risk_routes.py` to lock the shape. Frontend types generated from a single contract file (or hand-mirrored with a smoke test). |
| 7-layer status logic differs between backend and frontend (e.g. backend says NEUTRAL but frontend renders NEGATIVE because of a threshold off-by-one) | Status MUST be authored by backend. Frontend NEVER computes `status` itself — it only renders. Document this in the type comment. |
| Risk timeline composite score is a frontend invention | If backend doesn't expose a 0–100 composite, derive it client-side from `RISK_ROLLING_VAR` per spec §6, but mark it `data-source="derived"` in the SVG figcaption for traceability. Better long-term: add `/api/risk/timeline` returning the score authored backend-side so it matches what the layers report. |
| Concentration HHI shown in gauge but not in defense table | The HHI is listed twice intentionally (Block 1 gauge + Block 2 layer 06) for narrative reasons — the gauge is "headline status", the layer row is "where it lives in the defense stack". Verify both pull from the same source field to avoid drift. |
| Disclaimer drift | `DisclaimerBanner` has a single source. The "VaR is probabilistic, not a guarantee" line is appended via a prop, not duplicated. If the banner doesn't accept that prop yet, **extend the prop API additively** — never inline a second banner. |
| Color is the only signal | Verified in spec §11 — every status color is paired with text. Verify in design-review skill before merge. |

---

## 11. Definition of done

- [ ] CEO-approved screenshot match (1280px desktop) ≥ 98%.
- [ ] `pytest tests/test_no_hardcoded_samples.py -v` green.
- [ ] `axe-core` zero violations on `/risk` (under flag).
- [ ] All 5 blocks render with real backend data on a populated test account (no `—` placeholders for non-cashPct fields).
- [ ] `useRiskSummary`, `useRiskLayers`, `useConcentration`, `useRiskTimeline`, `useSectorExposure` shipped with SWR-style dedupe (60s idle / 5s during market hours).
- [ ] Feature flag rollout doc updated in `HANDOVER.md`.
- [ ] No banned UI strings (BUY/SELL/HOLD/recommend/advice/AI Coach/추천/조언/reduce/exit/cut) anywhere in risk-v2 source.
- [ ] **종목명 main pattern** verified by visual review on:
  - concentration table (Block 3) ✓
  - sector leader table (Block 4 right) ✓
  - any future links into `/detail/[ticker]` if added later
- [ ] Disclaimer extension shipped via prop, not inline duplicate.
- [ ] Risk timeline composite score documented as backend-authored or frontend-derived (data-source metadata).
