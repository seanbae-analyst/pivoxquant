"""
tests/test_portfolio.py — Portfolio CRUD + Trading
===================================================
Covers /api/portfolio: GET/POST/PATCH /positions, POST /trades (recorded
fills), history. 2026-09-29: the deprecated singular write routes
(/position, /position/<id>[/buy|/sell], /position/buy-new), DELETE
/positions/<id>, PUT /capital and GET "" were removed; their meaningful assertions
now run against the live routes below.

External APIs are mocked — no network calls.
"""
import json
from unittest.mock import patch

import pytest

# ── MARKET_DATA_DISPLAY_ENABLED ──────────────────────────────────────────────
# This module's portfolio price / market-value / NAV assertions
# only make sense while vendor-quote display is ON. The flag defaults to OFF
# (config.py — FMP Data Display Agreement pending), so the whole module opts in
# and thereby pins "flag on == exactly the pre-flag behaviour". The OFF
# contract is pinned separately in tests/test_market_data_display_flag.py.
@pytest.fixture(autouse=True)
def _market_display_on(market_display_on):
    yield




# ── GET /api/portfolio/positions ────────────────────────────────────────────
# 2026-09-29: the legacy full list GET /api/portfolio was removed (its only
# reader, RealtimeProvider, moved to /positions); its assertions run here.

class TestGetPortfolio:
    def test_unauthenticated_returns_401(self, client):
        r = client.get("/api/portfolio/positions")
        assert r.status_code == 401

    def test_empty_portfolio(self, client, auth_user):
        r = client.get("/api/portfolio/positions")
        assert r.status_code == 200
        d = r.get_json()
        assert d["positions"] == []
        assert d["total_value_usd"] == 0

    def test_portfolio_with_positions(self, client, auth_user, add_position):
        add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=150.0)
        r = client.get("/api/portfolio/positions")
        assert r.status_code == 200
        d = r.get_json()
        assert len(d["positions"]) == 1
        p = d["positions"][0]
        assert p["symbol"] == "AAPL"
        assert p["shares"] == 10
        assert p["avgCost"] == 150.0
        assert p["market_value"] == 10 * 150.0  # no signal cache -> fallback to avg_cost

    def test_positions_alias_emits_market_value_and_totals(
        self, client, auth_user, add_position,
    ):
        """GET /api/portfolio/positions MUST emit per-position market_value AND
        portfolio totals. Without them the /risk weight aggregators divide by
        0 and every concentration/sector weight renders 0% (CEO 2026-05-24)."""
        add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=150.0)
        r = client.get("/api/portfolio/positions")
        assert r.status_code == 200
        d = r.get_json()
        assert len(d["positions"]) == 1
        # per-position native market value present + non-zero
        assert d["positions"][0]["market_value"] == 10 * 150.0
        # portfolio totals present so denom != 0 in the weight calc
        assert "total_value_all_krw" in d
        assert "total_value_usd" in d
        assert "fx_rate" in d
        assert d["total_value_usd"] == 1500.0
        assert d["total_value_all_krw"] > 0

    def test_totals_bucket_by_suffix_not_poisoned_cache_currency(
        self, client, auth_user, add_position, app,
    ):
        """NAV totals must bucket on the ticker-suffix is_kr, NOT the cache
        blob's `currency` string. A cross-contaminated SignalCache row that
        says a .KS position is "USD" used to push its native-KRW market value
        into the USD bucket — total_value_all_krw then multiplied it by the
        FX rate (~1380x overstatement). 2026-06-10 fix: suffix-authoritative
        accumulation (same as _build_positions_list / summary)."""
        from extensions import db
        from models import SignalCache

        # 10 shares × ₩70,000 — a KR position whose cache lies "USD".
        add_position(auth_user["id"], ticker="005930.KS", shares=10, avg_cost=70000.0)
        with app.app_context():
            db.session.add(SignalCache(
                ticker="005930.KS",
                data_json=json.dumps({
                    "name": "삼성전자", "is_korean": False, "currency": "USD",
                    "price": 70000.0,
                }),
            ))
            db.session.commit()

        # Wave-3 P1 (2026-06-10): /api/portfolio/positions is the endpoint the
        # v2 frontend polls. Its totals must bucket on suffix.
        r = client.get("/api/portfolio/positions")
        assert r.status_code == 200
        d = r.get_json()
        # The KR market value must land in the KRW bucket despite the cache.
        assert d["total_value_krw"] == 700000.0
        assert d["total_value_usd"] == 0
        # And the blended total must NOT be FX-inflated (700k KRW, not 700k USD→KRW).
        assert d["total_value_all_krw"] == 700000


