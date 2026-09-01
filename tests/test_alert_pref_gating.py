"""FIX 2 (2026-05-22) regression coverage.

The FIX 1 half of this file covered the "signal_state" gate in
services/alert_service.maybe_generate. That module went with the quant engine
on 2026-09-01 — no signals are produced any more, so there is no signal alert
to gate. The equivalent contract for the alerts that DO fire (52-week range,
sector concentration) is pinned in tests/test_alert_push.py.

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
