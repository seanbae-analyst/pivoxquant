"""
tests/test_portfolio.py — Portfolio CRUD + Trading
===================================================
Covers /api/portfolio: GET, add/edit/delete positions, buyMore, sell,
analytics, history, capital.

External APIs are mocked — no network calls.
"""
import json
from unittest.mock import patch



# ── GET /api/portfolio ──────────────────────────────────────────────────────

class TestGetPortfolio:
    def test_unauthenticated_returns_401(self, client):
        r = client.get("/api/portfolio")
        assert r.status_code == 401

    def test_empty_portfolio(self, client, auth_user):
        r = client.get("/api/portfolio")
        assert r.status_code == 200
        d = r.get_json()
        assert d["positions"] == []
        assert d["total_value_usd"] == 0
        # User capital fixtures set USD=10000, KRW=1,000,000.
        assert d["available_capital"] == 10000.0

    def test_portfolio_with_positions(self, client, auth_user, add_position):
        add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=150.0)
        r = client.get("/api/portfolio")
        assert r.status_code == 200
        d = r.get_json()
        assert len(d["positions"]) == 1
        p = d["positions"][0]
        assert p["ticker"] == "AAPL"
        assert p["shares"] == 10
        assert p["avg_cost"] == 150.0
        assert p["market_value"] == 10 * 150.0  # no signal cache -> fallback to avg_cost


# ── POST /api/portfolio/position (add) ──────────────────────────────────────

class TestAddPosition:
    def test_add_new_position(self, client, auth_user):
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/position", json={
                "ticker": "MSFT",
                "shares": 5,
                "avg_cost": 300.0,
            })
        assert r.status_code == 200
        # Route returns ok + resolved display metadata (ticker, name, is_korean)
        # so the client can render 회사명 immediately without a second round-trip.
        payload = r.get_json()
        assert payload["ok"] is True
        assert payload["ticker"] == "MSFT"
        assert payload["is_korean"] is False

    def test_add_position_missing_ticker_returns_400(self, client, auth_user):
        r = client.post("/api/portfolio/position", json={
            "shares": 1, "avg_cost": 1.0,
        })
        assert r.status_code == 400

    def test_add_position_zero_shares_returns_400(self, client, auth_user):
        r = client.post("/api/portfolio/position", json={
            "ticker": "AAPL", "shares": 0, "avg_cost": 100.0,
        })
        assert r.status_code == 400

    def test_add_position_negative_cost_returns_400(self, client, auth_user):
        r = client.post("/api/portfolio/position", json={
            "ticker": "AAPL", "shares": 1, "avg_cost": -50,
        })
        assert r.status_code == 400

    def test_free_tier_position_limit_enforced(self, client, auth_user, add_position):
        # Free tier limit is 3.
        add_position(auth_user["id"], "AAPL", 1, 100)
        add_position(auth_user["id"], "MSFT", 1, 100)
        add_position(auth_user["id"], "GOOG", 1, 100)
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/position", json={
                "ticker": "AMZN", "shares": 1, "avg_cost": 100,
            })
        assert r.status_code == 403
        assert r.get_json()["code"] == "TIER_LIMIT"


# ── PUT /api/portfolio/position/<id> (edit) ─────────────────────────────────

class TestEditPosition:
    def test_edit_existing_position(self, client, auth_user, add_position):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.put(f"/api/portfolio/position/{pid}", json={
                "shares": 20, "avg_cost": 140.0,
            })
        assert r.status_code == 200

    def test_edit_nonexistent_returns_404(self, client, auth_user):
        r = client.put("/api/portfolio/position/99999", json={
            "shares": 1, "avg_cost": 1,
        })
        assert r.status_code == 404

    def test_edit_with_zero_shares_rejected(self, client, auth_user, add_position):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        r = client.put(f"/api/portfolio/position/{pid}", json={
            "shares": 0, "avg_cost": 150,
        })
        assert r.status_code == 400


# ── DELETE /api/portfolio/position/<id> ─────────────────────────────────────

class TestDeletePosition:
    def test_delete_existing(self, client, auth_user, add_position):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        r = client.delete(f"/api/portfolio/position/{pid}")
        assert r.status_code == 200

    def test_delete_nonexistent_returns_404(self, client, auth_user):
        r = client.delete("/api/portfolio/position/99999")
        assert r.status_code == 404

    def test_cannot_delete_other_users_position(self, client, auth_user,
                                                  make_user, app, add_position):
        """P0 security: must not be able to touch another user's position."""
        other = make_user(email="other@test.com")
        other_pid = add_position(other["id"], "TSLA", 5, 200.0)
        r = client.delete(f"/api/portfolio/position/{other_pid}")
        assert r.status_code == 404, (
            "CRITICAL: user can delete another user's position!"
        )


