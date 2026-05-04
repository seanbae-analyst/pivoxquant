"""Counterfactual ("What-If") Simulator — public, no-auth endpoint.

Computes "what would your investment be worth today?" for a historical
purchase of a single ticker. Supports one-time lump-sum and periodic
(weekly/monthly) DCA.

Endpoint:
    GET /api/simulate/counterfactual

This endpoint is intentionally PUBLIC (no auth) — it is a viral-growth
hook (see docs/regret-simulator-spec.md). Rate limit + TTL cache mitigate
abuse and upstream data-provider cost.

Language rules (자본시장법):
- Never emit BUY/SELL/HOLD labels.
- Never use the words "추천", "조언", "recommendation", "advice".
- All responses include a disclaimer payload.
"""
from __future__ import annotations

import logging
import math
import time as _time
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request

from services.fx_service import get_rate as _fx_get_rate
from services.fx_service import get_rate_at as _fx_get_rate_at
from services.name_resolver import resolve_stock_name

logger = logging.getLogger(__name__)

counterfactual_bp = Blueprint("counterfactual", __name__, url_prefix="/api/simulate")


# ── Disclaimers (자본시장법 필수) ───────────────────────────────────────────

DISCLAIMERS = [
    "과거 수익률이 미래 수익률을 보장하지 않습니다",
    "배당금 재투자, 세금, 거래 수수료는 반영되지 않습니다",
    "본 서비스는 정보 제공 도구이며 투자 추천 또는 조언이 아닙니다",
    "모든 투자 결정과 책임은 이용자 본인에게 있습니다",
]


# ── Tunables ────────────────────────────────────────────────────────────────

_MIN_AMOUNT = 1.0                         # 최소 투자금 (USD/KRW 공통)
_MAX_AMOUNT = 1_000_000_000.0             # 10억원 상한
_EARLIEST_DATE = date(1990, 1, 1)         # 1990년 이전 데이터 거부
_MAX_CHART_POINTS = 500                   # 응답 경량화
_CACHE_TTL = 3600                         # 1시간 (장 마감 후만 실제 갱신)
_VALID_RECURRING = {"none", "weekly", "monthly"}


# ── In-memory LRU-ish cache ─────────────────────────────────────────────────
# Key: (ticker, start_date, amount, recurring) → {data, ts}
# NOTE: cache is per-process; acceptable for single-worker gunicorn on
# Railway. Swap to Redis when migrating to multi-worker.
_counterfactual_cache: dict[tuple, dict] = {}


def _cache_get(key: tuple):
    entry = _counterfactual_cache.get(key)
    if not entry:
        return None
    if _time.time() - entry["ts"] >= _CACHE_TTL:
        return None
    return entry["data"]


def _cache_set(key: tuple, data: dict):
    # Bound cache size — simple FIFO trim to 500 entries
    if len(_counterfactual_cache) > 500:
        oldest = min(_counterfactual_cache.items(), key=lambda kv: kv[1]["ts"])[0]
        _counterfactual_cache.pop(oldest, None)
    _counterfactual_cache[key] = {"data": data, "ts": _time.time()}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _is_korean(ticker: str) -> bool:
    t = (ticker or "").upper()
    return t.endswith(".KS") or t.endswith(".KQ")


def _period_for_years(years: float) -> str:
    """Map an elapsed-year count to the closest supported `period` key
    understood by data_fetcher.get_price_history()."""
    if years <= 1.0:
        return "1y"
    if years <= 2.0:
        return "2y"
    if years <= 3.0:
        return "3y"
    if years <= 5.0:
        return "5y"
    # period_map in data_fetcher/fmp caps at 5y. For older windows we
    # fall back to direct-source fetch with explicit from/to — see
    # _fetch_history_long().
    return "5y"


