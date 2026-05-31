"""tests/test_turnover_mirror.py — PivoxQuant Turnover (trade-activity) Mirror

Covers the retrospective trade-activity mirror:

    services.behavior.turnover_mirror.compute_turnover_mirror(trades, ...)
    GET /api/behavior/turnover-mirror?period=30d|all

Invariants validated here
-------------------------
- Pure function: no DB / network / live price / FX call. Operates on plain
  TradeHistory rows.
- Reports ABSOLUTE frequency (BUY+SELL fill counts) + per-currency gross
  traded value — NEVER a ratio / percentage / score / grade / label.
- Per-currency gross value groups ``total_value`` by ``currency`` and is
  NEVER FX-converted into a single mixed figure.
- median hold days is the headline, mean the secondary; both None when no
  round trip closed.
- Edge cases: empty / below min_trades / one currency / multi-currency.
- NO score / grade / ratio / index / label field ever appears.
- API: ?period validation, auth required, disclaimer present.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from models import TradeHistory
from services.behavior.turnover_mirror import compute_turnover_mirror


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


def _round_trip(
    *,
    ticker: str,
    hold_days: float,
    sell_days_ago: float = 1.0,
    currency: str = "USD",
    price_per_share: float = 100.0,
) -> list[TradeHistory]:
    """A matched BUY→SELL pair held ``hold_days`` days (2 fills)."""
    now = _now()
    sell_at = now - timedelta(days=sell_days_ago)
    buy_at = sell_at - timedelta(days=hold_days)
    return [
        _trade(ticker=ticker, action="BUY", traded_at=buy_at,
               price_per_share=price_per_share, currency=currency),
        _trade(ticker=ticker, action="SELL", traded_at=sell_at,
               price_per_share=price_per_share, currency=currency),
    ]


_FORBIDDEN_SCORE_KEYS = {"ratio", "score", "grade", "index", "label",
                         "turnover", "percentile"}


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
    # No judgement / verdict vocabulary leaks into the serialised result.
    assert "과잉" not in repr(result)
    assert "회전율" not in repr(result)
    assert "ratio" not in blob
    assert "score" not in blob


# ═════════════════════════════════════════════════════════════════════
# Edge case: brand-new user (zero trades)
# ═════════════════════════════════════════════════════════════════════

class TestNewUser:
    def test_no_trades_insufficient(self):
        result = compute_turnover_mirror([])
        assert result["sufficient_data"] is False
        assert result["trade_count"] == 0
        assert result["buy_count"] is None
        assert result["sell_count"] is None
        assert result["by_currency"] == []
        assert result["median_hold_days"] is None
        assert result["mean_hold_days"] is None
        _assert_no_scoring(result)


# ═════════════════════════════════════════════════════════════════════
# Gate: fewer than min_trades fills → insufficient
# ═════════════════════════════════════════════════════════════════════

class TestGate:
    def test_seven_fills_below_default_min_eight(self):
        # 3 round trips (6 fills) + 1 open buy = 7 fills < 8
        trades: list[TradeHistory] = []
        for i in range(3):
            trades += _round_trip(ticker=f"T{i}", hold_days=2.0)
        trades.append(
            _trade(ticker="OPEN", action="BUY", traded_at=_now())
        )
        result = compute_turnover_mirror(trades)
        assert result["trade_count"] == 7
        assert result["sufficient_data"] is False
        assert result["buy_count"] is None
        assert result["sell_count"] is None
        assert result["by_currency"] == []
        _assert_no_scoring(result)

    def test_exactly_min_trades_is_sufficient(self):
        # 4 round trips = 8 fills == min
        trades: list[TradeHistory] = []
        for i in range(4):
            trades += _round_trip(ticker=f"T{i}", hold_days=2.0)
        result = compute_turnover_mirror(trades)
        assert result["trade_count"] == 8
        assert result["sufficient_data"] is True
        _assert_no_scoring(result)

    def test_custom_min_trades(self):
        trades: list[TradeHistory] = []
        for i in range(5):
            trades += _round_trip(ticker=f"T{i}", hold_days=2.0)  # 10 fills
        result = compute_turnover_mirror(trades, min_trades=20)
        assert result["sufficient_data"] is False


# ═════════════════════════════════════════════════════════════════════
# Counts: BUY / SELL split
# ═════════════════════════════════════════════════════════════════════

class TestCounts:
    def test_buy_and_sell_counts(self):
        trades: list[TradeHistory] = []
        # 5 round trips (5 BUY + 5 SELL) = 10 fills
        for i in range(5):
            trades += _round_trip(ticker=f"T{i}", hold_days=2.0)
        # 2 extra open buys
        for i in range(2):
            trades.append(
                _trade(ticker=f"O{i}", action="BUY",
                       traded_at=_now() - timedelta(days=1))
            )
        result = compute_turnover_mirror(trades)
        assert result["sufficient_data"] is True
        assert result["buy_count"] == 7
        assert result["sell_count"] == 5
        assert result["trade_count"] == 12
        _assert_no_scoring(result)


# ═════════════════════════════════════════════════════════════════════
# Per-currency: separate aggregation, NEVER FX-converted
# ═════════════════════════════════════════════════════════════════════

class TestByCurrency:
    def test_currencies_aggregated_separately(self):
        trades: list[TradeHistory] = []
        # 3 KRW round trips, each fill total_value = 10 * 50000 = 500000
        for i in range(3):
            trades += _round_trip(ticker=f"K{i}", hold_days=2.0,
                                  currency="KRW", price_per_share=50000.0)
        # 2 USD round trips, each fill total_value = 10 * 100 = 1000
        for i in range(2):
            trades += _round_trip(ticker=f"U{i}", hold_days=2.0,
                                  currency="USD", price_per_share=100.0)
        result = compute_turnover_mirror(trades)
        assert result["sufficient_data"] is True

        by_cur = {row["currency"]: row for row in result["by_currency"]}
        assert set(by_cur) == {"KRW", "USD"}
        # KRW: 6 fills × 500000 = 3,000,000
        assert by_cur["KRW"]["gross_value"] == 3_000_000.0
        assert by_cur["KRW"]["trade_count"] == 6
        # USD: 4 fills × 1000 = 4,000
        assert by_cur["USD"]["gross_value"] == 4_000.0
        assert by_cur["USD"]["trade_count"] == 4
        # Ordered by descending gross value → KRW first (3M > 4k).
        assert result["by_currency"][0]["currency"] == "KRW"
        # No mixed/converted single total anywhere.
        _assert_no_scoring(result)

    def test_blank_currency_falls_back_to_default(self):
        trades: list[TradeHistory] = []
        for i in range(4):
            trades += _round_trip(ticker=f"T{i}", hold_days=2.0)
        # blank the currency on every row — should bucket under "USD"
        for t in trades:
            t.currency = ""
        result = compute_turnover_mirror(trades)
        by_cur = {row["currency"]: row for row in result["by_currency"]}
        assert set(by_cur) == {"USD"}
        assert by_cur["USD"]["trade_count"] == 8


# ═════════════════════════════════════════════════════════════════════
# Hold-day statistics: median primary, mean secondary
# ═════════════════════════════════════════════════════════════════════

class TestHoldDays:
    def test_median_hold_resists_outlier(self):
        trades: list[TradeHistory] = []
        for d in (8.0, 9.0, 10.0, 11.0):
            trades += _round_trip(ticker=f"T{d}", hold_days=d)
        trades += _round_trip(ticker="LX", hold_days=400.0)
        result = compute_turnover_mirror(trades)
        # median ~ 10 (middle of 8,9,10,11,400); mean dragged way up
        assert result["median_hold_days"] == 10.0
        assert result["mean_hold_days"] > 80.0
        _assert_no_scoring(result)

    def test_hold_days_none_when_no_closed_pairs(self):
        # 8 open buys, never sold → no round trip closes
        trades = [
            _trade(ticker=f"O{i}", action="BUY",
                   traded_at=_now() - timedelta(days=i + 1))
            for i in range(8)
        ]
        result = compute_turnover_mirror(trades)
        assert result["sufficient_data"] is True
        assert result["buy_count"] == 8
        assert result["sell_count"] == 0
        assert result["median_hold_days"] is None
        assert result["mean_hold_days"] is None
        _assert_no_scoring(result)


# ═════════════════════════════════════════════════════════════════════
# Period window (30d vs all)
# ═════════════════════════════════════════════════════════════════════

class TestPeriodWindow:
    def test_period_days_filters_old_trades(self):
        trades: list[TradeHistory] = []
        # 5 recent round trips (10 fills), sold 3 days ago
        for i in range(5):
            trades += _round_trip(ticker=f"R{i}", hold_days=2.0,
                                  sell_days_ago=3.0)
        # 5 old round trips (10 fills), sold 60 days ago
        for i in range(5):
            trades += _round_trip(ticker=f"O{i}", hold_days=2.0,
                                  sell_days_ago=60.0)
        all_result = compute_turnover_mirror(trades)  # period None
        assert all_result["trade_count"] == 20

        win = compute_turnover_mirror(trades, period_days=30)
        # only the recent fills survive the window
        assert win["trade_count"] == 10
        assert win["period_days"] == 30
        _assert_no_scoring(win)


# ═════════════════════════════════════════════════════════════════════
# No-score invariant — explicit recursive scan of a populated payload
# ═════════════════════════════════════════════════════════════════════

class TestNoScoreInvariant:
    def test_populated_payload_has_no_forbidden_keys(self):
        trades: list[TradeHistory] = []
        for i in range(4):
            trades += _round_trip(ticker=f"K{i}", hold_days=2.0,
                                  currency="KRW", price_per_share=50000.0)
        for i in range(2):
            trades += _round_trip(ticker=f"U{i}", hold_days=5.0,
                                  currency="USD")
        result = compute_turnover_mirror(trades)
        _assert_no_scoring(result)
        # Exact key set — proves no extra ratio/score field crept in.
        assert set(result) == {
            "sufficient_data", "period_days", "trade_count",
            "buy_count", "sell_count", "by_currency",
            "median_hold_days", "mean_hold_days",
        }
        for row in result["by_currency"]:
            assert set(row) == {"currency", "gross_value", "trade_count"}


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
        resp = client.get("/api/behavior/turnover-mirror")
        assert resp.status_code in (401, 403)

    def test_new_user_insufficient(self, client, auth_user):
        resp = client.get("/api/behavior/turnover-mirror")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["ok"] is True
        assert body["sufficient_data"] is False
        assert body["period"] == "all"
        assert "disclaimer" in body
        assert not (_FORBIDDEN_SCORE_KEYS & set(body))

    def test_invalid_period_rejected(self, client, auth_user):
        resp = client.get("/api/behavior/turnover-mirror?period=bogus")
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "BAD_INPUT"

    def test_arbitrary_integer_period_rejected(self, client, auth_user):
        resp = client.get("/api/behavior/turnover-mirror?period=90")
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "BAD_INPUT"

    def test_populated_response(self, client, auth_user, app):
        trades: list[TradeHistory] = []
        for i in range(4):
            trades += _round_trip(ticker=f"K{i}", hold_days=2.0,
                                  currency="KRW", price_per_share=50000.0)
        for i in range(2):
            trades += _round_trip(ticker=f"U{i}", hold_days=5.0,
                                  currency="USD")
        self._insert(app, auth_user["id"], trades)

        resp = client.get("/api/behavior/turnover-mirror?period=all")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["sufficient_data"] is True
        assert body["trade_count"] == 12
        assert body["buy_count"] == 6
        assert body["sell_count"] == 6
        currencies = {row["currency"] for row in body["by_currency"]}
        assert currencies == {"KRW", "USD"}
        _assert_no_scoring(body)

    def test_period_30d_param_passes_through(self, client, auth_user, app):
        resp = client.get("/api/behavior/turnover-mirror?period=30d")
        assert resp.status_code == 200
        assert resp.get_json()["period"] == "30d"
