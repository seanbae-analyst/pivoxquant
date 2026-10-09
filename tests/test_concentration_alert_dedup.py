"""Bell alert dedup — sector per 7 days, 52w per ticker per 7 days (2026-10-09).

Bugs pinned here (services/alert.py::alert_concentration):

1. The alert passed no ticker, so ``create_alert`` deduped on (user, kind)
   only. Two sectors >= 30% in the same sweep → the second was swallowed.
2. The window was 12h against a once-per-weekday sweep (app.py
   ``_scheduled_price_alerts``), so a standing concentration re-pushed every
   weekday. Now 7 days per (user, sector), matching that function's docstring.
3. 52w (``PRICE_52W_DEDUP_HOURS``) was 24h per ticker against the same daily
   sweep, so a ticker sitting at its 52-week high re-alerted every weekday.
   Now 7 days per (user, kind, ticker). 52w only fires while
   MARKET_DATA_DISPLAY_ENABLED is on.
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest


@pytest.fixture
def two_sector_book(app, make_user, add_position):
    """Technology 47.6% · Communication Services 47.6% · Energy 4.8% (KRW cost)."""
    import json
    from extensions import db
    from models import SignalCache

    user = make_user()
    add_position(user["id"], ticker="AAPL", shares=10, avg_cost=100, buy_fx=1300.0)
    add_position(user["id"], ticker="GOOGL", shares=10, avg_cost=100, buy_fx=1300.0)
    add_position(user["id"], ticker="XOM", shares=10, avg_cost=10, buy_fx=1300.0)
    with app.app_context():
        for tk, sector in (("AAPL", "Technology"),
                           # 22 chars — longer than alerts.ticker String(20),
                           # which is why the sector is not stored there.
                           ("GOOGL", "Communication Services"),
                           ("XOM", "Energy")):
            db.session.merge(SignalCache(ticker=tk, data_json=json.dumps({"sector": sector})))
        db.session.commit()
    return user


def _conc_titles(user_id):
    from models import Alert
    rows = Alert.query.filter_by(user_id=user_id, kind="concentration_alert").all()
    return sorted(r.title for r in rows)


def _age_alerts(user_id, delta):
    """Move every concentration alert ``delta`` into the past (a later sweep)."""
    from extensions import db
    from models import Alert
    for a in Alert.query.filter_by(user_id=user_id, kind="concentration_alert").all():
        a.created_at = a.created_at - delta
    db.session.commit()


def test_two_sectors_over_limit_in_one_sweep_both_alert(app, two_sector_book):
    from services import alert as alert_mod

    uid = two_sector_book["id"]
    with app.app_context(), patch("services.push_service.notify_bell_alert") as push:
        metrics = alert_mod.check_concentration_alerts()
        titles = _conc_titles(uid)

    assert metrics["alerts_created"] == 2, metrics
    assert len(titles) == 2, titles
    assert any(t.startswith("Portfolio concentration — Technology ") for t in titles)
    assert any(t.startswith("Portfolio concentration — Communication Services ") for t in titles)
    assert not any("Energy" in t for t in titles), titles
    assert push.call_count == 2


def test_next_day_sweep_does_not_repeat(app, two_sector_book):
    from services import alert as alert_mod

    uid = two_sector_book["id"]
    with app.app_context(), patch("services.push_service.notify_bell_alert") as push:
        alert_mod.check_concentration_alerts()
        _age_alerts(uid, timedelta(days=1))          # next weekday's sweep
        metrics = alert_mod.check_concentration_alerts()
        titles = _conc_titles(uid)

    assert metrics["alerts_created"] == 0, metrics
    assert len(titles) == 2, titles
    assert push.call_count == 2, "the next-day sweep must not push again"


def test_sweep_after_window_alerts_again(app, two_sector_book):
    """The window is a week, not forever — a persisting condition resurfaces."""
    from services import alert as alert_mod

    uid = two_sector_book["id"]
    with app.app_context(), patch("services.push_service.notify_bell_alert"):
        alert_mod.check_concentration_alerts()
        _age_alerts(uid, timedelta(hours=alert_mod.CONCENTRATION_DEDUP_HOURS + 1))
        metrics = alert_mod.check_concentration_alerts()
    assert metrics["alerts_created"] == 2, metrics


def test_sector_prefix_does_not_match_a_longer_sector_name(app, make_user):
    """"Tech" must not be deduped by an existing "Technology" alert."""
    from services import alert as alert_mod

    user = make_user()
    with app.app_context(), patch("services.push_service.notify_bell_alert"):
        assert alert_mod.alert_concentration(user["id"], "Technology", 41.0) is not None
        assert alert_mod.alert_concentration(user["id"], "Tech", 35.0) is not None
        # Same sector, new pct → deduped.
        assert alert_mod.alert_concentration(user["id"], "Tech", 36.5) is None
        assert len(_conc_titles(user["id"])) == 2


def test_sector_with_like_wildcards_matches_literally(app, make_user):
    """A "%" / "_" in a sector name is literal, not a LIKE wildcard."""
    from services import alert as alert_mod

    user = make_user()
    with app.app_context(), patch("services.push_service.notify_bell_alert"):
        assert alert_mod.alert_concentration(user["id"], "A_B", 40.0) is not None
        # "A_B" as a LIKE pattern would match "AxB" — it must not.
        assert alert_mod.alert_concentration(user["id"], "AxB", 40.0) is not None
        assert alert_mod.alert_concentration(user["id"], "100%", 40.0) is not None
        assert alert_mod.alert_concentration(user["id"], "100x", 40.0) is not None


def _age_52w_alerts(user_id, delta):
    """Move every 52w alert ``delta`` into the past (a later sweep)."""
    from extensions import db
    from models import Alert
    for a in Alert.query.filter(Alert.user_id == user_id,
                                Alert.kind.in_(("price_52w_high",
                                                "price_52w_low"))).all():
        a.created_at = a.created_at - delta
    db.session.commit()


def test_price_52w_dedup_is_weekly_per_ticker(app, make_user):
    """52w moved 24h → 7d per ticker (2026-10-09), same cadence as sector.

    A ticker parked at its 52-week high touches it on every weekday sweep; a
    24h window (vs a 24h sweep interval, with created_at drift) re-alerted it
    every weekday.
    """
    from services import alert as alert_mod

    assert alert_mod.PRICE_52W_DEDUP_HOURS == 7 * 24
    assert alert_mod.CONCENTRATION_DEDUP_HOURS == 7 * 24
    user = make_user()
    with app.app_context(), patch("services.push_service.notify_bell_alert"):
        assert alert_mod.alert_52w_high(user["id"], "AAPL", name="Apple") is not None
        # Key is per ticker — another ticker the same sweep still alerts.
        assert alert_mod.alert_52w_high(user["id"], "MSFT", name="Microsoft") is not None
        assert alert_mod.alert_52w_high(user["id"], "AAPL", name="Apple") is None


@pytest.mark.parametrize("days_later", [1, 4, 6])
def test_price_52w_later_sweeps_inside_week_do_not_repeat(app, make_user, days_later):
    """Next weekday, after a weekend, and day 6 — all still inside the window."""
    from services import alert as alert_mod

    user = make_user()
    with app.app_context(), patch("services.push_service.notify_bell_alert") as push:
        assert alert_mod.alert_52w_high(user["id"], "AAPL", name="Apple") is not None
        # A few minutes of created_at drift past the 24h mark used to be
        # exactly what let the next sweep through.
        _age_52w_alerts(user["id"], timedelta(days=days_later, minutes=5))
        assert alert_mod.alert_52w_high(user["id"], "AAPL", name="Apple") is None
    assert push.call_count == 1


def test_price_52w_after_window_alerts_again(app, make_user):
    """The window is a week, not forever — a ticker still at its high resurfaces."""
    from services import alert as alert_mod

    user = make_user()
    with app.app_context(), patch("services.push_service.notify_bell_alert"):
        assert alert_mod.alert_52w_low(user["id"], "XOM", name="Exxon") is not None
        _age_52w_alerts(user["id"],
                        timedelta(hours=alert_mod.PRICE_52W_DEDUP_HOURS + 1))
        assert alert_mod.alert_52w_low(user["id"], "XOM", name="Exxon") is not None
