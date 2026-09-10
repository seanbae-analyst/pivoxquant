"""Headline index snapshots — the upstream fetch behind /api/market/indices.

Moved out of ``routes/market.py`` on 2026-09-10. That file held 1145 lines for
four routes; 659 of them were this — upstream fetching, per-provider fallback,
proxy disclosure and a market-aware cache. None of it is HTTP handling, and
CLAUDE.md's standing rule is that routes/ stays a routing layer.

The move is behaviour-preserving by construction: the functions came across
unmodified, ``_indices_cache`` is the same dict object every reader binds to
(callers mutate it, nobody rebinds it), and tests/test_indices_cache_warm.py
was written against the old location first so the same eighteen assertions
could be re-run here.

Two things a reader should not have to rediscover:

* ``_compute_indices_snapshot`` performs LIVE upstream calls. Anything that
  must stay cache-only — the public landing snapshot in particular — must go
  through the cache, never through this.
* KR index levels are gated behind ``KR_INDEX_KIS_ENABLED`` (SHIP_BLOCKERS
  R7). A KIS app key does not license redistributing KRX-derived levels to
  every user; that needs a KOSCOM/KRX 정보이용계약.
"""
from __future__ import annotations

import logging
import os
import time as _time
from datetime import datetime, timezone

from services import fx_service
from services.container import fetcher

logger = logging.getLogger(__name__)

# Market-aware cache for /api/market/indices. Intraday: 15s so the KOSPI /
# S&P tiles feel live. Off-hours: 300s so we don't spin upstreams while
# levels aren't moving. See services.cache_ttl.indices_ttl().
_indices_cache: dict = {}  # region -> {"ts": float, "data": [...]}
def _indices_ttl() -> int:
    try:
        from services.cache_ttl import indices_ttl
        return indices_ttl()
    except Exception:
        return 300
