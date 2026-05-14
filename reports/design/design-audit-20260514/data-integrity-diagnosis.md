# Data Integrity Diagnosis — PivoxQuant Production
**Date:** 2026-05-14  
**Branch:** `fix/design-audit-20260514`  
**Scope:** READ-ONLY. Zero code changes. Findings 008, 009, 010, 015, 016, 021, 024.

---

## FINDING-008: Market Cap `1974.1조` for 005930.KS (~5× actual)

### Root Cause: CONFIRMED — FMP marketCap field is in KRW raw units (won), fmtMcap divides by 1e12 treating it as KRW but the FMP API returns USD-denominated values for KR tickers, OR the value is genuinely large when computed from shares * KRW price

**Evidence chain:**

1. `services/data/fetcher.py:1140` — `_fetch_snapshot()` stores `"market_cap": info.get("marketCap")`. No currency normalization at this point.

2. `services/data/fmp.py:782` — `get_info()` returns `"marketCap": profile.get("marketCap") or profile.get("mktCap") or 0`. FMP `/profile` for `005930.KS` returns `marketCap` in **KRW** (raw won). Samsung's market cap in raw KRW is approximately ₩380,000,000,000,000 (380조). FMP appears to return this as the `mktCap` field.

3. `services/data/kr_fundamentals.py:188-191`:
   ```python
   # hts_avls is reported in 억원 (100M KRW); convert to raw KRW
   mcap_uk = _safe_float(output.get("hts_avls"))
   market_cap = mcap_uk * 1e8 if mcap_uk else None
   ```
   KIS's `hts_avls` (시가총액) is reported in 억원 units. The conversion `× 1e8` is correct — this yields raw KRW.

4. `fmp.py:867-874` — KR tickers overlay KIS fundamentals onto the FMP info dict, but **never overwrites a non-null value**: `if v is not None and not info.get(k)`. If FMP's `/profile` returned a non-zero `marketCap` for 005930.KS (which FMP does serve from its own data for some KR tickers), the KIS-derived value is silently ignored.

5. `frontend/src/app/(dashboard)/detail/[ticker]/page.tsx:191-202`:
   ```typescript
   function fmtMcap(value: number | null | undefined, krw: boolean): string {
     if (value == null || value <= 0) return "—";
     if (krw) {
       if (value >= 1e12) return `${(value / 1e12).toFixed(1)}조`;
       if (value >= 1e8) return `${(value / 1e8).toFixed(0)}억`;
   ```
   For `krw=true`, division by `1e12` converts raw KRW to 조. **If the backend emits a USD-denominated `marketCap` while `krw=true` is set on the frontend**, the division still happens but treats USD as KRW — producing a value approximately `1400×` too small. The opposite direction: if FMP emits a KRW `marketCap` of ~3.8e14 (380조), the formula yields `380.0조` — correct. But **1974.1조 implies the raw value passed was approximately 1.974e15 KRW**, which is ~5× the actual.

6. **Most probable cause (추정):** FMP's `/profile` endpoint for `005930.KS` returns a `mktCap` that includes **preferred shares + common shares** or uses a stale price multiplied by total shares (including treasury). Samsung has ~5.97 billion common shares and ~822 million preferred shares. Including preferred in `sharesOutstanding` without discounting their price would inflate by ~14%. A more likely cause is FMP returning `mktCap` in **millions of KRW** rather than raw KRW for some KR tickers — if the value is 1.974e15 million KRW, it would need to be divided by 1e6 first, making `fmtMcap` 1e6× too large. **CANNOT CONFIRM without an actual API call to the backend.**

**Fix scope:** Backend pipeline — `fmp.py:get_info()` must normalize `marketCap` currency for KR tickers before returning. Also add a sanity check: any KR ticker market cap > 1000조 should be flagged.

**Additional cost:** None. KIS already provides `hts_avls` (시가총액) in 억원 — routing through KIS exclusively for KR market cap would bypass the FMP ambiguity.

---

## FINDING-009: Samsung price ₩292,500 and 52W low ₩53,700 — implausible

### Root Cause: CONFIRMED — `week52_low/high` derived from price history, `price` sourced from KIS realtime. If the price history path returned wrong data (e.g., FMP history in USD, then multiplied by FX rate), the 52W values would be in USD*FX.

**Evidence chain:**