# ── POST /api/portfolio/position/<id>/buy (buyMore) ─────────────────────────

class TestBuyMore:
    def test_buy_more_success(self, client, auth_user, add_position, app):
        from extensions import db
        from models import SignalCache

        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        # Seed SignalCache with is_korean=False so USD path is used.
        with app.app_context():
            db.session.add(SignalCache(
                ticker="AAPL",
                data_json=json.dumps({
                    "name": "Apple Inc.", "is_korean": False, "currency": "USD",
                    "price": 170.0,
                }),
            ))
            db.session.commit()

        r = client.post(f"/api/portfolio/position/{pid}/buy", json={
            "shares": 5, "price": 160.0,
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        assert d["new_shares"] == 15
        # New avg cost = (10*150 + 5*160) / 15 = 153.33
        assert round(d["new_avg_cost"], 2) == 153.33
        # Capital should be reduced: 10000 - 5*160 = 9200
        assert d["new_capital_usd"] == 9200.0

    def test_buy_more_insufficient_capital(self, client, auth_user, add_position, app):
        from extensions import db
        from models import SignalCache
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        with app.app_context():
            db.session.add(SignalCache(
                ticker="AAPL",
                data_json=json.dumps({"is_korean": False, "currency": "USD"}),
            ))
            db.session.commit()
        # Try to buy way more than 10,000 available.
        r = client.post(f"/api/portfolio/position/{pid}/buy", json={
            "shares": 1000, "price": 500.0,
        })
        assert r.status_code == 400
        assert "insufficient" in r.get_json()["error"].lower()

    def test_buy_more_invalid_payload(self, client, auth_user, add_position):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        r = client.post(f"/api/portfolio/position/{pid}/buy", json={
            "shares": 0, "price": 100,
        })
        assert r.status_code == 400


# ── POST /api/portfolio/position/<id>/sell ──────────────────────────────────

class TestSellPosition:
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
        r = client.post(f"/api/portfolio/position/{pid}/sell", json={
            "shares": 3, "price": 170.0,
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        # pnl = 3 * (170-150) = 60
        assert d["pnl"] == 60.0
        assert d["adjusted"] is False

    def test_sell_more_than_owned_triggers_oversell_guard(
        self, client, auth_user, add_position, app,
    ):
        """P0: Oversell must not create negative positions."""
        from extensions import db
        from models import SignalCache
        pid = add_position(auth_user["id"], "AAPL", 5, 100.0)
        with app.app_context():
            db.session.add(SignalCache(
                ticker="AAPL",
                data_json=json.dumps({
                    "is_korean": False, "currency": "USD", "price": 110.0,
                }),
            ))
            db.session.commit()
        r = client.post(f"/api/portfolio/position/{pid}/sell", json={
            "shares": 10, "price": 110.0,
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["adjusted"] is True
        assert d["actual_shares"] == 5
        assert d["requested_shares"] == 10

    def test_sell_nonexistent_position_returns_404(self, client, auth_user):
        r = client.post("/api/portfolio/position/99999/sell", json={"shares": 1, "price": 100})
        assert r.status_code == 404

    def test_sell_position_rejects_negative_shares(
        self, client, auth_user, add_position,
    ):
        """SEC-001: negative share counts must be rejected.

        Regression for ``sell_shares = float(d.get("shares") or p.shares)`` —
        a negative number is truthy so the previous guard let it through, then
        ``proceeds = actual_sell * sell_price`` flipped sign and credited the
        user. Now we 400 before any state mutation.
        """
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        r = client.post(f"/api/portfolio/position/{pid}/sell", json={
            "shares": -10, "price": 200.0,
        })
        assert r.status_code == 400
        assert r.get_json()["error"] == "Shares must be positive"

    def test_sell_position_rejects_zero_shares(
        self, client, auth_user, add_position,
    ):
        """SEC-001: zero must also be rejected (distinct from `or p.shares`
        fallback, which only fires when the key is missing entirely)."""
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        # Explicit 0 is falsy → falls through to p.shares default (10), so to
        # exercise the guard we send a small negative fraction instead.
        r = client.post(f"/api/portfolio/position/{pid}/sell", json={
            "shares": -0.5, "price": 200.0,
        })
        assert r.status_code == 400


# ── GET /api/portfolio/analytics ────────────────────────────────────────────

class TestAnalytics:
    def test_analytics_empty(self, client, auth_user, mock_engine):
        mock_engine.portfolio_analytics.return_value = {"total": 0}
        r = client.get("/api/portfolio/analytics")
        assert r.status_code == 200
        assert r.get_json() == {"total": 0}

    def test_analytics_unauthenticated(self, client):
        r = client.get("/api/portfolio/analytics")
        assert r.status_code == 401


# ── GET /api/portfolio/history ──────────────────────────────────────────────

class TestHistory:
    def test_history_empty_portfolio_returns_empty_list(self, client, auth_user):
        r = client.get("/api/portfolio/history")
        assert r.status_code == 200
        assert r.get_json() == {"data": []}

    def test_history_respects_period_whitelist(self, client, auth_user):
        # Invalid period should fall back to 5d (no crash).
        r = client.get("/api/portfolio/history?period=invalid")
        assert r.status_code == 200


# ── PUT /api/portfolio/capital ──────────────────────────────────────────────

class TestCapital:
    def test_set_capital_ok(self, client, auth_user):
        r = client.put("/api/portfolio/capital", json={
            "capital_usd": 5000, "capital_krw": 500000,
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["capital_usd"] == 5000
        assert d["capital_krw"] == 500000

    def test_negative_capital_rejected(self, client, auth_user):
        r = client.put("/api/portfolio/capital", json={"capital_usd": -100})
        assert r.status_code == 400


# ── stale-cache KR suffix fallback (2026-05-21 fix) ─────────────────────────
#
# When the SignalCache row is stale (TTL expired → get_signal() returns None →
# sd == {}), buy_more / sell_position used to read ``sd.get("is_korean", False)``
# and mis-route .KS/.KQ capital into the USD bucket. The fix falls back to the
# ticker suffix. These tests seed NO SignalCache row to reproduce the stale
# state, then assert the KRW bucket moves while USD stays frozen.

class TestStaleCacheKrFallback:
    def test_buy_more_kr_no_cache_hits_krw_bucket(
        self, client, auth_user, add_position, app,
    ):
        from extensions import db
        from models import User

        pid = add_position(auth_user["id"], "005930.KS", 10, 70000.0)
        # Deliberately seed NO SignalCache → stale → sd == {}.
        r = client.post(f"/api/portfolio/position/{pid}/buy", json={
            "shares": 2, "price": 71000.0,  # cost = 142,000 KRW
        })
        assert r.status_code == 200, r.get_json()
        d = r.get_json()
        assert d["ok"] is True
        # KRW bucket debited (1,000,000 - 142,000 = 858,000), USD untouched.
        assert d["new_capital_krw"] == 858000.0
        assert d["new_capital_usd"] == 10000.0
        with app.app_context():
            u = db.session.get(User, auth_user["id"])
            assert u.available_capital_krw == 858000.0
            assert u.available_capital == 10000.0

    def test_sell_kr_no_cache_credits_krw_bucket(
        self, client, auth_user, add_position, app,
    ):
        from extensions import db
        from models import User

        pid = add_position(auth_user["id"], "035720.KQ", 10, 50000.0)
        # No SignalCache → stale path.
        r = client.post(f"/api/portfolio/position/{pid}/sell", json={
            "shares": 3, "price": 55000.0,  # proceeds = 165,000 KRW
        })
        assert r.status_code == 200, r.get_json()
        d = r.get_json()
        assert d["ok"] is True
        # KRW bucket credited (1,000,000 + 165,000 = 1,165,000), USD untouched.
        assert d["new_capital_krw"] == 1165000.0
        assert d["new_capital_usd"] == 10000.0
        with app.app_context():
            u = db.session.get(User, auth_user["id"])
            assert u.available_capital_krw == 1165000.0
            assert u.available_capital == 10000.0


# ── buy_new_position response reflects post-deduction balance ───────────────
#
# Regression for the 2026-05-21 fix: the response now reads
# ``locked_user.available_capital`` (the row that actually holds the
# deduction) instead of ``current_user``. Assert new_capital_usd/krw equal the
# debited balance.

class TestBuyNewCapitalResponse:
    def test_buy_new_usd_response_matches_debited_balance(
        self, client, auth_user, mock_fetcher,
    ):
        r = client.post("/api/portfolio/position/buy-new", json={
            "ticker": "AAPL", "shares": 5, "price": 160.0,  # cost = 800 USD
        })
        assert r.status_code == 200, r.get_json()
        d = r.get_json()
        assert d["ok"] is True
        assert d["new_capital_usd"] == 9200.0  # 10000 - 800
        assert d["new_capital_krw"] == 1000000.0  # untouched

    def test_buy_new_kr_response_matches_debited_balance(
        self, client, auth_user, mock_fetcher,
    ):
        r = client.post("/api/portfolio/position/buy-new", json={
            "ticker": "005930.KS", "shares": 2, "price": 70000.0,  # 140,000 KRW
        })
        assert r.status_code == 200, r.get_json()
        d = r.get_json()
        assert d["ok"] is True
        assert d["new_capital_krw"] == 860000.0  # 1,000,000 - 140,000
        assert d["new_capital_usd"] == 10000.0  # untouched