# US indices → liquid ETF proxies. FMP Starter and Alpaca both refuse to
# serve caret-prefixed index symbols (^GSPC, ^IXIC…). The ETFs track the
# indices within ±0.02% intraday, so level + 1d%change + 52W range +
# sparkline are all mathematically honest when published in ETF units.
# The UI renders a single number so the unit difference (SPY=$708 vs
# GSPC=5800) is invisible. Do NOT attempt a "ratio conversion" — the
# ratio drifts over time and would inject wrong values.
_US_INDEX_PROXY = {
    "^GSPC": ("SPY",  "S&P 500"),
    "^IXIC": ("QQQ",  "Nasdaq 100"),
    "^DJI":  ("DIA",  "Dow Jones"),
    "^RUT":  ("IWM",  "Russell 2000"),
    "^VIX":  ("VIXY", "Volatility (VIXY)"),
}
_KR_INDEX_SPEC = [
    # ticker,    display,       kis_code, macro_key
    ("^KS11",    "KOSPI",       "0001",   "kospi"),
    ("^KQ11",    "KOSDAQ",      "1001",   "kosdaq"),
    ("^KS200",   "KOSPI 200",   "2001",   None),
    ("^KQ150",   "KOSDAQ 150",  "2203",   None),
    # USDKRW handled separately via fx_service / macro
]
def _etf_snapshot(etf: str, display: str, ticker_alias: str) -> dict | None:
    """Build the standard index entry from a liquid ETF proxy.

    Uses the SAME fallback chain as ``/api/lookup/<ticker>`` — namely
    ``fetcher.quick_lookup`` (Alpaca realtime → FMP quote → FMP profile)
    for the live level, then ``fetcher.get_price_history`` (same engine
    as ``/api/chart/<ticker>``) for the sparkline + 52W range + the 1d%
    fallback when the live quote payload lacks it.

    Previous implementation used ``services.data.alpaca_market_adapter.get_quote``
    which hits Alpaca's ``get_stock_bars`` daily endpoint — on the free IEX
    tier this returns empty bars for many sessions and silently drops the
    whole index payload (regression #80c7d26). The ``/api/lookup`` path
    already survives that case via Alpaca realtime trade/quote/bar →
    FMP → FMP profile chain, so we reuse it verbatim.

    Returns None only when BOTH live quote AND history are unavailable —
    partial data is more honest than hardcoded mocks.
    """
    level: float | None = None
    # `None` (not 0.0) when the daily change cannot be derived: emitting a
    # fabricated "+0.00%" reads as a real "no change" datapoint. Same
    # data-honesty contract as `range_52w` above — the frontend renders
    # null as "—" (lib/format.ts::fmtPct, 자본시장법 §101 guard).
    change_pct: float | None = None

    # 1) Live quote — identical code path as /api/lookup/<ticker>.
    try:
        q = fetcher.quick_lookup(etf)
        if q and q.get("price"):
            level = float(q["price"])
    except Exception as e:
        logger.debug("market.indices lookup %s failed: %s", etf, e)

    # 2) History for sparkline + 52W + fallback level / change.
    #    Same engine as /api/chart/<ticker>?period=1y.
    sparkline: list[float] = []
    range_52w: list[float] | None = [0.0, 0.0]
    is_stale = False
    closes = None
    try:
        h = fetcher.get_price_history(etf, period="1y")
        if h is not None and not h.empty and "Close" in h.columns:
            c = h["Close"].astype(float).dropna()
            if len(c):
                closes = c
    except Exception as e:
        logger.debug("market.indices history %s failed: %s", etf, e)

    # Staleness guard (same policy as `_kis_index_snapshot`): reject any
    # history whose tail diverges from the live level by >30%. Protects
    # against FMP returning year-old data on Starter-tier quiet windows.
    if closes is not None and len(closes) and level is not None and level > 0:
        last_hist = float(closes.iloc[-1])
        if abs(last_hist - level) / level > 0.30:
            logger.warning(
                "market.indices %s (%s) history stale: tail=%.2f vs "
                "live level=%.2f — discarding series",
                ticker_alias, etf, last_hist, level,
            )
            closes = None
            is_stale = True

    if closes is not None and len(closes):
        if level is None:
            level = float(closes.iloc[-1])
        if len(closes) >= 2:
            prev = float(closes.iloc[-2])
            if prev:
                last = float(closes.iloc[-1])
                # Prefer history-derived change: even when live quote
                # has a value, lookup doesn't surface a d/d%, so
                # closes.iloc[-1]/[-2] is our only source.
                change_pct = (last - prev) / prev * 100.0
        sparkline = [round(float(v), 4) for v in closes.tail(30).tolist()]
        range_52w = [round(float(closes.min()), 2),
                     round(float(closes.max()), 2)]
    else:
        sparkline = []
        range_52w = None

    if level is None:
        return None  # truly nothing to show — caller skips this entry

    return {
        "ticker":        ticker_alias,
        "proxy_ticker":  etf,
        "name":          display,
        "level":         round(level, 2),
        "change_1d_pct": round(change_pct, 2) if change_pct is not None else None,
        "range_52w":     range_52w,
        "sparkline_30d": sparkline,
        "observed_at":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "is_stale":      is_stale,
    }
