"""Tests for services.access_guard — §101 회피 화이트리스트 가드.

Verifies that:
1. Position-only tickers pass.
2. Watchlist-only tickers pass.
3. Tickers with neither return False (and the routes return 403).
4. Case-insensitive ticker matching.
5. Empty/invalid inputs fail closed.
6. /api/signals/<ticker> and /api/scan return 403 on out-of-scope tickers.
"""
from __future__ import annotations

import pytest

from services.access_guard import is_user_allowed_ticker, access_denied_response


# ── Unit tests for is_user_allowed_ticker ────────────────────────────────────

class TestIsUserAllowedTicker:
    def test_position_match(self, app, make_user, add_position):
        user = make_user()
        add_position(user["id"], ticker="AAPL", shares=10, avg_cost=150)
        with app.app_context():
            assert is_user_allowed_ticker(user["id"], "AAPL") is True

    def test_position_match_case_insensitive(self, app, make_user, add_position):
        user = make_user()
        add_position(user["id"], ticker="AAPL")
        with app.app_context():
            assert is_user_allowed_ticker(user["id"], "aapl") is True
            assert is_user_allowed_ticker(user["id"], "AaPl") is True

    def test_watchlist_match(self, app, make_user):
        from extensions import db
        from models import Watchlist
        user = make_user()
        with app.app_context():
            w = Watchlist(user_id=user["id"], ticker="MSFT")
            db.session.add(w)
            db.session.commit()
            assert is_user_allowed_ticker(user["id"], "MSFT") is True

    def test_neither_returns_false(self, app, make_user):
        user = make_user()
        with app.app_context():
            assert is_user_allowed_ticker(user["id"], "TSLA") is False

    def test_other_user_position_does_not_grant_access(self, app, make_user, add_position):
        owner = make_user(email="owner@test.com")
        intruder = make_user(email="intruder@test.com")
        add_position(owner["id"], ticker="NVDA")
        with app.app_context():
            assert is_user_allowed_ticker(owner["id"], "NVDA") is True
            assert is_user_allowed_ticker(intruder["id"], "NVDA") is False

    def test_kr_bare_code_matches_suffixed_holding(self, app, make_user, add_position):
        """A bare 6-digit URL ("/detail/005930") must resolve to the user's
        suffixed holding ("005930.KS"). Frontend cannot infer the suffix."""
        user = make_user()
        add_position(user["id"], ticker="005930.KS")
        with app.app_context():
            assert is_user_allowed_ticker(user["id"], "005930") is True

    def test_kr_mismatched_suffix_matches_holding(self, app, make_user, add_position):
        """A KOSDAQ stock held as ".KQ" must still resolve when the client
        mis-suffixes it as ".KS" (the old hardcode bug). KOSPI/KOSDAQ cannot
        be inferred client-side."""
        user = make_user()
        add_position(user["id"], ticker="035760.KQ")
        with app.app_context():
            assert is_user_allowed_ticker(user["id"], "035760.KS") is True
            assert is_user_allowed_ticker(user["id"], "035760") is True

    def test_kr_tolerant_match_does_not_leak_across_users(self, app, make_user, add_position):
        """Suffix-tolerant matching must remain user-scoped — an intruder who
        does not hold the KRX code is still denied for every suffix form."""
        owner = make_user(email="kr-owner@test.com")
        intruder = make_user(email="kr-intruder@test.com")
        add_position(owner["id"], ticker="005930.KS")
        with app.app_context():
            assert is_user_allowed_ticker(intruder["id"], "005930") is False
            assert is_user_allowed_ticker(intruder["id"], "005930.KS") is False
            assert is_user_allowed_ticker(intruder["id"], "005930.KQ") is False

    def test_empty_ticker_returns_false(self, app, make_user):
        user = make_user()
        with app.app_context():
            assert is_user_allowed_ticker(user["id"], "") is False
            assert is_user_allowed_ticker(user["id"], "   ") is False

    def test_none_ticker_returns_false(self, app, make_user):
        user = make_user()
        with app.app_context():
            assert is_user_allowed_ticker(user["id"], None) is False

    def test_zero_user_id_returns_false(self, app):
        with app.app_context():
            assert is_user_allowed_ticker(0, "AAPL") is False
            assert is_user_allowed_ticker(None, "AAPL") is False


class TestAccessDeniedResponse:
    def test_returns_403_payload(self):
        body, status = access_denied_response()
        assert status == 403
        assert body["error"] == "ticker_not_in_user_scope"
        assert body["cta"] == "add_to_watchlist"
        assert "보유" in body["message"]


# ── Integration tests for guarded routes ─────────────────────────────────────
