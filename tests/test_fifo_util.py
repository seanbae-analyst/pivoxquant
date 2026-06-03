"""tests/test_fifo_util.py — PivoxQuant shared FIFO normaliser.

Unit coverage for the core trade normaliser that every behavioural mirror
shares (``services.profile.fifo_util``). Until now it was exercised only
*indirectly* through the mirrors; these tests pin two correctness properties
the mirror audit (2026-06-02) flagged:

1. Determinism on same-timestamp trades — date-grain manual entries share a
   midnight ``traded_at``, so matching must fall back to row ``id`` order, not
   DB-arbitrary order (regression: missing sort tiebreaker).
2. ``fifo_open_position_ages`` must not collapse two same-ticker BUYs that
   share a ``traded_at`` into one bucket — the old ``{(ticker, buy_time): qty}``
   index summed them and silently dropped still-open shares.
"""
from __future__ import annotations

from datetime import datetime

from models import TradeHistory
from services.profile.fifo_util import (
    fifo_match_closed_trades,
    fifo_open_position_ages,
)


_T0 = datetime(2026, 1, 1)   # naive-UTC, the date-grain "midnight" all
_T1 = datetime(2026, 1, 10)  # manual same-day entries collapse to.


def _trade(
    *,
    id: int | None,
    ticker: str,
    action: str,
    traded_at: datetime,
    shares: float = 10.0,
    price_per_share: float = 100.0,
    pnl_pct: float = 0.0,
) -> TradeHistory:
    return TradeHistory(
        id=id,
        ticker=ticker,
        action=action,
        shares=shares,
        price_per_share=price_per_share,
        total_value=shares * price_per_share,
        pnl=shares * pnl_pct,
        pnl_pct=pnl_pct,
        traded_at=traded_at,
    )


# ── #2: deterministic FIFO order on same-timestamp lots ──────────────────

def test_same_timestamp_buys_match_in_id_order_not_input_order():
    """Two BUYs of one ticker share a ``traded_at``; the SELL must consume the
    lower-``id`` lot first regardless of input list order.

    The buys are fed in REVERSE id order — a stable sort with no tiebreaker
    would match the $200 lot (input-first); the id tiebreaker makes it match
    the $100 lot deterministically.
    """
    trades = [
        _trade(id=2, ticker="AAPL", action="BUY", traded_at=_T0, price_per_share=200.0),
        _trade(id=1, ticker="AAPL", action="BUY", traded_at=_T0, price_per_share=100.0),
        _trade(id=3, ticker="AAPL", action="SELL", traded_at=_T1, price_per_share=300.0),
    ]
    pairs = fifo_match_closed_trades(trades)
    assert len(pairs) == 1
    # FIFO by (traded_at, id) → the id=1 ($100) lot is consumed first.
    assert pairs[0].buy_price == 100.0


# ── #3: open-age collision on same-timestamp BUYs ────────────────────────

def test_open_ages_keeps_both_same_timestamp_buys():
    """Two same-ticker BUYs at the same ``traded_at``, one closed by a later
    SELL → exactly one slice stays open (regression: the old index zeroed
    both and reported nothing open)."""
    trades = [
        _trade(id=1, ticker="AAPL", action="BUY", traded_at=_T0, shares=10.0),
        _trade(id=2, ticker="AAPL", action="BUY", traded_at=_T0, shares=10.0),
        _trade(id=3, ticker="AAPL", action="SELL", traded_at=_T1, shares=10.0),
    ]
    ages = fifo_open_position_ages(trades)
    # One 10-share slice remains open, held _T0 → reference (latest = _T1) = 9d.
    assert len(ages) == 1
    assert ages[0] == (_T1 - _T0).days  # 9.0


def test_open_ages_simple_single_open_buy():
    trades = [_trade(id=1, ticker="MSFT", action="BUY", traded_at=_T0, shares=5.0)]
    ages = fifo_open_position_ages(trades)
    assert len(ages) == 1


def test_open_ages_fully_closed_is_empty():
    trades = [
        _trade(id=1, ticker="MSFT", action="BUY", traded_at=_T0, shares=5.0),
        _trade(id=2, ticker="MSFT", action="SELL", traded_at=_T1, shares=5.0),
    ]
    assert fifo_open_position_ages(trades) == []


def test_open_ages_partial_close_leaves_remainder():
    """Buy 10, sell 4 → 6 still open as a single slice."""
    trades = [
        _trade(id=1, ticker="MSFT", action="BUY", traded_at=_T0, shares=10.0),
        _trade(id=2, ticker="MSFT", action="SELL", traded_at=_T1, shares=4.0),
    ]
    ages = fifo_open_position_ages(trades)
    assert len(ages) == 1


def test_empty_input_returns_empty():
    assert fifo_match_closed_trades([]) == []
    assert fifo_open_position_ages([]) == []