# ── POST /api/portfolio/positions (add) ─────────────────────────────────────

class TestAddPosition:
    def test_add_new_position(self, client, auth_user):
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/positions", json={
                "symbol": "MSFT", "quantity": 5, "price": 300.0,
            })
        assert r.status_code == 200
        # Route returns ok + resolved display metadata (symbol, name, is_korean)
        # so the client can render 회사명 immediately without a second round-trip.
        payload = r.get_json()
        assert payload["ok"] is True
        assert payload["symbol"] == "MSFT"
        assert payload["is_korean"] is False

    def test_add_position_missing_ticker_returns_400(self, client, auth_user):
        r = client.post("/api/portfolio/positions", json={
            "quantity": 1, "price": 1.0,
        })
        assert r.status_code == 400

    def test_add_position_zero_shares_returns_400(self, client, auth_user):
        r = client.post("/api/portfolio/positions", json={
            "symbol": "AAPL", "quantity": 0, "price": 100.0,
        })
        assert r.status_code == 400

    def test_add_position_negative_cost_returns_400(self, client, auth_user):
        r = client.post("/api/portfolio/positions", json={
            "symbol": "AAPL", "quantity": 1, "price": -50,
        })
        assert r.status_code == 400

    def test_add_position_too_long_ticker_returns_400(self, client, auth_user):
        """SEC-004: Position.ticker is String(20) — rejected before SQL."""
        r = client.post("/api/portfolio/positions", json={
            "symbol": "X" * 21, "quantity": 1, "price": 10.0,
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_TICKER"


# ── POST /api/portfolio/positions — purchase_date (open date) ───────────────
#
# FIX (2026-05-22): the production alias endpoint now reads an optional
# "purchase_date" ("YYYY-MM-DD") and stores it as Position.added_at
# (serialised as opened_at). Frontend contract: POST body may include
# purchase_date. Invalid / missing / future → default server clock.

class TestPurchaseDate:
    def _load_added_at(self, app, pid):
        from models import Position
        with app.app_context():
            return Position.query.get(int(pid)).added_at

    def test_valid_purchase_date_sets_added_at(self, client, app, auth_user):
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/positions", json={
                "symbol": "AAPL", "quantity": 10, "price": 150.0,
                "purchase_date": "2025-01-15",
            })
        assert r.status_code == 200, r.data
        pid = r.get_json()["id"]
        added = self._load_added_at(app, pid)
        assert added is not None
        assert added.year == 2025 and added.month == 1 and added.day == 15

    def test_missing_purchase_date_falls_back_to_now(self, client, app, auth_user):
        from datetime import datetime, timezone
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/positions", json={
                "symbol": "MSFT", "quantity": 5, "price": 300.0,
            })
        assert r.status_code == 200, r.data
        added = self._load_added_at(app, r.get_json()["id"])
        assert added is not None
        # Defaulted to ~now (within a generous window).
        assert added >= before.replace(microsecond=0).replace(second=0, minute=0, hour=0)
        assert added.year == before.year

    def test_invalid_format_falls_back_to_now(self, client, app, auth_user):
        from datetime import datetime, timezone
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/positions", json={
                "symbol": "GOOG", "quantity": 1, "price": 100.0,
                "purchase_date": "not-a-date",
            })
        # UX: malformed value must not 400 — falls back silently.
        assert r.status_code == 200, r.data
        added = self._load_added_at(app, r.get_json()["id"])
        assert added is not None
        assert added.year == datetime.now(timezone.utc).year

    def test_future_date_rejected_falls_back_to_now(self, client, app, auth_user):
        from datetime import datetime, timezone, timedelta
        future = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/positions", json={
                "symbol": "NVDA", "quantity": 2, "price": 500.0,
                "purchase_date": future,
            })
        assert r.status_code == 200, r.data
        added = self._load_added_at(app, r.get_json()["id"])
        # Cannot open a position in the future → defaulted to now (this year).
        assert added is not None
        assert added.year == datetime.now(timezone.utc).year
        assert added.date() <= datetime.now(timezone.utc).date()

    def test_ancient_date_rejected_falls_back_to_now(self, client, app, auth_user):
        from datetime import datetime, timezone
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/positions", json={
                "symbol": "TSLA", "quantity": 1, "price": 200.0,
                "purchase_date": "1850-06-01",
            })
        assert r.status_code == 200, r.data
        added = self._load_added_at(app, r.get_json()["id"])
        assert added is not None
        assert added.year == datetime.now(timezone.utc).year

    def test_merge_preserves_original_added_at(self, client, app, auth_user):
        # First buy with an explicit early open date.
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r1 = client.post("/api/portfolio/positions", json={
                "symbol": "AAPL", "quantity": 10, "price": 150.0,
                "purchase_date": "2024-03-01",
            })
        assert r1.status_code == 200, r1.data
        pid = r1.get_json()["id"]
        # Second buy (same ticker) merges; must NOT overwrite added_at.
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r2 = client.post("/api/portfolio/positions", json={
                "symbol": "AAPL", "quantity": 5, "price": 160.0,
                "purchase_date": "2025-09-09",
            })
        assert r2.status_code == 200, r2.data
        added = self._load_added_at(app, pid)
        assert added.year == 2024 and added.month == 3 and added.day == 1