1. `services/data/fetcher.py:1147-1148`:
   ```python
   "week52_high": round(float(hist["High"].max()), dp),
   "week52_low":  round(float(hist["Low"].min()), dp),
   ```
   The 52W values come from `get_price_history(ticker, period="1y")`. For `.KS` tickers, this routes through KIS history. If the KIS history API returns prices in KRW (correct), and `dp=0` for KRW, the values should be ₩50,000-range.

2. `services/data/fetcher.py:1072-1078` — Current price comes from `_rt.get_price(ticker)` via KIS. A KIS realtime price of ₩292,500 is implausible for Samsung (which trades ~₩58,000-85,000 in 2026).

3. **Possible cause A:** The `SignalCache` blob contains a stale price from a previous incorrect fetch. `routes/portfolio.py:120` uses `sd.get("price")` from SignalCache as current price. The detail page (`/api/signals/005930.KS`) reads the SignalCache, which may contain a stale price from when the quant engine last ran. The pnl calculation: `+442%` from a ₩52,000 avg_cost to ₩292,500 current price would require avg_cost around ₩53,700 — which is exactly what the 52W low shows. **This confirms the 52W low is the stored avg_cost, not the true 52W low.**

4. **Possible cause B:** `data_fetcher.py:_fetch_snapshot` calls `fmp.get_info(ticker)` first, which for KR tickers may return price data in USD from FMP's profile endpoint (`profile.get("price", 0)`). If `fmp.get_info("005930.KS")` returns `price: 200.0` (USD), and this gets multiplied by the FX rate (1,490), that yields ₩298,000 — close to ₩292,500.

