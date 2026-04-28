# /signals v2 — Migration Plan

> Companion to `mockup.html` and `SPEC.md`. Describes how to land the v2 stream
> without breaking the existing `/signals` route or the home-page mini-stream.

---

## 1. Impact summary

| Area | Change | Risk |
|---|---|---|
| Route `/signals` | Replaced behind feature flag | Low — flag defaults `false` until QA passes |
| Home page mini-stream (Card 5) | Unchanged. Still pulls from `useSignals` (newly introduced); v1 fallback kept | Low |
| Backend `/api/signals` | **No URL change.** Possible label-mapper added inside `routes/signals.py` to enforce POSITIVE/NEGATIVE/NEUTRAL on the wire. | Low — additive only; legacy fields remain inside server but never leave |
| CSV export endpoint | NEW (optional, can ship later) | Low |
| Type contracts | Additive — `SignalEntry`, `SignalsResponse` added to `lib/types.ts` | Zero (no removals) |
| Existing pages that read signals | Home Card 5 (`SignalsCard` placeholder) consumes the same hook — single source of truth | Zero |

---

## 2. New components (files to create)

| File | Responsibility |
|---|---|
| `frontend/src/app/(dashboard)/signals/page.tsx` | New page shell. Replaces or wraps current `/signals` with feature flag |
| `frontend/src/components/signals/signals-hero.tsx` | `<SignalsHeroV2/>` |
| `frontend/src/components/signals/signals-filter-bar.tsx` | `<SignalsFilterBar/>` (sticky 4-col, chips + slider) |
| `frontend/src/components/signals/signals-movers-rail.tsx` | `<SignalsMoversRail/>` (top-5 horizontal cards) |
| `frontend/src/components/signals/signals-timeline.tsx` | `<SignalsTimeline/>` + `<SignalRow/>` + `<DayRule/>` |
| `frontend/src/components/signals/signals-pager.tsx` | `<SignalsPager/>` |
| `frontend/src/components/signals/signal-label-pill.tsx` | `<SignalLabelPill label="POSITIVE \| NEGATIVE \| NEUTRAL"/>` shared with home Card 5 |
| `frontend/src/components/signals/signal-strength-bar.tsx` | `<SignalStrengthBar value={0..1}/>` shared |

All components use the existing token surface in `globals.css` — **no new tokens introduced**.

---

## 3. New hook (additive)

Append to `frontend/src/lib/hooks.ts`:

```ts
export interface SignalFilters {
  labels: Set<"POSITIVE" | "NEGATIVE" | "NEUTRAL">;
  strengthMin: number;
  strengthMax: number;
  symbol: string | null;
  window: "today" | "7d" | "30d";
}

export function useSignals(filters: Partial<SignalFilters> = {}) { … }
```

Append to `frontend/src/lib/types.ts`:

```ts
export interface SignalEntry { … }   // see SPEC §6
export interface SignalsResponse { … }
```

No existing exports change. Old code that may reference `signals` anywhere keeps working.

---

## 4. Backend touchpoint (label mapper only, no schema change)

Inside `routes/signals.py::all()` — verify the response payload uses only
`POSITIVE / NEGATIVE / NEUTRAL` for the `label` field. If legacy `recommendation`
strings (`BUY/SELL/HOLD`) leak out, apply a one-line mapper:

```python
LABEL_MAP = {
    "BUY": "POSITIVE", "STRONG_BUY": "POSITIVE",
    "SELL": "NEGATIVE", "STRONG_SELL": "NEGATIVE",
    "HOLD": "NEUTRAL", "NEUTRAL": "NEUTRAL", None: "NEUTRAL",
}
for s in payload["signals"]:
    s["label"] = LABEL_MAP.get(s.get("recommendation") or s.get("label"), "NEUTRAL")
    s.pop("recommendation", None)   # strip banned vocab from wire format
```

This satisfies the legal-guard CI rule (`tests/test_no_hardcoded_samples.py` and
`.github/workflows/legal-guard.yml`) — banned vocabulary never reaches the client.

The internal `engine.py` recommendation field can keep its current vocabulary if
needed for backtesting; only the route-layer serializer changes.

---

## 5. Feature flag

Add to `frontend/src/lib/auth.tsx` (or wherever flags live):