def _kis_index_snapshot(kis_code: str, ticker: str, display: str) -> dict | None:
    """Build standard index entry from a KIS index code.

    Strategy mirrors ``_etf_snapshot``: live KIS quote if available,
    otherwise fall back to price history for level + sparkline + 52W.
    Many KIS index codes (2001/2203) lack historical endpoints so
    sparkline may be empty, but we still return a valid entry as long as
    EITHER the KIS quote OR the history engine produced a level.
    """
    level: float | None = None
    # `None` (not 0.0) when the daily change cannot be derived: emitting a
    # fabricated "+0.00%" reads as a real "no change" datapoint. Same
    # data-honesty contract as `range_52w` above — the frontend renders
    # null as "—" (lib/format.ts::fmtPct, 자본시장법 §101 guard).
    change_pct: float | None = None

    # Candidate KIS index codes. KIS's `inquire-index-price` endpoint is
    # documented with 0001/1001 for KOSPI/KOSDAQ and 2001/2203 for
    # KOSPI200/KOSDAQ150 — but the 2xxx codes have been observed returning
    # rt_cd!=0 on the Starter plan. When the primary code yields no data we
    # retry a known alternate (some regional docs use "201"/"301"). First
    # non-empty hit wins.
    _kis_code_candidates = {
        "2001": ["2001", "0201"],   # KOSPI 200 alternatives
        "2203": ["2203", "1150"],   # KOSDAQ 150 alternatives
    }.get(kis_code, [kis_code])

    # 1) Live KIS quote (best — includes native d/d%).
    # Bug D (2026-04-24): previously gated on `_rt.kis_available`, but that
    # flag is a realtime-service-side init signal that can go False during a
    # restart window even when the KIS keys are valid. KISService.__init__
    # performs its own credential check (see `self.available` in
    # kis_service.py) so we always *attempt* KIS here and let the service
    # short-circuit internally. Keeps the KR-indices tiles alive when
    # realtime init is briefly degraded.
    kis_level_raw: float | None = None      # raw KIS level for diagnostic
    kis_passed_sanity: bool = False         # did KIS level pass per-ticker bounds?
    try:
        from services.kis.service import KISService
        _svc = KISService()
        for _code in _kis_code_candidates:
            idx = _svc.get_index_price(_code)
            if idx and idx.get("price"):
                level = float(idx["price"])
                kis_level_raw = level
                change_pct = float(idx.get("change_pct") or 0)
                if _code != kis_code:
                    logger.info(
                        "market.indices KIS primary code %s empty; "
                        "resolved via alternate %s", kis_code, _code,
                    )
                break
    except Exception as e:
        logger.debug("market.indices KIS %s failed: %s", kis_code, e)

    # 2) History for sparkline + 52W + fallback level / change.
    #
    # KR-index history source policy (2026-04-24, fix for BUG #RANGE-STALE):
    #   KIS *live* quote is authoritative for `level` (e.g., KOSPI 6475.63
    #   matches Yahoo/Investing). FMP `^KS11`/`^KQ11` history is known to
    #   lag by quarters on the Starter plan — using it for sparkline/range
    #   while `level` is KIS-live produced self-contradictory payloads
    #   where `level > sparkline.max()` by >2x and `range_52w[1] < level`.
    #
    # New policy: for KR indices we *prefer KIS* `inquire-index-daily-price`
    # (FHPUP02120000) since it shares units with the live quote. FMP is
    # only used as a fallback, and any FMP series whose tail diverges from
    # the live level by more than 30% is rejected as stale.
    sparkline: list[float] = []
    range_52w: list[float] | None = [0.0, 0.0]
    closes = None
    hist_source = None  # "kis" | "fmp" | None — for logging + stale guard
    is_stale = False

    # 2a) KIS history FIRST (unit-consistent with live quote).
    # Bug D (2026-04-24): attempt KIS directly without the realtime-side
    # `kis_available` gate — KISService has its own credential check and
    # returns None cleanly when keys are missing. The prior gate hid the
    # history endpoint whenever realtime init was degraded, sending us to
    # the unit-divergent FMP path.
    try:
        from services.kis.service import KISService
        _svc = KISService()
        for _code in _kis_code_candidates:
            hist = _svc.get_index_history(_code, period="1y")
            if hist:
                vals = [float(row.get("close"))
                        for row in hist
                        if row and row.get("close") is not None]
                if vals:
                    import pandas as _pd
                    closes = _pd.Series(vals)
                    hist_source = "kis"
                    break
    except Exception as e:
        logger.debug("market.indices KIS history %s failed: %s", kis_code, e)

    # 2b) FMP fallback ONLY when KIS history unavailable.
    if closes is None or len(closes) == 0:
        try:
            h = fetcher.get_price_history(ticker, period="1y")
            if h is not None and not h.empty and "Close" in h.columns:
                c = h["Close"].astype(float).dropna()
                if len(c):
                    closes = c
                    hist_source = "fmp"
        except Exception as e:
            logger.debug("market.indices fmp history %s failed: %s", ticker, e)

    # 2c) Staleness guard — source-aware (Bug B fix, 2026-05-13).
    #
    # The 30% divergence guard was originally added (PR #196) to protect
    # against FMP caret-prefixed KR index tickers on the Starter tier
    # serving year-old snapshots. In 2026-Q2 the Korean market re-rated
    # sharply (KOSPI 5,052 → 7,643, verified via PR #234 B-06 live KIS
    # probe), which the 30% guard incorrectly flagged as stale because
    # `tail(history) vs live` exceeded 30% for completely legitimate
    # monotonic uptrends — silently discarding real KIS data and
    # producing the empty-sparkline / null-range_52w symptom CEO saw
    # on 2026-05-12.
    #
    # Fix: trust KIS daily-history (broker-issued, unit-consistent with
    # the live KIS quote — confirmed via B-06). Keep the divergence
    # guard only for non-KIS history sources (FMP today, future
    # providers). For KIS we still flag is_stale when the live level
    # disagrees with the tail in a way that *cannot* be explained by a
    # monotonic uptrend (allows down-trend stale detection too).
    if closes is not None and len(closes) and level is not None:
        last_hist = float(closes.iloc[-1])
        divergence = abs(last_hist - level) / level if level > 0 else 0.0
        if hist_source == "kis":
            # KIS is trustworthy: only flag stale on extreme unit-confusion
            # (100% = 2x apart, which is what a 0001-vs-0001-x-3 quirk
            # would produce). Sanity bound below catches pure unit errors;
            # this layer catches subtler stale-cache anomalies.
            if divergence > 1.0:
                logger.warning(
                    "market.indices %s KIS history extreme divergence: "
                    "tail=%.2f vs live=%.2f (%.1f%%) — discarding",
                    ticker, last_hist, level, divergence * 100.0,
                )
                closes = None
                is_stale = True
        else:
            # Non-KIS (FMP / future): keep 30% guard.
            if divergence > 0.30:
                logger.warning(
                    "market.indices %s history (%s) stale: tail=%.2f vs "
                    "live level=%.2f (diff %.1f%%) — discarding series",
                    ticker, hist_source or "?", last_hist, level,
                    divergence * 100.0,
                )
                closes = None
                is_stale = True

    if closes is not None and len(closes):
        if level is None:
            level = float(closes.iloc[-1])
        if change_pct == 0.0 and len(closes) >= 2:
            prev = float(closes.iloc[-2])
            if prev:
                change_pct = (float(closes.iloc[-1]) - prev) / prev * 100.0
        sparkline = [round(float(v), 4) for v in closes.tail(30).tolist()]
        range_52w = [round(float(closes.min()), 2),
                     round(float(closes.max()), 2)]

        # Bug #2 (2026-05-14): stale-window cross-validation.
        #
        # Phase-0 finding: the KIS "0001" current level (~7,981 on
        # 2026-05-14) is REAL — KOSPI hit an all-time high ~7,844 on
        # 2026-05-13 (AI-chip rally, +31% MoM). There is NO 3x scaling
        # bug; the wide sanity bounds are correct and must NOT be
        # tightened (a 4,500 ceiling would reject the real index).
        #
        # The genuine defect: KIS's `inquire-index-daily-price` endpoint
        # lags — on 2026-05-14 its newest row was 2026-04-14 (5,967.75),
        # a full month behind the live quote. The history is internally
        # consistent (a legitimate uptrend), just from an older window.
        # When `level` sits well above the whole sparkline, the frontend
        # would draw a chart whose every point is below the headline
        # number — visually a "contradiction" even though both values
        # are real. This is the symptom the live bug-hunt flagged.
        #
        # Fix: when the live level exceeds the sparkline max by >15%,
        # tag `is_stale=true` so the consumer can suppress / annotate
        # the lagging chart. We keep the real `level` and the real
        # (stale) sparkline — no data is discarded, the consumer just
        # gets an honest staleness signal.
        #
        # 2026-05-15 (bug-hunter P1 follow-up): when staleness is
        # detected, ALSO null out `range_52w`. Reason — the historical
        # `closes.min()/.max()` come from the lagging KIS daily-history
        # window (e.g. 2,293–2,671 for KOSPI as of mid-April) while the
        # live `level` (e.g. 7,619 mid-May) is from a different time
        # window. Co-emitting them produces a level OUTSIDE its own
        # stated 52W range — an obviously-broken UI signal regardless
        # of which scale is "real". `level` and `sparkline` stay (the
        # frontend can render the chart with stale dimming + the level
        # alongside) but the standalone 52W summary is suppressed to
        # avoid the contradiction. Frontend renders "N/A" on null
        # range — same code path already used when history is missing
        # entirely (the `else` branch immediately below). Capital-
        # markets-law misrepresentation guard: showing a 52W range
        # narrower than the current level is implicit "all-time high"
        # framing the data doesn't support.
        if level is not None and sparkline:
            spark_max = max(sparkline)
            spark_min = min(sparkline)
            if spark_max > 0 and level > spark_max * 1.15:
                logger.info(
                    "market.indices %s: live level %.2f exceeds sparkline "
                    "max %.2f by >15%% — KIS daily-history window lags the "
                    "live quote; tagging is_stale + suppressing range_52w",
                    ticker, level, spark_max,
                )
                is_stale = True
                range_52w = None
            # 2026-05-21: symmetric DOWNWARD guard. The upward check above
            # only caught a level ABOVE the sparkline. A lagging KIS history
            # window can also leave the live level BELOW the historical
            # range_52w floor (e.g. KOSDAQ 150 "2203": level 1,875.52 vs
            # range_52w [2,041.65, 2,483.80] → level outside its own stated
            # range, is_stale silently false). 0.85 mirrors the 1.15 upper
            # band. Same remediation: tag is_stale + suppress the
            # contradictory range_52w so the frontend renders "N/A".
            elif spark_min > 0 and level < spark_min * 0.85:
                logger.info(
                    "market.indices %s: live level %.2f sits below sparkline "
                    "min %.2f by >15%% — KIS daily-history window lags the "
                    "live quote; tagging is_stale + suppressing range_52w",
                    ticker, level, spark_min,
                )
                is_stale = True
                range_52w = None
    else:
        # No trustworthy history — return null range so the frontend
        # renders "N/A" rather than [0.0, 0.0] (which the bar chart
        # would otherwise draw as a degenerate point).
        sparkline = []
        range_52w = None

    # Per-ticker sanity bounds. These exist only to catch gross unit
    # confusion (e.g. KOSPI returned as 749,800 — a 100x scaling glitch),
    # NOT to second-guess a high-but-real index level.
    #
    # 2026-05-14 (Bug #2 Phase-0, DEFINITIVE): the KIS "0001" level of
    # ~7,981 IS the real KOSPI. Confirmed against external press
    # (KOSPI all-time high ~7,844 on 2026-05-13; +31% MoM, +197% YoY on
    # the AI-chipmaker rally). The earlier "~3x scaled KOSPI-200" and
    # "real index trades 2,500–3,200" comments were a WRONG hypothesis —
    # they have been removed to stop misleading future readers. KIS
    # `0001` live and KIS `0001` daily-history are the same product;
    # the only real defect is the daily-history endpoint lagging by ~1
    # month (handled by the is_stale tag above). Bounds stay wide.
    _PER_TICKER_BOUNDS = {
        "^KS11":  (1_500.0, 50_000.0),  # KOSPI composite — head-room to 50k
        "^KQ11":  (500.0,   50_000.0),  # KOSDAQ composite
        "^KS200": (300.0,   10_000.0),  # KOSPI 200
        "^KQ150": (500.0,   10_000.0),  # KOSDAQ 150
    }
    lo, hi = _PER_TICKER_BOUNDS.get(ticker, (100.0, 50_000.0))

    def _in_bound(v: float | None) -> bool:
        return v is not None and lo <= v <= hi

    kis_passed_sanity = _in_bound(level)

    # 2026-05-09 P0 graceful-degradation: when the KIS-derived level either
    # is missing or fails the per-ticker sanity bound (the dominant failure
    # mode is the KIS `0001`/`2001`/`2203` unit/code quirk that returns
    # values like 7498 for KOSPI — see PR #188), attempt FMP as a fallback
    # source for the live level. Sanity bound is then *re-applied* to the
    # FMP value — only realistic values surface, so the defensive guard
    # introduced by PR #188 is fully preserved.
    #
    # KNOWN LIMITATION (recorded for parent agent on 2026-05-09): on the
    # current FMP Premium ($29) plan, caret-prefixed KR index symbols
    # (`^KS11`, `^KQ11`, `^KS200`, `^KQ150`) all return HTTP 402 from both
    # `/quote` and `/historical-price-eod/full`. This fallback path is
    # therefore architectural — it engages cleanly the moment FMP's plan
    # permits index symbols (or an alternate symbol mapping is added).
    # On today's plan the entry remains dropped when KIS sanity fails;
    # behavior matches PR #188 for the failing tickers.
    if not kis_passed_sanity:
        try:
            from services.data import fmp as _fmp
            q = _fmp.get_quote(ticker)
            if q and q.get("price"):
                fmp_price = float(q["price"])
                if _in_bound(fmp_price):
                    logger.info(
                        "market.indices %s: KIS level %s sanity-failed "
                        "(bound [%.0f,%.0f]); FMP fallback succeeded with "
                        "%.2f",
                        ticker,
                        f"{kis_level_raw:.2f}" if kis_level_raw is not None
                        else "missing",
                        lo, hi, fmp_price,
                    )
                    level = fmp_price
                    # Prefer FMP-derived d/d% when present, otherwise keep
                    # whatever change_pct we already had (KIS or 0).
                    fmp_change = q.get("changesPercentage") or q.get("change_pct")
                    if fmp_change is not None:
                        try:
                            change_pct = float(fmp_change)
                        except (TypeError, ValueError):
                            pass
                    # Re-validate any sparkline/range derived from the
                    # earlier (sanity-failed) level. The 30% staleness
                    # check at line ~781 ran against the bogus KIS level —
                    # a series that "passed" relative to KIS 7498 may now
                    # diverge wildly from the trustworthy FMP 2540. Drop
                    # those artifacts so we don't render
                    # level=2540 / range_52w=[5700,6800] together.
                    if sparkline:
                        spark_max = max(sparkline) if sparkline else 0.0
                        spark_min = min(sparkline) if sparkline else 0.0
                        # If either end of the series is outside the
                        # per-ticker sanity bound, the series came from the
                        # KIS-quirk path and must not co-exist with the
                        # FMP-derived level. Discard.
                        if not (_in_bound(spark_max) and _in_bound(spark_min)):
                            logger.warning(
                                "market.indices %s: sparkline/range from "
                                "pre-fallback path (min=%.2f max=%.2f) "
                                "incompatible with FMP level %.2f — "
                                "discarding history series",
                                ticker, spark_min, spark_max, fmp_price,
                            )
                            sparkline = []
                            range_52w = None
                            is_stale = True
                else:
                    logger.warning(
                        "market.indices %s: FMP fallback level %.2f also "
                        "outside sanity bound [%.0f,%.0f] — dropping",
                        ticker, fmp_price, lo, hi,
                    )
        except Exception as e:
            logger.debug(
                "market.indices %s FMP fallback failed: %s", ticker, e,
            )

    if level is None:
        return None

    if not _in_bound(level):
        logger.warning(
            "market.indices %s level %.2f outside sanity bound [%.0f,%.0f]; "
            "dropping entry (KIS quirk + no FMP fallback available)",
            ticker, level, lo, hi,
        )
        return None

    return {
        "ticker":        ticker,
        "name":          display,
        "level":         round(level, 2),
        "change_1d_pct": round(change_pct, 2) if change_pct is not None else None,
        "range_52w":     range_52w,
        "sparkline_30d": sparkline,
        "observed_at":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "is_stale":      is_stale,
    }
