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

        r = client.get("/api/portfolio")
        assert r.status_code == 200
        d = r.get_json()
        # The KR market value must land in the KRW bucket despite the cache.
        assert d["total_value_krw"] == 700000.0
        assert d["total_value_usd"] == 0
        # And the blended total must NOT be FX-inflated (700k KRW, not 700k USD→KRW).
        assert d["total_value_all_krw"] == 700000
        # The per-row display field still echoes the cache (unchanged behavior).
        assert d["positions"][0]["currency"] == "USD"


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
        """FIX 3 (2026-05-22): an explicit shares=0 must be rejected with 400
        and must NOT fall back to a full-position close.

        Previously ``float(d.get("shares") or p.shares)`` treated 0 as falsy
        and silently sold the entire position. The handler now distinguishes
        "key omitted" (None → full-position fallback) from "explicit 0" (→ 400)."""
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        r = client.post(f"/api/portfolio/position/{pid}/sell", json={
            "shares": 0, "price": 200.0,
        })
        assert r.status_code == 400, r.get_json()
        assert r.get_json()["error"] == "Shares must be positive"

    def test_sell_position_zero_shares_does_not_full_close(
        self, client, auth_user, add_position, app,
    ):
        """FIX 3 (2026-05-22): the rejected 0-share sell must leave the
        position untouched (no accidental full-close, no trade recorded)."""
        from extensions import db
        from models import Position, TradeHistory
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        r = client.post(f"/api/portfolio/position/{pid}/sell", json={
            "shares": 0, "price": 200.0,
        })
        assert r.status_code == 400
        with app.app_context():
            p = db.session.get(Position, pid)
            assert p is not None  # not full-closed
            assert p.shares == 10
            assert TradeHistory.query.filter_by(user_id=auth_user["id"]).count() == 0

    def test_sell_position_omitted_shares_full_closes(
        self, client, auth_user, add_position, app,
    ):
        """FIX 3 (2026-05-22): omitting `shares` entirely preserves the
        documented "sell entire position" fallback (None → p.shares)."""
        from extensions import db
        from models import Position, SignalCache
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        with app.app_context():
            db.session.add(SignalCache(
                ticker="AAPL",
                data_json=json.dumps({"is_korean": False, "currency": "USD",
                                      "price": 170.0}),
            ))
            db.session.commit()
        r = client.post(f"/api/portfolio/position/{pid}/sell", json={
            "price": 170.0,  # no "shares" key → full close
        })
        assert r.status_code == 200, r.get_json()
        with app.app_context():
            assert db.session.get(Position, pid) is None


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


# ── FIX 2 (2026-05-22): legacy buy_more/sell currency uses KR-aware default ──
#
# When SignalCache is stale (sd == {}), buy_more (:539) and sell_position
# (:821) used `sd.get("currency", "USD")`, stamping .KS/.KQ TradeHistory rows
# as "USD" → realizedYtd sums KRW pnl into the USD bucket (huge inflation).
# Fix: default to "KRW" when the ticker suffix marks it KR.

class TestStaleCacheCurrencyFallback:
    def _latest_trade(self, app, user_id):
        from extensions import db
        from models import TradeHistory
        with app.app_context():
            return (TradeHistory.query.filter_by(user_id=user_id)
                    .order_by(TradeHistory.id.desc()).first())

    def test_buy_more_kr_no_cache_records_krw_currency(
        self, client, auth_user, add_position, app,
    ):
        pid = add_position(auth_user["id"], "005930.KS", 10, 70000.0)
        # No SignalCache → stale → sd == {}.
        r = client.post(f"/api/portfolio/position/{pid}/buy", json={
            "shares": 2, "price": 71000.0,
        })
        assert r.status_code == 200, r.get_json()
        t = self._latest_trade(app, auth_user["id"])
        assert t.currency == "KRW"

    def test_sell_kr_no_cache_records_krw_currency(
        self, client, auth_user, add_position, app,
    ):
        pid = add_position(auth_user["id"], "035720.KQ", 10, 50000.0)
        r = client.post(f"/api/portfolio/position/{pid}/sell", json={
            "shares": 3, "price": 55000.0,
        })
        assert r.status_code == 200, r.get_json()
        t = self._latest_trade(app, auth_user["id"])
        assert t.currency == "KRW"

    def test_buy_more_us_no_cache_still_usd(
        self, client, auth_user, add_position, app,
    ):
        """Non-KR ticker keeps USD fallback (no regression)."""
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        r = client.post(f"/api/portfolio/position/{pid}/buy", json={
            "shares": 2, "price": 160.0,
        })
        assert r.status_code == 200, r.get_json()
        t = self._latest_trade(app, auth_user["id"])
        assert t.currency == "USD"


# ── FIX 4 (2026-05-22): add-buy cost-weights buy_fx_rate (USD positions) ─────
#
# avg_cost was gradient-averaged on add-buy but buy_fx_rate stayed pinned to
# the first lot's rate → KRW cost-basis / KRW P&L% drifted. Now buy_fx_rate is
# cost-weighted (mirrors add_position._merge_into). KR keeps buy_fx_rate 0.