def _fetch_history_long(ticker: str, start: date):
    """Fetch historical daily OHLCV from start-date to today.

    - For windows ≤ 5 years → delegate to data_fetcher (respects cache,
      multi-source fallback).
    - For windows > 5 years → hit FMP directly with explicit from/to
      since the shared get_price_history API tops out at '5y' string
      key. FMP Starter tier supports back to IPO for US names.
    """
    from services.container import fetcher

    years = (date.today() - start).days / 365.25
    if years <= 5.0:
        return fetcher.get_price_history(ticker, period=_period_for_years(years))

    # Long-window path — skip the period-string indirection.
    # Prefer FMP (has deep history) for both US + KR.
    try:
        from services.data import fmp as fmp
        import pandas as pd
        from_date = start.strftime("%Y-%m-%d")
        to_date = date.today().strftime("%Y-%m-%d")
        data = fmp._fmp_get("/historical-price-eod/full", {
            "symbol": ticker, "from": from_date, "to": to_date,
        })
        if not data:
            return fetcher.get_price_history(ticker, period="5y")
        records = data.get("historical", data) if isinstance(data, dict) else data
        if not isinstance(records, list) or not records:
            return fetcher.get_price_history(ticker, period="5y")
        df = pd.DataFrame(records)
        col_map = {
            "date": "Date", "open": "Open", "high": "High",
            "low": "Low", "close": "Close", "adjClose": "Adj Close",
            "volume": "Volume",
        }
        df = df.rename(columns=col_map)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date").sort_index()
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col not in df.columns:
                df[col] = 0
        return df
    except Exception as e:
        logger.warning("long-window fetch failed %s: %s", ticker, e)
        return fetcher.get_price_history(ticker, period="5y")


def _parse_date(s: str) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        logger.debug("silent-fallback: _parse_date", exc_info=True)
        return None


def _error(code: str, message: str, http: int = 400, suggestion: dict | None = None):
    body = {
        "success": False,
        "error": message,
        "error_code": code,
        "disclaimers": DISCLAIMERS,
    }
    if suggestion:
        body["suggestion"] = suggestion
    return jsonify(body), http


def _safe_float(v) -> float | None:
    try:
        f = float(v)
        if not math.isfinite(f):
            return None
        return f
    except (TypeError, ValueError):
        logger.debug("silent-fallback: _safe_float", exc_info=True)
        return None


# ── Core simulation ─────────────────────────────────────────────────────────

def _iter_buy_dates(start: date, end: date, recurring: str):
    """Yield scheduled buy dates between start (inclusive) and end (inclusive).

    For "weekly" → every 7 days from start.
    For "monthly" → same day-of-month each month.
    For "none" → only start.
    """
    if recurring == "none":
        yield start
        return

    cur = start
    yield cur

    if recurring == "weekly":
        while True:
            cur = cur + timedelta(days=7)
            if cur > end:
                return
            yield cur

    if recurring == "monthly":
        while True:
            # add roughly one month preserving day when possible
            y, m = cur.year, cur.month + 1
            if m > 12:
                y, m = y + 1, 1
            d = min(cur.day, _days_in_month(y, m))
            cur = date(y, m, d)
            if cur > end:
                return
            yield cur


def _days_in_month(y: int, m: int) -> int:
    if m == 12:
        return (date(y + 1, 1, 1) - date(y, 12, 1)).days
    return (date(y, m + 1, 1) - date(y, m, 1)).days