# ── PATCH /api/portfolio/positions/<id> (edit) ──────────────────────────────

class TestEditPosition:
    def test_edit_existing_position(self, client, auth_user, add_position, app):
        from extensions import db
        from models import Position
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        r = client.patch(f"/api/portfolio/positions/{pid}", json={
            "avg_cost": 140.0, "note": "메모",
        })
        assert r.status_code == 200
        with app.app_context():
            p = db.session.get(Position, pid)
            assert p.avg_cost == 140.0
            assert p.shares == 10  # PATCH never touches shares
            assert p.thesis == "메모"

    def test_edit_nonexistent_returns_404(self, client, auth_user):
        r = client.patch("/api/portfolio/positions/99999", json={"avg_cost": 1})
        assert r.status_code == 404

    def test_edit_with_zero_cost_rejected(self, client, auth_user, add_position):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        r = client.patch(f"/api/portfolio/positions/{pid}", json={"avg_cost": 0})
        assert r.status_code == 400

    def test_cannot_edit_other_users_position(self, client, auth_user,
                                               make_user, app, add_position):
        """P0 security: must not be able to touch another user's position."""
        other = make_user(email="other@test.com")
        other_pid = add_position(other["id"], "TSLA", 5, 200.0)
        r = client.patch(f"/api/portfolio/positions/{other_pid}", json={"avg_cost": 1.0})
        assert r.status_code == 404, (
            "CRITICAL: user can edit another user's position!"
        )
        r = client.post("/api/portfolio/trades", json={
            "position_id": other_pid, "action": "sell", "quantity": 1, "price": 1.0,
        })
        assert r.status_code == 404, (
            "CRITICAL: user can record a trade on another user's position!"
        )


# ── POST /api/portfolio/trades — 매수 ────────────────────────────────────────

class TestTradeBuy:
    def test_buy_success(self, client, auth_user, add_position, app):
        from extensions import db
        from models import SignalCache

        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        with app.app_context():
            db.session.add(SignalCache(
                ticker="AAPL",
                data_json=json.dumps({
                    "name": "Apple Inc.", "is_korean": False, "currency": "USD",
                    "price": 170.0,
                }),
            ))
            db.session.commit()

        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "buy", "quantity": 5, "price": 160.0,
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        assert d["newShares"] == 15
        # New avg cost = (10*150 + 5*160) / 15 = 153.33
        assert round(d["newAvgCost"], 2) == 153.33

    def test_buy_invalid_payload(self, client, auth_user, add_position):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "buy", "quantity": 0, "price": 100,
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "TRADE_FIELDS_REQUIRED"

    def test_invalid_action_rejected(self, client, auth_user, add_position):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "hold", "quantity": 1, "price": 100,
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "TRADE_ACTION_INVALID"


