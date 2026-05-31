"""Turnover Mirror — retrospective reflection of *how active* a user's
trading was: how many BUY/SELL fills, and the gross traded value per
currency.

What this is (and is NOT)
-------------------------
This is a **retrospective factual mirror** of the user's own trade
activity over a window: "지난 N일 동안 매수 P건 · 매도 Q건, KRW 거래대금
합계 …원, USD 거래대금 합계 …달러." It is purely observational — raw
counts and gross traded value, stated as plain numbers.

It is deliberately **not**:

* A *turnover ratio* / *score* / *grade* / *index* / *label*. There is
  **NO ratio** anywhere in this module. A turnover *percentage* would
  require a portfolio-valuation denominator (``routes/portfolio.py``
  line 258), which needs a **live price call** — that would break the
  determinism this pure function guarantees, and mixing KRW/USD market
  values into one denominator is not meaningful anyway. So the mirror
  reports **absolute frequency + per-currency gross traded value only**,
  never a normalised ratio. (DECISIONS.md — AI 점수화 폐기;
  research_cbt_bias_model.md — 사실만 비추고 재구성은 사용자.)
* A "you trade too much / 과잉거래" verdict. The module never判定s the
  activity level — efficacy statistics (Barber&Odean, KCMI 회전율, etc.)
  are intentionally NOT referenced here. It reports counts and value,
  and the user draws their own conclusion.
* A per-trade judgement. Every fill is counted equally; no individual
  trade is flagged.

Per-currency gross value
------------------------
Each ``TradeHistory`` row stores its own ``currency`` (default "USD")
and ``total_value`` (shares × price, in that currency). We sum
``total_value`` **grouped by currency** — KRW and USD are reported as
separate lines and are **never FX-converted into one figure** (no live
FX rate, no混合 sum). A row with a blank currency is bucketed under its
stored default ("USD").

Average holding period
-----------------------
For context next to the activity counts we surface the same hold-day
statistic the holding/profit-loss mirrors use, derived from the shared
:func:`services.profile.fifo_util.fifo_match_closed_trades`
``MatchedPair.hold_days`` — median primary (right-skew resistant), mean
secondary. Both are ``None`` when there are no closed round trips in the
window. This is the *only* derived statistic; everything else is a raw
count or a raw value sum.

Statistics
----------
* **median primary, mean secondary** for hold days — realised hold logs
  are heavily right-skewed (one forgotten 400-day position wrecks a
  mean). Median is the headline; mean is kept for transparency.
* counts are over **all** fills in the window (BUY + SELL), independent
  of whether a round trip closed.

Public API
----------
:func:`compute_turnover_mirror` — pure function over a list of
    ``TradeHistory`` rows. No DB access, no network, no ORM mutation,
    no live price/FX call, and **no score/grade/ratio/index/label field
    ever in the output**.
"""
from __future__ import annotations

import statistics
from datetime import timedelta
from typing import Iterable

from models import TradeHistory
from services.profile.fifo_util import fifo_match_closed_trades


# ── tunables ─────────────────────────────────────────────────────────
#
# ``min_trades`` default: below this many fills (BUY+SELL) in the window
# we refuse to report numbers — too small a sample to be a meaningful
# self-reflection (and risks reading as a judgement). Matches the spec's
# ``min_trades=8``.
_DEFAULT_MIN_TRADES: int = 8

# Currency a row falls back to when ``currency`` is blank — matches the
# ``TradeHistory.currency`` column default so a blank never silently
# drops a trade's value out of the per-currency sum.
_DEFAULT_CURRENCY: str = "USD"


def _hold_day_stats(
    trades: list[TradeHistory],
) -> tuple[float | None, float | None]:
    """Return ``(median_hold_days, mean_hold_days)`` for closed pairs.

    Derived from the shared FIFO matcher so this never diverges from the
    holding / profit-loss mirrors. ``(None, None)`` when no round trip
    closed in the window (e.g. a user with only open buys).
    """
    pairs = fifo_match_closed_trades(trades)
    if not pairs:
        return None, None
    holds = [float(p.hold_days) for p in pairs]
    return (
        round(statistics.median(holds), 1),
        round(statistics.fmean(holds), 1),
    )