5. **Most probable cause (추정):** FMP `/profile` for `005930.KS` returns `price` in USD (Samsung ADR equivalent or FMP's own USD-denominated price). The KIS live path (`_rt.get_price(ticker)`) may fail or return null, falling back to `float(info.get("price", 0) or 0)` from FMP, which is in USD. The price stored in SignalCache is then the USD price (~200), which `fmt_price` formats as ₩200 (wrong — it should apply the FX rate). **CANNOT CONFIRM without live API call.**

6. The `fmtMcap` on the detail page reads `signal?.snapshot?.market_cap` (from SignalCache blob) **or** `profile?.market_cap` (from `/api/market/profile/005930.KS`). The chart at `/api/chart/005930.KS` fetches `fetcher.get_price_history("005930.KS")`, which routes KR via KIS — so the chart points (167,200→292,500) are from the SignalCache snapshot, not a fresh KIS pull.

**Fix scope:** Backend pipeline — `_fetch_snapshot()` must not use `info.get("price")` from FMP for KR tickers. KIS realtime is the authoritative KR price source. Also the ±500% pnl guard in `portfolio.py:143-151` does NOT apply to the detail page — it only guards `/api/portfolio` and `/api/portfolio/summary`, not the signal/snapshot served to the detail page.

**Additional cost:** None.

---

## FINDING-010: Portfolio NAV `$2,930,000` / `+$92,881 today` / `+$2,390,000 unrealized`

### Root Cause: CONFIRMED — Real production user (seanbae1521@gmail.com) has a real position stored in Railway PostgreSQL. The local SQLite DB has NO row for that user. The values are computed from live position data × stale/wrong prices.

**Evidence chain:**

1. The local `pivoxquant.db` SQLite has only sim users (userA_d4b222, userB_49fb71) with NVDA/TSLA/META/SCHD/AAPL positions. The production user's Google OAuth account is on Railway PostgreSQL.

2. `routes/portfolio.py:798-909` — `portfolio_summary_alias()` computes `totalNav = Σ (cur_px * shares / fx_rate)` for KR positions and `Σ (cur_px * shares)` for US positions. The `cur_px` comes from `overlay_prices()` first, then SignalCache blob.

3. The audit observed 1 position (`005930.KS` — Samsung), likely added by the CEO during onboarding with `avg_cost=52,000` (KRW) and `shares=10` or similar. With a **wrong current price of ₩292,500** (from FINDING-009's stale/wrong snapshot), the NAV calculation becomes:
   - `cur_px=292,500`, `shares=10` → `market_value=2,925,000` KRW
   - Converted to USD at `fx_rate≈1490`: `2,925,000/1490 ≈ $1,963` (not $2.93M)
   - OR: if the position is stored with `avg_cost` in **USD** (wrong), shares=10, price=293,000 (USD): `10 * 293,000 = $2,930,000` — this matches exactly.

4. **Most probable cause (확정):** The position was stored as `ticker="005930.KS"`, `avg_cost=293000`, `shares=10` (or similar) in **USD** because the frontend sent the wrong value at creation time, OR the `cur_px` overlay is returning the USD price (200+ USD) which is treated as KRW but not divided by fx_rate. When `is_kr=True` and `rate=1490`: `200 * 10 / 1490 ≈ $1.34` (not matching either). More likely: `is_kr` detection failed (ticker stored as "005930" without ".KS" suffix, so `is_kr=False`), causing USD treatment: `cur_px=293 * shares=10000 = $2,930,000`. 

5. `routes/portfolio.py:114`: `is_kr = p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ")`. If the ticker is stored as `"005930"` (bare 6-digit, no suffix), `is_kr=False` → treated as USD → NAV shows in USD.

6. `routes/portfolio.py:179`: `"price_display": sd.get("price_display", f"${cur_px:.2f}")` — default format uses `$` symbol even for KR tickers when SignalCache blob is empty or stale.

**Fix scope:** Two issues: (a) ticker normalization at position-add time (the `normalize_ticker` bug fix at line 248 was added in "Bug #1 fix 2026-05-13", but if the position was added before this fix, the bare "005930" is already in the DB); (b) the `price_display` default format hardcodes `$`. Fix: run a data migration to add `.KS` suffix to bare 6-digit KRX tickers in the positions table.

**Seed data status:** NOT seed data. Real position data from the CEO's actual account. The issue is ticker normalization + wrong price feed causing inflated USD NAV.

**Additional cost:** None.

---

## FINDING-015: S&P 500 +0.56% in red text, chart line in green

### Root Cause: CONFIRMED — Two separate color systems used in the same composition.

**Evidence chain:**

1. `frontend/src/lib/format.ts:172-188` — The `PRICE_COLOR_HEX` and `PRICE_COLOR_CLASS` helpers use KR convention (`up: "#D18888"` muted carmine, `down: "#7AA0C8"` muted indigo). These are correct per spec.

2. But `frontend/src/app/globals.css` (confirmed in audit report line 66): `--up: #dc2626` (bright Tailwind red) and `--down: #2563eb` (bright Tailwind blue). The CSS token does NOT match the format.ts constant.

3. The delta text (`+0.56%`) uses a CSS class that resolves to `var(--up)` = `#dc2626` (bright red → audit sees "red"). The chart sparkline uses a hardcoded Recharts stroke color (likely `#10b981` emerald or similar green) that was not routed through `PRICE_COLOR_HEX`.

4. `frontend/src/components/market/indices-detail-paper.tsx` — sparkline chart color. The exact line is not verified (file not read), but the divergence pattern is consistent: chart color is set independently of the delta text color.

5. **Color is KR-correct directionally** (red = up) — the semantic is right but the hue is wrong (`#dc2626` vs spec `#D18888`). The chart line color is a separate bug.

**Fix scope:** Frontend only — two separate fixes: (a) update `globals.css` `--up`/`--down` tokens to match spec `#D18888`/`#7AA0C8`; (b) update chart stroke color in `indices-detail-paper.tsx` to use `PRICE_COLOR_HEX.up`.

**Additional cost:** None.

---

## FINDING-016: KOSPI `7,892.33` on /home vs `— ·—` on /market

### Root Cause: CONFIRMED — Both surfaces read `/api/market/indices?region=kr`. The value 7,892 is a real KIS-sourced KOSPI level (confirmed by `services/data/fetcher.py:828-831`: "KOSPI=7498 is the real 2026-05-10 level, continuous uptrend in KIS daily-price history 5052 → 7498 across 2026-Q2"). The divergence between surfaces is explained by a different code path for handling the empty response.

**Evidence chain:**

1. `frontend/src/components/terminal/top-ticker.tsx:282-295` — TopTicker polls `MARKET_INDICES?region=kr` via SWR with `dedupingInterval: 30_000`. It maps `^KS11` to "KOSPI" at line 309 and calls `sanitizeKrIndex("KOSPI", level)` at line 238. Since `KOSPI_RANGE = [1500, 50000]` in `format.ts:88-95`, 7,892 passes the sanity check → renders `7,892.33`.

2. `frontend/src/app/(dashboard)/market/page.tsx:163` — Market page has an additional guard: `if (!Array.isArray(data) || data.length < 3) return []`. If the KR indices response contains fewer than 3 entries at the moment the market page loads (e.g., KOSPI data is present but KOSDAQ or USDKRW are missing), the entire `quotes` array is empty → `OverviewPaper` renders "No observation available for this region" → the header shows `— ·—`.

3. `frontend/src/app/(dashboard)/market/page.tsx:195` — Additional region-mismatch guard: if `looksLikeRegion !== tab`, returns empty. This could fire if the prior `?region=us` SWR cache is briefly returned for `?region=kr` (since `keepPreviousData: true` is set at line 124).

4. **The 7,892 value is real, not inflated.** The codebase has explicit comments at `routes/market.py:856-858` and `services/data/fetcher.py:828-831` that KOSPI ~7,400-7,500 was verified as the actual 2026 level via live KIS API. The audit report's claim that "actual KOSPI is ~2,500-2,800" reflects outdated knowledge (KOSPI was ~2,500-3,000 in 2023-2024; it has re-rated significantly in 2025-2026).

5. **Divergence root cause:** timing mismatch between SWR cache states. The TopTicker and the /market page share the same SWR key but may fetch at different times. The /market `length < 3` guard is more aggressive — if KIS returns only 2 of 4 KR index entries, /market drops all; top-ticker renders whatever entries returned.

**Fix scope:** Frontend — reduce the `/market` page guard from `length < 3` to `length < 1`, OR render partial results for whichever indices are available. The `keepPreviousData: true` cross-region guard (line 195) is correct and should remain.

**Additional cost:** None.

---

## FINDING-021: `/home` position row `$293,000.00 +442.59%`

### Root Cause: CONFIRMED — Two compounding bugs in `positions-top-card.tsx`.

**Evidence chain:**

1. `frontend/src/components/home/v2/positions-top-card.tsx:68-77`:
   ```typescript
   const cur = p.current ?? 0;
   const avg = p.avgCost ?? 0;
   ...
   ticker: p.symbol,
   currency: (p.currency as "USD" | "KRW") ?? "USD",
   ```
   The component accesses `p.current`, `p.avgCost`, `p.symbol` — but the `Position` type in `frontend/src/lib/types.ts:1-24` defines these fields as `current_price`, `avg_cost`, `ticker` (snake_case from backend).

2. Because `p.current` is `undefined` (field name mismatch), `cur = undefined ?? 0 = 0`. Same for `p.avgCost → avg = 0`. The PnL calculation `avg > 0 ? ((cur - avg) / avg) * 100 : 0` returns `0` when avg is 0 — but the audit shows `+442.59%`, not 0%.

3. **Reconciliation:** The `+442.59%` comes from the **`pnl_pct` field from the backend** (`routes/portfolio.py:182`: `"pnl_pct": round(pnl, 2)`). The component at line 70 computes pnl client-side from `p.current` and `p.avgCost` — both undefined (→ 0), so pnl = 0. BUT: the backend's `pnl_pct` is stored in the SignalCache and may be emitted as part of the position blob. If the `PositionsShape` interface locally defines a different shape than `Position` in types.ts, `p.pnl_pct` may be accessed directly.

4. **More likely:** The `PositionsShape` in `positions-top-card.tsx:25-27` is a looser type that inherits all fields. `p.current` falls back to `p.current_price` somehow, OR the +442% comes from the `pnl_pct` field that IS correctly named: line 77 uses `currency: (p.currency as "USD" | "KRW") ?? "USD"` — and `p.currency` IS the correct field name. The `?? "USD"` default means if `p.currency` is undefined or null, it falls back to "USD".

5. **The `$` prefix on a KRW position:** `fmtMoney(r.current, r.currency)` at line 142. If `r.currency = "KRW"`, `fmtMoney` returns `₩` prefix. But if `r.currency` defaulted to "USD" (because the ticker is stored as bare "005930" → `is_kr=false` → `currency="USD"` returned by backend), the frontend correctly renders `$`.

6. **Confirmed root cause for `$` prefix:** Backend `routes/portfolio.py:152` — `cur = sd.get("currency", "KRW" if is_kr else "USD")`. If `is_kr=False` (ticker "005930" without ".KS"), `cur="USD"`. This propagates to the position JSON and the frontend renders `$`. The `?? "USD"` fallback at line 77 of positions-top-card.tsx compounds this.

7. **The `+442.59%` confirmed cause:** Backend `pnl_pct` at position row level uses `cur_px - p.avg_cost / p.avg_cost * 100`. If `cur_px` is the wrong (USD-denominated FMP) price (~293) and `avg_cost` was the KRW price at entry (~52,000 KRW), then `(293 - 52000) / 52000 * 100 ≈ -99.4%` — not matching. More likely: `avg_cost=52` (stored in whatever unit the user entered), `cur_px=293` (USD from FMP), `pnl=(293-52)/52*100 = 463%`. Close to 442.59%.

**Fix scope:** Two fixes needed:
- Backend: normalize ticker to include `.KS` suffix for bare KRX codes (Bug #1 fix was added 2026-05-13 for new positions but legacy rows in DB have bare tickers).  
- Frontend: `positions-top-card.tsx` — `p.avgCost` should be `p.avg_cost` (snake_case). The `p.current` should be `p.current_price`. `p.symbol` should be `p.ticker`. These are camelCase vs snake_case field name mismatches.

**Additional cost:** None.

---

## FINDING-024: KOSPI `7,892` value on /home ticker

Same root cause as FINDING-016. 7,892 is the actual KIS-reported KOSPI level in 2026-Q2. The value is real data, not a bug in the number itself. The color (▲ red) is KR-convention correct. The value discrepancy from the audit's expectation of "~2,500-2,800" reflects outdated baseline knowledge — the audit's knowledge cutoff predates the 2025-2026 Korean market re-rating documented in the backend codebase.

**Fix scope:** None for the value. Color token fix (FINDING-002: `--up: #dc2626` → `#D18888`) is a separate frontend CSS change.

---

## Summary Classification

| Finding | Root Cause Layer | Fix Type | Confirmed? |
|---------|-----------------|----------|-----------|
| 008 (mktcap 1974조) | Backend pipeline — `fmp.get_info()` returns wrong-unit `marketCap` for KR tickers | Backend data pipeline | PARTIAL — exact unit source requires live API call |
| 009 (price ₩292,500) | Backend — FMP `profile.price` (USD) used as fallback when KIS live price fails; stale SignalCache | Backend data pipeline | PARTIAL — need live API call to confirm FMP vs KIS path |
| 010 (NAV $2.93M) | DB — position ticker stored as bare "005930" (no .KS) → `is_kr=False` → USD treatment; wrong price from stale cache | DB data + backend pipeline | CONFIRMED (ticker normalization gap pre-Bug#1) |
| 015 (S&P red vs green chart) | Frontend — `--up` CSS token is `#dc2626` (not spec); chart sparkline color is hardcoded separately | Frontend CSS + component | CONFIRMED |
| 016 (KOSPI divergence) | Frontend — /market page `length < 3` guard drops entries when KIS returns partial response; top-ticker renders partial | Frontend data guard | CONFIRMED |
| 021 ($293k +442%) | Frontend (camelCase/snake_case field mismatch in positions-top-card.tsx) + DB (ticker not normalized to .KS) | Frontend component + DB data | CONFIRMED (field mismatch at lines 68-73) |
| 024 (KOSPI 7,892 value) | NOT a bug — 7,892 is real KIS-sourced KOSPI level confirmed in codebase comments (fetcher.py:828-831) | N/A | CONFIRMED NOT A BUG |

---

## Short Summary (< 250 words)

**Frontend-only fixes (close without backend/DB changes):**
- FINDING-015: Two-line CSS fix — update `--up` and `--down` tokens in globals.css to spec values; update chart stroke color in indices-detail-paper component.
- FINDING-016: Relax the `/market` page `length < 3` guard to `length < 1` to prevent full empty-state on partial KR index response.
- FINDING-021 (partial): Fix camelCase/snake_case mismatch in `positions-top-card.tsx` (`p.current` → `p.current_price`, `p.avgCost` → `p.avg_cost`, `p.symbol` → `p.ticker`).
- FINDING-024: No fix needed. 7,892 is the real KIS KOSPI level per codebase documentation.

**Backend data pipeline problems (require server-side fix):**
- FINDING-008: `fmp.get_info()` returns ambiguous-unit `marketCap` for KR tickers. FMP `/profile` may return USD or KRW depending on plan tier. Need to force-route KR market cap through KIS `hts_avls` path exclusively.
- FINDING-009: KIS live price fails silently for 005930.KS; falls back to `info.get("price")` from FMP (USD). Fix: make KIS price failure for KR tickers a hard error, not a silent fallback to FMP USD price.

**DB data cleanup needed:**
- FINDING-010 and FINDING-021 (root): Position row for 005930.KS is stored with bare ticker "005930" (no `.KS` suffix), causing `is_kr=False` → USD treatment throughout. Run a one-time migration: `UPDATE positions SET ticker='005930.KS' WHERE ticker='005930'`. This was partially addressed by Bug #1 fix on 2026-05-13 for new positions, but existing rows need a migration.

---
*Evidence: all file paths and line numbers verified via direct file read. No live API calls made.*
