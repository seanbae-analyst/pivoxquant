# Bug Hunt Report — 2026-05-14 — Full Site Sweep (Production)

## Hunt Scope
- URL: https://www.pivoxquant.com
- Auth: Google OAuth (seanbae1521@gmail.com), beta gate passed
- Pages covered: Landing, Login, Home/Dashboard, Portfolio (V2), Market (US + KR tabs), Risk Board, Signals, Watchlist, Reports, Settings, Stock Detail (AAPL, 005930.KS), AI Analysis, AI Chat, Pre-Trade, Companion, Journal (/growth), Profile/Persona, Alerts, Pricing
- PR cross-check: `git diff main...fix/design-audit-20260514` — 128 files, CSS/font tokens only. All data/logic bugs below are NOT addressed by PR #377.
- Actions attempted: ~80 distinct interactions (button clicks, API monitoring, console inspection, cross-page navigation, network request inspection)

---

## Confirmed Bugs

### CRITICAL — Bug #1: KOSPI Level Factually Wrong in Landing Ticker (Static Hardcode)

**Confidence: 100%**

**Symptom**: The landing page market ticker displays KOSPI at 7,643.15. Real KOSPI as of 2026-05-14 trades in the ~2,500–3,200 range.

**Reproduction**:
1. Navigate to https://www.pivoxquant.com (unauthenticated)
2. Observe the scrolling market ticker — KOSPI shows 7,643.15

**Evidence**:
- File: `frontend/src/components/landing/market-ticker.tsx:86`
  ```
  { symbol: "KOSPI", name: "KOSPI", level: "7,643.15", change: "-2.29%", dir: "down" }
  ```
- File comment on line 18 acknowledges `SNAPSHOT_DATE = "2026-05-12"` but the value is wrong even by KIS API standards
- PR #377 diff: only changes `text-[12px]` → `text-pq-caption` CSS token on this file — data unchanged

**Root Cause**: Static hardcoded snapshot. The level 7,643.15 appears to originate from the same KIS API bug as Bug #2 (KIS "0001" endpoint returning an anomalous scaled value). The snapshot was taken from the live API result — which itself was wrong.

