"""tests/test_rebuy_mirror.py — PivoxQuant Rebuy Mirror

Covers the retrospective sell → later-buy mirror:

    services.behavior.rebuy_mirror.compute_rebuy_mirror(...)
    GET /api/behavior/rebuy-mirror?period=30d|all

Invariants validated here
-------------------------
- Pure function over plain TradeHistory rows: no DB / network / live price /
  FX call. Both prices in a pair are the user's own fills of one ticker.
- A sale pairs with the FIRST later buy of the same ticker, only within
  REBUY_WINDOW_DAYS; the comparison is with the MOST RECENT sale.
- Registration rows (holding_seed / holding_adjust) never open or close a
  pair; zero-price / non-positive-share rows are ignored.
- period_days filters by the buy's date, but the walk sees full history.
- Deterministic regardless of input order.
- NO score / grade / ratio / index / label field ever appears.
- API: ?period validation, auth required, disclaimer present.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from models import TradeHistory
from services.behavior.rebuy_mirror import REBUY_WINDOW_DAYS, compute_rebuy_mirror
from services.profile.fifo_util import HOLDING_ADJUST_SOURCE, HOLDING_SEED_SOURCE


# ═════════════════════════════════════════════════════════════════════
# Helpers — build plain (unpersisted) TradeHistory rows
# ═════════════════════════════════════════════════════════════════════

_BASE = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _trade(ticker, action, price, *, days_ago, shares=10.0, name="", source=None):
    return TradeHistory(
        ticker=ticker,
        name=name,
        action=action,
        shares=shares,
        price_per_share=price,
        total_value=shares * price,
        pnl=0.0,
        pnl_pct=0.0,
        currency="USD",
        traded_at=_BASE - timedelta(days=days_ago),
        source=source,
    )


def _buy(ticker, price, *, days_ago, **kw):
    return _trade(ticker, "BUY", price, days_ago=days_ago, **kw)


def _sell(ticker, price, *, days_ago, **kw):
    return _trade(ticker, "SELL", price, days_ago=days_ago, **kw)


_FORBIDDEN_SCORE_KEYS = {"ratio", "score", "grade", "index", "label",
                         "percentile", "health"}


def _assert_no_scoring(result: dict) -> None:
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


def _three_pairs():
    """AAA: sold 100 → rebought 120 (higher), BBB: sold 50 → 40 (lower),
    CCC: sold 10 → 10 (flat)."""
    return [
        _buy("AAA", 90.0, days_ago=60),
        _sell("AAA", 100.0, days_ago=50),
        _buy("AAA", 120.0, days_ago=40),   # +20%, 10 days
        _buy("BBB", 30.0, days_ago=60),
        _sell("BBB", 50.0, days_ago=30),
        _buy("BBB", 40.0, days_ago=10),    # -20%, 20 days
        _buy("CCC", 8.0, days_ago=60),
        _sell("CCC", 10.0, days_ago=35),
        _buy("CCC", 10.0, days_ago=5),     # 0%, 30 days
    ]


# ═════════════════════════════════════════════════════════════════════
# Pairing
# ═════════════════════════════════════════════════════════════════════

class TestPairing:
    def test_counts_and_medians(self):
        r = compute_rebuy_mirror(_three_pairs())
        assert r["sufficient_data"] is True
        assert r["rebuy_count"] == 3
        assert r["higher_count"] == 1
        assert r["lower_count"] == 1
        assert r["flat_count"] == 1
        assert r["median_gap_days"] == 20.0
        assert r["median_price_change_pct"] == 0.0
        assert r["rebuy_window_days"] == REBUY_WINDOW_DAYS

    def test_buy_without_prior_sale_is_not_a_rebuy(self):
        trades = [_buy("AAA", 10.0, days_ago=d) for d in (30, 20, 10)]
        r = compute_rebuy_mirror(trades, min_pairs=1)
        assert r["sufficient_data"] is False
        assert r["rebuy_count"] is None

    def test_sale_pairs_with_first_later_buy_only(self):
        trades = [
            _sell("AAA", 100.0, days_ago=30),
            _buy("AAA", 110.0, days_ago=20),
            _buy("AAA", 130.0, days_ago=10),  # no sale before it any more
        ]
        r = compute_rebuy_mirror(trades, min_pairs=1)
        assert r["rebuy_count"] == 1
        assert r["median_price_change_pct"] == 10.0

    def test_most_recent_sale_is_the_reference(self):
        trades = [
            _sell("AAA", 100.0, days_ago=30, shares=5),
            _sell("AAA", 200.0, days_ago=20, shares=5),
            _buy("AAA", 150.0, days_ago=10),
        ]
        r = compute_rebuy_mirror(trades, min_pairs=1)
        assert r["rebuy_count"] == 1
        assert r["lower_count"] == 1
        assert r["median_price_change_pct"] == -25.0
        assert r["median_gap_days"] == 10.0

    def test_buy_after_window_does_not_pair(self):
        trades = [
            _sell("AAA", 100.0, days_ago=REBUY_WINDOW_DAYS + 20),
            _buy("AAA", 120.0, days_ago=10),
        ]
        r = compute_rebuy_mirror(trades, min_pairs=1)
        assert r["sufficient_data"] is False

    def test_buy_exactly_at_window_edge_pairs(self):
        trades = [
            _sell("AAA", 100.0, days_ago=REBUY_WINDOW_DAYS + 1),
            _buy("AAA", 120.0, days_ago=1),
        ]
        r = compute_rebuy_mirror(trades, min_pairs=1)
        assert r["rebuy_count"] == 1

    def test_tickers_do_not_cross_pair(self):
        trades = [_sell("AAA", 100.0, days_ago=20), _buy("BBB", 50.0, days_ago=10)]
        r = compute_rebuy_mirror(trades, min_pairs=1)
        assert r["sufficient_data"] is False

    def test_ticker_case_is_normalised(self):
        trades = [_sell("aaa", 100.0, days_ago=20), _buy("AAA", 90.0, days_ago=10)]
        r = compute_rebuy_mirror(trades, min_pairs=1)
        assert r["rebuy_count"] == 1


# ═════════════════════════════════════════════════════════════════════
# Rows that are not fills
# ═════════════════════════════════════════════════════════════════════

class TestNonFillRows:
    def test_holding_seed_buy_does_not_close_a_pair(self):
        trades = [
            _sell("AAA", 100.0, days_ago=20),
            _buy("AAA", 120.0, days_ago=15, source=HOLDING_SEED_SOURCE),
            _buy("AAA", 90.0, days_ago=10),
        ]
        r = compute_rebuy_mirror(trades, min_pairs=1)
        assert r["rebuy_count"] == 1
        assert r["lower_count"] == 1

    def test_holding_adjust_sell_does_not_open_a_pair(self):
        trades = [
            _sell("AAA", 100.0, days_ago=20, source=HOLDING_ADJUST_SOURCE),
            _buy("AAA", 120.0, days_ago=10),
        ]
        r = compute_rebuy_mirror(trades, min_pairs=1)
        assert r["sufficient_data"] is False

    def test_zero_price_and_zero_share_rows_ignored(self):
        trades = [
            _sell("AAA", 100.0, days_ago=30),
            _buy("AAA", 0.0, days_ago=25),
            _buy("AAA", 90.0, days_ago=20, shares=0.0),
            _buy("AAA", 80.0, days_ago=10),
            _sell("BBB", 0.0, days_ago=10),
            _buy("BBB", 80.0, days_ago=5),
        ]
        r = compute_rebuy_mirror(trades, min_pairs=1)
        assert r["rebuy_count"] == 1
        assert r["median_price_change_pct"] == -20.0


class TestPositionAndCalendar:
    """2026-10-22 bug hunt — trims, suffixes, currency, date-only order."""

    def test_trim_then_add_is_not_a_rebuy(self):
        trades = [
            _buy("AAPL", 100.0, days_ago=30, shares=100),
            _sell("AAPL", 120.0, days_ago=20, shares=1),   # trim, still holds 99
            _buy("AAPL", 110.0, days_ago=17, shares=50),
        ]
        r = compute_rebuy_mirror(trades, min_pairs=1)
        assert r["sufficient_data"] is False

    def test_trims_down_to_zero_open_the_sale(self):
        trades = [
            _buy("AAPL", 100.0, days_ago=30, shares=10),
            _sell("AAPL", 120.0, days_ago=20, shares=4),
            _sell("AAPL", 125.0, days_ago=19, shares=6),   # now out of the name
            _buy("AAPL", 110.0, days_ago=10, shares=5),
        ]
        r = compute_rebuy_mirror(trades, min_pairs=1)
        assert r["rebuy_count"] == 1
        assert r["median_price_change_pct"] == -12.0

    def test_holding_seed_counts_as_held(self):
        trades = [
            _buy("AAPL", 100.0, days_ago=40, shares=10, source=HOLDING_SEED_SOURCE),
            _sell("AAPL", 120.0, days_ago=20, shares=3),
            _buy("AAPL", 110.0, days_ago=10, shares=3),
        ]
        assert compute_rebuy_mirror(trades, min_pairs=1)["sufficient_data"] is False

    def test_kr_suffix_variants_are_one_name(self):
        trades = [
            _sell("035720.KQ", 50000.0, days_ago=20),
            _buy("035720.KS", 45000.0, days_ago=10, name="카카오"),
        ]
        r = compute_rebuy_mirror(trades, min_pairs=1)
        assert r["rebuy_count"] == 1
        assert r["by_ticker"][0]["ticker"] == "035720.KS"
        assert r["by_ticker"][0]["name"] == "카카오"

    def test_other_currency_does_not_pair(self):
        sell = _sell("AAPL", 100.0, days_ago=20)
        buy = _buy("AAPL", 130000.0, days_ago=10)
        buy.currency = "KRW"
        assert compute_rebuy_mirror([sell, buy], min_pairs=1)["sufficient_data"] is False

    def test_timed_sale_then_date_only_buy_same_kst_day(self):
        day = datetime(2026, 3, 2)
        sell = _sell("AAPL", 100.0, days_ago=0)
        sell.traded_at = day + timedelta(hours=5)          # 14:00 KST
        same_day = _buy("AAPL", 95.0, days_ago=0)
        same_day.traded_at = day                           # date-only 3/2
        later = _buy("AAPL", 150.0, days_ago=0)
        later.traded_at = day + timedelta(days=49, hours=3)
        r = compute_rebuy_mirror([sell, same_day, later], min_pairs=1)
        assert r["rebuy_count"] == 1
        assert r["median_price_change_pct"] == -5.0
        assert r["median_gap_days"] < 1

    def test_period_anchors_to_now(self):
        trades = _three_pairs()
        for t in trades:
            t.traded_at -= timedelta(days=100)
        # Without ``now`` the window hangs off the latest fill (105 days ago)
        # and still holds the pairs; anchored to now, "the last 30 days" has
        # none of them — and a later unrelated buy cannot move it.
        assert compute_rebuy_mirror(trades, period_days=30, min_pairs=1)["rebuy_count"] == 2
        r = compute_rebuy_mirror(trades, period_days=30, min_pairs=1, now=_BASE)
        assert r["sufficient_data"] is False
        r = compute_rebuy_mirror(trades, period_days=200, min_pairs=1, now=_BASE)
        assert r["rebuy_count"] == 3


# ═════════════════════════════════════════════════════════════════════
# Window, threshold, determinism
# ═════════════════════════════════════════════════════════════════════

class TestWindowAndThreshold:
    def test_period_counts_by_buy_date_but_sees_older_sale(self):
        trades = _three_pairs()
        # Only the CCC buy (5 days ago, the latest fill = anchor) falls in a
        # 3-day window; its sale (35 days ago) is outside but still pairs.
        r = compute_rebuy_mirror(trades, period_days=3, min_pairs=1)
        assert r["rebuy_count"] == 1
        assert r["flat_count"] == 1
        assert r["period_days"] == 3

    def test_below_min_pairs_reports_nothing(self):
        r = compute_rebuy_mirror(_three_pairs()[:6])  # two pairs, default min 3
        assert r["sufficient_data"] is False
        for k in ("rebuy_count", "higher_count", "lower_count", "flat_count",
                  "median_gap_days", "median_price_change_pct"):
            assert r[k] is None
        assert r["by_ticker"] == []

    def test_empty_input(self):
        r = compute_rebuy_mirror([])
        assert r["sufficient_data"] is False
        r = compute_rebuy_mirror([], period_days=30)
        assert r["sufficient_data"] is False

    def test_shuffled_input_gives_same_result(self):
        trades = _three_pairs()
        expected = compute_rebuy_mirror(trades)
        shuffled = trades[:]
        random.Random(7).shuffle(shuffled)
        assert compute_rebuy_mirror(shuffled) == expected

    def test_by_ticker_is_neutral_and_named(self):
        trades = _three_pairs() + [
            _sell("AAA", 130.0, days_ago=3, name="Alpha Co"),
            _buy("AAA", 125.0, days_ago=2, name="Alpha Co"),
        ]
        r = compute_rebuy_mirror(trades)
        top = r["by_ticker"][0]
        assert top == {
            "ticker": "AAA", "name": "Alpha Co",
            "rebuy_count": 2, "higher_count": 1, "lower_count": 1,
        }


class TestNoScoreInvariant:
    def test_payload_shape(self):
        r = compute_rebuy_mirror(_three_pairs())
        _assert_no_scoring(r)
        assert set(r) == {
            "sufficient_data", "period_days", "rebuy_window_days",
            "rebuy_count", "higher_count", "lower_count", "flat_count",
            "median_gap_days", "median_price_change_pct", "by_ticker",
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
        resp = client.get("/api/behavior/rebuy-mirror")
        assert resp.status_code in (401, 403)

    def test_new_user_insufficient(self, client, auth_user):
        resp = client.get("/api/behavior/rebuy-mirror")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["ok"] is True
        assert body["sufficient_data"] is False
        assert body["period"] == "all"
        assert "disclaimer" in body

    def test_invalid_period_rejected(self, client, auth_user):
        for bad in ("bogus", "90"):
            resp = client.get(f"/api/behavior/rebuy-mirror?period={bad}")
            assert resp.status_code == 400
            assert resp.get_json()["code"] == "BAD_INPUT"

    def test_populated_response(self, client, auth_user, app):
        self._insert(app, auth_user["id"], _three_pairs())
        resp = client.get("/api/behavior/rebuy-mirror?period=all")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["sufficient_data"] is True
        assert body["rebuy_count"] == 3
        assert body["median_gap_days"] == 20.0
        _assert_no_scoring(body)
