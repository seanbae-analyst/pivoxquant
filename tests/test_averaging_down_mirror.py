"""tests/test_averaging_down_mirror.py — PivoxQuant Averaging-Down Mirror

Covers the retrospective follow-on-add mirror:

    services.behavior.averaging_down_mirror.compute_averaging_down_mirror(...)
    GET /api/behavior/averaging-down-mirror?period=30d|all

Invariants validated here
-------------------------
- Pure function: no DB / network / live price / FX call. Operates on plain
  TradeHistory rows.
- Reports INTEGER COUNTS only (follow-on adds, and how many fell below /
  above / at the position's running average cost) — NEVER a ratio /
  percentage / score / grade / label.
- The *first* BUY opening a position is NOT a follow-on; only adds to an
  already-held position count.
- Partial sells leave the running average unchanged; a full liquidation
  resets the position so a later re-buy is a fresh open (not a follow-on).
- Zero-price / non-positive-share rows are skipped from classification.
- Deterministic regardless of input order.
- NO score / grade / ratio / index / label field ever appears.
- API: ?period validation, auth required, disclaimer present.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from models import TradeHistory
from services.behavior.averaging_down_mirror import (
    compute_averaging_down_mirror,
)


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
    currency: str = "USD",
    name: str = "",
) -> TradeHistory:
    return TradeHistory(
        ticker=ticker,
        name=name,
        action=action,
        shares=shares,
        price_per_share=price_per_share,
        total_value=shares * price_per_share,
        pnl=0.0,
        pnl_pct=0.0,
        currency=currency,
        traded_at=traded_at,
    )


def _buy(ticker: str, price: float, *, days_ago: float,
         shares: float = 10.0, name: str = "") -> TradeHistory:
    return _trade(
        ticker=ticker, action="BUY", price_per_share=price, shares=shares,
        traded_at=_now() - timedelta(days=days_ago), name=name,
    )


def _sell(ticker: str, price: float, *, days_ago: float,
          shares: float = 10.0) -> TradeHistory:
    return _trade(
        ticker=ticker, action="SELL", price_per_share=price, shares=shares,
        traded_at=_now() - timedelta(days=days_ago),
    )


_FORBIDDEN_SCORE_KEYS = {"ratio", "score", "grade", "index", "label",
                         "percentile", "averaging_down", "health"}


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
    blob = repr(result).lower()
    assert "ratio" not in blob
    assert "score" not in blob
    assert "물타기" not in repr(result)
    assert "편향" not in repr(result)


# ═════════════════════════════════════════════════════════════════════
# Below-average detection
# ═════════════════════════════════════════════════════════════════════

class TestBelowAverage:
    def test_adds_below_running_average_are_counted_below(self):
        # Open at 100, then add three times below the running average.
        trades = [
            _buy("AAA", 100.0, days_ago=10),  # open (not follow-on)
            _buy("AAA", 90.0, days_ago=9),    # avg before = 100 → below
            _buy("AAA", 80.0, days_ago=8),    # avg before < 100 → below
            _buy("AAA", 70.0, days_ago=7),    # below again
        ]
        result = compute_averaging_down_mirror(trades, min_follow_on=3)
        assert result["sufficient_data"] is True
        assert result["follow_on_count"] == 3
        assert result["below_avg_count"] == 3
        assert result["above_avg_count"] == 0
        assert result["flat_count"] == 0
        _assert_no_scoring(result)


# ═════════════════════════════════════════════════════════════════════
# Above-average detection
# ═════════════════════════════════════════════════════════════════════

class TestAboveAverage:
    def test_adds_above_running_average_are_counted_above(self):
        trades = [
            _buy("BBB", 100.0, days_ago=10),  # open
            _buy("BBB", 110.0, days_ago=9),   # avg 100 → above
            _buy("BBB", 130.0, days_ago=8),   # avg ~105 → above
            _buy("BBB", 200.0, days_ago=7),   # above
        ]
        result = compute_averaging_down_mirror(trades, min_follow_on=3)
        assert result["follow_on_count"] == 3
        assert result["above_avg_count"] == 3
        assert result["below_avg_count"] == 0
        _assert_no_scoring(result)

    def test_flat_add_at_running_average(self):
        trades = [
            _buy("CCC", 100.0, days_ago=10),  # open
            _buy("CCC", 100.0, days_ago=9),   # avg 100 → flat
            _buy("CCC", 100.0, days_ago=8),   # avg 100 → flat
            _buy("CCC", 100.0, days_ago=7),   # flat
        ]
        result = compute_averaging_down_mirror(trades, min_follow_on=3)
        assert result["follow_on_count"] == 3
        assert result["flat_count"] == 3
        assert result["below_avg_count"] == 0
        assert result["above_avg_count"] == 0
        _assert_no_scoring(result)


# ═════════════════════════════════════════════════════════════════════
# First BUY is never a follow-on
# ═════════════════════════════════════════════════════════════════════

class TestFirstBuyNotFollowOn:
    def test_first_buy_in_each_ticker_excluded(self):
        # Three separate single-open positions → zero follow-ons.
        trades = [
            _buy("AAA", 100.0, days_ago=10),
            _buy("BBB", 50.0, days_ago=9),
            _buy("CCC", 25.0, days_ago=8),
        ]
        result = compute_averaging_down_mirror(trades, min_follow_on=1)
        assert result["sufficient_data"] is False
        assert result["follow_on_count"] is None


# ═════════════════════════════════════════════════════════════════════
# Partial sell leaves the running average unchanged
# ═════════════════════════════════════════════════════════════════════

class TestPartialSell:
    def test_partial_sell_keeps_average_then_classifies_next_add(self):
        trades = [
            _buy("AAA", 100.0, days_ago=10, shares=10),   # open, avg 100
            _buy("AAA", 200.0, days_ago=9, shares=10),    # follow-on above
            # avg now (100*10 + 200*10)/20 = 150 over 20 shares
            _sell("AAA", 300.0, days_ago=8, shares=10),   # partial → avg stays 150
            _buy("AAA", 140.0, days_ago=7, shares=10),    # 140 < 150 → below
            _buy("AAA", 160.0, days_ago=6, shares=10),    # 160 > running avg → above
        ]
        result = compute_averaging_down_mirror(trades, min_follow_on=1)
        assert result["follow_on_count"] == 3
        assert result["above_avg_count"] == 2  # the 200 add + the 160 add
        assert result["below_avg_count"] == 1  # the 140 add (avg held at 150)
        _assert_no_scoring(result)


# ═════════════════════════════════════════════════════════════════════
# Full liquidation resets; later re-buy is a fresh open
# ═════════════════════════════════════════════════════════════════════

class TestFullLiquidationResets:
    def test_rebuy_after_full_exit_is_new_open(self):
        trades = [
            _buy("AAA", 100.0, days_ago=10, shares=10),   # open
            _buy("AAA", 80.0, days_ago=9, shares=10),     # follow-on below
            _sell("AAA", 90.0, days_ago=8, shares=20),    # full exit → reset
            _buy("AAA", 50.0, days_ago=7, shares=10),     # NEW open, not follow-on
            _buy("AAA", 40.0, days_ago=6, shares=10),     # follow-on below
        ]
        result = compute_averaging_down_mirror(trades, min_follow_on=1)
        # Two follow-ons total: the 80 add and the 40 add. The 50 re-buy
        # opened a fresh position so it is NOT counted.
        assert result["follow_on_count"] == 2
        assert result["below_avg_count"] == 2
        _assert_no_scoring(result)


# ═════════════════════════════════════════════════════════════════════
# Period window (30d vs all)
# ═════════════════════════════════════════════════════════════════════

class TestPeriodWindow:
    def test_period_days_filters_old_trades(self):
        trades = [
            # Old position fully outside a 30d window.
            _buy("OLD", 100.0, days_ago=90, shares=10),
            _buy("OLD", 80.0, days_ago=89, shares=10),
            _buy("OLD", 70.0, days_ago=88, shares=10),
            # Recent position inside 30d.
            _buy("NEW", 100.0, days_ago=10, shares=10),
            _buy("NEW", 90.0, days_ago=9, shares=10),
            _buy("NEW", 80.0, days_ago=8, shares=10),
        ]
        all_result = compute_averaging_down_mirror(trades, min_follow_on=1)
        assert all_result["follow_on_count"] == 4  # 2 OLD + 2 NEW

        win = compute_averaging_down_mirror(
            trades, period_days=30, min_follow_on=1,
        )
        # Only the NEW position's two follow-on adds survive the window.
        # The anchor (max traded_at) is 8d ago; 30d cutoff is 38d ago, so
        # the OLD fills (88-90d ago) drop out entirely.
        assert win["follow_on_count"] == 2
        assert win["below_avg_count"] == 2
        assert win["period_days"] == 30
        _assert_no_scoring(win)


# ═════════════════════════════════════════════════════════════════════
# Insufficient data gate
# ═════════════════════════════════════════════════════════════════════

class TestGate:
    def test_no_trades_insufficient(self):
        result = compute_averaging_down_mirror([])
        assert result["sufficient_data"] is False
        assert result["follow_on_count"] is None
        assert result["below_avg_count"] is None
        assert result["above_avg_count"] is None
        assert result["flat_count"] is None
        assert result["by_ticker"] == []
        _assert_no_scoring(result)

    def test_two_follow_ons_below_default_min_three(self):
        trades = [
            _buy("AAA", 100.0, days_ago=10),
            _buy("AAA", 90.0, days_ago=9),   # follow-on 1
            _buy("AAA", 80.0, days_ago=8),   # follow-on 2
        ]
        result = compute_averaging_down_mirror(trades)  # default min 3
        assert result["sufficient_data"] is False
        assert result["follow_on_count"] is None

    def test_exactly_min_follow_on_is_sufficient(self):
        trades = [
            _buy("AAA", 100.0, days_ago=10),
            _buy("AAA", 90.0, days_ago=9),   # 1
            _buy("AAA", 80.0, days_ago=8),   # 2
            _buy("AAA", 70.0, days_ago=7),   # 3
        ]
        result = compute_averaging_down_mirror(trades)
        assert result["sufficient_data"] is True
        assert result["follow_on_count"] == 3


# ═════════════════════════════════════════════════════════════════════
# Zero-price / non-positive-share rows are skipped
# ═════════════════════════════════════════════════════════════════════

class TestZeroPriceSkip:
    def test_zero_price_buy_skipped_from_classification(self):
        trades = [
            _buy("AAA", 100.0, days_ago=10),
            _buy("AAA", 0.0, days_ago=9),    # zero price → skipped
            _buy("AAA", 90.0, days_ago=8),   # follow-on below (avg still 100)
            _buy("AAA", 80.0, days_ago=7),   # follow-on below
            _buy("AAA", 70.0, days_ago=6),   # follow-on below
        ]
        result = compute_averaging_down_mirror(trades, min_follow_on=1)
        # Zero-price row neither counts as a follow-on nor shifts the avg.
        assert result["follow_on_count"] == 3
        assert result["below_avg_count"] == 3
        _assert_no_scoring(result)

    def test_non_positive_share_buy_skipped(self):
        trades = [
            _buy("AAA", 100.0, days_ago=10, shares=10),
            _buy("AAA", 90.0, days_ago=9, shares=0),   # zero shares → skipped
            _buy("AAA", 85.0, days_ago=8, shares=10),  # follow-on below
            _buy("AAA", 80.0, days_ago=7, shares=10),  # follow-on below
            _buy("AAA", 75.0, days_ago=6, shares=10),  # follow-on below
        ]
        result = compute_averaging_down_mirror(trades, min_follow_on=1)
        assert result["follow_on_count"] == 3
        assert result["below_avg_count"] == 3


# ═════════════════════════════════════════════════════════════════════
# Determinism — order independence
# ═════════════════════════════════════════════════════════════════════

class TestDeterminism:
    def test_shuffled_input_gives_same_result(self):
        import random

        trades = [
            _buy("AAA", 100.0, days_ago=10),
            _buy("AAA", 90.0, days_ago=9),
            _buy("AAA", 120.0, days_ago=8),
            _buy("AAA", 80.0, days_ago=7),
            _buy("BBB", 50.0, days_ago=6),
            _buy("BBB", 40.0, days_ago=5),
        ]
        ordered = compute_averaging_down_mirror(trades, min_follow_on=1)

        shuffled = list(trades)
        random.Random(7).shuffle(shuffled)
        out = compute_averaging_down_mirror(shuffled, min_follow_on=1)
        assert out == ordered


# ═════════════════════════════════════════════════════════════════════
# Per-ticker breakdown
# ═════════════════════════════════════════════════════════════════════

class TestByTicker:
    def test_by_ticker_breakdown_is_neutral(self):
        trades = [
            _buy("AAA", 100.0, days_ago=10, name="Alpha Corp"),
            _buy("AAA", 90.0, days_ago=9),
            _buy("AAA", 80.0, days_ago=8),
            _buy("BBB", 50.0, days_ago=7, name="Beta Inc"),
            _buy("BBB", 40.0, days_ago=6),
        ]
        result = compute_averaging_down_mirror(trades, min_follow_on=1)
        by = {row["ticker"]: row for row in result["by_ticker"]}
        assert set(by) == {"AAA", "BBB"}
        assert by["AAA"]["follow_on"] == 2
        assert by["AAA"]["below_avg"] == 2
        assert by["AAA"]["name"] == "Alpha Corp"
        assert by["BBB"]["follow_on"] == 1
        # AAA (2 follow-ons) ordered before BBB (1).
        assert result["by_ticker"][0]["ticker"] == "AAA"
        for row in result["by_ticker"]:
            assert set(row) == {
                "ticker", "name", "follow_on", "below_avg", "above_avg",
            }
        _assert_no_scoring(result)


# ═════════════════════════════════════════════════════════════════════
# No-score invariant — explicit key-set check on a populated payload
# ═════════════════════════════════════════════════════════════════════

class TestNoScoreInvariant:
    def test_populated_payload_has_no_forbidden_keys(self):
        trades = [
            _buy("AAA", 100.0, days_ago=10),
            _buy("AAA", 90.0, days_ago=9),
            _buy("AAA", 120.0, days_ago=8),
            _buy("AAA", 80.0, days_ago=7),
        ]
        result = compute_averaging_down_mirror(trades, min_follow_on=1)
        _assert_no_scoring(result)
        assert set(result) == {
            "sufficient_data", "period_days", "follow_on_count",
            "below_avg_count", "above_avg_count", "flat_count", "by_ticker",
        }


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
        resp = client.get("/api/behavior/averaging-down-mirror")
        assert resp.status_code in (401, 403)

    def test_new_user_insufficient(self, client, auth_user):
        resp = client.get("/api/behavior/averaging-down-mirror")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["ok"] is True
        assert body["sufficient_data"] is False
        assert body["period"] == "all"
        assert "disclaimer" in body
        assert not (_FORBIDDEN_SCORE_KEYS & set(body))

    def test_invalid_period_rejected(self, client, auth_user):
        resp = client.get("/api/behavior/averaging-down-mirror?period=bogus")
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "BAD_INPUT"

    def test_arbitrary_integer_period_rejected(self, client, auth_user):
        resp = client.get("/api/behavior/averaging-down-mirror?period=90")
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "BAD_INPUT"

    def test_populated_response(self, client, auth_user, app):
        trades = [
            _buy("AAA", 100.0, days_ago=10),
            _buy("AAA", 90.0, days_ago=9),
            _buy("AAA", 80.0, days_ago=8),
            _buy("AAA", 70.0, days_ago=7),
        ]
        self._insert(app, auth_user["id"], trades)

        resp = client.get("/api/behavior/averaging-down-mirror?period=all")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["sufficient_data"] is True
        assert body["follow_on_count"] == 3
        assert body["below_avg_count"] == 3
        _assert_no_scoring(body)

    def test_period_30d_param_passes_through(self, client, auth_user):
        resp = client.get("/api/behavior/averaging-down-mirror?period=30d")
        assert resp.status_code == 200
        assert resp.get_json()["period"] == "30d"
