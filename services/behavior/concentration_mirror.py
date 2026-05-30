"""Concentration Mirror — factual reflection of how much of a user's
portfolio (at cost basis) sits in their single largest holding.

What this is (and is NOT)
-------------------------
This is a **factual mirror** of the user's own open positions:
"가장 큰 보유 종목이 포트폴리오의 N% 를 차지합니다." It is purely
observational — a description of the current composition, stated as a
fact.

It is deliberately **not**:

* A *score*, *grade*, *index*, or *ratio* surfaced to the user. We never
  reuse the 0-100 ``_position_sizing_subscore`` from
  ``services.behavior.scorer`` — importing or deriving that number here
  is forbidden. (DECISIONS.md — AI 점수화 폐기.) Only the raw
  ``largest / total`` percentage and the holding count leave this module.
* A behavioural-mistake *label*. We never emit "과집중" / "집중 위험" /
  "분산 필요" / "위험수준" or any judgement framing. The user reads the
  fact and draws their own conclusion (research_cbt_bias_model.md — 사실만
  비추고 재구성은 사용자).
* A persona-average comparison. No "평균보다 높다" framing.

Cost basis, not market value
----------------------------
Weights are computed on ``shares * avg_cost`` (the amount the user
actually paid), never on a live market price. This keeps the module
free of any external price call (feedback_official_data_only.md) and
makes the figure deterministic and self-consistent with what the user
entered.

Name display
------------
The largest holding surfaces its display NAME via
``name_resolver.kr_display_name`` — the same resolution the disposition
mirror uses — so a Korean position reads "삼성전자", never a naked
``005930.KS`` code (feedback_ticker_display.md).

Public API
----------
:func:`compute_concentration_mirror` — queries the user's open
    ``Position`` rows and returns the factual concentration mirror dict.
    No network, no external price call, no score field.
"""
from __future__ import annotations

from models import Position
from services.name_resolver import kr_display_name


def _insufficient() -> dict:
    """The empty / zero-cost-basis result.

    Returned for a new user, an all-zero portfolio, or any state where a
    weight cannot be meaningfully computed (zero-div guard).
    """
    return {
        "sufficient_data": False,
        "ticker_count": 0,
        "max_weight_pct": None,
        "largest_ticker": None,
        "cost_basis_note": _COST_BASIS_NOTE,
    }


_COST_BASIS_NOTE = "평균매입가 기준 (시장가 아님)"


def compute_concentration_mirror(user_id: int) -> dict:
    """Compute the cost-basis concentration mirror for one user.

    Parameters
    ----------
    user_id : int
        The user whose open positions to mirror.

    Returns
    -------
    dict
        ``{sufficient_data, ticker_count, max_weight_pct, largest_ticker,
        cost_basis_note}``. No score/grade/ratio/index field is ever
        included. ``max_weight_pct`` / ``largest_ticker`` are ``None``
        when the data is insufficient (no positions with a positive
        cost basis).
    """
    positions = Position.query.filter_by(user_id=user_id).all()

    # Pair each surviving position with its cost-basis value so we can
    # name the largest one without a second scan. A position is counted
    # only when BOTH shares and avg_cost are strictly positive — a 0/None
    # share or 0/None cost contributes nothing and is excluded entirely.
    valued: list[tuple[Position, float]] = []
    for p in positions:
        try:
            shares = float(p.shares or 0)
            avg_cost = float(p.avg_cost or 0)
        except (TypeError, ValueError):
            continue
        if shares <= 0 or avg_cost <= 0:
            continue
        value = shares * avg_cost
        if value > 0:
            valued.append((p, value))

    total = sum(value for _, value in valued)
    # zero-div guard: no positions, or every position netted to zero cost
    # basis → we cannot state a weight, so report insufficient data.
    if not valued or total <= 0:
        return _insufficient()

    largest_position, largest_value = max(valued, key=lambda pair: pair[1])
    max_weight_pct = round(largest_value / total * 100.0, 1)
    largest_ticker = kr_display_name(largest_position.ticker)

    return {
        "sufficient_data": True,
        "ticker_count": len(valued),
        "max_weight_pct": max_weight_pct,
        "largest_ticker": largest_ticker,
        "cost_basis_note": _COST_BASIS_NOTE,
    }


__all__ = ["compute_concentration_mirror"]
