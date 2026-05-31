"""Holding Mirror — retrospective reflection of how long a user held
their *winning* round trips versus their *losing* ones.

What this is (and is NOT)
-------------------------
This is a **retrospective factual mirror** of the user's own closed
round trips: "지난 거래에서 이익 본 종목은 평균 N일, 손실 본 종목은 평균 M일
보유하셨습니다." It is purely observational — a description of what
already happened.

It is deliberately **not**:

* A *score*, *grade*, *index*, or *ratio* surfaced to the user. The
  internal winner/loser hold comparison is used only to decide whether
  the data is "one-sided" — no numeric judgement leaves this module.
  (DECISIONS.md — AI 점수화 폐기.)
* The market-microstructure ``DispositionEffect`` (CGO) signal in
  ``services/quant/signals.py``. That computes a *market-wide*
  capital-gains-overhang factor from price/volume history. This module
  touches only the user's *own* realised ``TradeHistory`` round trips
  via :func:`fifo_match_closed_trades`. The two must never be conflated
  — importing ``signals.DispositionEffect`` here is forbidden.
* A behavioural-mistake *label*. The cron-side
  ``group_benchmark._user_mistakes`` may emit a ``MISTAKE_DISPOSITION``
  label internally, but this module never surfaces that label — only
  raw counts and holding-day statistics.

Relationship to ``group_benchmark._user_mistakes``
---------------------------------------------------
The winner/loser hold-day slicing logic was extracted from
``group_benchmark._user_mistakes`` (lines 482-523 as of 2026-05-30) so
both share the same per-SELL pnl-attribution. The original is left
untouched on purpose: the ``BehavioralScore`` cron depends on it and a
behavioural-change regression there is far costlier than a small amount
of duplicated slicing logic. If the two ever need to converge, do it in
a dedicated refactor with a regression test on both call sites.

Statistics
----------
* **median primary, mean secondary** — the median is reported as the
  headline holding period because realised trade logs are heavily
  right-skewed (a single forgotten loser held 400 days wrecks a mean).
  The mean is kept as a secondary figure for transparency.
* winner / loser split is by the SELL row's stored ``pnl_pct`` sign:
  ``> 0`` win, ``< 0`` loss, ``== 0`` (break-even) excluded entirely.
* only **closed** FIFO pairs participate — open positions are ignored.

Public API
----------
:func:`compute_holding_mirror` — pure function over a list of
    ``TradeHistory`` rows. No DB access, no network, no ORM mutation.
"""
from __future__ import annotations

import statistics
from datetime import timedelta
from typing import Iterable

from models import TradeHistory
from services.name_resolver import kr_display_name
from services.profile.fifo_util import (
    MatchedPair,
    fifo_match_closed_trades_with_pnl,
)


# ── tunables ─────────────────────────────────────────────────────────
#
# ``min_pairs`` default: below this many *classified* (non-break-even)
# closed pairs we refuse to report numbers — too small a sample to be a
# meaningful self-reflection (and risks reading as a judgement). Matches
# the spec's ``min_pairs=5``.
_DEFAULT_MIN_PAIRS: int = 5

# ``max_examples`` default: how many extreme round trips to surface per
# side. Winners surface the *shortest* holds (sold quickest), losers the
# *longest* holds (held longest) — the textbook disposition pattern,
# shown as raw facts, never labelled as a mistake.
_DEFAULT_MAX_EXAMPLES: int = 3


def _classify_pairs(
    trades: list[TradeHistory],
) -> tuple[
    list[tuple[MatchedPair, float]],
    list[tuple[MatchedPair, float]],
    int,
]:
    """Split closed FIFO pairs into (winners, losers, total_closed).

    Each bucket entry is ``(pair, pnl_pct)`` where ``pnl_pct`` is the
    realised return of **the exact SELL row that closed that pair**,
    attributed inside :func:`fifo_match_closed_trades_with_pnl`. This
    avoids the old ``{(ticker, traded_at): pnl_pct}`` dict that *collided*
    when two same-ticker SELLs landed on the same date-grain
    ``traded_at`` — the last SELL's sign then overwrote the earlier one,
    flipping a take-profit pair into the loss bucket (and vice-versa).

    Break-even pairs (``pnl_pct == 0``) are returned in neither bucket
    but DO count toward ``total_closed``.
    """
    attributed = fifo_match_closed_trades_with_pnl(trades)
    total_closed = len(attributed)

    winners: list[tuple[MatchedPair, float]] = []
    losers: list[tuple[MatchedPair, float]] = []
    for pair, pct in attributed:
        if pct > 0:
            winners.append((pair, pct))
        elif pct < 0:
            losers.append((pair, pct))
        # pct == 0 → break-even, excluded from both buckets on purpose.
    return winners, losers, total_closed


