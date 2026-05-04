"""tests/test_trades_route.py — /api/trades user isolation.

Wave 11 (P1 critical path) — trades_bp had no direct HTTP test. Trades
are user-private financial records; an isolation regression here would
leak one user's history to another. We verify:

  - GET returns only the authenticated user's trades.
  - Other users' trades are excluded even when the DB has both.
"""
from __future__ import annotations

from datetime import datetime, timezone


def _make_trade(app, user_id, *, ticker="AAPL", action="BUY", shares=10.0):
    """Insert a TradeHistory row directly."""
    from extensions import db
    from models import TradeHistory
    with app.app_context():
        t = TradeHistory(
            user_id=user_id,
            ticker=ticker,
            name=ticker,
            action=action,
            shares=shares,
            price_per_share=150.0,
            total_value=shares * 150.0,
            currency="USD",
            traded_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.session.add(t)
        db.session.commit()
        return t.id


class TestTradesOwnTrades:
    def test_trades_returns_own_trades_only(self, client, auth_user, app):
        """The authenticated user sees their own trades and only their own."""
        _make_trade(app, auth_user["id"], ticker="AAPL", action="BUY")
        _make_trade(app, auth_user["id"], ticker="MSFT", action="SELL")

        r = client.get("/api/trades")
        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        assert "trades" in body
        tickers = {t["ticker"] for t in body["trades"]}
        assert tickers == {"AAPL", "MSFT"}


class TestTradesUserIsolation:
    def test_trades_user_isolation_other_user_excluded(
        self, client, auth_user, make_user, app
    ):
        """Another user's trades must NEVER appear in this user's response.

        IDOR regression guard — a missing user_id filter on the SQLAlchemy
        query would leak the entire trade_history table.
        """
        # auth_user owns AAPL
        _make_trade(app, auth_user["id"], ticker="AAPL", action="BUY")

        # A second, unrelated user owns TSLA — must NOT leak.
        other = make_user(email="other@test.com", password="other12345")
        _make_trade(app, other["id"], ticker="TSLA", action="BUY")
        _make_trade(app, other["id"], ticker="NVDA", action="SELL")

        r = client.get("/api/trades")
        assert r.status_code == 200, r.get_json()
        tickers = {t["ticker"] for t in r.get_json()["trades"]}
        assert "AAPL" in tickers
        assert "TSLA" not in tickers, "IDOR: other user's trade leaked"
        assert "NVDA" not in tickers, "IDOR: other user's trade leaked"
