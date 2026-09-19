"""MARKET_DATA_DISPLAY_ENABLED — the OFF contract.

2026-09-19: no free, legal source lets us display vendor closing prices to a
user (FMP ToS §2.2.2 display / §2.2 derived works; 금융위 4유형 and KRX Open API
restrict redistribution; every free US EOD feed is personal-use only). CEO
decision: turn the display off, run on cost basis, turn it back on the day the
FMP Data Display Agreement is executed.

This module pins what "off" means, endpoint by endpoint, because the frontend
builds against exactly these shapes. The mirror-image "on == unchanged
behaviour" contract is pinned by every pre-existing suite, which now opts in
through the ``market_display_on`` fixture (tests/conftest.py).

Two properties matter most and are asserted repeatedly below:
  1. OFF nulls the market leg but NEVER the cost leg. avg_cost, shares,
     krw_cost, realized P&L and every cost-basis total stay real numbers.
  2. OFF is a stated fact, not an absence. Every affected response carries
     ``market_data_display`` so the client branches on one field.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest


# ═════════════════════════════════════════════════════════════════════════
# The flag itself
# ═════════════════════════════════════════════════════════════════════════

def test_default_is_off_when_env_unset(monkeypatch):
    """An UNSET env var must mean OFF — render.yaml deliberately omits it, so
    'off' has to be what a fresh production boot gets."""
    import importlib
    import config as config_mod

    monkeypatch.delenv("MARKET_DATA_DISPLAY_ENABLED", raising=False)
    reloaded = importlib.reload(config_mod)
    try:
        assert reloaded.MARKET_DATA_DISPLAY_ENABLED is False
        assert reloaded.Config.MARKET_DATA_DISPLAY_ENABLED is False
    finally:
        importlib.reload(config_mod)


@pytest.mark.parametrize("raw,expected", [
    ("1", True), ("true", True), ("True", True), ("TRUE", True), ("yes", True),
    ("0", False), ("", False), ("off", False), ("no", False), ("maybe", False),
])
def test_env_parsing_matches_house_convention(monkeypatch, raw, expected):
    """Same truthy vocabulary as ALPACA_ENABLED — one parser, no drift."""
    import importlib
    import config as config_mod

    monkeypatch.setenv("MARKET_DATA_DISPLAY_ENABLED", raw)
    reloaded = importlib.reload(config_mod)
    try:
        assert reloaded.MARKET_DATA_DISPLAY_ENABLED is expected
    finally:
        monkeypatch.delenv("MARKET_DATA_DISPLAY_ENABLED", raising=False)
        importlib.reload(config_mod)


def test_helper_prefers_app_config(app):
    """``current_app.config`` wins over the env-derived constant — otherwise
    .env's override=True would make the flag untestable (CLAUDE.md 함정 2)."""
    from services.market_display import market_data_display_enabled

    previous = app.config.get("MARKET_DATA_DISPLAY_ENABLED")
    try:
        with app.app_context():
            app.config["MARKET_DATA_DISPLAY_ENABLED"] = True
            assert market_data_display_enabled() is True
            app.config["MARKET_DATA_DISPLAY_ENABLED"] = False
            assert market_data_display_enabled() is False
    finally:
        app.config["MARKET_DATA_DISPLAY_ENABLED"] = previous


# ═════════════════════════════════════════════════════════════════════════
# GET /api/portfolio
# ═════════════════════════════════════════════════════════════════════════

