"""
tests/test_profile_layer2.py — Living CFO Layer 2 backend API
=============================================================
Covers the 4 endpoints wired from ``frontend/src/lib/cfo/hooks.ts``:

    GET  /api/profile/persona
    GET  /api/profile/rolling-window
    POST /api/profile/feedback
    GET  /api/profile/pulse
    POST /api/profile/pulse

All endpoints must:
  - Require authentication (401 otherwise).
  - Return HTTP 200 with a *valid* payload even when the user has no
    trade history (brand-new account path) — the frontend SWR layer
    relies on this contract to avoid flicker.
  - Only return data scoped to the authenticated user.

External APIs are NOT called — persona/rolling computations are pure
over the SQLite test DB.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _add_trades(app, user_id: int, specs: list[dict]) -> None:
    """Insert TradeHistory rows directly.

    Each spec: ticker, action, shares, price, days_ago.
    """
    from extensions import db
    from models import TradeHistory

    now = _utc_now()
    with app.app_context():
        for s in specs:
            db.session.add(TradeHistory(
                user_id=user_id,
                ticker=s["ticker"],
                action=s["action"],
                shares=float(s["shares"]),
                price_per_share=float(s.get("price", 100.0)),
                total_value=float(s.get("shares", 1)) * float(s.get("price", 100.0)),
                traded_at=now - timedelta(days=float(s.get("days_ago", 1))),
            ))
        db.session.commit()


def _set_profile(app, user_id: int, profile_type: str = "growth", risk_tolerance: int = 7) -> None:
    from extensions import db
    from models import InvestmentProfile

    with app.app_context():
        p = InvestmentProfile.query.filter_by(user_id=user_id).first()
        if p is None:
            p = InvestmentProfile(user_id=user_id)
            db.session.add(p)
        p.profile_type = profile_type
        p.risk_tolerance = risk_tolerance
        p.apply_preset()
        db.session.commit()


# ═════════════════════════════════════════════════════════════════════
# GET /api/profile/persona
# ═════════════════════════════════════════════════════════════════════

class TestGetPersona:
    def test_unauthenticated_returns_401(self, client):
        r = client.get("/api/profile/persona")
        assert r.status_code == 401

    def test_empty_user_returns_200_with_balanced_fallback(self, client, auth_user):
        r = client.get("/api/profile/persona")
        assert r.status_code == 200
        d = r.get_json()
        # Even without profile or trades, the contract must hold.
        assert "declared" in d and "observed" in d
        assert set(d["observed"].keys()) == {"window_30d", "window_60d", "window_90d"}
        assert d["declared"]["persona"] in (
            "growth", "value", "balanced", "income",
            "quant", "speculator", "daytrader", "beginner",
        )
        # Drift is always bounded.
        assert 0 <= d["drift"] <= 100
        # Sparkline can be empty but must exist.
        assert isinstance(d["sparkline"], list)

    def test_declared_resolves_from_profile(self, app, client, auth_user):
        _set_profile(app, auth_user["id"], profile_type="growth", risk_tolerance=8)
        r = client.get("/api/profile/persona")
        d = r.get_json()
        assert d["declared"]["persona"] == "growth"
        assert d["declared"]["label"] == "Growth CFO"
        assert d["declared"]["tagline"]  # non-empty
        assert 35 <= d["declared"]["score"] <= 95

    def test_observed_persona_populated_with_trades(self, app, client, auth_user):
        _set_profile(app, auth_user["id"], profile_type="growth", risk_tolerance=6)
        # Daytrader pattern: many same-day BUY/SELL trades.
        specs = []
        for i in range(20):
            specs.append({"ticker": "AAPL", "action": "BUY",  "shares": 10, "price": 150, "days_ago": 10 - (i * 0.1)})
            specs.append({"ticker": "AAPL", "action": "SELL", "shares": 10, "price": 151, "days_ago": 10 - (i * 0.1) - 0.01})
        _add_trades(app, auth_user["id"], specs)
        r = client.get("/api/profile/persona")
        d = r.get_json()
        assert d["observed"]["window_30d"]["score"] > 0
        # Expect a short-hold / high-turnover persona label.
        assert d["observed"]["window_30d"]["persona"] in (
            "daytrader", "speculator", "growth", "quant",
        )


# ═════════════════════════════════════════════════════════════════════
# GET /api/profile/rolling-window
# ═════════════════════════════════════════════════════════════════════

class TestRollingWindow:
    def test_unauthenticated_returns_401(self, client):
        r = client.get("/api/profile/rolling-window")
        assert r.status_code == 401

    def test_empty_user_returns_200_with_empty_series(self, client, auth_user):
        r = client.get("/api/profile/rolling-window")
        assert r.status_code == 200
        d = r.get_json()
        assert "series" in d and "contrast" in d
        assert d["series"]["window_30d"] == []
        assert d["series"]["window_60d"] == []
        assert d["series"]["window_90d"] == []
        assert d["contrast"]["window_days"] == 30

    def test_series_populated_with_trades(self, app, client, auth_user):
        _set_profile(app, auth_user["id"], profile_type="growth", risk_tolerance=7)
        specs = [
            {"ticker": "AAPL", "action": "BUY",  "shares": 10, "price": 150, "days_ago": 25},
            {"ticker": "AAPL", "action": "SELL", "shares": 10, "price": 160, "days_ago": 10},
            {"ticker": "TSLA", "action": "BUY",  "shares": 5,  "price": 200, "days_ago": 15},
            {"ticker": "NVDA", "action": "BUY",  "shares": 3,  "price": 500, "days_ago": 5},
        ]
        _add_trades(app, auth_user["id"], specs)
        r = client.get("/api/profile/rolling-window")
        d = r.get_json()
        # At least one point in the 30d window.
        assert len(d["series"]["window_30d"]) >= 1
        pt = d["series"]["window_30d"][0]
        assert {"date", "holdingPeriod", "turnover", "sectorTilt"} <= set(pt.keys())
        assert 0.0 <= pt["turnover"] <= 1.0
        assert 0.0 <= pt["sectorTilt"] <= 1.0
        # Contrast contains the declared persona.
        assert d["contrast"]["declared_persona"] == "growth"


# ═════════════════════════════════════════════════════════════════════
# POST /api/profile/feedback
# ═════════════════════════════════════════════════════════════════════

class TestFeedback:
    def test_unauthenticated_returns_401(self, client):
        r = client.post("/api/profile/feedback", json={
            "artifact_id": "abc",
            "section": "opener",
            "vote": "useful",
        })
        assert r.status_code == 401

    def test_valid_vote_persists(self, app, client, auth_user):
        r = client.post("/api/profile/feedback", json={
            "artifact_id": "memo-2026-04-23",
            "section": "signal_focus",
            "vote": "useful",
        })
        assert r.status_code == 200, r.data
        assert r.get_json() == {"ok": True}

        from extensions import db
        from models import ArtifactFeedback
        with app.app_context():
            rows = ArtifactFeedback.query.filter_by(user_id=auth_user["id"]).all()
            assert len(rows) == 1
            assert rows[0].vote == "useful"
            assert rows[0].section == "signal_focus"

    def test_missing_artifact_id_rejected(self, client, auth_user):
        r = client.post("/api/profile/feedback", json={
            "section": "opener",
            "vote": "useful",
        })
        assert r.status_code == 400

    def test_invalid_vote_rejected(self, client, auth_user):
        r = client.post("/api/profile/feedback", json={
            "artifact_id": "a",
            "section": "opener",
            "vote": "love-it",
        })
        assert r.status_code == 400

    def test_duplicate_votes_allowed(self, app, client, auth_user):
        # Frontend re-clicks are a legitimate "changed my mind" signal.
        for vote in ("useful", "meh", "skip"):
            r = client.post("/api/profile/feedback", json={
                "artifact_id": "memo-1",
                "section": "opener",
                "vote": vote,
            })
            assert r.status_code == 200
        from models import ArtifactFeedback
        with app.app_context():
            assert ArtifactFeedback.query.filter_by(user_id=auth_user["id"]).count() == 3


# ═════════════════════════════════════════════════════════════════════
# GET / POST /api/profile/pulse
# ═════════════════════════════════════════════════════════════════════

class TestPulse:
    def test_get_unauthenticated_returns_401(self, client):
        r = client.get("/api/profile/pulse")
        assert r.status_code == 401

    def test_post_unauthenticated_returns_401(self, client):
        r = client.post("/api/profile/pulse", json={"mood": 3, "confidence": 4})
        assert r.status_code == 401

    def test_empty_user_returns_200_empty_history(self, client, auth_user):
        r = client.get("/api/profile/pulse")
        assert r.status_code == 200
        d = r.get_json()
        assert d["history"] == []
        assert d["cadence"] == "weekly"
        # next_due_at is still populated relative to "now" so the UI can
        # render a timer on day 1.
        assert d["next_due_at"] is not None

    def test_valid_submission_persists_and_is_returned(self, app, client, auth_user):
        r = client.post("/api/profile/pulse", json={
            "mood": 4,
            "confidence": 3,
            "worry": "rate cuts slower than expected",
            "topics": ["macro", "tech"],
            "learn": "compare sharpe to sortino",
        })
        assert r.status_code == 200, r.data
        assert r.get_json() == {"ok": True}

        r2 = client.get("/api/profile/pulse")
        d = r2.get_json()
        assert len(d["history"]) == 1
        entry = d["history"][0]
        assert entry["mood"] == 4
        assert entry["confidence"] == 3
        assert entry["worry"] == "rate cuts slower than expected"
        assert entry["topics"] == ["macro", "tech"]
        assert entry["learn"] == "compare sharpe to sortino"
        assert entry["submitted_at"]  # ISO timestamp present

    def test_mood_out_of_range_rejected(self, client, auth_user):
        r = client.post("/api/profile/pulse", json={"mood": 7, "confidence": 3})
        assert r.status_code == 400

    def test_confidence_non_integer_rejected(self, client, auth_user):
        r = client.post("/api/profile/pulse", json={"mood": 3, "confidence": "high"})
        assert r.status_code == 400

    def test_long_text_silently_truncated(self, app, client, auth_user):
        long_str = "a" * 2000
        r = client.post("/api/profile/pulse", json={
            "mood": 3,
            "confidence": 3,
            "worry": long_str,
            "learn": long_str,
        })
        assert r.status_code == 200
        from models import WeeklyPulse
        with app.app_context():
            row = WeeklyPulse.query.filter_by(user_id=auth_user["id"]).first()
            assert len(row.worry) == 500
            assert len(row.learn) == 500

    def test_cadence_respected(self, app, client, auth_user):
        r = client.post("/api/profile/pulse", json={
            "mood": 3, "confidence": 3, "cadence": "biweekly",
        })
        assert r.status_code == 200
        r2 = client.get("/api/profile/pulse")
        d = r2.get_json()
        assert d["cadence"] == "biweekly"

    def test_invalid_cadence_falls_back_to_default(self, app, client, auth_user):
        r = client.post("/api/profile/pulse", json={
            "mood": 3, "confidence": 3, "cadence": "daily",
        })
        assert r.status_code == 200
        r2 = client.get("/api/profile/pulse")
        assert r2.get_json()["cadence"] == "weekly"

    def test_user_scoping(self, app, client, make_user, auth_user):
        # Submit as user A.
        client.post("/api/profile/pulse", json={"mood": 5, "confidence": 5})

        # Log in as a different user B.
        other = make_user(email="other@test.com")
        client.post("/api/auth/logout")
        client.post("/api/auth/login", json={
            "email": other["email"], "password": other["password"],
        })
        r = client.get("/api/profile/pulse")
        d = r.get_json()
        assert d["history"] == []  # user B sees nothing of user A


# ═════════════════════════════════════════════════════════════════════
# Cross-endpoint: feedback + pulse scoping under user switch
# ═════════════════════════════════════════════════════════════════════

class TestScoping:
    def test_feedback_is_user_scoped(self, app, client, make_user, auth_user):
        client.post("/api/profile/feedback", json={
            "artifact_id": "a", "section": "opener", "vote": "useful",
        })
        other = make_user(email="other2@test.com")
        client.post("/api/auth/logout")
        client.post("/api/auth/login", json={
            "email": other["email"], "password": other["password"],
        })
        from models import ArtifactFeedback
        with app.app_context():
            assert ArtifactFeedback.query.filter_by(user_id=other["id"]).count() == 0
            assert ArtifactFeedback.query.filter_by(user_id=auth_user["id"]).count() == 1