def _example_from_pair(
    pair: MatchedPair,
    pnl_pct: float,
    names_by_ticker: dict[str, str],
) -> dict:
    """Build a single example dict for one extreme round trip.

    ``pnl_pct`` is the realised return of the **exact SELL** that closed
    this pair (already attributed in :func:`_classify_pairs`), so an
    example never shows the wrong sign even when two same-ticker SELLs
    share a ``traded_at``.

    ``display_name`` follows feedback_ticker_display.md priority:
    the stored ``trade.name`` first, then KR hangul resolution, then the
    raw ticker as a last resort — never a naked ``.KS`` code when a name
    is resolvable. Name is resolved per-ticker (collision-free: every
    SELL of one ticker carries the same name).
    """
    stored_name = names_by_ticker.get(pair.ticker, "")
    display_name = stored_name or kr_display_name(pair.ticker) or pair.ticker

    return {
        "display_name": display_name,
        "ticker": pair.ticker,
        "pnl_pct": round(float(pnl_pct), 2),
        "hold_days": round(float(pair.hold_days), 1),
        "sell_at": pair.sell_time.isoformat() if pair.sell_time else None,
    }


def _side_summary(
    pairs: list[tuple[MatchedPair, float]],
    *,
    longest_first: bool,
    max_examples: int,
    names_by_ticker: dict[str, str],
) -> dict | None:
    """Summarise one side (winners or losers).

    ``pairs`` is a list of ``(pair, pnl_pct)`` tuples already attributed
    to the closing SELL. Returns ``None`` when the side has zero pairs
    (the caller uses that to set ``one_sided`` and null out the empty
    side). Otherwise returns
    ``{count, median_hold_days, mean_hold_days, examples}``.

    ``longest_first=True`` (losers) surfaces the trips held *longest*;
    ``False`` (winners) surfaces those sold *quickest*.
    """
    if not pairs:
        return None

    holds = [float(p.hold_days) for p, _ in pairs]
    median_hold = round(statistics.median(holds), 1)
    mean_hold = round(statistics.fmean(holds), 1)

    ordered = sorted(
        pairs, key=lambda pp: pp[0].hold_days, reverse=longest_first
    )
    examples = [
        _example_from_pair(p, pct, names_by_ticker)
        for p, pct in ordered[: max(0, max_examples)]
    ]

    return {
        "count": len(pairs),
        "median_hold_days": median_hold,
        "mean_hold_days": mean_hold,
        "examples": examples,
    }


def compute_holding_mirror(
    trades: Iterable[TradeHistory],
    *,
    period_days: int | None = None,
    min_pairs: int = _DEFAULT_MIN_PAIRS,
    max_examples: int = _DEFAULT_MAX_EXAMPLES,
) -> dict:
    """Compute the retrospective holding-period mirror for one user.

    Parameters
    ----------
    trades : Iterable[TradeHistory]
        All trade rows for a single user. Order-independent; FIFO
        matching sorts internally.
    period_days : int | None
        When set, only trades whose ``traded_at`` falls within the last
        ``period_days`` days (relative to the latest trade in the input,
        for determinism) are considered. ``None`` → all history.
    min_pairs : int
        Minimum number of *classified* (non-break-even) closed pairs
        required before numeric stats are reported. Below this,
        ``sufficient_data`` is ``False`` and both sides are ``None``.
    max_examples : int
        Max extreme round trips surfaced per side.

    Returns
    -------
    dict
        ``{sufficient_data, one_sided, total_closed_pairs, winners,
        losers}``. No score/grade/ratio/index field is ever included.
        ``winners``/``losers`` are ``None`` when their side is empty or
        when ``sufficient_data`` is ``False``.
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

    winners, losers, total_closed = _classify_pairs(materialised)
    classified = len(winners) + len(losers)

    # ── insufficient data: new user, too few pairs, all break-even ──
    if classified < max(0, min_pairs):
        return {
            "sufficient_data": False,
            "one_sided": False,
            "total_closed_pairs": total_closed,
            "winners": None,
            "losers": None,
        }

    # Index stored display names per ticker for the example builder.
    # Name is a per-ticker property, so a plain ticker→name map is
    # collision-free (unlike the old (ticker, traded_at) pnl_pct dict).
    names_by_ticker: dict[str, str] = {}
    for t in materialised:
        if (t.action or "").upper() == "SELL" and t.ticker:
            name = (getattr(t, "name", None) or "").strip()
            if name:
                names_by_ticker.setdefault(t.ticker.upper(), name)

    winners_summary = _side_summary(
        winners,
        longest_first=False,  # winners: surface the quickest sells
        max_examples=max_examples,
        names_by_ticker=names_by_ticker,
    )
    losers_summary = _side_summary(
        losers,
        longest_first=True,  # losers: surface the longest holds
        max_examples=max_examples,
        names_by_ticker=names_by_ticker,
    )

    one_sided = (winners_summary is None) or (losers_summary is None)

    return {
        "sufficient_data": True,
        "one_sided": one_sided,
        "total_closed_pairs": total_closed,
        "winners": winners_summary,
        "losers": losers_summary,
    }


__all__ = ["compute_holding_mirror"]