def _next_trading_day_index(dates_sorted, target: date) -> int | None:
    """Binary search for first date >= target in an already-sorted list of
    python `date` objects. Returns index or None if none exists."""
    lo, hi = 0, len(dates_sorted)
    while lo < hi:
        mid = (lo + hi) // 2
        if dates_sorted[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    if lo >= len(dates_sorted):
        return None
    return lo


def _downsample(chart: list[dict], max_points: int) -> list[dict]:
    """Uniform stride downsampling, preserving first + last + every buy
    point (buy_point: True). Budget‐soft: may exceed max_points by small
    delta if buys are dense."""
    if len(chart) <= max_points:
        return chart
    # Always keep points where buy_point is True
    must_keep = {i for i, p in enumerate(chart) if p.get("buy_point")}
    must_keep.add(0)
    must_keep.add(len(chart) - 1)

    budget = max_points - len(must_keep)
    if budget <= 0:
        return [chart[i] for i in sorted(must_keep)]

    stride = max(1, (len(chart) - len(must_keep)) // budget)
    selected = set(must_keep)
    for i in range(0, len(chart), stride):
        selected.add(i)
    return [chart[i] for i in sorted(selected)]


def _compute_shares_series(hist, start: date, amount: float, recurring: str):
    """Walk the historical dataframe and compute shares held, invested
    total, and per-day portfolio value.

    Args:
        hist: pandas DataFrame indexed by Date with a 'Close' column
            (already sorted ascending by date).
        start: first purchase date requested.
        amount: size (in the ticker's native currency) of each buy.
        recurring: "none" | "weekly" | "monthly".

    Returns:
        (chart_data, total_invested, total_shares, first_buy_price,
         first_buy_actual_date) — or (None, None, None, None, None) if
        data is insufficient.
    """
    if hist is None or hist.empty:
        return None, None, None, None, None

    # Normalize dates (may be pandas Timestamp → date)
    try:
        idx_dates = [d.date() if hasattr(d, "date") else d for d in hist.index]
    except Exception:
        return None, None, None, None, None

    if not idx_dates:
        return None, None, None, None, None

    closes = [float(c) for c in hist["Close"].tolist()]
    if not closes or closes[0] <= 0:
        return None, None, None, None, None

    end_date = idx_dates[-1]

    # Pre-compute scheduled buy dates
    scheduled = list(_iter_buy_dates(start, end_date, recurring))
    # Map each scheduled date to the next available trading-day index
    buy_indices: dict[int, int] = {}       # idx → number of scheduled buys on that idx
    for sd in scheduled:
        if sd > end_date:
            break
        idx = _next_trading_day_index(idx_dates, sd)
        if idx is None:
            continue
        buy_indices[idx] = buy_indices.get(idx, 0) + 1

    if not buy_indices:
        return None, None, None, None, None

    first_buy_idx = min(buy_indices.keys())
    first_buy_price = closes[first_buy_idx]
    first_buy_actual_date = idx_dates[first_buy_idx]

    shares = 0.0
    invested = 0.0
    chart_data: list[dict] = []
    for i in range(first_buy_idx, len(closes)):
        price = closes[i]
        if price <= 0:
            # skip corrupt row but keep prior state
            continue
        buys_here = buy_indices.get(i, 0)
        if buys_here:
            for _ in range(buys_here):
                shares += amount / price
                invested += amount
        value = shares * price
        chart_data.append({
            "date": idx_dates[i].isoformat(),
            "price": round(price, 4),
            "invested": round(invested, 2),
            "value": round(value, 2),
            "buy_point": bool(buys_here),
        })

    if not chart_data or invested <= 0:
        return None, None, None, None, None

    return chart_data, invested, shares, first_buy_price, first_buy_actual_date


def _extract_milestones(chart_data: list[dict], invested_principal_at_start: float) -> list[dict]:
    """Detect notable events:

    - First time portfolio hits 2x / 3x / 5x / 10x of the FIRST-DAY
      invested amount (i.e. "원금 2배" when the lump-sum was `amount`).
      NOTE: we anchor to the first day's invested value, not cumulative,
      because a DCA plan increases `invested` over time and "원금 2배"
      reads more intuitively against the starting stake.
    - Drawdown trough: global-min date + % drop from prior peak (most
      painful point) — included when drop ≥ 10%.
    - All-time high within the window.
    """
    if not chart_data or invested_principal_at_start <= 0:
        return []

    milestones: list[dict] = []
    multipliers = [(2, "원금 2배 달성"), (3, "원금 3배 달성"), (5, "원금 5배 달성"), (10, "원금 10배 달성")]

    hit = set()
    peak_value = chart_data[0]["value"]
    max_drawdown_pct = 0.0
    trough_idx: int | None = None
    ath_idx = 0
    ath_value = chart_data[0]["value"]

    for i, pt in enumerate(chart_data):
        v = pt["value"]

        # Multiplier milestones (vs first-day stake)
        for mult, label in multipliers:
            if mult in hit:
                continue
            if v >= invested_principal_at_start * mult:
                hit.add(mult)
                milestones.append({
                    "date": pt["date"],
                    "label": label,
                    "type": "multiplier",
                    "value": mult,
                    "portfolio_value": round(v, 2),
                })

        # Peak / drawdown tracking
        if v > peak_value:
            peak_value = v
        elif peak_value > 0:
            dd_pct = (v - peak_value) / peak_value * 100.0
            if dd_pct < max_drawdown_pct:
                max_drawdown_pct = dd_pct
                trough_idx = i

        if v > ath_value:
            ath_value = v
            ath_idx = i

    if trough_idx is not None and max_drawdown_pct <= -10.0:
        milestones.append({
            "date": chart_data[trough_idx]["date"],
            "label": f"최대 낙폭 ({round(max_drawdown_pct, 1)}%)",
            "type": "drawdown",
            "value": round(max_drawdown_pct, 2),
            "portfolio_value": round(chart_data[trough_idx]["value"], 2),
        })

    # All-time high within window — only if it's not at the last point
    # (the last point is separately shown as "end value")
    if ath_idx != len(chart_data) - 1 and ath_idx > 0:
        milestones.append({
            "date": chart_data[ath_idx]["date"],
            "label": "기간 내 최고가 도달",
            "type": "ath",
            "value": None,
            "portfolio_value": round(ath_value, 2),
        })

    # Sort by date ascending for UX
    milestones.sort(key=lambda m: m["date"])
    return milestones


def _benchmark_ticker_for(ticker: str) -> str:
    """Pick a sensible benchmark:
       - Korean listings → KOSPI composite (^KS11)
       - US listings → SPY (most-traded proxy for S&P 500; FMP/Alpaca
         both supply it without needing an index entitlement)
    """
    return "^KS11" if _is_korean(ticker) else "SPY"


def _simulate_benchmark(
    bench_ticker: str,
    start: date,
    amount: float,
    recurring: str,
    hist_period: str,
):
    """Cheap benchmark run — returns (end_value, return_pct, invested) or None."""
    try:
        hist = _fetch_history_long(bench_ticker, start)
    except Exception as e:
        logger.warning("benchmark fetch failed %s: %s", bench_ticker, e)
        return None

    chart, invested, _shares, _fbp, _fbd = _compute_shares_series(
        hist, start, amount, recurring
    )
    if not chart or not invested:
        return None

    end_val = chart[-1]["value"]
    ret_pct = (end_val - invested) / invested * 100.0
    return {
        "ticker": bench_ticker,
        "name": resolve_stock_name(bench_ticker) or bench_ticker,
        "end_value": round(end_val, 2),
        "return_pct": round(ret_pct, 2),
        "total_invested": round(invested, 2),
    }


# ── Endpoint ────────────────────────────────────────────────────────────────

@counterfactual_bp.route("/counterfactual")
def counterfactual():
    """GET /api/simulate/counterfactual

    Query params:
        ticker       — e.g. AAPL, NVDA, 005930.KS  (required)
        start_date   — YYYY-MM-DD                   (required)
        amount       — positive float               (required)
        recurring    — "none" | "weekly" | "monthly" (default "none")
    """
    ticker_raw = (request.args.get("ticker") or "").strip()
    start_raw = (request.args.get("start_date") or "").strip()
    amount_raw = request.args.get("amount")
    recurring_raw = (request.args.get("recurring") or "none").strip().lower()
    # Optional: user-facing currency of the `amount` input. When provided and
    # it differs from the ticker's native listing currency, we FX-convert the
    # amount before buying shares — otherwise a 5_000_000 "KRW" input against
    # an NVDA (USD) ticker would be interpreted as $5M and inflate shares by
    # ~1,475× (the KRW/USD rate). Response values are emitted in this
    # user-facing currency so the UI reads naturally.
    # FX-historical (resolved 2026-05-02 / B9):
    #   - Amount INGRESS  → fx_service.get_rate_at(start)  (rate at the
    #     time the user *would have* bought)
    #   - Value EGRESS    → fx_service.get_rate()          (today's spot,
    #     correct for "what's it worth right now in your currency?")
    # The end_value is *re-evaluated today*, so converting it at today's
    # spot is the natural reading. Only the ingress (amount → shares)
    # needs the historical rate, and that's what we apply.
    user_currency_raw = (request.args.get("currency") or "").strip().upper()
    user_currency: str | None = user_currency_raw if user_currency_raw in ("KRW", "USD") else None

    # ── Validation ────────────────────────────────────────────────
    if not ticker_raw:
        return _error("TICKER_REQUIRED", "티커를 입력하세요. 예: AAPL, NVDA, TSLA")
    ticker = ticker_raw.upper()
    # Reject obviously invalid tickers (no control chars, reasonable len)
    if len(ticker) > 20 or not all(c.isalnum() or c in ".^-" for c in ticker):
        return _error("TICKER_NOT_FOUND", "티커 형식이 올바르지 않습니다. 예: AAPL, NVDA, 005930.KS")

    start = _parse_date(start_raw)
    if not start:
        return _error("DATE_INVALID", "시작일 형식이 올바르지 않습니다. (YYYY-MM-DD)")

    today = date.today()
    if start >= today:
        return _error("DATE_IN_FUTURE", "시작일은 오늘 이전이어야 합니다.")
    if start < _EARLIEST_DATE:
        return _error(
            "DATE_TOO_OLD",
            f"시작일은 {_EARLIEST_DATE.isoformat()} 이후로 설정해주세요.",
        )

    amount = _safe_float(amount_raw)
    if amount is None or amount <= 0:
        return _error("AMOUNT_REQUIRED", "투자 금액을 1원 이상으로 입력하세요.")
    if amount < _MIN_AMOUNT:
        return _error(
            "AMOUNT_OUT_OF_RANGE",
            f"최소 투자 금액은 {_MIN_AMOUNT:.0f} 입니다.",
        )
    if amount > _MAX_AMOUNT:
        return _error(
            "AMOUNT_OUT_OF_RANGE",
            "투자 금액은 10억원 이하로 입력해주세요.",
        )

    if recurring_raw not in _VALID_RECURRING:
        return _error(
            "RECURRING_INVALID",
            "recurring 값은 none / weekly / monthly 중 하나여야 합니다.",
        )
    recurring = recurring_raw

    # Soft fallback: recurring chosen but window < 1 period → lump sum
    duration_days = (today - start).days
    if recurring == "monthly" and duration_days < 30:
        recurring = "none"
    if recurring == "weekly" and duration_days < 7:
        recurring = "none"

    # ── Cache check ───────────────────────────────────────────────
    # user_currency is part of the key because it controls both the
    # native-amount derivation (shares count) and the response egress
    # currency — two distinct payloads for the same ticker/date/amount.
    cache_key = (ticker, start.isoformat(), round(amount, 2), recurring, user_currency)
    cached = _cache_get(cache_key)
    if cached is not None:
        return jsonify(cached)

    # ── Fetch history ─────────────────────────────────────────────
    # Map elapsed years to supported `period` key on data_fetcher,
    # or fall back to a direct FMP query with explicit from/to for
    # windows older than 5 years.
    years = duration_days / 365.25
    period_key = _period_for_years(years)

    try:
        hist = _fetch_history_long(ticker, start)
    except Exception as e:
        logger.error("counterfactual fetch failed %s: %s", ticker, e)
        return _error(
            "DATA_UNAVAILABLE",
            "가격 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.",
            http=503,
        )

    if hist is None or hist.empty:
        return _error(
            "TICKER_NOT_FOUND",
            "해당 티커의 가격 데이터를 찾을 수 없습니다. 티커를 확인해주세요.",
            http=404,
        )

    # Ensure we have data reaching back to (or near) the start date.
    try:
        first_available = hist.index[0]
        first_available = first_available.date() if hasattr(first_available, "date") else first_available
    except Exception:
        first_available = None

    if first_available and first_available > start + timedelta(days=14):
        # Data window starts well after requested start → likely listing
        # happened later or upstream only returned a shorter window.
        return _error(
            "DATE_BEFORE_LISTING",
            f"{first_available.isoformat()} 이후의 데이터만 이용 가능합니다. 시작일을 조정해주세요.",
            suggestion={
                "field": "start_date",
                "value": first_available.isoformat(),
                "reason": f"{first_available.isoformat()} 상장 또는 데이터 시작일",
            },
        )

    # ── Currency normalization ────────────────────────────────────
    # `amount` comes in the user's requested currency (user_currency). The
    # price series is in the ticker's native listing currency. Convert the
    # amount to native BEFORE computing shares so shares = amount_native /
    # price yields a sane count regardless of (user currency, ticker
    # currency) combination.
    #
    # Historical FX (B9): the *ingress* conversion uses the rate AT
    # `start` so a 2020 KRW input buying NVDA buys the right share count
    # at the 2020 USD/KRW rate. Spot-rate fallback inside
    # `fx_service.get_rate_at()` keeps the call infallible.
    native_currency = "KRW" if _is_korean(ticker) else "USD"
    effective_user_currency = user_currency or native_currency
    fx_rate = None  # spot rate, used for response-time egress conversion
    fx_rate_at_start = None  # historical rate, used for ingress conversion
    amount_native = amount
    if user_currency and user_currency != native_currency:
        fx_rate = _fx_get_rate()  # USD → KRW spot (e.g., 1380)
        fx_rate_at_start = _fx_get_rate_at(start)
        if not fx_rate or fx_rate <= 0 or not fx_rate_at_start or fx_rate_at_start <= 0:
            return _error(
                "DATA_UNAVAILABLE",
                "환율 정보를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.",
                http=503,
            )
        if user_currency == "KRW" and native_currency == "USD":
            amount_native = amount / fx_rate_at_start
        elif user_currency == "USD" and native_currency == "KRW":
            amount_native = amount * fx_rate_at_start

    # ── Core simulation ───────────────────────────────────────────
    chart_data, invested_total, shares_total, first_buy_price, first_buy_date = \
        _compute_shares_series(hist, start, amount_native, recurring)

    if not chart_data or not invested_total:
        return _error(
            "DATA_UNAVAILABLE",
            "시뮬레이션에 필요한 가격 데이터가 부족합니다.",
            http=503,
        )

    end_point = chart_data[-1]
    end_value = end_point["value"]
    # return_pct is currency-invariant (ratio of end/invested), so it's safe
    # to compute in native space — no re-conversion needed when we later
    # present invested/end_value in user_currency.
    return_pct = (end_value - invested_total) / invested_total * 100.0

    # CAGR for display (only meaningful for ≥ 30 day windows)
    annualized = None
    real_years = (date.fromisoformat(end_point["date"]) - first_buy_date).days / 365.25
    if real_years >= (1.0 / 12.0) and invested_total > 0 and end_value > 0:
        try:
            annualized = ((end_value / invested_total) ** (1.0 / max(real_years, 1e-9)) - 1.0) * 100.0
        except (ValueError, ZeroDivisionError, OverflowError):
            annualized = None

    # Milestones anchored to FIRST DAY's native stake (DCA first buy size).
    # amount_native matches chart_data[*].value currency, so labels like
    # "원금 2배" compare correctly.
    milestones = _extract_milestones(chart_data, amount_native)

    # Benchmark — always include so the frontend can render "+$X vs S&P 500".
    # Pass amount_native so the benchmark buys shares of SPY/KOSPI in the
    # benchmark's own native price series. The benchmark's native currency
    # matches native_currency here (SPY → USD for US tickers, ^KS11 → KRW
    # for KR tickers), so results are directly comparable.
    bench_ticker = _benchmark_ticker_for(ticker)
    benchmark_payload = None
    if bench_ticker.upper() != ticker.upper():
        bench = _simulate_benchmark(bench_ticker, start, amount_native, recurring, period_key)
        if bench:
            diff_value_native = end_value - bench["end_value"]
            diff_pct = return_pct - bench["return_pct"]
            benchmark_payload = {
                "ticker": bench["ticker"],
                "name": bench.get("name") or bench["ticker"],
                "end_value": round(_to_user_ccy(bench["end_value"], user_currency, native_currency, fx_rate), 2),
                "return_pct": bench["return_pct"],
                "total_invested": round(_to_user_ccy(bench["total_invested"], user_currency, native_currency, fx_rate), 2),
                "diff_value": round(_to_user_ccy(diff_value_native, user_currency, native_currency, fx_rate), 2),
                "diff_pct": round(diff_pct, 2),
            }

    # Downsample chart (still in native currency at this point)
    chart_data_native = _downsample(chart_data, _MAX_CHART_POINTS)
    # Re-project chart values into user_currency for UI rendering. Prices
    # stay in native (they're a reference; the chart plots portfolio VALUE).
    if user_currency and user_currency != native_currency and fx_rate:
        chart_data_out = [
            {
                **pt,
                "invested": round(_to_user_ccy(pt["invested"], user_currency, native_currency, fx_rate), 2),
                "value": round(_to_user_ccy(pt["value"], user_currency, native_currency, fx_rate), 2),
            }
            for pt in chart_data_native
        ]
        milestones_out = [
            {**m, "portfolio_value": round(_to_user_ccy(m["portfolio_value"], user_currency, native_currency, fx_rate), 2)}
            for m in milestones
        ]
    else:
        chart_data_out = chart_data_native
        milestones_out = milestones

    # Top-level scalars in user_currency
    invested_total_out = _to_user_ccy(invested_total, user_currency, native_currency, fx_rate)
    end_value_out = _to_user_ccy(end_value, user_currency, native_currency, fx_rate)
    amount_initial_out = amount  # user's original input — already in user_currency
    recurring_amount_out = amount if recurring != "none" else 0

    payload = {
        "success": True,
        "ticker": ticker,
        "name": resolve_stock_name(ticker) or ticker,
        "start_date": start.isoformat(),
        "first_buy_date": first_buy_date.isoformat(),
        "end_date": end_point["date"],
        "recurring": recurring,
        "recurring_amount": round(recurring_amount_out, 2),
        "amount_initial": round(amount_initial_out, 2),
        "total_invested": round(invested_total_out, 2),
        "end_value": round(end_value_out, 2),
        "profit_loss": round(end_value_out - invested_total_out, 2),
        "return_pct": round(return_pct, 2),
        "annualized_return_pct": round(annualized, 2) if annualized is not None else None,
        "duration_days": (date.fromisoformat(end_point["date"]) - first_buy_date).days,
        "shares_total": round(shares_total, 6),
        "first_buy_price": round(first_buy_price, 4),
        "last_price": round(end_point["price"], 4),
        "currency": effective_user_currency,
        "native_currency": native_currency,
        "fx_rate": round(fx_rate, 4) if fx_rate else None,
        "chart_data": chart_data_out,
        "milestones": milestones_out,
        "benchmark": benchmark_payload,
        "disclaimers": DISCLAIMERS,
    }

    _cache_set(cache_key, payload)
    return jsonify(payload)


def _to_user_ccy(value_native: float, user_ccy: str | None, native_ccy: str, fx_rate: float | None) -> float:
    """Convert a native-currency amount into the user-facing currency.

    - If user did not specify a currency, or it matches native, return as-is.
    - KRW↔USD conversion uses the *current* (spot) USD/KRW rate from
      fx_service for value egress — i.e. "what is this worth in your
      currency right now". For amount ingress (the user's historical
      stake → native shares) the route applies the historical rate via
      ``fx_service.get_rate_at(start)`` instead.
    """
    if not user_ccy or user_ccy == native_ccy or not fx_rate or fx_rate <= 0:
        return value_native
    if user_ccy == "KRW" and native_ccy == "USD":
        return value_native * fx_rate
    if user_ccy == "USD" and native_ccy == "KRW":
        return value_native / fx_rate
    return value_native
