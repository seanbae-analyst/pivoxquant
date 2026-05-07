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

from datetime import datetime, timezone
from typing import Iterable, NamedTuple

from models import TradeHistory


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

    @property
    def hold_days(self) -> float:
        """Days held for this slice — clamped at zero (no negative holds)."""
        delta_seconds = (self.sell_time - self.buy_time).total_seconds()
        return max(0.0, delta_seconds / 86400.0)


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
        key=lambda t: t.traded_at,
    )

    # ticker → FIFO queue of (time, remaining_shares, buy_price)
    opens: dict[str, list[tuple[datetime, float, float]]] = {}
    pairs: list[MatchedPair] = []

    for t in ordered:
        action = (t.action or "").upper()
        key = t.ticker.upper()
        shares = float(t.shares or 0.0)
        if shares <= 0:
            continue
        price = float(t.price_per_share or 0.0)
        if action == "BUY":
            opens.setdefault(key, []).append((t.traded_at, shares, price))
            continue
        if action != "SELL":
            continue
        remaining = shares
        sell_pnl = float(t.pnl or 0.0)
        queue = opens.get(key, [])
        while remaining > _SHARE_EPSILON and queue:
            buy_time, buy_sh, buy_px = queue[0]
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
                )
            )
            remaining -= take
            if take >= buy_sh - _SHARE_EPSILON:
                queue.pop(0)
            else:
                queue[0] = (buy_time, buy_sh - take, buy_px)
    return pairs


def fifo_open_position_ages(
    trades: Iterable[TradeHistory],
    *,
    reference_time: datetime | None = None,
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

    pairs = fifo_match_closed_trades(materialised)
    # We need the queue *after* matching — easiest is to re-walk and
    # let pairs absorb the closed BUYs.
    closed_index: dict[tuple[str, datetime], float] = {}
    for p in pairs:
        closed_index[(p.ticker, p.buy_time)] = (
            closed_index.get((p.ticker, p.buy_time), 0.0) + p.quantity
        )

    ordered_buys = [
        t for t in sorted(materialised, key=lambda x: x.traded_at)
        if (t.action or "").upper() == "BUY"
    ]

    elapsed: list[float] = []
    for t in ordered_buys:
        opened = float(t.shares or 0.0)
        if opened <= 0:
            continue
        consumed = closed_index.get((t.ticker.upper(), t.traded_at), 0.0)
        # Guard against rounding making consumed appear slightly larger.
        remaining = max(0.0, opened - consumed)
        if remaining <= _SHARE_EPSILON:
            continue
        delta_days = max(
            0.0, (reference_time - t.traded_at).total_seconds() / 86400.0
        )
        elapsed.append(delta_days)
    return elapsed


__all__ = [
    "MatchedPair",
    "fifo_match_closed_trades",
    "fifo_open_position_ages",
]