# ── POST /api/portfolio/trades — 매도 ────────────────────────────────────────

class TestTradeSell:
    def test_sell_partial(self, client, auth_user, add_position, app):
        from extensions import db
        from models import SignalCache
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        with app.app_context():
            db.session.add(SignalCache(
                ticker="AAPL",
                data_json=json.dumps({
                    "name": "Apple", "is_korean": False, "currency": "USD",
                    "price": 170.0,
                }),
            ))
            db.session.commit()
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "sell", "quantity": 3, "price": 170.0,
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        # pnl = 3 * (170-150) = 60
        assert d["pnl"] == 60.0
        assert d["closed"] is False

    def test_sell_more_than_owned_rejected(self, client, auth_user, add_position, app):
        """P0: Oversell must not create negative positions — rejected, and
        the position is left as it was."""
        from extensions import db
        from models import Position, TradeHistory
        pid = add_position(auth_user["id"], "AAPL", 5, 100.0)
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "sell", "quantity": 10, "price": 110.0,
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "TRADE_SELL_EXCEEDS_HOLDING"
        with app.app_context():
            assert db.session.get(Position, pid).shares == 5
            assert TradeHistory.query.filter_by(user_id=auth_user["id"]).count() == 0

    def test_sell_nonexistent_position_returns_404(self, client, auth_user):
        r = client.post("/api/portfolio/trades", json={
            "position_id": 99999, "action": "sell", "quantity": 1, "price": 100,
        })
        assert r.status_code == 404

    @pytest.mark.parametrize("qty", [-10, 0])
    def test_sell_rejects_non_positive_quantity(
        self, client, auth_user, add_position, app, qty,
    ):
        """SEC-001 / FIX 3: a negative or zero quantity is rejected before any
        state mutation — no sign-flipped proceeds, no accidental full close,
        no trade recorded."""
        from extensions import db
        from models import Position, TradeHistory
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "sell", "quantity": qty, "price": 200.0,
        })
        assert r.status_code == 400
        with app.app_context():
            p = db.session.get(Position, pid)
            assert p is not None
            assert p.shares == 10
            assert TradeHistory.query.filter_by(user_id=auth_user["id"]).count() == 0


# ── GET /api/portfolio/analytics ────────────────────────────────────────────

class TestHistory:
    def test_history_empty_portfolio_returns_empty_list(self, client, auth_user):
        r = client.get("/api/portfolio/history")
        assert r.status_code == 200
        # `market_data_display` rides on every quote-bearing response so the
        # frontend has one field to branch on in both flag states.
        assert r.get_json() == {"data": [], "market_data_display": True}

    def test_history_respects_period_whitelist(self, client, auth_user):
        # Invalid period should fall back to 5d (no crash).
        r = client.get("/api/portfolio/history?period=invalid")
        assert r.status_code == 200


# ── POST /api/profile/capital (seed capital) ────────────────────────────────
# 2026-09-29: PUT /api/portfolio/capital (no frontend consumer) was removed;
# the settings card writes seed capital through API.profile.capital.