class TestAddBuyFxRate:
    def test_buy_more_updates_buy_fx_rate_weighted(
        self, client, auth_user, add_position, app,
    ):
        from extensions import db
        from models import Position, SignalCache
        # Existing lot: 10 sh @ 150, buy_fx_rate 1000 (from add_position default).
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0, buy_fx=1000.0)
        with app.app_context():
            db.session.add(SignalCache(
                ticker="AAPL",
                data_json=json.dumps({"is_korean": False, "currency": "USD",
                                      "price": 160.0}),
            ))
            db.session.commit()
        with patch("routes.portfolio.fx_service.get_rate", return_value=1400.0):
            r = client.post(f"/api/portfolio/position/{pid}/buy", json={
                "shares": 5, "price": 160.0,  # cost-basis 800 @ fx 1400
            })
        assert r.status_code == 200, r.get_json()
        with app.app_context():
            p = db.session.get(Position, pid)
            # Weighted: (1000*1500 + 1400*800) / (1500+800) = 2,620,000/2300
            expected = (1000.0 * 1500 + 1400.0 * 800) / (1500 + 800)
            assert round(p.buy_fx_rate, 4) == round(expected, 4)
            assert p.buy_fx_rate != 1000.0  # actually moved

    def test_buy_more_kr_keeps_zero_buy_fx_rate(
        self, client, auth_user, add_position, app,
    ):
        from extensions import db
        from models import Position
        # KR position seeded with buy_fx_rate 0 (KR convention).
        pid = add_position(auth_user["id"], "005930.KS", 10, 70000.0, buy_fx=0.0)
        with patch("routes.portfolio.fx_service.get_rate", return_value=1400.0):
            r = client.post(f"/api/portfolio/position/{pid}/buy", json={
                "shares": 2, "price": 71000.0,
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

    def test_buy_new_position_merge_updates_buy_fx_rate(
        self, client, auth_user, add_position, app, mock_fetcher,
    ):
        from extensions import db
        from models import Position
        # buy-new merges into existing AAPL row when one exists.
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0, buy_fx=1000.0)
        with patch("routes.portfolio.fx_service.get_rate", return_value=1400.0):
            r = client.post("/api/portfolio/position/buy-new", json={
                "ticker": "AAPL", "shares": 5, "price": 160.0,
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
            r = client.post("/api/portfolio/position", json={
                "ticker": "AAPL", "shares": 1e308, "avg_cost": 100.0,
            })
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_AMOUNT"

    def test_add_position_rejects_huge_cost(self, client, auth_user):
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/position", json={
                "ticker": "AAPL", "shares": 5, "avg_cost": 1e308,
            })
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_AMOUNT"

    def test_add_position_rejects_inf(self, client, auth_user):
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post(
                "/api/portfolio/position",
                data='{"ticker":"AAPL","shares":Infinity,"avg_cost":100.0}',
                content_type="application/json",
            )
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_AMOUNT"

    def test_add_position_rejects_nan(self, client, auth_user):
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post(
                "/api/portfolio/position",
                data='{"ticker":"AAPL","shares":NaN,"avg_cost":100.0}',
                content_type="application/json",
            )
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_AMOUNT"

    def test_buy_more_rejects_huge_price(self, client, auth_user, add_position, app):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        self._signal(app)
        r = client.post(f"/api/portfolio/position/{pid}/buy", json={
            "shares": 1, "price": 1e308,
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_AMOUNT"

    def test_buy_new_rejects_huge_shares(self, client, auth_user, mock_fetcher):
        r = client.post("/api/portfolio/position/buy-new", json={
            "ticker": "AAPL", "shares": 1e308, "price": 100.0,
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_AMOUNT"

    def test_sell_rejects_huge_shares(self, client, auth_user, add_position, app):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        self._signal(app)
        r = client.post(f"/api/portfolio/position/{pid}/sell", json={
            "shares": 1e308, "price": 100.0,
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_AMOUNT"

    def test_sell_rejects_huge_price(self, client, auth_user, add_position, app):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        self._signal(app)
        r = client.post(f"/api/portfolio/position/{pid}/sell", json={
            "shares": 1, "price": 1e308,
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_AMOUNT"

    def test_create_position_alias_rejects_huge_quantity(self, client, auth_user):
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/positions", json={
                "symbol": "AAPL", "quantity": 1e308, "price": 100.0,
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
            r = client.post("/api/portfolio/position", json={
                "ticker": "MSFT", "shares": 5, "avg_cost": 300.0,
            })
        assert r.status_code == 200, r.get_json()
        assert r.get_json()["ok"] is True

    def test_max_amount_boundary_accepted_just_above_rejected(
        self, client, auth_user,
    ):
        with patch("routes.portfolio.cache_service.cache_ticker"):
            ok = client.post("/api/portfolio/position", json={
                "ticker": "BND", "shares": 1e9, "avg_cost": 1.0,
            })
        assert ok.status_code == 200, ok.get_json()
        with patch("routes.portfolio.cache_service.cache_ticker"):
            bad = client.post("/api/portfolio/position", json={
                "ticker": "BNX", "shares": 2e9, "avg_cost": 1.0,
            })
        assert bad.status_code == 400
        assert bad.get_json()["code"] == "INVALID_AMOUNT"


# ── Bug C#2: free-tier 3-position cap is enforced under a User-row lock ──────
# The cap COUNT now runs while holding SELECT FOR UPDATE on the User row, which
# serializes per-user adds and closes the TOCTOU window. True greenlet
# concurrency isn't reproducible under SQLite's single-writer test harness, so
# these assert the locked code path still enforces the cap across all three add
# entry points and never deadlocks.

class TestFreeTierCapUnderLock:
    def test_add_position_cap_enforced(self, client, auth_user, add_position):
        add_position(auth_user["id"], "AAPL", 1, 100)
        add_position(auth_user["id"], "MSFT", 1, 100)
        add_position(auth_user["id"], "GOOG", 1, 100)
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/position", json={
                "ticker": "AMZN", "shares": 1, "avg_cost": 100,
            })
        assert r.status_code == 403
        assert r.get_json()["code"] == "TIER_LIMIT"

    def test_buy_new_cap_enforced(self, client, auth_user, add_position, mock_fetcher):
        add_position(auth_user["id"], "AAPL", 1, 100)
        add_position(auth_user["id"], "MSFT", 1, 100)
        add_position(auth_user["id"], "GOOG", 1, 100)
        r = client.post("/api/portfolio/position/buy-new", json={
            "ticker": "TSLA", "shares": 1, "price": 100,
        })
        assert r.status_code == 403
        assert r.get_json()["code"] == "TIER_LIMIT"

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

    def test_under_cap_add_still_succeeds(self, client, auth_user, add_position):
        add_position(auth_user["id"], "AAPL", 1, 100)
        add_position(auth_user["id"], "MSFT", 1, 100)
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/position", json={
                "ticker": "GOOG", "shares": 1, "avg_cost": 100,
            })
        assert r.status_code == 200, r.get_json()


# ── Bug C#1: position lost-update — locked re-load preserves correctness ────
# buy_more / sell_position / create_trade_alias now re-load the Position under
# SELECT FOR UPDATE *after* locking the User row (lock order User→Position on
# every path → deadlock-free). SQLite no-ops row locks, so we can't reproduce a
# true interleave; these assert the locked-reload path leaves shares /
# avg_cost / capital consistent and that the reorder didn't break the 404 /
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

    def test_buy_more_locked_reload_updates_shares_and_capital(
        self, client, auth_user, add_position, app,
    ):
        from extensions import db
        from models import Position, User
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        self._signal(app)
        r = client.post(f"/api/portfolio/position/{pid}/buy", json={
            "shares": 5, "price": 160.0,
        })
        assert r.status_code == 200, r.get_json()
        with app.app_context():
            p = db.session.get(Position, pid)
            assert p.shares == 15
            assert round(p.avg_cost, 2) == 153.33
            u = db.session.get(User, auth_user["id"])
            assert u.available_capital == 10000.0 - 5 * 160.0  # 9200

    def test_buy_more_locked_reload_404_when_missing(self, client, auth_user):
        r = client.post("/api/portfolio/position/99999/buy", json={
            "shares": 1, "price": 100.0,
        })
        assert r.status_code == 404

    def test_sell_locked_reload_full_close_deletes_row(
        self, client, auth_user, add_position, app,
    ):
        from extensions import db
        from models import Position, User
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        self._signal(app)
        r = client.post(f"/api/portfolio/position/{pid}/sell", json={
            "shares": 10, "price": 170.0,
        })
        assert r.status_code == 200, r.get_json()
        with app.app_context():
            assert db.session.get(Position, pid) is None
            u = db.session.get(User, auth_user["id"])
            assert u.available_capital == 10000.0 + 10 * 170.0

    def test_sell_locked_reload_partial_decrements(
        self, client, auth_user, add_position, app,
    ):
        from extensions import db
        from models import Position
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        self._signal(app)
        r = client.post(f"/api/portfolio/position/{pid}/sell", json={
            "shares": 3, "price": 170.0,
        })
        assert r.status_code == 200, r.get_json()
        with app.app_context():
            p = db.session.get(Position, pid)
            assert p.shares == 7

    def test_create_trade_alias_buy_locked_reload(
        self, client, auth_user, add_position, app,
    ):
        from extensions import db
        from models import Position
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        self._signal(app)
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "buy", "quantity": 5, "price": 160.0,
        })
        assert r.status_code == 200, r.get_json()
        with app.app_context():
            p = db.session.get(Position, pid)
            assert p.shares == 15

    def test_create_trade_alias_404_when_missing(self, client, auth_user):
        r = client.post("/api/portfolio/trades", json={
            "position_id": 99999, "action": "buy", "quantity": 1, "price": 100.0,
        })
        assert r.status_code == 404