class TestPortfolioOff:
    def test_market_fields_null_cost_fields_intact(
        self, client, auth_user, add_position, market_display_off,
    ):
        add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=150.0)
        r = client.get("/api/portfolio")
        assert r.status_code == 200
        d = r.get_json()
        assert d["market_data_display"] is False

        p = d["positions"][0]
        # Market leg — withheld.
        for field in ("price", "current_price", "price_display", "observed_at",
                      "pnl_pct", "pnl_krw_pct", "market_value", "krw_value",
                      "take_profit", "stop_loss"):
            assert p[field] is None, f"{field} must be null while display is off"
        assert p["price_source"] == "display_disabled"
        # Cost leg — untouched, this is the user's own data.
        assert p["ticker"] == "AAPL"
        assert p["shares"] == 10
        assert p["avg_cost"] == 150.0
        # Totals.
        assert d["total_value_usd"] is None
        assert d["total_value_krw"] is None
        assert d["total_value_all_krw"] is None
        assert d["cost_basis_all_krw"] > 0
        # FX stays available — open.er-api.com permits commercial use and a
        # multi-currency cost basis cannot be summed without it.
        assert d["fx_rate"] > 0

    def test_kr_position_keeps_krw_cost(
        self, client, auth_user, add_position, market_display_off,
    ):
        add_position(auth_user["id"], ticker="005930.KS", shares=10, avg_cost=70000.0)
        d = client.get("/api/portfolio").get_json()
        p = d["positions"][0]
        assert p["krw_cost"] == 700000      # 10 x ₩70,000, no quote involved
        assert p["krw_value"] is None
        assert d["cost_basis_all_krw"] == 700000

    def test_no_quote_overlay_is_called(
        self, client, auth_user, add_position, market_display_off,
    ):
        """Off means we don't even ASK the vendor — no budget burned on a
        surface that may not render the answer."""
        add_position(auth_user["id"], ticker="AAPL", shares=1, avg_cost=100.0)
        with patch("routes.portfolio.overlay_prices") as spy:
            client.get("/api/portfolio")
            client.get("/api/portfolio/positions")
            client.get("/api/portfolio/summary")
        spy.assert_not_called()

    def test_poisoned_cache_cannot_leak_a_price(
        self, client, auth_user, add_position, app, market_display_off,
    ):
        """A SignalCache row holding a stale vendor price must not surface
        through the cache-blob fallback path either."""
        from extensions import db
        from models import SignalCache

        add_position(auth_user["id"], ticker="AAPL", shares=2, avg_cost=100.0)
        with app.app_context():
            db.session.add(SignalCache(ticker="AAPL", data_json=json.dumps({
                "name": "Apple", "price": 402.91, "price_display": "$402.91",
                "take_profit": 450.0, "stop_loss": 380.0,
            })))
            db.session.commit()

        body = client.get("/api/portfolio").data.decode()
        assert "402.91" not in body
        assert "450" not in body.split('"take_profit"')[1][:10]


# ═════════════════════════════════════════════════════════════════════════
# GET /api/portfolio/positions
# ═════════════════════════════════════════════════════════════════════════

class TestPositionsOff:
    def test_shape(self, client, auth_user, add_position, market_display_off):
        add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=150.0)
        r = client.get("/api/portfolio/positions")
        assert r.status_code == 200
        d = r.get_json()
        assert d["market_data_display"] is False
        p = d["positions"][0]
        assert p["current"] is None
        assert p["change_pct"] is None
        assert p["market_value"] is None
        assert p["observed_at"] is None
        assert p["price_source"] == "display_disabled"
        # Cost basis is the weight denominator while market value is withheld.
        assert p["avgCost"] == 150.0
        assert p["shares"] == 10
        assert p["cost_basis_krw"] > 0
        assert d["total_value_usd"] is None
        assert d["total_value_krw"] is None
        assert d["total_value_all_krw"] is None
        assert d["cost_basis_all_krw"] == round(p["cost_basis_krw"])

    def test_cost_basis_uses_the_shared_fx_helper(
        self, client, auth_user, add_position, market_display_off,
    ):
        """No second cost-basis implementation: the row value must be exactly
        what fx_service.cost_basis_krw (the journal concentration mirror's
        helper) returns for the same position — Pattern 7 divergence guard."""
        from models import Position
        from services import fx_service

        add_position(auth_user["id"], ticker="005930.KS", shares=3, avg_cost=70000.0)
        add_position(auth_user["id"], ticker="AAPL", shares=4, avg_cost=100.0)
        rows = client.get("/api/portfolio/positions").get_json()["positions"]
        by_ticker = {r["ticker"]: r for r in rows}

        with market_display_off.app_context():
            for pos in Position.query.all():
                assert by_ticker[pos.ticker]["cost_basis_krw"] == (
                    fx_service.cost_basis_krw(pos)
                )


# ═════════════════════════════════════════════════════════════════════════
# GET /api/portfolio/summary  +  /history
# ═════════════════════════════════════════════════════════════════════════

class TestSummaryOff:
    def test_kpis_null_realized_and_cost_basis_intact(
        self, client, auth_user, add_position, app, market_display_off,
    ):
        from extensions import db
        from models import TradeHistory
        from datetime import datetime, timezone

        add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=150.0)
        add_position(auth_user["id"], ticker="005930.KS", shares=2, avg_cost=70000.0)
        with app.app_context():
            db.session.add(TradeHistory(
                user_id=auth_user["id"], ticker="MSFT", action="SELL",
                shares=1, price_per_share=300.0, total_value=300.0,
                pnl=25.0, pnl_pct=9.1, currency="USD",
                traded_at=datetime.now(timezone.utc),
            ))
            db.session.commit()

        d = client.get("/api/portfolio/summary").get_json()
        assert d["market_data_display"] is False
        for field in ("totalNav", "navUsd", "navKrw", "todayPnl", "todayPnlPct",
                      "unrealized", "todayPnlUsd", "todayPnlKrw",
                      "unrealizedUsd", "unrealizedKrw", "cashPct"):
            assert d[field] is None, f"{field} must be null while display is off"
        # Realized P&L is the user's own recorded execution — never gated.
        assert d["realizedYtd"] == 25.0
        assert d["realizedUsd"] == 25.0
        # Cost basis, native subtotals + FX-normalised total.
        assert d["costBasisUsd"] == 1500.0
        assert d["costBasisKrw"] == 140000
        assert d["costBasisTotalKrw"] > 140000
        assert d["positionCount"] == 2
        assert d["fxRate"] > 0