class TestCapital:
    def test_set_capital_ok(self, client, auth_user):
        r = client.post("/api/profile/capital", json={
            "available_capital_usd": 5000, "available_capital_krw": 500000,
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["available_capital"] == 5000
        assert d["available_capital_krw"] == 500000

    def test_negative_capital_rejected(self, client, auth_user):
        r = client.post("/api/profile/capital", json={"available_capital_usd": -100})
        assert r.status_code == 400


# ── FIX 1 (2026-05-22): create_trade_alias honours user-supplied trade date ──
#
# TradeModalV2 record-mode sends body["date"] ("YYYY-MM-DD") for already-
# executed past trades. The handler used to ignore it → TradeHistory.traded_at
# fell to default now(), so a 2023 trade was stamped today. Now a valid date is
# applied to traded_at; missing / malformed / future → server-clock fallback.

class TestCreateTradeAliasDate:
    def _seed_cache(self, app, ticker="AAPL", is_kr=False):
        from extensions import db
        from models import SignalCache
        with app.app_context():
            db.session.add(SignalCache(
                ticker=ticker,
                data_json=json.dumps({
                    "name": "Apple", "is_korean": is_kr,
                    "currency": "KRW" if is_kr else "USD", "price": 170.0,
                }),
            ))
            db.session.commit()

    def _latest_trade(self, app, user_id):
        from extensions import db
        from models import TradeHistory
        with app.app_context():
            return (TradeHistory.query.filter_by(user_id=user_id)
                    .order_by(TradeHistory.id.desc()).first())

    def test_buy_with_valid_date_sets_traded_at(
        self, client, auth_user, add_position, app,
    ):
        self._seed_cache(app)
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "buy",
            "quantity": 2, "price": 160.0, "date": "2023-06-15",
        })
        assert r.status_code == 200, r.get_json()
        t = self._latest_trade(app, auth_user["id"])
        assert t.action == "BUY"
        assert t.traded_at.year == 2023
        assert t.traded_at.month == 6
        assert t.traded_at.day == 15

    def test_sell_with_valid_date_sets_traded_at(
        self, client, auth_user, add_position, app,
    ):
        self._seed_cache(app)
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "sell",
            "quantity": 3, "price": 170.0, "date": "2022-01-04",
        })
        assert r.status_code == 200, r.get_json()
        t = self._latest_trade(app, auth_user["id"])
        assert t.action == "SELL"
        assert t.traded_at.year == 2022
        assert t.traded_at.month == 1
        assert t.traded_at.day == 4

    def test_missing_date_falls_back_to_now(
        self, client, auth_user, add_position, app,
    ):
        from datetime import datetime, timezone
        self._seed_cache(app)
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "buy", "quantity": 1, "price": 160.0,
        })
        assert r.status_code == 200, r.get_json()
        t = self._latest_trade(app, auth_user["id"])
        # Within a small window of server "now" (not 1970/epoch, not a past date).
        assert t.traded_at >= before
        assert (t.traded_at - before).total_seconds() < 60

    def test_future_or_malformed_date_falls_back_to_now(
        self, client, auth_user, add_position, app,
    ):
        from datetime import datetime, timezone
        self._seed_cache(app)
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        # Malformed string → None → server clock.
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "buy", "quantity": 1, "price": 160.0,
            "date": "not-a-date",
        })
        assert r.status_code == 200, r.get_json()
        t = self._latest_trade(app, auth_user["id"])
        assert t.traded_at >= before
        # Future date → None → server clock (cannot trade in the future).
        r2 = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "buy", "quantity": 1, "price": 160.0,
            "date": "2099-12-31",
        })
        assert r2.status_code == 200, r2.get_json()
        t2 = self._latest_trade(app, auth_user["id"])
        assert t2.traded_at.year != 2099
        assert t2.traded_at >= before


# ── FIX 2 (2026-05-22): trade currency uses KR-aware default ─────────────────
#
# When SignalCache is stale (sd == {}), the buy/sell paths
# used `sd.get("currency", "USD")`, stamping .KS/.KQ TradeHistory rows
# as "USD" → realizedYtd sums KRW pnl into the USD bucket (huge inflation).
# Fix: default to "KRW" when the ticker suffix marks it KR.

class TestStaleCacheCurrencyFallback:
    def _latest_trade(self, app, user_id):
        from extensions import db
        from models import TradeHistory
        with app.app_context():
            return (TradeHistory.query.filter_by(user_id=user_id)
                    .order_by(TradeHistory.id.desc()).first())

    def test_trade_buy_kr_no_cache_records_krw_currency(
        self, client, auth_user, add_position, app,
    ):
        pid = add_position(auth_user["id"], "005930.KS", 10, 70000.0)
        # No SignalCache → stale → sd == {}.
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "buy", "quantity": 2, "price": 71000.0,
        })
        assert r.status_code == 200, r.get_json()
        t = self._latest_trade(app, auth_user["id"])
        assert t.currency == "KRW"

    def test_sell_kr_no_cache_records_krw_currency(
        self, client, auth_user, add_position, app,
    ):
        pid = add_position(auth_user["id"], "035720.KQ", 10, 50000.0)
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "sell", "quantity": 3, "price": 55000.0,
        })
        assert r.status_code == 200, r.get_json()
        t = self._latest_trade(app, auth_user["id"])
        assert t.currency == "KRW"

    def test_trade_buy_us_no_cache_still_usd(
        self, client, auth_user, add_position, app,
    ):
        """Non-KR ticker keeps USD fallback (no regression)."""
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "buy", "quantity": 2, "price": 160.0,
        })
        assert r.status_code == 200, r.get_json()
        t = self._latest_trade(app, auth_user["id"])
        assert t.currency == "USD"


