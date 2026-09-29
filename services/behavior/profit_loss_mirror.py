"""Profit/Loss Mirror — retrospective reflection of how the user's
*profit-realising* sells compare with their *loss-realising* sells on two
plain facts: how long the position was held, and by what percentage it
closed.

What this is (and is NOT)
-------------------------
This is a **retrospective factual mirror** of the user's own closed round
trips, split by the sign of the realised return on the SELL leg:
"이익을 실현한 매도는 중앙값 N일 보유, 손실을 실현한 매도는 중앙값 M일
보유하셨습니다." It is purely observational — a description of what already
happened, stated as raw numbers.

It is deliberately **not**:

* A *score*, *grade*, *index*, *ratio*, or *label* surfaced to the user.
  No numeric judgement, no "처분효과" / "편향" / "과속" / "지연" / "개선"
  framing leaves this module. (DECISIONS.md — AI 점수화 폐기;
  research_cbt_bias_model.md — 사실만 비추고 재구성은 사용자.)
* A per-trade "right / wrong" verdict. Because a disposition split can be
  fully rational (rational disposition, JBF 2023), the module never判定s
  any individual round trip — it reports only aggregate hold-day and
  return statistics per side.
* The market-microstructure ``DispositionEffect`` (CGO) signal that used to
  live in ``services/quant/signals.py`` (deleted 2026-08-31). That computed a
  *market-wide* factor from price/volume history. This module touches only the user's *own* realised
  ``TradeHistory`` round trips via
  :func:`fifo_match_closed_trades_with_pnl`.

Relationship to ``holding_mirror.compute_holding_mirror``
---------------------------------------------------------
Both **live** mirrors slice the same FIFO-matched closed pairs by the
SELL row's ``pnl_pct`` sign and both are anchored on
``services.profile.fifo_util.fifo_match_closed_trades_with_pnl`` — the
collision-free matcher that attaches each SELL's ``pnl_pct`` to its pair
*inside* the matcher — so these two never diverge from each other. The
win/loss classification logic is intentionally **duplicated** here (not
imported) rather than coupling this module to the holding mirror: a
refactor across both is not worth a few lines of shared slicing.

Note this is no longer true of the **dormant**
``group_benchmark._user_mistakes`` (the disposition arm of the disabled
``BehavioralScore`` cron). It still uses the plain
:func:`fifo_match_closed_trades` and re-buckets via a
``{(ticker, sell_time): holds}`` dict, whose key **collides** when the
same ticker is sold 2+ times on one calendar day (see the collision
discussion in the :func:`fifo_match_closed_trades_with_pnl` docstring).
So on a same-day multi-SELL these live mirrors can disagree with that
dormant path. It is left untouched on purpose — the cron is dormant — and
should be migrated to the collision-free helper if/when it is reactivated.

Where the holding mirror surfaces *example* round trips, this mirror does
**not** — the disposition mirror already exposes examples on the same
page, so this one stays focused on the four aggregate statistics per side
(count, hold days, return %) to avoid duplicate example noise.

Statistics
----------
* **median primary, mean secondary** — realised trade logs (both hold days
  and return %) are heavily right-skewed (one forgotten 400-day loser, or
  a single +300% moonshot, wrecks a mean). The median is the headline; the
  mean is kept for transparency.
* take-profit side: SELL ``pnl_pct > 0`` (gains kept positive).
* stop-loss side:   SELL ``pnl_pct < 0`` (losses keep their negative sign —
  the raw fact, never an absolute value).
* break-even (``pnl_pct == 0``) pairs are excluded from BOTH sides but DO
  count toward ``total_closed_pairs``.
* only **closed** FIFO pairs participate — open positions are ignored.

Public API
----------
:func:`compute_profit_loss_mirror` — pure function over a list of
    ``TradeHistory`` rows. No DB access, no network, no ORM mutation, and
    no score/grade/label field ever in the output.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta
from typing import Iterable

from models import TradeHistory
from services.profile.fifo_util import (
    MatchedPair,
    collapse_pairs_by_sell,
    fifo_match_closed_trades_with_pnl,
    is_holding_seed,
)


# ── tunables ─────────────────────────────────────────────────────────
#
# ``min_pairs`` default: below this many *classified* (non-break-even)
# closed pairs we refuse to report numbers — too small a sample to be a
# meaningful self-reflection (and risks reading as a judgement). Matches
# the spec's ``min_pairs=5``.
_DEFAULT_MIN_PAIRS: int = 5


def _classify_pairs(
    trades: list[TradeHistory],
    *,
    since: datetime | None = None,
) -> tuple[
    list[tuple[MatchedPair, float]],
    list[tuple[MatchedPair, float]],
    int,
]:
    """Split closed FIFO pairs into (take_profit, stop_loss, total_closed).

    Each returned entry is ``(pair, pnl_pct)`` so the caller can compute
    both the hold-day and the return statistics without re-scanning. A
    pair is attributed to the ``pnl_pct`` of **the exact SELL row that
    closed it**, computed inside
    :func:`fifo_match_closed_trades_with_pnl`. This replaces the old
    ``{(ticker, traded_at): pnl_pct}`` dict that *collided* when a user
    closed the same ticker with two SELLs on the same date-grain
    ``traded_at`` — the last SELL's sign then overwrote the earlier one
    and flipped a take-profit pair into the stop-loss bucket (and
    vice-versa). The holding mirror uses the identical helper, so the two
    never diverge.

    Break-even pairs (``pnl_pct == 0``) land in neither bucket but DO
    count toward ``total_closed``.

    ``since`` 는 매도 시각이 그 이후인 쌍만 남긴다. 매칭은 항상 전체 이력으로
    먼저 한다 (2026-09-29): FIFO 전에 창을 자르면 창보다 오래된 매수가 사라져
    창 안의 매도가 로트를 잃었다 — ``persona_classifier_v2`` 가 2026-09-10 에
    고친 것과 같은 버그.
    """
    attributed = fifo_match_closed_trades_with_pnl(trades)
    if since is not None:
        attributed = [(p, pct) for p, pct in attributed if p.sell_time >= since]
    # 2026-09-29: 매도 한 번 = 관찰 한 건. 한 매도가 여러 로트를 닫으면 슬라이스
    # 수만큼 세어 min_pairs 를 혼자 넘겼다. 보유일은 그 매도 슬라이스들의
    # 수량 가중 평균 (collapse_pairs_by_sell 참조).
    attributed = collapse_pairs_by_sell(attributed)
    total_closed = len(attributed)

    take_profit: list[tuple[MatchedPair, float]] = []
    stop_loss: list[tuple[MatchedPair, float]] = []
    for pair, pct in attributed:
        if pct > 0:
            take_profit.append((pair, pct))
        elif pct < 0:
            stop_loss.append((pair, pct))
        # pct == 0 → break-even, excluded from both buckets on purpose.
    return take_profit, stop_loss, total_closed


def _side_summary(
    classified: list[tuple[MatchedPair, float]],
    *,
    pct_key: str,
) -> dict | None:
    """Summarise one side (take-profit or stop-loss).

    Returns ``None`` when the side has zero pairs (the caller uses that to
    set ``one_sided`` and null out the empty side). Otherwise returns
    ``{count, median_hold_days, mean_hold_days, <pct_key>_median, ...}``.

    ``pct_key`` is ``"gain"`` for the take-profit side and ``"loss"`` for
    the stop-loss side, producing ``median_gain_pct`` / ``mean_gain_pct``
    or ``median_loss_pct`` / ``mean_loss_pct`` respectively. Loss
    percentages keep their negative sign — the raw fact, never abs().
    """
    if not classified:
        return None

    # 2026-09-29: 보유 등록 시드 로트만 닫은 매도는 수익률은 유효하지만
    # (평단 = 등록 때 적은 평균매입가) 보유일은 모른다 — 보유일 통계에서만 뺀다.
    holds = [float(pair.hold_days) for pair, _ in classified if not pair.buy_is_seed]
    pcts = [pct for _, pct in classified]

    return {
        "count": len(classified),
        # median primary / mean secondary — both right-skew-resistant on
        # the headline figure. None when every 매도 on this side closed only
        # holding-seed lots (hold time unknown).
        "median_hold_days": round(statistics.median(holds), 1) if holds else None,
        "mean_hold_days": round(statistics.fmean(holds), 1) if holds else None,
        f"median_{pct_key}_pct": round(statistics.median(pcts), 2),
        f"mean_{pct_key}_pct": round(statistics.fmean(pcts), 2),
    }


def compute_profit_loss_mirror(
    trades: Iterable[TradeHistory],
    *,
    period_days: int | None = None,
    min_pairs: int = _DEFAULT_MIN_PAIRS,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> dict:
    """Compute the retrospective profit/loss mirror for one user.

    Parameters
    ----------
    trades : Iterable[TradeHistory]
        All trade rows for a single user. Order-independent; FIFO matching
        sorts internally.
    period_days : int | None
        When set, only trades whose ``traded_at`` falls within the last
        ``period_days`` days (relative to the latest trade in the input,
        for determinism) are considered. ``None`` → all history.
    window_start, window_end : datetime | None
        명시적 창 (naive UTC). ``window_start`` 가 있으면 ``period_days`` 의
        "마지막 체결 기준" 창 대신 이 시각을 창의 시작으로 쓴다.
        ``window_end`` 가 있으면 그 이후의 기록은 통째로 없는 것으로 본다
        (as-of 리포트). 둘 다 FIFO/평단 계산은 창 이전 이력까지 본다 —
        월간 리포트(``services/reports/mirror_pdf``)가 창을 잘라 넣던 것을
        대체한다 (2026-09-29).
    min_pairs : int
        Minimum number of *classified* (non-break-even) closed pairs
        required before numeric stats are reported. Below this,
        ``sufficient_data`` is ``False`` and both sides are ``None``.

    Returns
    -------
    dict
        ``{sufficient_data, one_sided, total_closed_pairs, take_profit,
        stop_loss}``. **No score / grade / ratio / index / label field is
        ever included.** ``take_profit`` / ``stop_loss`` are ``None`` when
        their side is empty or when ``sufficient_data`` is ``False``.
    """
    materialised = [t for t in trades if t is not None]
    if window_end is not None:
        materialised = [
            t for t in materialised
            if t.traded_at and t.traded_at <= window_end
        ]

    # ── optional period window ──────────────────────────────────────
    # 창은 매도 시각으로 쌍을 고른다; FIFO 는 전체 이력으로 맞춘다
    # (_classify_pairs 참조).
    cutoff: datetime | None = None
    if window_start is not None:
        cutoff = window_start
    elif period_days is not None and period_days > 0:
        # 창의 기준점은 마지막 *체결* — 보유 등록 시드는 체결이 아니다 (2026-09-29).
        dated = [t for t in materialised if t.traded_at and not is_holding_seed(t)]
        if dated:
            anchor = max(t.traded_at for t in dated)
            cutoff = anchor - timedelta(days=period_days)
        else:
            materialised = []

    take_profit, stop_loss, total_closed = _classify_pairs(materialised, since=cutoff)
    classified = len(take_profit) + len(stop_loss)

    # ── insufficient data: new user, too few pairs, all break-even ──
    if classified < max(0, min_pairs):
        return {
            "sufficient_data": False,
            "one_sided": False,
            "total_closed_pairs": total_closed,
            "take_profit": None,
            "stop_loss": None,
        }

    take_profit_summary = _side_summary(take_profit, pct_key="gain")
    stop_loss_summary = _side_summary(stop_loss, pct_key="loss")

    one_sided = (take_profit_summary is None) or (stop_loss_summary is None)

    return {
        "sufficient_data": True,
        "one_sided": one_sided,
        "total_closed_pairs": total_closed,
        "take_profit": take_profit_summary,
        "stop_loss": stop_loss_summary,
    }


__all__ = ["compute_profit_loss_mirror"]