```ts
const FF_SIGNALS_V2 = process.env.NEXT_PUBLIC_FF_SIGNALS_V2 === "1";
```

Inside `app/(dashboard)/signals/page.tsx`:

```tsx
import LegacySignalsPage from "@/components/signals/legacy-signals-page";
import SignalsV2Page from "@/components/signals/signals-v2-page";
import { FF_SIGNALS_V2 } from "@/lib/flags";

export default function Page() {
  return FF_SIGNALS_V2 ? <SignalsV2Page /> : <LegacySignalsPage />;
}
```

**v1 preservation:** The existing `/signals/page.tsx` body (whatever lives there
today) is moved verbatim to `components/signals/legacy-signals-page.tsx`. No code
deleted. Roll-back = flip env var.

`.env.local` for dev: `NEXT_PUBLIC_FF_SIGNALS_V2=1`. Production stays `=0` until
QA + design review pass.

---

## 6. Rollout sequence

1. **PR 1 — types + hook (no UI).**
   - Add `SignalEntry`, `SignalsResponse`, `SignalFilters` to `lib/types.ts`.
   - Add `useSignals(filters)` to `lib/hooks.ts`.
   - Backend label mapper (if needed).
   - Tests: `tests/test_signals_route.py` asserts no banned vocab in response.
   - Ship.
2. **PR 2 — shared atoms.**
   - `<SignalLabelPill/>`, `<SignalStrengthBar/>`. Used by both the new page and home Card 5.
   - Refactor home Card 5 to consume them — visual no-op.
   - Ship.
3. **PR 3 — v2 page behind flag.**
   - Add `<SignalsHeroV2/>`, filter bar, movers rail, timeline, pager.
   - Mount under flag. Default `off`.
   - QA on staging with flag `on`.
4. **PR 4 — flip flag + remove `legacy-signals-page.tsx`.**
   - After 2 weeks of stable QA + design review sign-off, flag default flips to `on` in code.
   - Legacy file deleted in the same PR (kept in git history for rollback).

---

## 7. Disclaimer banner — already mounted

`DisclaimerBanner` is mounted once by `app/(dashboard)/layout.tsx`. Verify that
single instance still renders below the new `<SignalsTimeline/>` + pager (no
duplicate). The mockup's footer-disclaimer block is illustrative; in production
it comes from the layout, not the page.

The custom copy ("Signals are observations of model state, not actions…") should
live as a `variant="signals"` on `<DisclaimerBanner/>` if the component supports
variants; otherwise the page can pass a `children` override. Both approaches
acceptable; design lead picks one.

---

## 8. Tests / CI

- [ ] `tests/test_no_hardcoded_samples.py` — already runs on every commit; covers banned vocab.
- [ ] `tests/test_signals_route.py` — NEW. Asserts `/api/signals` response contains only `POSITIVE/NEGATIVE/NEUTRAL` labels and no `recommendation` key.
- [ ] Visual regression (Playwright) — capture `/signals` at flag `on`, store baseline. Add to `.github/workflows/frontend-tests.yml`.
- [ ] `axe-core` a11y — new test asserting H1 → H2 → H3 order, all rows have `aria-label`, slider has `aria-valuenow`.
- [ ] Storybook stories — `<SignalRow/>` with all 3 labels, `<SignalsFilterBar/>` empty + populated state.

---

## 9. Migration metrics (record after PR 4 lands)

- Time-to-first-signal-card: target ≤700ms p75 on cold cache.
- Stream tick latency: ≤6s when market open, ≤62s when closed (matches `liveRefresh` budget).
- A11y score: 100/100 on `axe` for the route.
- Zero instances of `BUY`/`SELL`/`HOLD` in any rendered DOM (Playwright asserts).

---

## 10. Open questions for engineering

1. Pagination vs. infinite scroll — pick one before PR 3. Default recommendation: **infinite scroll** with `IntersectionObserver` because stream context is more natural; pagination kept as a fallback under a sub-flag.
2. Does the legacy `/signals` page have any side-effects (e.g. mark-as-read on visit)? If yes, port to the new page before flipping the flag.
3. CSV export endpoint — ship in PR 5 or grey-out the button?
4. Push notification on new high-strength POSITIVE/NEGATIVE — out of scope for this v2 (handled by `useAlerts()` already), but worth confirming before launch.