# ── FIX 4 (2026-05-22): add-buy cost-weights buy_fx_rate (USD positions) ─────
#
# avg_cost was gradient-averaged on add-buy but buy_fx_rate stayed pinned to
# the first lot's rate → KRW cost-basis / KRW P&L% drifted. Now buy_fx_rate is
# cost-weighted (services/position_writes.merge_buy_into). KR keeps buy_fx_rate 0.

class TestAddBuyFxRate:
    def test_trade_buy_kr_keeps_zero_buy_fx_rate(
        self, client, auth_user, add_position, app,
    ):
        from extensions import db
        from models import Position
        # KR position seeded with buy_fx_rate 0 (KR convention).
        pid = add_position(auth_user["id"], "005930.KS", 10, 70000.0, buy_fx=0.0)
        with patch("routes.portfolio.fx_service.get_rate", return_value=1400.0):
            r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "buy", "quantity": 2, "price": 71000.0,
            })
        assert r.status_code == 200, r.get_json()
        with app.app_context():
            p = db.session.get(Position, pid)
            assert p.buy_fx_rate == 0.0  # KR stays 0

    def test_create_trade_alias_buy_updates_buy_fx_rate(
        self, client, auth_user, add_position, app,
    ):
        from extensions import db
        from models import Position, SignalCache
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0, buy_fx=1000.0)
        with app.app_context():
            db.session.add(SignalCache(
                ticker="AAPL",
                data_json=json.dumps({"is_korean": False, "currency": "USD",
                                      "price": 160.0}),
            ))
            db.session.commit()
        with patch("routes.portfolio.fx_service.get_rate", return_value=1400.0):
            r = client.post("/api/portfolio/trades", json={
                "position_id": pid, "action": "buy",
                "quantity": 5, "price": 160.0,
            })
        assert r.status_code == 200, r.get_json()
        with app.app_context():
            p = db.session.get(Position, pid)
            expected = (1000.0 * 1500 + 1400.0 * 800) / (1500 + 800)
            assert round(p.buy_fx_rate, 4) == round(expected, 4)

    def test_positions_merge_updates_buy_fx_rate(
        self, client, auth_user, add_position, app,
    ):
        from extensions import db
        from models import Position
        # POST /positions merges into the existing AAPL row.
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0, buy_fx=1000.0)
        with patch("routes.portfolio.fx_service.get_rate", return_value=1400.0), \
             patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/positions", json={
                "symbol": "AAPL", "quantity": 5, "price": 160.0,
            })
        assert r.status_code == 200, r.get_json()
        with app.app_context():
            p = db.session.get(Position, pid)
            expected = (1000.0 * 1500 + 1400.0 * 800) / (1500 + 800)
            assert round(p.buy_fx_rate, 4) == round(expected, 4)


# ── Bug API#5: non-finite / out-of-range amount rejection ───────────────────
# A crafted shares/price like 1e308 (or inf / nan) previously flowed into
# ``shares * price`` → Infinity → json.dumps(Infinity) → frontend JSON.parse
# crash. Every add/buy/sell entry point now rejects with code=INVALID_AMOUNT
# (400) immediately after float() conversion. Normal small values still pass.

