"""Averaging-Down Mirror — retrospective factual count of, when the user
**added to an already-held position** (a follow-on BUY), how often that
add landed *below*, *above*, or *at* the position's running average cost
at that moment.

What this is (and is NOT)
-------------------------
This is a **retrospective factual mirror** of the user's own follow-on
buys over a window: "지난 N일 동안 이미 보유 중인 종목을 추가로 매수한
것이 P건, 그중 평균가보다 낮은 가격에 Q건 · 평균가보다 높은 가격에 R건."
It is purely observational — raw counts of where each add fell relative to
the running average cost at the instant of that add, stated as plain
numbers.

It is deliberately **not**:

* A *score* / *grade* / *ratio* / *index* / *label* / *percentile* /
  "health" number. There is **NO ratio** anywhere in this module — only
  integer counts. (DECISIONS.md — AI 점수화 폐기.)
* A verdict. The module never says adding below the average is good or
  bad, never says it "deepens losses" or anything causal. It reports how
  many adds were below / above / at the running average and the user
  draws their own conclusion. (research_cbt_bias_model.md — "처분효과조차
  합리적일 수 있다 — 개별 편향 판정은 위험"; 사실만 비추고 재구성은
  사용자.) The slang "물타기" — which carries a judgement — is NEVER used
  in any user-facing surface; the internal module name uses
  ``averaging_down`` only as a neutral technical identifier.
* An efficacy claim. Efficacy statistics (Barber&Odean, etc.) are
  intentionally NOT referenced — the mirror reports counts, full stop.

The running-average tracker
---------------------------
Per ticker, walking the user's fills in chronological order, we keep a
weighted-average cost (총원가 ÷ 총주식수). A BUY is a **follow-on** only
when the position already holds shares (> ``_SHARE_EPSILON``) at that
moment; the *first* BUY that opens a position is NOT a follow-on (there is
no prior average to compare against). For each follow-on BUY we compare
its per-share price to the **average cost just before this add** and bucket
it ``below_avg`` / ``above_avg`` / ``flat`` (within ``_PRICE_EPSILON``),
then fold the add into the running average.

A SELL reduces shares and total cost proportionally (partial sells leave
the average unchanged); a full liquidation resets the position, so a later
re-buy counts as a fresh open (not a follow-on). Rows with a non-positive
share count or a zero per-share price are skipped from classification.

Same-ticker, same-currency comparison only
-------------------------------------------
The average cost and every compared price come from the **same ticker's**
own fills, which carry the same currency — so no FX conversion is ever
needed or performed. The module is a pure function: no DB access, no
network, no ORM mutation, no live price / FX call, and **no score / grade
/ ratio / index / label field ever in the output**.

Public API
----------
:func:`compute_averaging_down_mirror` — pure function over a list of
    ``TradeHistory`` rows.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Iterable, NamedTuple

from models import TradeHistory


# ── tunables ─────────────────────────────────────────────────────────
#
# ``min_follow_on`` default: below this many follow-on BUY events in the
# window we refuse to report numbers — too small a sample to be a
# meaningful self-reflection (and risks reading as a judgement). Mirrors
# the turnover mirror's ``min_trades`` insufficient-data gate.
_DEFAULT_MIN_FOLLOW_ON: int = 3

# Share-quantity epsilon — a position is "still open" when its running
# share count exceeds this. Matches services.profile.fifo_util._SHARE_EPSILON.
_SHARE_EPSILON: float = 1e-9

# Price epsilon — an add within this of the running average is bucketed
# ``flat`` rather than below/above, so float drift never mislabels an add
# that was effectively at the average.
_PRICE_EPSILON: float = 1e-9

# How many tickers to surface in the neutral per-ticker breakdown.
_MAX_TICKERS: int = 5


class _FollowOnTally(NamedTuple):
    """Per-ticker running tally of follow-on add classifications."""

    follow_on: int
    below_avg: int
    above_avg: int
    flat: int
    name: str | None


def _classify_follow_ons(
    trades: list[TradeHistory],
) -> dict[str, _FollowOnTally]:
    """Walk each ticker's fills and tally follow-on adds vs running average.

    Returns ``{ticker -> _FollowOnTally}``. Tickers with no follow-on add
    are omitted (their tally would be all-zero). The walk is deterministic:
    fills are sorted by ``traded_at`` so out-of-order ingestion (backfill)
    does not corrupt the running average.
    """
    ordered = sorted(
        (t for t in trades if t.traded_at and t.ticker),
        key=lambda t: t.traded_at,
    )

    # ticker -> (total_shares, total_cost, latest_name)
    positions: dict[str, tuple[float, float, str | None]] = {}
    tally: dict[str, dict[str, int]] = {}

    def _bump(key: str, bucket: str | None, name: str | None) -> None:
        rec = tally.setdefault(
            key,
            {"follow_on": 0, "below_avg": 0, "above_avg": 0, "flat": 0},
        )
        # Carry the freshest non-empty display name for this ticker.
        if name:
            rec["__name__"] = name  # type: ignore[assignment]
        if bucket is not None:
            rec["follow_on"] += 1
            rec[bucket] += 1

    for t in ordered:
        key = t.ticker.upper()
        action = (t.action or "").upper()
        shares = float(t.shares or 0.0)
        price = float(t.price_per_share or 0.0)
        name = (t.name or "").strip() or None
        held_shares, held_cost, held_name = positions.get(
            key, (0.0, 0.0, None)
        )

        if action == "BUY":
            # Skip malformed rows from classification, but never let them
            # corrupt the running average.
            if shares <= 0 or price <= 0:
                if name:
                    _bump(key, None, name)
                continue
            is_follow_on = held_shares > _SHARE_EPSILON
            if is_follow_on:
                avg_before = held_cost / held_shares
                if price < avg_before - _PRICE_EPSILON:
                    bucket = "below_avg"
                elif price > avg_before + _PRICE_EPSILON:
                    bucket = "above_avg"
                else:
                    bucket = "flat"
                _bump(key, bucket, name)
            else:
                _bump(key, None, name)
            positions[key] = (
                held_shares + shares,
                held_cost + shares * price,
                name or held_name,
            )
            continue

        if action == "SELL":
            if name:
                _bump(key, None, name)
            if shares <= 0 or held_shares <= _SHARE_EPSILON:
                continue
            remaining = held_shares - shares
            if remaining <= _SHARE_EPSILON:
                # Full (or over-) liquidation → position resets; a later
                # re-buy is a fresh open, not a follow-on.
                positions[key] = (0.0, 0.0, name or held_name)
            else:
                # Partial sell — average cost unchanged, total cost scales
                # with the surviving share fraction.
                avg = held_cost / held_shares
                positions[key] = (
                    remaining,
                    remaining * avg,
                    name or held_name,
                )
            continue

        # Unknown action types are ignored entirely.

    result: dict[str, _FollowOnTally] = {}
    for key, rec in tally.items():
        name = rec.pop("__name__", None)  # type: ignore[arg-type]
        if rec["follow_on"] <= 0:
            continue
        result[key] = _FollowOnTally(
            follow_on=rec["follow_on"],
            below_avg=rec["below_avg"],
            above_avg=rec["above_avg"],
            flat=rec["flat"],
            name=name,  # type: ignore[arg-type]
        )
    return result


def _by_ticker(tallies: dict[str, _FollowOnTally]) -> list[dict]:
    """Neutral per-ticker breakdown — top ``_MAX_TICKERS`` by follow-on count.

    Each entry: ``{ticker, name, follow_on, below_avg, above_avg}``.
    Ordered by descending follow-on count, ties broken by ticker code for
    determinism. No ratio / score field — counts only.
    """
    ordered = sorted(
        tallies.items(),
        key=lambda kv: (-kv[1].follow_on, kv[0]),
    )
    return [
        {
            "ticker": ticker,
            "name": tally.name,
            "follow_on": tally.follow_on,
            "below_avg": tally.below_avg,
            "above_avg": tally.above_avg,
        }
        for ticker, tally in ordered[:_MAX_TICKERS]
    ]


def compute_averaging_down_mirror(
    trades: Iterable[TradeHistory],
    *,
    period_days: int | None = None,
    min_follow_on: int = _DEFAULT_MIN_FOLLOW_ON,
) -> dict:
    """Compute the retrospective follow-on-add mirror for one user.

    For every BUY that **added to an already-held position**, classifies
    whether the add's price was below / above / at the position's running
    average cost at that instant, and returns **integer counts only** —
    there is **no ratio, no score, no grade, no label** anywhere.

    Parameters
    ----------
    trades : Iterable[TradeHistory]
        All trade rows for a single user. Order-independent (sorted
        internally by ``traded_at`` for a deterministic running average).
    period_days : int | None
        When set, only trades whose ``traded_at`` falls within the last
        ``period_days`` days (relative to the latest trade in the input,
        for determinism) are considered. ``None`` → all history.
    min_follow_on : int
        Minimum number of follow-on BUY events in the window required
        before numeric facts are reported. Below this, ``sufficient_data``
        is ``False`` and the count fields are ``None``.

    Returns
    -------
    dict
        ``{sufficient_data, period_days, follow_on_count, below_avg_count,
        above_avg_count, flat_count, by_ticker}``. **No score / grade /
        ratio / index / label field is ever included.** When
        ``sufficient_data`` is ``False`` the count fields are ``None`` and
        ``by_ticker`` is ``[]``.
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

    tallies = _classify_follow_ons(materialised)

    follow_on_count = sum(tly.follow_on for tly in tallies.values())
    below_avg_count = sum(tly.below_avg for tly in tallies.values())
    above_avg_count = sum(tly.above_avg for tly in tallies.values())
    flat_count = sum(tly.flat for tly in tallies.values())

    # ── insufficient data: too few follow-on adds ───────────────────
    if follow_on_count < max(0, min_follow_on):
        return {
            "sufficient_data": False,
            "period_days": period_days,
            "follow_on_count": None,
            "below_avg_count": None,
            "above_avg_count": None,
            "flat_count": None,
            "by_ticker": [],
        }

    return {
        "sufficient_data": True,
        "period_days": period_days,
        "follow_on_count": follow_on_count,
        "below_avg_count": below_avg_count,
        "above_avg_count": above_avg_count,
        "flat_count": flat_count,
        "by_ticker": _by_ticker(tallies),
    }


__all__ = ["compute_averaging_down_mirror"]