class TestHistoryOff:
    def test_empty_series_no_benchmark(
        self, client, auth_user, add_position, market_display_off,
    ):
        add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=150.0)
        r = client.get("/api/portfolio/history?period=1mo")
        assert r.status_code == 200
        assert r.get_json() == {"data": [], "market_data_display": False}

    def test_does_not_record_a_nav_snapshot(
        self, client, auth_user, add_position, market_display_off,
    ):
        """The opportunistic snapshot write costs a quote call per page load;
        with nothing to display there is nothing to record."""
        add_position(auth_user["id"], ticker="AAPL", shares=1, avg_cost=100.0)
        with patch("services.portfolio.nav_snapshot.record_today_snapshot") as spy:
            client.get("/api/portfolio/history")
        spy.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════
# Market routes
# ═════════════════════════════════════════════════════════════════════════

class TestMarketRoutesOff:
    def test_indices_refuses(self, client, auth_user, market_display_off):
        r = client.get("/api/market/indices?region=kr")
        assert r.status_code == 503
        body = r.get_json()
        assert body["code"] == "MARKET_DATA_DISPLAY_DISABLED"
        assert body["market_data_display"] is False
        assert body["error"] and body["error_kr"]      # EN + KR both present

    def test_public_snapshot_refuses(self, client, market_display_off):
        r = client.get("/api/public/market-snapshot")
        assert r.status_code == 503
        assert r.get_json()["code"] == "MARKET_DATA_DISPLAY_DISABLED"

    def test_fx_is_exempt(self, client, auth_user, market_display_off):
        """open.er-api.com permits commercial use and the cost-basis sum needs
        the rate — /api/market/fx must keep working."""
        r = client.get("/api/market/fx")
        assert r.status_code == 200
        assert r.get_json()["usd_krw"] > 0

    def test_search_is_exempt(self, client, auth_user, market_display_off):
        """Reference data, no quote. Gating it would make it impossible to
        record a new position, which is the whole product."""
        r = client.get("/api/search?q=005930")
        assert r.status_code == 200
        assert "results" in r.get_json()


class TestRealtimeOff:
    def test_single_price_refuses(self, client, auth_user, market_display_off):
        r = client.get("/api/realtime/price/AAPL")
        assert r.status_code == 503
        assert r.get_json()["code"] == "MARKET_DATA_DISPLAY_DISABLED"

    def test_portfolio_stream_refuses_as_an_sse_event(
        self, client, auth_user, market_display_off,
    ):
        """EventSource cannot read a non-200 body, so the refusal has to ride
        the stream (same shape as the SSE_LIMIT_EXCEEDED precedent)."""
        r = client.get("/api/realtime/portfolio-stream")
        assert r.status_code == 200
        assert r.mimetype == "text/event-stream"
        body = r.get_data(as_text=True)
        assert "event: error" in body
        assert "MARKET_DATA_DISPLAY_DISABLED" in body

    def test_status_reports_the_flag(self, client, auth_user, market_display_off):
        """Provider health is not a quote, so the route stays open — but a
        'live' indicator must not light up."""
        r = client.get("/api/realtime/status")
        assert r.status_code == 200
        assert r.get_json()["market_data_display"] is False


# ═════════════════════════════════════════════════════════════════════════
# GET /api/data/stale-status
# ═════════════════════════════════════════════════════════════════════════

class TestStaleStatusOff:
    def test_reports_not_displayed_never_stale(self, client, market_display_off):
        r = client.get("/api/data/stale-status")
        assert r.status_code == 200
        d = r.get_json()
        assert d["market_data_display"] is False
        assert d["is_stale"] is False
        assert d["stale_ratio"] == 0.0
        assert d["affected_markets"] == []

    def test_degraded_kr_feed_does_not_raise_the_banner(
        self, client, market_display_off,
    ):
        """No prices on screen ⇒ a '시세가 지연되고 있어요' banner would be
        noise about data the user cannot see."""
        from services.container import realtime as rt

        with patch.object(rt, "kr_health", return_value={"degraded": True}):
            d = client.get("/api/data/stale-status").get_json()
        assert d["is_stale"] is False
        assert d["affected_markets"] == []
        assert d["market_data_display"] is False


