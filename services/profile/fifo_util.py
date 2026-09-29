"""FIFO trade-pair matcher — single source of truth.

Pairs BUY/SELL ``TradeHistory`` rows on a per-ticker FIFO queue and
returns one record per matched share-quantity slice. Removes a 4-way
duplication previously embedded in:

  * ``persona_analytics._avg_holding_period``
  * ``rolling_metrics._holding_period_days``
  * ``group_benchmark._avg_holding_days`` and ``_user_mistakes``
  * ``persona_classifier_v2._hold_time_cv`` and ``_loss_cut_discipline``

The previous copies had subtly different fallback policies (``utcnow``
vs ``trades[-1].traded_at``); this module canonicalises the fallback to
**``trades[-1].traded_at`` first, ``datetime.utcnow()`` last** so that
money/CAGR computations across modules are guaranteed to agree to the
nearest microsecond.

Why a dedicated module
----------------------
The earlier copies were copy-pasted with hand-edits — meaning a bug fix
in one branch (e.g. correct epsilon handling, deterministic queue
mutation) silently failed to propagate. Money math has zero tolerance
for divergence: a 0.01% drift in average holding period changes the
CAGR-from-pnls denominator and produces user-visible Sharpe deltas.
Every caller now goes through :func:`fifo_match_closed_trades`.

Public API
----------
:func:`fifo_match_closed_trades` — primary entry point. Returns matched
    pairs as plain tuples (no ORM object exposure).
:func:`fifo_open_position_ages` — fallback for callers that need
    elapsed time on still-open positions when no round trip closed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, NamedTuple

from models import TradeHistory
from models.trade_history import (
    HOLDING_ADJUST_SOURCE,
    HOLDING_SEED_SOURCE,
    REGISTRATION_SOURCES,
)


# Numerical epsilon for share-quantity comparisons. Matches the value
# used historically across all four duplicate sites — do NOT loosen
# without a regression test in tests/test_fifo_util.py.
_SHARE_EPSILON: float = 1e-9


class MatchedPair(NamedTuple):
    """One FIFO-matched (BUY → SELL) slice.

    Attributes
    ----------
    ticker : str
        Upper-cased ticker symbol the pair belongs to.
    quantity : float
        Share quantity of this slice. A single SELL of 100 shares against
        three earlier BUYs of 30/40/30 produces three pairs.
    buy_time : datetime
        The BUY's ``traded_at`` (used as the open of the round trip).
    sell_time : datetime
        The SELL's ``traded_at`` (the close of the round trip).
    buy_price : float
        Per-share price paid on the BUY leg. ``0.0`` when the source row
        has no ``price_per_share`` populated — callers that need price
        must guard for that.
    sell_price : float
        Per-share price received on the SELL leg.
    sell_pnl : float
        Realised pnl reported on the SELL row (``TradeHistory.pnl``).
        Note this is per-row, NOT per-slice — when one SELL closes
        multiple BUYs the same pnl appears on every emitted pair.
        Callers that need slice-level pnl should derive it from prices.
    """
    ticker: str
    quantity: float
    buy_time: datetime
    sell_time: datetime
    buy_price: float
    sell_price: float
    sell_pnl: float
    # 2026-09-29 — 이 슬라이스를 닫은 매도 행의 식별자 (한 번의 매칭 호출 안에서
    # 매도 행마다 0,1,2… 로 매긴다). 한 매도가 여러 매수 로트를 닫으면 슬라이스가
    # 여럿 나오는데, "매도 한 번 = 관찰 한 건" 으로 세려면 이 값으로 묶는다
    # (:func:`collapse_pairs_by_sell`). ``-1`` = 알 수 없음.
    sell_seq: int = -1
    # 2026-09-29 — 이 슬라이스의 매수 로트가 보유 등록 시드인가
    # (``TradeHistory.source == "holding_seed"``, :func:`is_holding_seed`).
    # 시드의 ``buy_time`` 은 등록 시각이지 실제 매수일이 아니므로 보유기간
    # 통계를 내는 호출자는 이 슬라이스를 건너뛴다. 수량·단가는 유효하다
    # (평단 = 등록 때 적은 평균매입가).
    buy_is_seed: bool = False
    # 2026-09-29 — 이 슬라이스를 닫은 매도 행이 보유 등록 조정인가
    # (``TradeHistory.source == "holding_adjust"``, :func:`is_holding_adjust`).
    # 조정은 기록된 매도 없이 보유가 줄어든 것을 로트에 반영할 뿐 관찰된 매도가
    # 아니다 — 로트는 소모하지만 통계를 내는 호출자는 이 슬라이스를 건너뛴다.
    # :func:`collapse_pairs_by_sell` 은 조정 매도를 아예 내보내지 않는다.
    sell_is_adjust: bool = False

    @property
    def hold_days(self) -> float:
        """Days held for this slice — clamped at zero (no negative holds)."""
        delta_seconds = (self.sell_time - self.buy_time).total_seconds()
        return max(0.0, delta_seconds / 86400.0)


def is_holding_seed(t) -> bool:
    """True when ``t`` is a holding-registration seed row, not a fill.

    Seeds are 매수 rows written when the user registers shares they already
    hold (``TradeHistory.source == "holding_seed"``). They feed FIFO lots
    (quantity / cost) but their ``traded_at`` is the registration time, so
    they are never a hold-time observation, a counted fill or a follow-on.
    Rows without the attribute (plain test doubles) are not seeds.
    """
    return (getattr(t, "source", None) or "") == HOLDING_SEED_SOURCE


def is_holding_adjust(t) -> bool:
    """True when ``t`` is a holding-registration adjust 매도 row, not a fill.

    Written when a registration path lowers a holding without a recorded
    매도 (``TradeHistory.source == "holding_adjust"``). It consumes FIFO lots
    so they stay in sync with the holding, but it is never an observed 매도:
    no hold time, no P&L disposition, no fill count, no gross value.
    """
    return (getattr(t, "source", None) or "") == HOLDING_ADJUST_SOURCE


def is_registration_row(t) -> bool:
    """True for any row a registration path wrote (seed 매수 or adjust 매도)
    rather than a recorded fill — the rows fill counts / gross values and
    period anchors leave out."""
    return (getattr(t, "source", None) or "") in REGISTRATION_SOURCES


def fifo_match_closed_trades(
    trades: Iterable[TradeHistory],
) -> list[MatchedPair]:
    """Pair BUY/SELL ``TradeHistory`` rows via per-ticker FIFO queues.

    Parameters
    ----------
    trades : Iterable[TradeHistory]
        Trade rows for a single user. Order does not have to be sorted —
        this function sorts internally by ``traded_at`` ascending so
        out-of-order ingestion (e.g. backfill) does not corrupt the
        queue. Rows with no ``traded_at`` or no ``ticker`` are skipped.

    Returns
    -------
    list[MatchedPair]
        Matched slices in chronological SELL order. Empty when there are
        no closed round trips. **Open** positions (BUYs without a SELL)
        are NOT in the result — use :func:`fifo_open_position_ages`
        for the elapsed-time fallback path.

    Notes
    -----
    * SELL quantities exceeding all queued BUYs are truncated silently
      (the same behaviour the four legacy implementations had — short
      positions are not modelled in TradeHistory).
    * Share comparisons use ``_SHARE_EPSILON`` (1e-9) to guard against
      float drift on partial fills.
    """
    ordered = sorted(
        (t for t in trades if t.traded_at and t.ticker),
        # Tiebreak on row id so same-timestamp trades (date-grain manual
        # entries share a midnight ``traded_at``) match in a stable, insertion
        # order instead of DB-arbitrary order — deterministic FIFO pairing.
        key=lambda t: (t.traded_at, t.id or 0),
    )

    # ticker → FIFO queue of (time, remaining_shares, buy_price, is_seed)
    opens: dict[str, list[tuple[datetime, float, float, bool]]] = {}
    pairs: list[MatchedPair] = []
    sell_seq = -1

    for t in ordered:
        action = (t.action or "").upper()
        key = t.ticker.upper()
        shares = float(t.shares or 0.0)
        if shares <= 0:
            continue
        price = float(t.price_per_share or 0.0)
        if action == "BUY":
            opens.setdefault(key, []).append(
                (t.traded_at, shares, price, is_holding_seed(t))
            )
            continue
        if action != "SELL":
            continue
        sell_seq += 1
        remaining = shares
        sell_pnl = float(t.pnl or 0.0)
        sell_adjust = is_holding_adjust(t)
        queue = opens.get(key, [])
        while remaining > _SHARE_EPSILON and queue:
            buy_time, buy_sh, buy_px, buy_seed = queue[0]
            take = min(buy_sh, remaining)
            pairs.append(
                MatchedPair(
                    ticker=key,
                    quantity=take,
                    buy_time=buy_time,
                    sell_time=t.traded_at,
                    buy_price=buy_px,
                    sell_price=price,
                    sell_pnl=sell_pnl,
                    sell_seq=sell_seq,
                    buy_is_seed=buy_seed,
                    sell_is_adjust=sell_adjust,
                )
            )
            remaining -= take
            if take >= buy_sh - _SHARE_EPSILON:
                queue.pop(0)
            else:
                queue[0] = (buy_time, buy_sh - take, buy_px, buy_seed)
    return pairs


def fifo_match_closed_trades_with_pnl(
    trades: Iterable[TradeHistory],
) -> list[tuple[MatchedPair, float]]:
    """Like :func:`fifo_match_closed_trades`, but attribute each matched
    pair to **the exact SELL row that closed it**, returning
    ``(pair, sell_pnl_pct)`` tuples.

    Why this exists
    ---------------
    Callers that split pairs into win/loss buckets used to re-derive the
    SELL's ``pnl_pct`` by looking it up in a
    ``{(ticker, traded_at): pnl_pct}`` dict keyed on the pair's
    ``sell_time``. That mapping **collides** when a user closes the same
    ticker with two or more SELLs on the same ``traded_at`` (date-grain
    parsing makes intraday SELLs share a timestamp): the last SELL's
    ``pnl_pct`` overwrites the earlier one, so every pair on that key —
    including pairs closed by an *earlier, oppositely-signed* SELL — gets
    bucketed by the wrong sign (a +30% take-profit shown as a loss, and
    vice-versa).

    Attributing the pnl_pct **inside** the matcher, where the SELL row's
    identity is unambiguous, removes the collision entirely: each pair
    carries the pnl_pct of precisely the SELL that produced it, even when
    several same-key SELLs interleave. A single SELL that closes multiple
    BUYs yields multiple pairs that all share that SELL's pnl_pct — the
    intended grouping.

    The order/contract is identical to :func:`fifo_match_closed_trades`
    (chronological SELL order, open positions excluded); only the per-pair
    pnl_pct attribution is added. ``pnl_pct`` defaults to ``0.0`` when the
    SELL row's stored value is missing or unparseable.
    """
    ordered = sorted(
        (t for t in trades if t.traded_at and t.ticker),
        # Tiebreak on row id so same-timestamp trades (date-grain manual
        # entries share a midnight ``traded_at``) match in a stable, insertion
        # order instead of DB-arbitrary order — deterministic FIFO pairing.
        key=lambda t: (t.traded_at, t.id or 0),
    )

    opens: dict[str, list[tuple[datetime, float, float, bool]]] = {}
    attributed: list[tuple[MatchedPair, float]] = []
    sell_seq = -1

    for t in ordered:
        action = (t.action or "").upper()
        key = t.ticker.upper()
        shares = float(t.shares or 0.0)
        if shares <= 0:
            continue
        price = float(t.price_per_share or 0.0)
        if action == "BUY":
            opens.setdefault(key, []).append(
                (t.traded_at, shares, price, is_holding_seed(t))
            )
            continue
        if action != "SELL":
            continue
        try:
            sell_pnl_pct = float(t.pnl_pct or 0.0)
        except (TypeError, ValueError):
            sell_pnl_pct = 0.0
        sell_seq += 1
        remaining = shares
        sell_pnl = float(t.pnl or 0.0)
        sell_adjust = is_holding_adjust(t)
        queue = opens.get(key, [])
        while remaining > _SHARE_EPSILON and queue:
            buy_time, buy_sh, buy_px, buy_seed = queue[0]
            take = min(buy_sh, remaining)
            attributed.append((
                MatchedPair(
                    ticker=key,
                    quantity=take,
                    buy_time=buy_time,
                    sell_time=t.traded_at,
                    buy_price=buy_px,
                    sell_price=price,
                    sell_pnl=sell_pnl,
                    sell_seq=sell_seq,
                    buy_is_seed=buy_seed,
                    sell_is_adjust=sell_adjust,
                ),
                sell_pnl_pct,
            ))
            remaining -= take
            if take >= buy_sh - _SHARE_EPSILON:
                queue.pop(0)
            else:
                queue[0] = (buy_time, buy_sh - take, buy_px, buy_seed)
    return attributed


def collapse_pairs_by_sell(
    attributed: Iterable[tuple[MatchedPair, float]],
) -> list[tuple[MatchedPair, float]]:
    """Merge the slices of each 매도 행 into ONE ``(pair, pnl_pct)`` entry.

    2026-09-29: the holding / profit-loss mirrors counted FIFO *slices*, so
    one 매도 that closed five 매수 lots counted as five round trips and passed
    ``min_pairs=5`` on its own. A user decides once per 매도 — that is the
    unit these mirrors count.

    The merged entry keeps the ticker, ``sell_time``, sell price, ``sell_seq``
    and the 매도 행's ``pnl_pct`` (shared by all its slices). ``quantity`` is
    the summed quantity and ``buy_price`` the share-weighted cost. Hold days
    are the **share-weighted mean** of the slices' holds: ``buy_time`` is set
    to ``sell_time - weighted_hold`` so ``pair.hold_days`` returns exactly
    that. (Chosen over quantity-weighting the median across all slices so
    every 매도 is one observation with one hold value.)

    Input order is preserved by first appearance; entries whose
    ``sell_seq`` is ``-1`` (unknown) are passed through unmerged.

    Holding-registration adjust 매도 (``sell_is_adjust``) are dropped — they
    keep the FIFO lots in sync but are not an observed 매도 (2026-09-29).
    """
    groups: dict[int, list[tuple[MatchedPair, float]]] = {}
    order: list[int | tuple[MatchedPair, float]] = []
    for pair, pct in attributed:
        if pair.sell_is_adjust:
            continue
        if pair.sell_seq < 0:
            order.append((pair, pct))
            continue
        if pair.sell_seq not in groups:
            groups[pair.sell_seq] = []
            order.append(pair.sell_seq)
        groups[pair.sell_seq].append((pair, pct))

    out: list[tuple[MatchedPair, float]] = []
    for item in order:
        if not isinstance(item, int):
            out.append(item)
            continue
        slices = groups[item]
        first, pct = slices[0]
        qty = sum(p.quantity for p, _ in slices)
        if qty <= _SHARE_EPSILON:
            out.append(slices[0])
            continue
        # 2026-09-29: hold days come from the non-seed slices only — a seed's
        # buy_time is the registration time, not a purchase date. When every
        # slice is a seed the merged entry is flagged ``buy_is_seed`` and its
        # hold value must not be used (callers skip it).
        dated = [p for p, _ in slices if not p.buy_is_seed] or [p for p, _ in slices]
        dated_qty = sum(p.quantity for p in dated) or qty
        hold = sum(p.hold_days * p.quantity for p in dated) / dated_qty
        cost = sum(p.buy_price * p.quantity for p, _ in slices) / qty
        out.append((
            first._replace(
                quantity=qty,
                buy_time=first.sell_time - timedelta(days=hold),
                buy_price=cost,
                buy_is_seed=all(p.buy_is_seed for p, _ in slices),
            ),
            pct,
        ))
    return out


def fifo_open_position_ages(
    trades: Iterable[TradeHistory],
    *,
    reference_time: datetime | None = None,
    include_seeds: bool = True,
) -> list[float]:
    """Return age-in-days of every still-open BUY share-slice.

    Used as the fallback path when no closed round trips exist but we
    still need a meaningful "average holding period" for a user with
    only open positions (e.g. brand-new long-only buyers).

    Parameters
    ----------
    trades : Iterable[TradeHistory]
        Same input as :func:`fifo_match_closed_trades`.
    reference_time : datetime | None
        Anchor for "now". When ``None`` the function picks **the latest
        ``traded_at`` in the input** as the reference (deterministic),
        falling back to :func:`datetime.utcnow` only when the input is
        empty. This priority order — ``traded_at`` > ``utcnow`` —
        matches the historical ``rolling_metrics`` behaviour and is the
        canonical contract going forward.
    include_seeds : bool
        ``False`` leaves out still-open holding-registration seed lots
        (:func:`is_holding_seed`) — their age would be time since
        registration, not since purchase. They still absorb 매도 수량 in
        FIFO order either way.

    Returns
    -------
    list[float]
        Days each open share-slice has been held. Empty when nothing
        is open.
    """
    materialised = [t for t in trades if t.traded_at and t.ticker]
    if reference_time is None:
        if materialised:
            reference_time = max(t.traded_at for t in materialised)
        else:
            # 2026-05-08 (NEW-D): datetime.utcnow() is deprecated in Python
            # 3.12+. Use timezone-aware now() then strip tzinfo so we keep
            # the naive-UTC contract that traded_at values follow (see
            # User.created_at convention referenced above).
            reference_time = datetime.now(timezone.utc).replace(tzinfo=None)

    # Replay the FIFO match but KEEP the residual open queue — each leftover
    # slice is a still-open BUY. Reading open lots straight off the queue
    # (instead of a ``{(ticker, buy_time): qty}`` index) avoids a collision:
    # two same-ticker BUYs that share a date-grain ``traded_at`` are distinct
    # queue entries, so consuming one never zeroes the other. The old index
    # summed them under one key, so a user with ≥2 same-day buys of one ticker
    # had still-open shares silently dropped from this average-holding fallback.
    ordered = sorted(materialised, key=lambda t: (t.traded_at, t.id or 0))
    opens: dict[str, list[list]] = {}  # ticker → [[buy_time, remaining_sh, is_seed], …]
    for t in ordered:
        action = (t.action or "").upper()
        key = t.ticker.upper()
        shares = float(t.shares or 0.0)
        if shares <= 0:
            continue
        if action == "BUY":
            opens.setdefault(key, []).append([t.traded_at, shares, is_holding_seed(t)])
            continue
        if action != "SELL":
            continue
        remaining = shares
        queue = opens.get(key, [])
        while remaining > _SHARE_EPSILON and queue:
            buy_time, buy_sh, _seed = queue[0]
            take = min(buy_sh, remaining)
            remaining -= take
            if take >= buy_sh - _SHARE_EPSILON:
                queue.pop(0)
            else:
                queue[0][1] = buy_sh - take

    elapsed: list[float] = []
    for queue in opens.values():
        for buy_time, remaining_sh, seed in queue:
            if remaining_sh <= _SHARE_EPSILON:
                continue
            if seed and not include_seeds:
                continue
            delta_days = max(
                0.0, (reference_time - buy_time).total_seconds() / 86400.0
            )
            elapsed.append(delta_days)
    return elapsed


__all__ = [
    "MatchedPair",
    "collapse_pairs_by_sell",
    "fifo_match_closed_trades",
    "fifo_match_closed_trades_with_pnl",
    "fifo_open_position_ages",
    "is_holding_adjust",
    "is_holding_seed",
    "is_registration_row",
]