class TestInfiniteAmountGuard:
    def _signal(self, app, ticker="AAPL"):
        from extensions import db
        from models import SignalCache
        with app.app_context():
            db.session.add(SignalCache(
                ticker=ticker,
                data_json=json.dumps({
                    "is_korean": False, "currency": "USD", "price": 100.0,
                    "name": "Apple",
                }),
            ))
            db.session.commit()

    def test_add_position_rejects_huge_shares(self, client, auth_user):
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/positions", json={
                "ticker": "AAPL", "shares": 1e308, "avg_cost": 100.0,
            })
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_AMOUNT"

    def test_add_position_rejects_huge_cost(self, client, auth_user):
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/positions", json={
                "ticker": "AAPL", "shares": 5, "avg_cost": 1e308,
            })
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_AMOUNT"

    def test_add_position_rejects_inf(self, client, auth_user):
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post(
                "/api/portfolio/positions",
                data='{"ticker":"AAPL","shares":Infinity,"avg_cost":100.0}',
                content_type="application/json",
            )
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_AMOUNT"

    def test_add_position_rejects_nan(self, client, auth_user):
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post(
                "/api/portfolio/positions",
                data='{"ticker":"AAPL","shares":NaN,"avg_cost":100.0}',
                content_type="application/json",
            )
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_AMOUNT"

    def test_trade_buy_rejects_huge_price(self, client, auth_user, add_position, app):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        self._signal(app)
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "buy", "quantity": 1, "price": 1e308,
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_AMOUNT"

    def test_sell_rejects_huge_shares(self, client, auth_user, add_position, app):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        self._signal(app)
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "sell", "quantity": 1e308, "price": 100.0,
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_AMOUNT"

    def test_sell_rejects_huge_price(self, client, auth_user, add_position, app):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        self._signal(app)
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "sell", "quantity": 1, "price": 1e308,
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_AMOUNT"

    def test_create_trade_alias_rejects_huge_quantity(
        self, client, auth_user, add_position, app,
    ):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        self._signal(app)
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "buy", "quantity": 1e308, "price": 100.0,
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_AMOUNT"

    def test_normal_amounts_still_accepted(self, client, auth_user, app, mock_fetcher):
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/positions", json={
                "ticker": "MSFT", "shares": 5, "avg_cost": 300.0,
            })
        assert r.status_code == 200, r.get_json()
        assert r.get_json()["ok"] is True

    def test_max_amount_boundary_accepted_just_above_rejected(
        self, client, auth_user,
    ):
        with patch("routes.portfolio.cache_service.cache_ticker"):
            ok = client.post("/api/portfolio/positions", json={
                "ticker": "BND", "shares": 1e9, "avg_cost": 1.0,
            })
        assert ok.status_code == 200, ok.get_json()
        with patch("routes.portfolio.cache_service.cache_ticker"):
            bad = client.post("/api/portfolio/positions", json={
                "ticker": "BNX", "shares": 2e9, "avg_cost": 1.0,
            })
        assert bad.status_code == 400
        assert bad.get_json()["code"] == "INVALID_AMOUNT"


# ── Bug C#2: free-tier 3-position cap is enforced under a User-row lock ──────
# The cap COUNT now runs while holding SELECT FOR UPDATE on the User row, which
# serializes per-user adds and closes the TOCTOU window. True greenlet
# concurrency isn't reproducible under SQLite's single-writer test harness, so
# these assert the locked code path still enforces the cap and never deadlocks.

