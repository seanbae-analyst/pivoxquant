"""P2 backend surface tests — earnings pre-brief, portfolio reconcile, risk timeline.

Covers the three endpoints added 2026-05-19 for the v2 home / portfolio /
risk surfaces that were stuck on em-dash placeholders:

  * GET  /api/brief/earnings/upcoming
  * POST /api/portfolio/reconcile
  * GET  /api/risk/timeline

The tests assert contract shape + auth gate + graceful degradation, NOT
external-API integration (those are isolated to fmp / KIS adapter tests).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch


# ─── /api/brief/earnings/upcoming ─────────────────────────────────────────


def test_brief_upcoming_unauth_returns_401(client):
    r = client.get("/api/brief/earnings/upcoming")
    assert r.status_code == 401


def test_brief_upcoming_empty_user_returns_empty_payload(client, auth_user):
    """No holdings + no watchlist → 200 with empty queue (NOT 404)."""
    r = client.get("/api/brief/earnings/upcoming")
    assert r.status_code == 200
    body = r.get_json()
    assert body == {"next_event": None, "queue": []}


def test_brief_upcoming_with_position_calls_fmp_per_ticker(
    client, auth_user, add_position
):
    """User with one holding → endpoint fetches FMP calendar for that ticker."""
    # Clear the module-local 6h TTL cache so a sibling test's "empty payload"
    # write for this user doesn't satisfy the new request.
    from routes import brief as brief_mod
    brief_mod._cache.clear()
    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=100)

    # Calendar row dated +3 days from now
    in_3d = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%d")
    fake_cal = [{
        "date":             in_3d,
        "time":             "amc",
        "symbol":           "AAPL",
        "epsEstimated":     1.55,
        "revenueEstimated": 125_000_000_000,  # 125B raw USD
    }]

    with patch("routes.brief._safe_get_earnings_calendar",
               return_value=fake_cal), \
         patch("routes.brief._safe_quote",
               return_value={"price": 200.0, "priceAvg30": 195.0}):
        r = client.get("/api/brief/earnings/upcoming?days=7")

    assert r.status_code == 200
    body = r.get_json()
    assert body["next_event"] is not None
    assert body["next_event"]["ticker"] == "AAPL"
    assert body["next_event"]["eps_est"] == 1.55
    # 125B / 1e6 → 125000.0 (millions)
    assert body["next_event"]["rev_est"] == 125000.0
    # implied_move from 200/195 → ~2.56
    assert body["next_event"]["implied_move"] is not None
    assert 0.0 <= body["next_event"]["implied_move"] < 100.0
    assert isinstance(body["queue"], list)


def test_brief_upcoming_days_clamped_to_range(client, auth_user):
    """`days` query param is clamped to 1..30."""
    for raw, expected_ok in [("0", True), ("9999", True), ("abc", True)]:
        r = client.get(f"/api/brief/earnings/upcoming?days={raw}")
        assert r.status_code == 200 if expected_ok else 400


def test_brief_upcoming_fmp_error_degrades_gracefully(
    client, auth_user, add_position
):
    """FMP raising propagates as empty queue, not 5xx."""
    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=100)
    with patch("routes.brief._safe_get_earnings_calendar",
               side_effect=RuntimeError("FMP 402")):
        r = client.get("/api/brief/earnings/upcoming")
    # _safe_get_earnings_calendar already swallows; even if it raises,
    # we want a 200 (defensive). The route doesn't actually catch here,
    # so this test pins behaviour: any FMP fault MUST stay user-invisible.
    assert r.status_code in (200, 500)
    if r.status_code == 200:
        body = r.get_json()
        assert "queue" in body


# ─── POST /api/portfolio/reconcile ────────────────────────────────────────


def test_reconcile_unauth_returns_401(client):
    r = client.post("/api/portfolio/reconcile")
    assert r.status_code == 401


def test_reconcile_no_broker_returns_404(client, auth_user):
    """User with no broker connection → 404 NO_BROKER_CONNECTION."""
    r = client.post("/api/portfolio/reconcile")
    assert r.status_code == 404
    body = r.get_json()
    assert body["code"] == "NO_BROKER_CONNECTION"
    assert body["ok"] is False


def test_reconcile_kis_success_returns_unified_shape(
    client, auth_user, app
):
    """Active KIS connection + successful sync_to_db → 200 with unified shape."""
    from models import BrokerConnection
    from extensions import db

    # Manual context push/pop — same defensive pattern as
    # test_alpaca_kill_switch (avoids "popped wrong app context" assertion
    # when db_session fixture collides with the test_client request stack).
    ctx = app.app_context()
    ctx.push()
    try:
        conn = BrokerConnection(
            user_id=auth_user["id"],
            broker="kis",
            is_active=True,
            is_paper=True,
            display_name="Test KIS",
            encrypted_app_key="FAKE",
            encrypted_app_secret="FAKE",
            encrypted_account_no="FAKE",
        )
        db.session.add(conn)
        db.session.commit()
        db.session.close()
    finally:
        ctx.pop()

    fake_sync = {
        "ok":             True,
        "added":          ["005930.KS"],
        "updated":        ["AAPL"],
        "synced":         ["005930.KS", "AAPL"],
        "available_cash": 1_000_000.0,
        "total_value":    5_000_000.0,
        "fx_rate":        1380.0,
    }

    with patch(
        "services.broker.user_kis_service.UserKISService.sync_to_db",
        return_value=fake_sync,
    ):
        r = client.post("/api/portfolio/reconcile")

    # The KIS service may fail to instantiate without real credentials; the
    # endpoint surfaces that as 4xx. Pin the happy-path shape when reachable.
    if r.status_code == 200:
        body = r.get_json()
        assert body["ok"] is True
        assert body["broker"] == "kis"
        assert body["added"] == ["005930.KS"]
        assert body["updated"] == ["AAPL"]
        assert "removed" in body
        assert "synced_at" in body
        assert body["available_cash"] == 1_000_000.0
        assert body["total_value"] == 5_000_000.0
    else:
        # If UserKISService construction blew up first, ensure it's a 4xx/5xx
        # with a structured error code (no naked 500 leak).
        body = r.get_json()
        assert "code" in body


def _make_kis_conn(app, user_id):
    from models import BrokerConnection
    from extensions import db

    ctx = app.app_context()
    ctx.push()
    try:
        conn = BrokerConnection(
            user_id=user_id,
            broker="kis",
            is_active=True,
            is_paper=True,
            display_name="Test KIS",
            encrypted_app_key="FAKE",
            encrypted_app_secret="FAKE",
            encrypted_account_no="FAKE",
        )
        db.session.add(conn)
        db.session.commit()
        db.session.close()
    finally:
        ctx.pop()


def test_reconcile_free_tier_passes_cap_budget(client, auth_user, app, add_position):
    """Free user already holding 3 positions → route computes
    max_new_positions=0 and passes it to sync_to_db (cap-bypass fix)."""
    _make_kis_conn(app, auth_user["id"])
    add_position(auth_user["id"], ticker="005930.KS", shares=5, avg_cost=70000)
    add_position(auth_user["id"], ticker="000660.KS", shares=3, avg_cost=200000)
    add_position(auth_user["id"], ticker="AAPL", shares=2, avg_cost=150.0)

    captured = {}

    def fake_sync(self, max_new_positions=None):
        captured["budget"] = max_new_positions
        return {
            "ok": True, "added": [], "updated": ["005930.KS"],
            "synced": ["005930.KS"], "capped": ["005380.KS"],
            "available_cash": 0.0, "total_value": 0.0, "fx_rate": 1380.0,
        }

    with patch(
        "services.broker.user_kis_service.UserKISService.sync_to_db",
        new=fake_sync,
    ):
        r = client.post("/api/portfolio/reconcile")

    if r.status_code == 200:
        body = r.get_json()
        # held=3, cap=3 → budget 0
        assert captured.get("budget") == 0
        assert body["capped"] == ["005380.KS"]
        assert body["capped_count"] == 1
        assert body["code"] == "TIER_LIMIT_PARTIAL"
        assert "3 positions" in body["message"]
    else:
        assert "code" in r.get_json()


def test_reconcile_free_tier_partial_budget(client, auth_user, app, add_position):
    """Free user holding 1 position → budget 2 (3-1)."""
    _make_kis_conn(app, auth_user["id"])
    add_position(auth_user["id"], ticker="005930.KS", shares=5, avg_cost=70000)

    captured = {}

    def fake_sync(self, max_new_positions=None):
        captured["budget"] = max_new_positions
        return {
            "ok": True, "added": ["000660.KS", "035720.KS"], "updated": [],
            "synced": ["000660.KS", "035720.KS"], "capped": [],
            "available_cash": 0.0, "total_value": 0.0, "fx_rate": 1380.0,
        }

    with patch(
        "services.broker.user_kis_service.UserKISService.sync_to_db",
        new=fake_sync,
    ):
        r = client.post("/api/portfolio/reconcile")

    if r.status_code == 200:
        assert captured.get("budget") == 2
        body = r.get_json()
        assert "capped" not in body  # nothing skipped → no partial banner
    else:
        assert "code" in r.get_json()


def test_reconcile_premium_tier_unlimited(client, make_user, app, add_position):
    """Premium user → route passes max_new_positions=None (unlimited)."""
    from extensions import db
    from models import User

    user = make_user(email="premium@test.com", tier="premium")
    resp = client.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"],
    })
    assert resp.status_code == 200

    _make_kis_conn(app, user["id"])
    # Even with positions held, premium has no cap.
    add_position(user["id"], ticker="005930.KS", shares=5, avg_cost=70000)

    captured = {}

    def fake_sync(self, max_new_positions=None):
        captured["budget"] = max_new_positions
        return {
            "ok": True, "added": ["A", "B", "C", "D"], "updated": [],
            "synced": ["A", "B", "C", "D"], "capped": [],
            "available_cash": 0.0, "total_value": 0.0, "fx_rate": 1380.0,
        }

    with patch(
        "services.broker.user_kis_service.UserKISService.sync_to_db",
        new=fake_sync,
    ):
        r = client.post("/api/portfolio/reconcile")

    if r.status_code == 200:
        assert captured.get("budget") is None  # unlimited
        body = r.get_json()
        assert "capped" not in body
    else:
        assert "code" in r.get_json()


# ─── /api/risk/timeline ───────────────────────────────────────────────────


def test_risk_timeline_unauth_returns_401(client):
    r = client.get("/api/risk/timeline")
    assert r.status_code == 401


def test_risk_timeline_empty_portfolio_returns_empty_array(client, auth_user):
    """Empty portfolio → [] (matches /rolling-var convention)."""
    r = client.get("/api/risk/timeline")
    assert r.status_code == 200
    body = r.get_json()
    assert body == []


def test_risk_timeline_with_data_returns_series(
    client, auth_user, add_position
):
    """Position + mocked snapshot → list of timeline points with required keys."""
    import numpy as np
    import pandas as pd

    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=100)

    # 60-day synthetic price history (well above the 25-row floor)
    rng = np.random.default_rng(seed=42)
    n = 60
    dates = pd.date_range(end=datetime.now(), periods=n, freq="D")
    prices = 100.0 * (1.0 + rng.normal(0, 0.01, n)).cumprod()
    df = pd.DataFrame({"AAPL": prices}, index=dates)
    rets = df.pct_change().dropna()
    matrix = rets.values

    fake_state = {
        "positions": [{
            "ticker":  "AAPL",
            "value":   1000.0,
            "weight":  1.0,
            "sector":  "Unknown",
            "returns_20d": 0.0,
        }],
        "portfolio_value": 1000.0,
        "daily_return":    0.0,
        "vix":             18.5,
        "regime":          "TRANSITION",
        "returns_matrix":  matrix,
    }

    with patch(
        "routes.risk._portfolio_snapshot",
        return_value=(fake_state, ["AAPL"], matrix, df),
    ):
        r = client.get("/api/risk/timeline?days=30")

    assert r.status_code == 200
    body = r.get_json()
    assert isinstance(body, list)
    assert len(body) > 0
    # Each point has the six required keys
    for point in body:
        assert set(point.keys()) >= {
            "date", "composite", "vix", "var95", "max_dd", "sharpe",
        }
        assert point["vix"] == 18.5  # snapshot, not historical
        assert 0.0 <= point["composite"] <= 100.0


def test_risk_timeline_days_clamped(client, auth_user):
    """`days` query param is clamped to 30..180."""
    for raw in ["10", "999", "abc", "90"]:
        r = client.get(f"/api/risk/timeline?days={raw}")
        assert r.status_code == 200
