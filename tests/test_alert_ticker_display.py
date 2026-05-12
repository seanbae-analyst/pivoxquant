"""Regression: alert title must never duplicate the ticker.

Memory rule ``feedback_ticker_display`` (CEO directive, repeated 3+ times):
- Display the company name primary, ticker secondary in parens.
- When the resolver can't find a name, render ONLY the ticker — never
  produce ``"124500.KQ (124500.KQ)"`` (the pre-2026-05-13 bug).

Background: ``services.alert_service.maybe_generate`` previously wrote
``f"{name} ({ticker}) — Score …"`` with ``name = resolved or ticker``,
so a resolver miss surfaced the ticker twice. The fix collapses the
parenthesised half when ``name == ticker``.
"""
from __future__ import annotations

import re
from unittest.mock import patch
from zoneinfo import ZoneInfo
from datetime import datetime


# ── helpers ─────────────────────────────────────────────────────────────────


def _kr_market_hours_now():
    """A datetime guaranteed to be inside KRX regular session.

    ``maybe_generate`` short-circuits outside 09:00–15:30 KST and weekends,
    so the test must pin ``datetime.now`` to a known weekday at 10:00 KST.
    """
    # 2026-05-13 is a Wednesday — pick 10:00 KST = 01:00 UTC.
    return datetime(2026, 5, 13, 1, 0, 0, tzinfo=ZoneInfo("UTC"))


def _us_market_hours_now():
    # 2026-05-13 10:30 ET = 14:30 UTC.
    return datetime(2026, 5, 13, 14, 30, 0, tzinfo=ZoneInfo("UTC"))


# ── tests ───────────────────────────────────────────────────────────────────


class TestAlertTitleNoTickerDuplication:
    """Guard the ``{name} ({ticker})`` format against resolver misses."""

    def test_kr_ticker_unresolved_renders_ticker_only(self, app, make_user):
        """When KR name resolution misses, message must NOT duplicate ticker."""
        from models import Alert
        from services import alert_service

        user = make_user(email="alert-kr-miss@test.com")

        signal = {
            "ticker": "124500.KQ",
            "name": "124500.KQ",  # upstream fetcher's ticker-fallback
            "signal": "POSITIVE",
            "score": 69,
            "is_korean": True,
            "rec_shares": 0,
            "rec_investment": 0,
            "rec_timing": "open window",
        }

        with app.app_context(), \
             patch("services.alert_service.datetime") as mock_dt, \
             patch(
                 "services.name_resolver.resolve_stock_name_with_db",
                 return_value=None,
             ):
            mock_dt.now.return_value = _kr_market_hours_now()
            # Preserve other datetime attributes the function may touch.
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            alert_service.maybe_generate(user["id"], signal)

            row = Alert.query.filter_by(user_id=user["id"],
                                         ticker="124500.KQ").first()
            assert row is not None, "alert must be persisted"
            assert row.message is not None
            # The bug pattern: ticker appears twice back-to-back inside the
            # subject (with parens around the second copy).
            assert "124500.KQ (124500.KQ)" not in row.message, (
                f"ticker duplicated in message: {row.message!r}"
            )
            # The subject should still mention the ticker (single copy).
            assert "124500.KQ" in row.message

    def test_kr_ticker_resolved_renders_name_with_ticker_suffix(
        self, app, make_user,
    ):
        """When the resolver returns a real name, format is ``name (ticker)``."""
        from models import Alert
        from services import alert_service

        user = make_user(email="alert-kr-hit@test.com")

        signal = {
            "ticker": "005930.KS",
            "name": "005930.KS",  # forces re-resolution path
            "signal": "POSITIVE",
            "score": 82,
            "is_korean": True,
            "rec_shares": 5,
            "rec_investment": 350000,
            "rec_timing": "open window",
        }

        with app.app_context(), \
             patch("services.alert_service.datetime") as mock_dt, \
             patch(
                 "services.name_resolver.resolve_stock_name_with_db",
                 return_value="삼성전자",
             ):
            mock_dt.now.return_value = _kr_market_hours_now()
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            alert_service.maybe_generate(user["id"], signal)

            row = Alert.query.filter_by(user_id=user["id"],
                                         ticker="005930.KS").first()
            assert row is not None
            assert "삼성전자 (005930.KS)" in row.message, row.message

    def test_us_ticker_unresolved_renders_ticker_only(self, app, make_user):
        from models import Alert
        from services import alert_service

        user = make_user(email="alert-us-miss@test.com")

        signal = {
            "ticker": "ZZZZ",
            "name": "ZZZZ",
            "signal": "NEGATIVE",
            "score": 28,
            "is_korean": False,
            "sell_pct": 50,
        }

        with app.app_context(), \
             patch("services.alert_service.datetime") as mock_dt, \
             patch(
                 "services.name_resolver.resolve_stock_name_with_db",
                 return_value=None,
             ):
            mock_dt.now.return_value = _us_market_hours_now()
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            alert_service.maybe_generate(user["id"], signal)

            row = Alert.query.filter_by(user_id=user["id"],
                                         ticker="ZZZZ").first()
            assert row is not None
            assert "ZZZZ (ZZZZ)" not in row.message, row.message
            assert "ZZZZ" in row.message

    def test_no_double_paren_pattern_in_any_branch(self, app, make_user):
        """Cheap belt-and-braces regex: ``X (X)`` (same token both sides) banned."""
        from models import Alert
        from services import alert_service

        user = make_user(email="alert-regex@test.com")
        signal = {
            "ticker": "FAKE.KQ",
            "name": "FAKE.KQ",
            "signal": "POSITIVE",
            "score": 50,
            "is_korean": True,
            "rec_shares": 0,
            "rec_investment": 0,
            "rec_timing": "",
        }
        with app.app_context(), \
             patch("services.alert_service.datetime") as mock_dt, \
             patch(
                 "services.name_resolver.resolve_stock_name_with_db",
                 return_value=None,
             ):
            mock_dt.now.return_value = _kr_market_hours_now()
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            alert_service.maybe_generate(user["id"], signal)

            row = Alert.query.filter_by(
                user_id=user["id"], ticker="FAKE.KQ"
            ).first()
            assert row is not None
            # Ban "<token> (<same token>)" anywhere in the message body.
            m = re.search(r"(\S+)\s+\(\1\)", row.message)
            assert m is None, (
                f"duplicated token pattern in alert message: {m.group(0)!r} "
                f"(full message: {row.message!r})"
            )
