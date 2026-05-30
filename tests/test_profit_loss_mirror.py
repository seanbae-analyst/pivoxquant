"""tests/test_profit_loss_mirror.py — PivoxQuant Profit/Loss Mirror

Covers the retrospective profit/loss holding + return mirror:

    services.behavior.profit_loss_mirror.compute_profit_loss_mirror(trades, ...)
    GET /api/behavior/profit-loss-mirror?period=30d|all

Invariants validated here
-------------------------
- Pure function: no DB / network. Operates on plain TradeHistory rows.
- take_profit = SELL pnl_pct > 0, stop_loss = pnl_pct < 0, break-even
  (== 0) excluded from both buckets BUT counted in total_closed_pairs.
- median is the headline statistic, mean is the secondary (both hold days
  and return %).
- stop_loss return % keeps its NEGATIVE sign (raw fact, never abs()).
- Edge cases: new user / < min_pairs / one-sided / break-even excluded.
- NO score / grade / ratio / index / label field ever appears.
- API: ?period validation, auth required, disclaimer present.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from models import TradeHistory
from services.behavior.profit_loss_mirror import compute_profit_loss_mirror


# ═════════════════════════════════════════════════════════════════════
# Helpers — build plain (unpersisted) TradeHistory rows
# ═════════════════════════════════════════════════════════════════════

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _trade(
    *,
    ticker: str,
    action: str,
    traded_at: datetime | None,
    shares: float = 10.0,
    price_per_share: float = 100.0,
    pnl_pct: float = 0.0,
    name: str = "",
) -> TradeHistory:
    return TradeHistory(
        ticker=ticker,
        name=name,
        action=action,
        shares=shares,
        price_per_share=price_per_share,
        total_value=shares * price_per_share,
        pnl=shares * pnl_pct,
        pnl_pct=pnl_pct,
        traded_at=traded_at,
    )


def _round_trip(
    *,
    ticker: str,
    pnl_pct: float,
    hold_days: float,
    sell_days_ago: float = 1.0,
    name: str = "",
    buy_price: float = 100.0,
) -> list[TradeHistory]:
    """A matched BUY→SELL pair held ``hold_days`` days closing at pnl_pct."""
    now = _now()
    sell_at = now - timedelta(days=sell_days_ago)
    buy_at = sell_at - timedelta(days=hold_days)
    sell_price = buy_price * (1.0 + pnl_pct / 100.0)
    return [
        _trade(ticker=ticker, action="BUY", traded_at=buy_at,
               price_per_share=buy_price, name=name),
        _trade(ticker=ticker, action="SELL", traded_at=sell_at,
               price_per_share=sell_price, pnl_pct=pnl_pct, name=name),
    ]


_FORBIDDEN_SCORE_KEYS = {"ratio", "score", "grade", "index", "label"}


def _assert_no_scoring(result: dict) -> None:
    """The mirror must never surface a score/grade/ratio/index/label."""
    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                assert k not in _FORBIDDEN_SCORE_KEYS, f"forbidden key {k!r}"
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(result)
    # No "disposition"/"편향" leak anywhere in the serialised result.
    blob = repr(result).lower()
    assert "disposition" not in blob
    assert "편향" not in repr(result)


# ═════════════════════════════════════════════════════════════════════
# Edge case: brand-new user (zero closed pairs)
# ═════════════════════════════════════════════════════════════════════

class TestNewUser:
    def test_no_trades_insufficient(self):
        result = compute_profit_loss_mirror([])
        assert result["sufficient_data"] is False
        assert result["one_sided"] is False
        assert result["total_closed_pairs"] == 0
        assert result["take_profit"] is None
        assert result["stop_loss"] is None
        _assert_no_scoring(result)

    def test_only_open_buys_no_closed_pairs(self):
        now = _now()
        trades = [
            _trade(ticker="AAPL", action="BUY", traded_at=now - timedelta(days=3)),
            _trade(ticker="MSFT", action="BUY", traded_at=now - timedelta(days=2)),
        ]
        result = compute_profit_loss_mirror(trades)
        assert result["sufficient_data"] is False
        assert result["total_closed_pairs"] == 0
        _assert_no_scoring(result)


# ═════════════════════════════════════════════════════════════════════
# Edge case: fewer than min_pairs classified → insufficient
# ═════════════════════════════════════════════════════════════════════

class TestBelowMinPairs:
    def test_four_pairs_below_default_min_five(self):
        trades: list[TradeHistory] = []
        for i in range(4):
            trades += _round_trip(ticker=f"T{i}", pnl_pct=5.0, hold_days=2.0)
        result = compute_profit_loss_mirror(trades)
        assert result["sufficient_data"] is False
        assert result["take_profit"] is None
        assert result["stop_loss"] is None
        # raw closed-pair count still honest
        assert result["total_closed_pairs"] == 4
        _assert_no_scoring(result)

    def test_exactly_min_pairs_is_sufficient(self):
        trades: list[TradeHistory] = []
        for i in range(3):
            trades += _round_trip(ticker=f"W{i}", pnl_pct=5.0, hold_days=2.0)
        for i in range(2):
            trades += _round_trip(ticker=f"L{i}", pnl_pct=-5.0, hold_days=10.0)
        result = compute_profit_loss_mirror(trades)  # 5 classified == min
        assert result["sufficient_data"] is True
        assert result["total_closed_pairs"] == 5
        _assert_no_scoring(result)

    def test_custom_min_pairs(self):
        trades: list[TradeHistory] = []
        for i in range(6):
            trades += _round_trip(ticker=f"T{i}", pnl_pct=5.0, hold_days=2.0)
        result = compute_profit_loss_mirror(trades, min_pairs=10)
        assert result["sufficient_data"] is False


# ═════════════════════════════════════════════════════════════════════
# Edge case: one-sided (all profit / all loss)
# ═════════════════════════════════════════════════════════════════════

class TestOneSided:
    def test_all_take_profit(self):
        trades: list[TradeHistory] = []
        for i in range(6):
            trades += _round_trip(ticker=f"W{i}", pnl_pct=8.0, hold_days=3.0)
        result = compute_profit_loss_mirror(trades)
        assert result["sufficient_data"] is True
        assert result["one_sided"] is True
        assert result["take_profit"] is not None
        assert result["take_profit"]["count"] == 6
        assert result["stop_loss"] is None
        _assert_no_scoring(result)

    def test_all_stop_loss(self):
        trades: list[TradeHistory] = []
        for i in range(6):
            trades += _round_trip(ticker=f"L{i}", pnl_pct=-8.0, hold_days=20.0)
        result = compute_profit_loss_mirror(trades)
        assert result["sufficient_data"] is True
        assert result["one_sided"] is True
        assert result["take_profit"] is None
        assert result["stop_loss"] is not None
        assert result["stop_loss"]["count"] == 6
        _assert_no_scoring(result)


# ═════════════════════════════════════════════════════════════════════
# Edge case: break-even (pnl_pct == 0) excluded but counted
# ═════════════════════════════════════════════════════════════════════

class TestBreakEvenExcluded:
    def test_break_even_pairs_not_classified_but_counted(self):
        trades: list[TradeHistory] = []
        for i in range(3):
            trades += _round_trip(ticker=f"W{i}", pnl_pct=5.0, hold_days=2.0)
        for i in range(3):
            trades += _round_trip(ticker=f"L{i}", pnl_pct=-5.0, hold_days=15.0)
        # two break-even round trips — must be ignored from both buckets
        for i in range(2):
            trades += _round_trip(ticker=f"E{i}", pnl_pct=0.0, hold_days=7.0)
        result = compute_profit_loss_mirror(trades)
        assert result["sufficient_data"] is True
        # total_closed counts ALL closed pairs incl. break-even (8)
        assert result["total_closed_pairs"] == 8
        # but classified buckets exclude the 2 break-even
        assert result["take_profit"]["count"] == 3
        assert result["stop_loss"]["count"] == 3
        _assert_no_scoring(result)


# ═════════════════════════════════════════════════════════════════════
# Sign preservation: loss % stays negative
# ═════════════════════════════════════════════════════════════════════

class TestLossSignPreserved:
    def test_loss_pct_keeps_negative_sign(self):
        trades: list[TradeHistory] = []
        for i in range(3):
            trades += _round_trip(ticker=f"W{i}", pnl_pct=6.0, hold_days=2.0)
        for i in range(3):
            trades += _round_trip(ticker=f"L{i}", pnl_pct=-7.0, hold_days=18.0)
        result = compute_profit_loss_mirror(trades)
        stop = result["stop_loss"]
        # the raw fact — a loss is a negative number, never abs()
        assert stop["median_loss_pct"] == -7.0
        assert stop["mean_loss_pct"] == -7.0
        assert stop["median_loss_pct"] < 0
        # take-profit side stays positive
        take = result["take_profit"]
        assert take["median_gain_pct"] == 6.0
        assert take["mean_gain_pct"] == 6.0
        _assert_no_scoring(result)

    def test_side_keys_are_named_per_sign(self):
        """take_profit exposes *_gain_pct, stop_loss exposes *_loss_pct."""
        trades: list[TradeHistory] = []
        for i in range(3):
            trades += _round_trip(ticker=f"W{i}", pnl_pct=4.0, hold_days=2.0)
        for i in range(3):
            trades += _round_trip(ticker=f"L{i}", pnl_pct=-4.0, hold_days=9.0)
        result = compute_profit_loss_mirror(trades)
        assert set(result["take_profit"]) == {
            "count", "median_hold_days", "mean_hold_days",
            "median_gain_pct", "mean_gain_pct",
        }
        assert set(result["stop_loss"]) == {
            "count", "median_hold_days", "mean_hold_days",
            "median_loss_pct", "mean_loss_pct",
        }


# ═════════════════════════════════════════════════════════════════════
# Statistics: median primary (right-skew resistant), mean secondary
# ═════════════════════════════════════════════════════════════════════

class TestStatistics:
    def test_median_hold_resists_outlier(self):
        """One forgotten loser held 400d must NOT move the median much,
        while the mean blows up — proves median is the right headline."""
        trades: list[TradeHistory] = []
        for d in (8.0, 9.0, 10.0, 11.0):
            trades += _round_trip(ticker=f"L{d}", pnl_pct=-5.0, hold_days=d)
        trades += _round_trip(ticker="LX", pnl_pct=-5.0, hold_days=400.0)
        for i in range(2):
            trades += _round_trip(ticker=f"W{i}", pnl_pct=5.0, hold_days=3.0)
        result = compute_profit_loss_mirror(trades)
        stop = result["stop_loss"]
        # median ~ 10 (middle of 8,9,10,11,400), mean dragged way up
        assert stop["median_hold_days"] == 10.0
        assert stop["mean_hold_days"] > 80.0

    def test_median_gain_resists_moonshot(self):
        """A single +300% moonshot must not drag the median gain."""
        trades: list[TradeHistory] = []
        for g in (4.0, 5.0, 6.0, 7.0):
            trades += _round_trip(ticker=f"W{int(g)}", pnl_pct=g, hold_days=2.0)
        trades += _round_trip(ticker="WX", pnl_pct=300.0, hold_days=2.0)
        for i in range(2):
            trades += _round_trip(ticker=f"L{i}", pnl_pct=-5.0, hold_days=20.0)
        result = compute_profit_loss_mirror(trades)
        take = result["take_profit"]
        # median resists the moonshot, mean is dragged up
        assert take["median_gain_pct"] == 6.0
        assert take["mean_gain_pct"] > 60.0


# ═════════════════════════════════════════════════════════════════════
# Period window (30d vs all)
# ═════════════════════════════════════════════════════════════════════

class TestPeriodWindow:
    def test_period_days_filters_old_trades(self):
        trades: list[TradeHistory] = []
        for i in range(5):
            trades += _round_trip(ticker=f"R{i}", pnl_pct=5.0, hold_days=2.0,
                                  sell_days_ago=3.0)
        for i in range(5):
            trades += _round_trip(ticker=f"O{i}", pnl_pct=-5.0, hold_days=2.0,
                                  sell_days_ago=60.0)
        all_result = compute_profit_loss_mirror(trades)  # period None
        assert all_result["total_closed_pairs"] == 10

        win_result = compute_profit_loss_mirror(trades, period_days=30)
        # only the 5 recent take-profit pairs survive the window
        assert win_result["total_closed_pairs"] == 5
        assert win_result["take_profit"]["count"] == 5
        assert win_result["stop_loss"] is None


# ═════════════════════════════════════════════════════════════════════
# API surface
# ═════════════════════════════════════════════════════════════════════

class TestApi:
    def _insert(self, app, user_id, trades):
        from extensions import db
        with app.app_context():
            for t in trades:
                t.user_id = user_id
                db.session.add(t)
            db.session.commit()

    def test_requires_auth(self, client):
        resp = client.get("/api/behavior/profit-loss-mirror")
        assert resp.status_code in (401, 403)

    def test_new_user_insufficient(self, client, auth_user):
        resp = client.get("/api/behavior/profit-loss-mirror")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["ok"] is True
        assert body["sufficient_data"] is False
        assert body["period"] == "all"
        assert "disclaimer" in body
        assert not (_FORBIDDEN_SCORE_KEYS & set(body))

    def test_invalid_period_rejected(self, client, auth_user):
        resp = client.get("/api/behavior/profit-loss-mirror?period=bogus")
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "BAD_INPUT"

    def test_arbitrary_integer_period_rejected(self, client, auth_user):
        # whitelist only — never echo a user-supplied window back.
        resp = client.get("/api/behavior/profit-loss-mirror?period=90")
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "BAD_INPUT"

    def test_populated_response(self, client, auth_user, app):
        trades: list[TradeHistory] = []
        for i in range(4):
            trades += _round_trip(ticker=f"W{i}", pnl_pct=6.0, hold_days=2.0)
        for i in range(3):
            trades += _round_trip(ticker=f"L{i}", pnl_pct=-6.0, hold_days=20.0)
        self._insert(app, auth_user["id"], trades)

        resp = client.get("/api/behavior/profit-loss-mirror?period=all")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["sufficient_data"] is True
        assert body["one_sided"] is False
        assert body["take_profit"]["count"] == 4
        assert body["stop_loss"]["count"] == 3
        # loss side keeps its negative sign through the envelope
        assert body["stop_loss"]["median_loss_pct"] < 0
        assert body["take_profit"]["median_gain_pct"] > 0
        _assert_no_scoring(body)

    def test_period_30d_param_passes_through(self, client, auth_user, app):
        resp = client.get("/api/behavior/profit-loss-mirror?period=30d")
        assert resp.status_code == 200
        assert resp.get_json()["period"] == "30d"