def _compute_indices_snapshot(region: str) -> list[dict]:
    """Live-fetch the headline index snapshot list for ``region``.

    Extracted from ``market_indices`` so the same upstream-fetch path can
    be reused by the background cache-warm scheduler job (see
    ``warm_indices_cache``). Performs live upstream calls — callers that
    must stay cache-only (e.g. the public landing snapshot) MUST NOT call
    this directly.

    Sources:
        - US: Alpaca ETF proxies (SPY/QQQ/DIA/IWM/VIXY) — FMP refuses
          index symbols on Starter tier and Alpaca does not serve raw ^GSPC.
        - KR: KIS index API for KOSPI/KOSDAQ (codes 0001/1001) and
          KOSPI200/KOSDAQ150 (codes 2001/2203); fx_service / macro for USD/KRW.
        - Partial failure: skip the failing ticker. Never mock.

    Returns the list of index snapshots (may be empty on total upstream
    failure). Does NOT touch ``_indices_cache`` — see ``warm_indices_cache``.
    """
    out: list[dict] = []

    if region == "us":
        for raw_ticker, (etf, display) in _US_INDEX_PROXY.items():
            snap = _etf_snapshot(etf, display, raw_ticker)
            if snap is not None:
                out.append(snap)
    else:
        # KR indices via KIS — GATED (SHIP_BLOCKERS R7). A KIS app-key does NOT
        # license commercial redistribution of KRX-derived index levels to all
        # users (KOSCOM/KRX 정보이용계약 required). Set KR_INDEX_KIS_ENABLED=0 to
        # stop serving the KIS index path (de-risk) until a licensed source
        # (금융위 공공데이터 T+1 / KOSCOM) is wired. Default "1" = current behavior,
        # so flipping this is a deliberate CEO/legal action — no prod change now.
        if os.environ.get("KR_INDEX_KIS_ENABLED", "1") not in ("0", "false", "False"):
            for raw_ticker, display, kis_code, _macro_key in _KR_INDEX_SPEC:
                snap = _kis_index_snapshot(kis_code, raw_ticker, display)
                if snap is not None:
                    out.append(snap)

        # USD/KRW — fx_service is always live (refreshed on app boot +
        # background tick). Fall back to macro payload if fx_service empty.
        usdkrw_level = None
        try:
            usdkrw_level = float(fx_service.get_rate() or 0) or None
        except Exception:
            usdkrw_level = None
        if usdkrw_level is None:
            try:
                macro = fetcher.get_enhanced_macro() or {}
                mv = macro.get("usdkrw") or {}
                if mv.get("price"):
                    usdkrw_level = float(mv["price"])
            except Exception:
                logger.debug("silent-fallback: market_indices", exc_info=True)
                pass
        if usdkrw_level:
            # Pull 1y FX history from FMP for sparkline + 52W range + d/d%.
            # fmp_service.get_history("USDKRW") returns a standard OHLCV
            # DataFrame; gracefully fall back to empty on any failure so a
            # history miss never drops the level tile.
            #
            # Symbol fallback ladder (2026-04-24):
            #   USDKRW  → FMP canonical. Empty on Starter tier during most
            #             windows.
            #   USDKRW=X → Yahoo-style alias; FMP sometimes resolves it.
            #   KRW=X    → Last-ditch inversion attempt.
            # If ALL three are empty, range_52w becomes None so the
            # frontend can render "N/A" instead of the buggy [0,0] hardcode.
            fx_change_pct: float | None = None
            fx_sparkline: list[float] = []
            fx_range_52w: list[float] | None = None
            fx_is_stale = False
            fx_closes = None
            try:
                from services.data import fmp as _fmp
                for _sym in ("USDKRW", "USDKRW=X", "KRW=X"):
                    try:
                        fx_hist = _fmp.get_history(_sym, period="1y")
                    except Exception:
                        fx_hist = None
                    if fx_hist is not None and not fx_hist.empty \
                            and "Close" in fx_hist.columns:
                        c = fx_hist["Close"].astype(float).dropna()
                        if len(c):
                            fx_closes = c
                            break
            except Exception as e:
                logger.debug("market.indices USDKRW history failed: %s", e)

            if fx_closes is not None and len(fx_closes):
                # Staleness guard mirrors the KR-index one: FMP USDKRW is
                # notorious for returning year-old tails during the Starter
                # plan's quiet windows. If the last close diverges from the
                # live rate by >10%, treat it as stale.
                last_fx = float(fx_closes.iloc[-1])
                if usdkrw_level > 0 and abs(last_fx - usdkrw_level) / usdkrw_level > 0.10:
                    logger.warning(
                        "market.indices USDKRW history stale: tail=%.2f "
                        "vs live level=%.2f — discarding series",
                        last_fx, usdkrw_level,
                    )
                    fx_closes = None
                    fx_is_stale = True

            if fx_closes is not None and len(fx_closes):
                if len(fx_closes) >= 2:
                    fx_prev = float(fx_closes.iloc[-2])
                    if fx_prev:
                        fx_change_pct = (
                            (float(fx_closes.iloc[-1]) - fx_prev)
                            / fx_prev * 100.0
                        )
                fx_sparkline = [
                    round(float(v), 4)
                    for v in fx_closes.tail(30).tolist()
                ]
                fx_range_52w = [
                    round(float(fx_closes.min()), 2),
                    round(float(fx_closes.max()), 2),
                ]

            out.append({
                "ticker":        "USDKRW",
                "name":          "USD / KRW",
                "level":         round(usdkrw_level, 2),
                "change_1d_pct": round(fx_change_pct, 2) if fx_change_pct is not None else None,
                "range_52w":     fx_range_52w,
                "sparkline_30d": fx_sparkline,
                "observed_at":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "is_stale":      fx_is_stale,
            })

    return out