# ═════════════════════════════════════════════════════════════════════════
# 52-week alert cron
# ═════════════════════════════════════════════════════════════════════════

def _price_alerts_job():
    """Pull the registered ``price_alerts_daily`` callable out of a scheduler
    built with every side effect stubbed (same technique as
    tests/test_price_alerts_cron.py)."""
    from apscheduler.schedulers.background import BackgroundScheduler
    import app as app_module

    captured = {}
    real_init = BackgroundScheduler.__init__

    def _capture_init(self, *a, **kw):
        real_init(self, *a, **kw)
        captured["sched"] = self

    with patch.object(BackgroundScheduler, "__init__", _capture_init), \
         patch.object(BackgroundScheduler, "start", lambda self, *a, **k: None), \
         patch.object(app_module, "_try_acquire_scheduler_lock", return_value=True):
        app_module._init_scheduler(app_module.app)

    jobs = {j.id: j for j in captured["sched"].get_jobs()}
    assert "price_alerts_daily" in jobs, "price_alerts_daily must stay registered"
    return app_module, jobs["price_alerts_daily"].func


@pytest.mark.parametrize("display_on,expect_52w", [(False, False), (True, True)])
def test_52w_sweep_gated_concentration_always_runs(display_on, expect_52w):
    """The job itself is NEVER unregistered (EXPECTED_JOB_COUNT stays put) —
    only the 52w half is skipped. ``check_concentration_alerts`` is cost-basis
    only (services/behavior/concentration_mirror.py) and keeps running."""
    app_module, job_func = _price_alerts_job()
    previous = app_module.app.config.get("MARKET_DATA_DISPLAY_ENABLED")
    app_module.app.config["MARKET_DATA_DISPLAY_ENABLED"] = display_on
    try:
        # ``_record_sched_success`` / ``_alert_sched`` are closures inside
        # ``_init_scheduler`` — patch what they call instead.
        with patch("services.alert.check_52w_highs_lows", return_value={}) as m52, \
             patch("services.alert.check_concentration_alerts", return_value={}) as mcon, \
             patch("services.observability.alerts.record_success"), \
             patch("services.observability.alerts.emit_failure"):
            job_func()
        assert m52.called is expect_52w
        assert mcon.called is True
    finally:
        app_module.app.config["MARKET_DATA_DISPLAY_ENABLED"] = previous


def test_skipped_52w_sweep_still_records_success():
    """A deliberate skip is not a failure — recording one would fire the
    3-strike scheduler watchdog every single day."""
    app_module, job_func = _price_alerts_job()
    previous = app_module.app.config.get("MARKET_DATA_DISPLAY_ENABLED")
    app_module.app.config["MARKET_DATA_DISPLAY_ENABLED"] = False
    try:
        with patch("services.alert.check_52w_highs_lows") as m52, \
             patch("services.alert.check_concentration_alerts", return_value={}), \
             patch("services.observability.alerts.record_success") as rec, \
             patch("services.observability.alerts.emit_failure") as alert:
            job_func()
        m52.assert_not_called()
        alert.assert_not_called()
        recorded = {c.args[0] for c in rec.call_args_list}
        assert "sched_price_alerts_52w" in recorded
        assert "sched_price_alerts_concentration" in recorded
    finally:
        app_module.app.config["MARKET_DATA_DISPLAY_ENABLED"] = previous


# ═════════════════════════════════════════════════════════════════════════
# Cost-basis guard messages
# ═════════════════════════════════════════════════════════════════════════

def test_avg_cost_guard_message_hides_the_vendor_figure(app, market_display_off):
    """The guard keeps running (data integrity) but must not quote the
    vendor's 52-week low back at the user."""
    from routes.portfolio import _avg_cost_implausible

    with app.app_context():
        with patch("services.data.fmp.get_quote", return_value={"yearLow": 180.0}):
            msg = _avg_cost_implausible("AAPL", 10.0)
    assert msg is not None
    assert "180" not in msg
    assert "52-week low" not in msg


def test_avg_cost_guard_message_keeps_the_figure_when_display_on(
    app, market_display_on,
):
    from routes.portfolio import _avg_cost_implausible

    with app.app_context():
        with patch("services.data.fmp.get_quote", return_value={"yearLow": 180.0}):
            msg = _avg_cost_implausible("AAPL", 10.0)
    assert "52-week low" in msg
    assert "180.00" in msg