class TestFreeTierCapUnderLock:
    def test_create_position_alias_cap_enforced(self, client, auth_user, add_position):
        add_position(auth_user["id"], "AAPL", 1, 100)
        add_position(auth_user["id"], "MSFT", 1, 100)
        add_position(auth_user["id"], "GOOG", 1, 100)
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/positions", json={
                "symbol": "AMZN", "quantity": 1, "price": 100,
            })
        assert r.status_code == 403
        assert r.get_json()["code"] == "TIER_LIMIT"

    # 2026-09-29 — 캡은 "새 종목" 에만 건다. 이미 들고 있는 종목에 주식을
    # 더하는 것은 종목 수를 늘리지 않으므로 3종목을 채운 무료 유저도 된다.
    def _fill_cap(self, uid, add_position):
        add_position(uid, "AAPL", 1, 100)
        add_position(uid, "MSFT", 1, 100)
        add_position(uid, "GOOG", 1, 100)

    def _shares(self, app, uid, ticker):
        from models import Position
        with app.app_context():
            return Position.query.filter_by(user_id=uid, ticker=ticker).one().shares

    def test_create_position_alias_merge_into_held_ticker_at_cap(self, client, auth_user, add_position, app):
        self._fill_cap(auth_user["id"], add_position)
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/positions", json={
                "symbol": "MSFT", "quantity": 2, "price": 100,
            })
        assert r.status_code == 200, r.get_json()
        assert self._shares(app, auth_user["id"], "MSFT") == 3

    def test_under_cap_add_still_succeeds(self, client, auth_user, add_position):
        add_position(auth_user["id"], "AAPL", 1, 100)
        add_position(auth_user["id"], "MSFT", 1, 100)
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/positions", json={
                "ticker": "GOOG", "shares": 1, "avg_cost": 100,
            })
        assert r.status_code == 200, r.get_json()

    # 2026-09-29 — 캡은 services/position_writes 한 벌. 원장(ledger)도 같은 상수.
    def test_cap_has_one_source(self):
        from services.imports import ledger
        from services import position_writes
        assert ledger.FREE_POSITION_CAP is position_writes.FREE_POSITION_CAP

    def test_blocks_new_symbol(self, app, auth_user, add_position):
        from extensions import db
        from models import User
        from services.position_writes import blocks_new_symbol
        self._fill_cap(auth_user["id"], add_position)
        with app.app_context():
            u = db.session.get(User, auth_user["id"])
            assert blocks_new_symbol(u, "AMZN") is True
            assert blocks_new_symbol(u, "AAPL") is False  # held → merge

    def test_tier_limit_error_is_bilingual(self, client, auth_user, add_position):
        self._fill_cap(auth_user["id"], add_position)
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/positions", json={
                "symbol": "AMZN", "quantity": 1, "price": 100,
            })
        assert r.status_code == 403
        body = r.get_json()
        assert body["code"] == "TIER_LIMIT"
        assert body["error_kr"]


# ── Bug C#1: position lost-update — locked re-load preserves correctness ────
# POST /trades re-loads the Position under
# SELECT FOR UPDATE *after* locking the User row (lock order User→Position on
# every path → deadlock-free). SQLite no-ops row locks, so we can't reproduce a
# true interleave; these assert the locked-reload path leaves shares /
# avg_cost consistent and that the reorder didn't break the 404 /
# full-close / partial paths.

class TestPositionLockedReload:
    def _signal(self, app, ticker="AAPL"):
        from extensions import db
        from models import SignalCache
        with app.app_context():
            db.session.add(SignalCache(
                ticker=ticker,
                data_json=json.dumps({
                    "is_korean": False, "currency": "USD", "price": 170.0,
                    "name": "Apple",
                }),
            ))
            db.session.commit()

    def test_buy_locked_reload_updates_shares_not_capital(
        self, client, auth_user, add_position, app,
    ):
        from extensions import db
        from models import Position, User
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        self._signal(app)
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "buy", "quantity": 5, "price": 160.0,
        })
        assert r.status_code == 200, r.get_json()
        with app.app_context():
            p = db.session.get(Position, pid)
            assert p.shares == 15
            assert round(p.avg_cost, 2) == 153.33
            u = db.session.get(User, auth_user["id"])
            assert u.available_capital == 10000.0  # recorded fill: seed untouched

    def test_buy_locked_reload_404_when_missing(self, client, auth_user):
        r = client.post("/api/portfolio/trades", json={
            "position_id": 99999, "action": "buy", "quantity": 1, "price": 100.0,
        })
        assert r.status_code == 404

    def test_sell_locked_reload_full_close_deletes_row(
        self, client, auth_user, add_position, app,
    ):
        from extensions import db
        from models import Position, User
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        self._signal(app)
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "sell", "quantity": 10, "price": 170.0,
        })
        assert r.status_code == 200, r.get_json()
        with app.app_context():
            assert db.session.get(Position, pid) is None
            u = db.session.get(User, auth_user["id"])
            assert u.available_capital == 10000.0  # recorded fill: seed untouched

    def test_sell_locked_reload_partial_decrements(
        self, client, auth_user, add_position, app,
    ):
        from extensions import db
        from models import Position
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        self._signal(app)
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "sell", "quantity": 3, "price": 170.0,
        })
        assert r.status_code == 200, r.get_json()
        with app.app_context():
            p = db.session.get(Position, pid)
            assert p.shares == 7