def warm_indices_cache(region: str, *, force: bool = False) -> int:
    """Refresh ``_indices_cache[region+"_v2"]`` via a live upstream fetch.

    Shared by the ``/api/market/indices`` request path and the background
    APScheduler cache-warm job (``app._scheduled_indices_cache_warm``).

    TTL-gated: unless ``force`` is set, skips the upstream fetch when the
    cached entry is still within ``_indices_ttl()``. Because that TTL is
    itself market-aware (15s intraday / 300s off-hours via
    ``services.cache_ttl.indices_ttl``), a fixed-interval scheduler tick
    naturally fetches often during market hours and rarely off-hours —
    no separate market-hours branch needed here.

    Only caches non-empty results: caching a thin failure would lock
    readers into empty data for the whole window.

    Returns the number of index rows now cached for the region (0 when
    the upstream fetch failed and no prior entry exists).
    """
    region = (region or "us").lower()
    if region not in ("us", "kr"):
        region = "us"
    cache_key = f"{region}_v2"
    now = _time.time()
    entry = _indices_cache.get(cache_key)
    if not force and entry and now - entry["ts"] < _indices_ttl():
        return len(entry.get("data") or [])

    out = _compute_indices_snapshot(region)
    if out:
        _indices_cache[cache_key] = {"ts": now, "data": out}
        return len(out)
    # Upstream failed — leave any prior (possibly aged) entry in place.
    return len(entry.get("data") or []) if entry else 0