def _by_currency(trades: list[TradeHistory]) -> list[dict]:
    """Sum ``total_value`` grouped by ``currency`` — NEVER FX-converted.

    Returns one entry per distinct currency:
    ``{currency, gross_value, trade_count}``. ``gross_value`` is the sum
    of ``total_value`` for that currency's rows; ``trade_count`` is the
    number of rows in that currency. Ordered by descending gross value so
    the largest-activity currency reads first (ties broken by currency
    code for determinism).
    """
    gross: dict[str, float] = {}
    counts: dict[str, int] = {}
    for t in trades:
        currency = (t.currency or _DEFAULT_CURRENCY).upper()
        try:
            value = float(t.total_value or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        gross[currency] = gross.get(currency, 0.0) + value
        counts[currency] = counts.get(currency, 0) + 1

    return [
        {
            "currency": currency,
            "gross_value": round(gross[currency], 2),
            "trade_count": counts[currency],
        }
        for currency in sorted(
            gross, key=lambda c: (-gross[c], c)
        )
    ]


def compute_turnover_mirror(
    trades: Iterable[TradeHistory],
    *,
    period_days: int | None = None,
    min_trades: int = _DEFAULT_MIN_TRADES,
) -> dict:
    """Compute the retrospective trade-activity mirror for one user.

    Reports **absolute frequency + per-currency gross traded value** —
    there is **no ratio, no score, no grade, no label** anywhere. A
    turnover *percentage* is deliberately not computed: it would need a
    live portfolio-valuation denominator (breaking determinism) and
    mixing KRW/USD market values into one figure is not meaningful.

    Parameters
    ----------
    trades : Iterable[TradeHistory]
        All trade rows for a single user. Order-independent.
    period_days : int | None
        When set, only trades whose ``traded_at`` falls within the last
        ``period_days`` days (relative to the latest trade in the input,
        for determinism) are considered. ``None`` → all history.
    min_trades : int
        Minimum number of fills (BUY+SELL) in the window required before
        numeric facts are reported. Below this, ``sufficient_data`` is
        ``False`` and the fact fields are ``None`` / empty.

    Returns
    -------
    dict
        ``{sufficient_data, period_days, trade_count, buy_count,
        sell_count, by_currency, median_hold_days, mean_hold_days}``.
        **No score / grade / ratio / index / label field is ever
        included.** When ``sufficient_data`` is ``False`` the fact
        fields are ``None`` (counts) / ``[]`` (by_currency).
    """
    materialised = [t for t in trades if t is not None]

    # ── optional period window ──────────────────────────────────────
    if period_days is not None and period_days > 0:
        dated = [t for t in materialised if t.traded_at]
        if dated:
            anchor = max(t.traded_at for t in dated)
            cutoff = anchor - timedelta(days=period_days)
            materialised = [
                t for t in materialised
                if t.traded_at and t.traded_at >= cutoff
            ]
        else:
            materialised = []

    buy_count = sum(
        1 for t in materialised if (t.action or "").upper() == "BUY"
    )
    sell_count = sum(
        1 for t in materialised if (t.action or "").upper() == "SELL"
    )
    trade_count = buy_count + sell_count

    # ── insufficient data: new user, too few fills ──────────────────
    if trade_count < max(0, min_trades):
        return {
            "sufficient_data": False,
            "period_days": period_days,
            "trade_count": trade_count,
            "buy_count": None,
            "sell_count": None,
            "by_currency": [],
            "median_hold_days": None,
            "mean_hold_days": None,
        }

    # Only BUY/SELL fills contribute to the per-currency gross value sum
    # (other action types, if any, are excluded from both count & value).
    fills = [
        t for t in materialised
        if (t.action or "").upper() in ("BUY", "SELL")
    ]
    median_hold, mean_hold = _hold_day_stats(materialised)

    return {
        "sufficient_data": True,
        "period_days": period_days,
        "trade_count": trade_count,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "by_currency": _by_currency(fills),
        "median_hold_days": median_hold,
        "mean_hold_days": mean_hold,
    }


__all__ = ["compute_turnover_mirror"]