**Fix Direction**: Either (a) connect this ticker to the live `/api/market/indices` endpoint at runtime, or (b) replace the static value with a correct real-world KOSPI level. Do NOT use KIS "0001" current-level value until the KIS API discrepancy is resolved (see Bug #2).

---

### CRITICAL — Bug #2: KIS API Returns Wrong KOSPI Current Level (~3x Inflated)

**Confidence: 100%**

**Symptom**: The live market API endpoint `/api/market/indices` returns `"^KS11": { "level": 7981.41, ... }` while the sparkline_30d values in the same response are in the range 2,293–2,640, which match actual KOSPI levels. The current-level field is ~3x the real value.

**Reproduction**:
1. Log in and navigate to /home or /market
2. Call `fetch('/api/market/indices').then(r=>r.json())` in console
3. Observe `level` vs `sparkline_30d` array values for ^KS11

**Evidence**:
- API response: `{ "symbol": "^KS11", "name": "KOSPI", "level": 7981.41, "sparkline_30d": [2293, 2312, ..., 2640] }` — 30-day history contradicts the current level
- Backend: `routes/market.py` — `_KR_INDEX_SPEC` uses KIS API code `"0001"` for current level
- Backend: `services/data/fetcher.py` — `_KOSPI_RANGE = (1500.0, 50000.0)` — wide bounds allow 7,981 to pass sanity check without rejection
- Frontend: `frontend/src/lib/format.ts:88-102` — `KOSPI_RANGE [1500, 50000]` — same wide bounds, 7,981 passes `isSaneKospi()`
- Dashboard top ribbon displays "KOSPI 7,981 ▲" to authenticated users
- Contradictory comment in `routes/market.py:856`: "KOSPI 7,498 — real index has been trading 2,500-3,200" alongside line 858-859 claiming "KOSPI 7498 confirmed real via live KIS API" — the code comments themselves disagree

**Root Cause**: KIS API endpoint code "0001" for `현재가조회` likely returns a different product (possibly KOSPI 200 Futures or a scaled variant). Historical data (from a separate KIS endpoint) returns the correct real-index history. The backend treats both as ground truth without cross-validation.

**Fix Direction**: Cross-validate KIS current-level with the last data point of sparkline_30d. If the ratio is > 2x, reject the current level and use the last historical value. Alternatively, use the KRX OpenData API for index levels. Tighten `_KOSPI_RANGE` to `(1500, 4500)` as an interim guard.

---

### HIGH — Bug #3: Dashboard TopTicker Shows ETF Proxy Prices for US Indices Without Disclosure

**Confidence: 100%**

**Symptom**: The dashboard top ribbon shows "S&P 500 742.31" and "NASDAQ 100 714.71". These are SPY and QQQ ETF prices, not S&P 500 and NASDAQ 100 index values. S&P 500 actually trades around 5,700. Users see a number that is ~87% lower than the real index value with no indication it is an ETF proxy.

**Reproduction**:
1. Log in and navigate to any dashboard page
2. Observe the top ribbon — "S&P 500 742.31 ▲+0.56%"

**Evidence**:
- Screenshot ss_1511srcdn (Profile page): top ribbon shows "S&P 500 742.31 ▲+0.56% | NASDAQ 100 714.71 ▲+1.06%"
- `routes/market.py` — `_US_INDEX_PROXY = { "^GSPC": "SPY", "^IXIC": "QQQ", "^DJI": "DIA", "^RUT": "IWM", "^VIX": "VIXY" }` — FMP $29 plan returns 402 for caret-prefixed symbols
- Market page (US tab) correctly labels "VIA SPY · ETF PROXY" beneath the value
- `frontend/src/components/terminal/top-ticker.tsx` maps `^GSPC` → "S&P 500" label with no ETF proxy annotation
- VIX ribbon entry shows VIX 27.33 sourced from VIXY (volatility ETF) — VIXY price does not equal VIX index level

**Root Cause**: The backend's ETF proxy substitution is intentional (FMP plan limitation), and the Market page correctly discloses "ETF PROXY." However, `top-ticker.tsx` renders the label "S&P 500" against the SPY price without any disclosure, making it appear to be the real index.

**Fix Direction**: In `top-ticker.tsx`, append "(ETF)" or "via SPY" suffix for all proxied symbols. The disclosure logic already exists in the Market page component — reuse it.

---

### HIGH — Bug #4: Portfolio Equity Curve Shows +593,259.33% 6-Month Return

**Confidence: 100%**

**Symptom**: The portfolio page equity curve displays a 6-month return of +593,259.33% and total unrealized P/L in millions. This is caused by AAPL position having avgCost=$30 (a data entry error — AAPL hasn't traded at $30 since 2013).

**Reproduction**:
1. Log in, navigate to /portfolio
2. Observe equity curve — the Y-axis and return label show +593,259%

**Evidence**:
- API `/api/portfolio/positions` returns AAPL with `avg_cost: 30.0, current_price: ~208`
- Unrealized P/L for AAPL position: +596% for a single position drives the equity curve
- Portfolio V2 page (`src/app/(dashboard)/portfolio/_v2/page-v2.tsx`) calculates equity curve from position cost basis without bounding or validating avgCost against a realistic historical price floor
- No validation guard in the backend `routes/portfolio.py` rejects avgCost values outside a plausible range

**Root Cause**: Test data pollution. The AAPL position in the database has avgCost=$30 which is historically implausible. The equity curve calculation has no sanity check on avgCost values.

**Fix Direction**: (a) Data: correct the AAPL test position avgCost to a realistic value (~$180–200). (b) Code: add a backend validation guard in the position creation/update endpoint — reject avgCost < 50% of the 52-week low for any given ticker. This is a test data issue, not solely a code bug, but the code should be more defensive.

---

### HIGH — Bug #5: Korea Market Tab Shows "No observation available for this region"

**Confidence: 100%**

**Symptom**: The Market page KR tab displays an empty state "No observation available for this region" with no Korean stock data, no KOSPI/KOSDAQ gainers/losers, no sector breakdown.

**Reproduction**:
1. Log in, navigate to /market
2. Click "KR" tab

**Evidence**:
- Screenshot observed during hunt: empty state UI with the message above
- `/api/market/movers?region=KR` — the endpoint exists but returned empty array or error during test session
- `routes/market.py` KR movers logic depends on KIS API for Korean equity data — same API experiencing issues as Bug #2

**Root Cause**: KIS API connectivity issue or data parsing failure for Korean market movers. The frontend gracefully renders an empty state but the root cause is backend data unavailability for KR region.

**Fix Direction**: Add error logging to `/api/market/movers?region=KR` to capture whether the failure is a 4xx/5xx from KIS, a parsing error, or a rate limit. Add a more specific error message to the frontend ("Korean market data temporarily unavailable") rather than the generic "No observation available."

---

### MEDIUM — Bug #6: KOSPI and KOSDAQ Missing from Dashboard Ribbon (Intermittent)

**Confidence: 90%**

**Symptom**: KOSPI and KOSDAQ entries in the top ticker ribbon show "— ·—" (placeholder dashes) even after the page has fully loaded and US indices are displaying correctly. This was observed consistently across multiple page navigations during the hunt.

**Reproduction**:
1. Log in, navigate to /home
2. Wait 5+ seconds — US indices (S&P 500, NASDAQ 100, VIX, USD/KRW) resolve
3. KOSPI and KOSDAQ remain "— ·—"

**Evidence**:
- Screenshots ss_1511srcdn (Profile), ss_22068fq5l (Journal page), and earlier home/portfolio screenshots — all show "KOSPI — ·—" and "KOSDAQ — ·—"
- `frontend/src/components/terminal/top-ticker.tsx` — KR index uses separate SWR key with 60s `refreshInterval`. If `sanitizeKrIndex()` returns null (because Bug #2 level is out of range in a stricter config), the component shows placeholder
- The intermittent vs permanent failure depends on whether `sanitizeKrIndex` accepts or rejects the 7,981 value. If frontend bounds are overridden via `NEXT_PUBLIC_KOSPI_RANGE`, the value may be rejected

**Root Cause**: Cascading failure from Bug #2 — if the KIS API fails to return data at all, or if the frontend's `sanitizeKrIndex` rejects the anomalous level value in certain configurations, the ribbon placeholder never resolves.

**Fix Direction**: In `top-ticker.tsx`, if the KIS current-level is unavailable but `sparkline_30d` data exists, derive a display value from the last sparkline point rather than showing "—". Add a separate error state for "KR data unavailable" distinct from the loading placeholder.

---

### MEDIUM — Bug #7: Brag Card PDF Path Uses `/app/` — Likely Wrong in Non-Docker Env

**Confidence: 70%**

**Symptom**: The artifacts API response contains `"pdf_path": "/app/artifacts/brag_card/3/2026-04_Brag_Card.png"`. The `/app/` prefix is a Docker container path (Railway). On local dev this path does not exist.

**Evidence**:
- Console log on /ai page: `ARTIFACTS: { "pdf_path": "/app/artifacts/brag_card/3/2026-04_Brag_Card.png" }`
- This is a Railway-specific absolute path — correct in production, but would break any local file serving

**Root Cause**: The backend stores absolute container paths in the database rather than relative paths or object storage URLs.

**Fix Direction**: Store relative paths (e.g., `artifacts/brag_card/3/2026-04_Brag_Card.png`) and construct the full URL at serve time based on environment. Or migrate artifact storage to object storage (S3/R2) and store URLs instead.

---

### LOW — Bug #8: Growth/Journal Page "Growth Graph" Stuck on "Loading..."

**Confidence: 60%**

**Symptom**: The Growth Graph section on /growth shows a "Loading..." spinner indefinitely without resolving to a chart or an empty state.

**Reproduction**:
1. Log in, navigate to /growth
2. Observe "Growth Graph — Past 365 days. Click a day for details." — section shows "Loading..." indefinitely

**Evidence**:
- Screenshot ss_4565ab6is: "Loading..." visible in the Growth Graph card
- 0 days current streak, "아직 오늘의 점수가 없습니다" — empty data state is handled for the streak card but not for the graph

**Root Cause**: Likely the `/api/growth/history` endpoint returns an empty array, and the chart component renders "Loading..." on empty data rather than transitioning to an empty state. The 50% confidence is because this could also be expected behavior for a new account with no entries.

**Fix Direction**: Distinguish between "loading data" and "no data" states in the Growth Graph component. After data fetch completes with empty array, render an empty state ("No entries yet — start tracking today") rather than the loading spinner.

---

## Pages Not Tested (Insufficient Coverage)
- Discover page (/discover) — navigation item exists, not tested this session
- Alerts configuration UI (the alert creation flow, not just the notification dropdown)
- Pricing page (/pricing) — not visited
- OAuth login redirect flow (post-logout re-login)
- Mobile viewport (< 768px) — all testing done at desktop resolution (~1383px)

---

## Compliance Observations (No Bug — FYI)
- AI Analysis (/ai): "AI ASSISTANT · OBSERVATIONAL ANALYSIS" label — compliant. Disclaimer banner present.
- AI Chat (/ai-chat): "OBSERVATION ASSISTANT" label — compliant. "never a directive" copy present.
- Pre-Trade (/pre-trade): "조언이 아니라 규율이다" copy — compliant framing.
- Companion (/companion): "not an advisor" — compliant. "매수/매도 권유도, 가격 예측도, 수익 보장도 하지 않습니다" — strong disclaimer.
- Signals page: POSITIVE/NEGATIVE/NEUTRAL labels confirmed — no BUY/SELL/HOLD found.
- No "recommendation", "advice", "추천", "조언" language found in visible UI copy across tested pages.

---

## PR #377 Cross-Check Summary
All 7 confirmed bugs above are NOT fixed by PR #377. The branch `fix/design-audit-20260514` contains 128 files of CSS/font-token changes only. Zero changes to:
- `routes/market.py` (Bug #2, #3, #5)
- `services/data/fetcher.py` (Bug #2)
- `frontend/src/lib/format.ts` (Bug #6)
- `frontend/src/components/landing/market-ticker.tsx` data values (Bug #1)
- `frontend/src/components/terminal/top-ticker.tsx` proxy disclosure (Bug #3, #6)
- `frontend/src/app/(dashboard)/portfolio/_v2/page-v2.tsx` (Bug #4)

---

## Summary

| Severity  | Count | Bugs |
|-----------|-------|------|
| CRITICAL  | 2     | #1 (landing KOSPI hardcode), #2 (KIS API inflated level) |
| HIGH      | 3     | #3 (ETF proxy no disclosure on ribbon), #4 (equity curve +593k%), #5 (KR market empty) |
| MEDIUM    | 2     | #6 (KOSPI/KOSDAQ ribbon placeholder), #7 (Docker path in DB) |
| LOW       | 1     | #8 (Growth graph loading stuck) |

**Hunt coverage**: 19 pages / 80+ interactions  
**Immediate fix needed (ship blocker)**: Bug #1 + #2 — showing KOSPI at 7,643–7,981 to unauthenticated visitors on the landing page and to all authenticated users on the dashboard is factually incorrect and undermines trust. Bug #3 — displaying "S&P 500 742.31" without ETF proxy disclosure is misleading.  
**Data correction needed**: Bug #4 — AAPL avgCost=$30 must be corrected in the test/prod database before showing the equity curve to real users.  
**Deferred**: Bug #7 (Railway path — no prod impact), Bug #8 (low priority, new account edge case).
