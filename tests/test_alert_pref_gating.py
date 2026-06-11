"""FIX 1 + FIX 2 (2026-05-22) regression coverage.

FIX 1 — per-event notification_prefs matrix must actually gate delivery:
  * A signal alert maps to the canonical event_id "signal_state". With
    push=False for "signal_state" the user gets NO signal_state push; with
    push=True they do.
  * The in-app (bell) channel pref for "signal_state" gates the persisted
    Alert row too.
  * Fail-open is covered in tests/test_alert_push.py (unmapped kind ships
    regardless of prefs).

FIX 2 — check_52w_highs_lows must skip KR (.KS/.KQ) tickers (FMP range
lookup is unreliable for KRX) while preserving US behaviour exactly.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest


def _us_market_hours_now():
    # 2026-05-13 (Wed) 10:30 ET = 14:30 UTC — inside the US regular session.
    return datetime(2026, 5, 13, 14, 30, 0, tzinfo=ZoneInfo("UTC"))


def _us_signal(ticker="AAPL"):
    return {
        "ticker": ticker,
        "name": "Apple Inc.",
        "signal": "POSITIVE",
        "score": 77,
        "is_korean": False,
        "rec_shares": 3,
        "rec_investment": 600,
        "rec_timing": "open window",
    }


def _set_signal_state_prefs(user_id, *, push, inapp):
    from extensions import db
    from models import User
    u = User.query.get(user_id)
    prefs = dict(u.notification_prefs or {})
    prefs["signal_state"] = {"email": False, "push": push, "inapp": inapp}
    u.notification_prefs = prefs
    db.session.commit()


# ── FIX 1: signal_state push pref gate ──────────────────────────────────────

class TestSignalStatePushGate:
    def test_push_false_suppresses_signal_push(self, app, make_user):
        from services import alert_service

        user = make_user(email="sigpush-off@test.com")
        with app.app_context():
            _set_signal_state_prefs(user["id"], push=False, inapp=True)
            with patch("services.alert_service.datetime") as mock_dt, \
                 patch("services.push_service.notify_alert") as mock_push:
                mock_dt.now.return_value = _us_market_hours_now()
                mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
                alert_service.maybe_generate(user["id"], _us_signal())
            mock_push.assert_not_called()

    def test_push_true_delivers_signal_push(self, app, make_user):
        from services import alert_service

        user = make_user(email="sigpush-on@test.com")
        with app.app_context():
            _set_signal_state_prefs(user["id"], push=True, inapp=True)
            with patch("services.alert_service.datetime") as mock_dt, \
                 patch("services.push_service.notify_alert") as mock_push:
                mock_dt.now.return_value = _us_market_hours_now()
                mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
                alert_service.maybe_generate(user["id"], _us_signal())
            assert mock_push.called, "signal push must fire when push=True"

    def test_inapp_false_suppresses_bell_row(self, app, make_user):
        from models import Alert
        from services import alert_service

        user = make_user(email="siginapp-off@test.com")
        with app.app_context():
            _set_signal_state_prefs(user["id"], push=True, inapp=False)
            with patch("services.alert_service.datetime") as mock_dt, \
                 patch("services.push_service.notify_alert"):
                mock_dt.now.return_value = _us_market_hours_now()
                mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
                alert_service.maybe_generate(user["id"], _us_signal("MSFT"))
            row = Alert.query.filter_by(user_id=user["id"], ticker="MSFT").first()
            assert row is None, "inapp=False must suppress the persisted bell row"

    def test_inapp_true_persists_bell_row(self, app, make_user):
        from models import Alert
        from services import alert_service

        user = make_user(email="siginapp-on@test.com")
        with app.app_context():
            _set_signal_state_prefs(user["id"], push=True, inapp=True)
            with patch("services.alert_service.datetime") as mock_dt, \
                 patch("services.push_service.notify_alert"):
                mock_dt.now.return_value = _us_market_hours_now()
                mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
                alert_service.maybe_generate(user["id"], _us_signal("NVDA"))
            row = Alert.query.filter_by(user_id=user["id"], ticker="NVDA").first()
            assert row is not None, "inapp=True must persist the bell row"

    def test_default_prefs_deliver_signal_push(self, app, make_user):
        """No customisation → NOTIFICATION_PREF_DEFAULTS (signal_state push=True
        / inapp=True) → both channels deliver. Confirms the gate is fail-open
        on the default path."""
        from models import Alert
        from services import alert_service

        user = make_user(email="sigdefault@test.com")
        with app.app_context():
            # notification_prefs left NULL (never customised).
            with patch("services.alert_service.datetime") as mock_dt, \
                 patch("services.push_service.notify_alert") as mock_push:
                mock_dt.now.return_value = _us_market_hours_now()
                mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
                alert_service.maybe_generate(user["id"], _us_signal("AMZN"))
            assert mock_push.called
            row = Alert.query.filter_by(user_id=user["id"], ticker="AMZN").first()
            assert row is not None


# ── FIX 2: check_52w_highs_lows skips KR tickers ────────────────────────────

class TestCheck52wKrRouting:
    """2026-06-11: the old "KR skipped before any range lookup" contract was
    replaced — KR now routes through the KIS-backed ``_lookup_52w_range``
    (w52_hgpr/w52_lwpr, official feed). The surviving safety contract: KR
    must never touch the FMP quote path, and a missing KIS range must stay
    a silent no-alert skip."""

    def test_kr_and_us_both_looked_up_us_alert_fires(self, app, make_user, add_position):
        from services import alert as alert_mod

        user = make_user(email="kr52w@test.com")
        with app.app_context():
            add_position(user["id"], "AAPL", shares=10, avg_cost=150.0)
            add_position(user["id"], "005930.KS", shares=5, avg_cost=70000.0)

            prices = {
                "AAPL": {"price": 199.0},
                "005930.KS": {"price": 80000.0},
            }

            range_calls = []

            def fake_range(ticker):
                range_calls.append(ticker)
                if ticker == "AAPL":
                    # US AAPL at/above 52w high to force an alert path.
                    return (200.0, 100.0)
                # KR: KIS range unavailable → missing pair → silent skip.
                return (None, None)

            with patch("services.container.fetcher") as mock_fetcher, \
                 patch.object(alert_mod, "_lookup_52w_range", side_effect=fake_range), \
                 patch("services.name_resolver.resolve_stock_name",
                       return_value="Apple Inc."), \
                 patch("services.push_service.notify_bell_alert"):
                mock_fetcher.get_prices_batch.return_value = prices
                metrics = alert_mod.check_52w_highs_lows()

            # KR now reaches the (KIS-routed) lookup alongside US.
            assert "005930.KS" in range_calls, \
                "KR ticker must be looked up via the KIS route"
            assert "AAPL" in range_calls, "US ticker must still be processed"
            assert metrics["users_scanned"] >= 1

    def test_kq_missing_kis_range_creates_no_alert(self, app, make_user, add_position):
        from services import alert as alert_mod
        from models import Alert

        user = make_user(email="kq52w@test.com")
        with app.app_context():
            add_position(user["id"], "124500.KQ", shares=5, avg_cost=10000.0)

            with patch("services.container.fetcher") as mock_fetcher, \
                 patch.object(alert_mod, "_lookup_52w_range",
                              return_value=(None, None)), \
                 patch("services.name_resolver.resolve_stock_name",
                       return_value=None), \
                 patch("services.push_service.notify_bell_alert"):
                mock_fetcher.get_prices_batch.return_value = {
                    "124500.KQ": {"price": 19000.0},
                }
                metrics = alert_mod.check_52w_highs_lows()

            # Missing range = silent skip — the old guard's safety, kept.
            assert metrics["alerts_created"] == 0
            assert Alert.query.filter_by(
                user_id=user["id"], ticker="124500.KQ").count() == 0
