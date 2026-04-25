"""Tests for Feature 6 — Pre-Trade Friction.

Covers the service-layer invariants (rationale floor, cooldown
duration, auto-extend triggers, ownership check) and the route-layer
contract (CSRF, status codes, observational disclaimer).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from extensions import db
from models import (
    PreTradeReflection,
    DEFAULT_COOLDOWN_SECONDS,
    EXTENDED_COOLDOWN_SECONDS,
    MIN_RATIONALE_CHARS,
)
from services.pre_trade.friction import (
    cancel,
    check_status,
    proceed,
    start_cooldown,
)


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

LONG_RATIONALE = (
    "포지션 사이즈가 작아도 손절 룰을 어기지 않기 위해 미리 reasoning 을 적어둔다. "
    "충분한 길이의 자기 reflection 메모로 사용한다."
)


def _make_user(make_user, email="pt@test.com"):
    return make_user(email=email)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─────────────────────────────────────────────────────────────────────
# Service layer
# ─────────────────────────────────────────────────────────────────────

def test_start_creates_reflection(app, make_user):
    user = _make_user(make_user)
    with app.app_context():
        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=10,
            rationale=LONG_RATIONALE,
        )
        assert out["intended_ticker"] == "AAPL"
        assert out["intended_side"] == "BUY"
        assert out["status"] == "pending"
        assert out["seconds_remaining"] > 0
        # Row persisted.
        row = db.session.get(PreTradeReflection, out["id"])
        assert row is not None
        assert int(row.user_id) == int(user["id"])


def test_rationale_too_short_rejects(app, make_user):
    user = _make_user(make_user, email="pt-short@test.com")
    with app.app_context():
        with pytest.raises(ValueError, match="rationale"):
            start_cooldown(
                user_id=user["id"],
                ticker="AAPL",
                side="BUY",
                shares=1,
                rationale="too short",
            )


def test_cooldown_2min_default(app, make_user):
    """Default cooldown is exactly 120 seconds when no extend trigger fires."""
    user = _make_user(make_user, email="pt-2min@test.com")
    with app.app_context(), patch(
        "services.pre_trade.friction._should_extend_cooldown",
        return_value=None,
    ):
        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
        )
        # Allow ±5s tolerance for test-runner clock drift.
        assert abs(out["seconds_remaining"] - DEFAULT_COOLDOWN_SECONDS) <= 5
        assert out["auto_extended_reason"] is None


def test_fomc_extension_to_5min(app, make_user):
    """FOMC trigger extends to 5 minutes and stamps the reason."""
    user = _make_user(make_user, email="pt-fomc@test.com")
    with app.app_context(), patch(
        "services.pre_trade.friction._fomc_window_active", return_value=True
    ), patch(
        "services.pre_trade.friction._read_vix", return_value=None
    ), patch(
        "services.pre_trade.friction._ticker_moved_more_than", return_value=False
    ):
        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
        )
        assert out["auto_extended_reason"] == "fomc_30min"
        assert abs(out["seconds_remaining"] - EXTENDED_COOLDOWN_SECONDS) <= 5


def test_high_vix_extension(app, make_user):
    """VIX > 30 extends to 5 minutes."""
    user = _make_user(make_user, email="pt-vix@test.com")
    with app.app_context(), patch(
        "services.pre_trade.friction._fomc_window_active", return_value=False
    ), patch(
        "services.pre_trade.friction._ticker_moved_more_than", return_value=False
    ):
        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
            market_volatility=35.0,
        )
        assert out["auto_extended_reason"] == "high_vix"
        assert abs(out["seconds_remaining"] - EXTENDED_COOLDOWN_SECONDS) <= 5


def test_proceed_before_cooldown_rejects(app, make_user):
    user = _make_user(make_user, email="pt-prep@test.com")
    with app.app_context():
        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
        )
        with pytest.raises(ValueError, match="cooldown"):
            proceed(out["id"], user["id"])


def test_proceed_after_cooldown_succeeds(app, make_user):
    user = _make_user(make_user, email="pt-after@test.com")
    with app.app_context():
        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
        )
        # Fast-forward by rewriting cooldown_ends_at backwards.
        row = db.session.get(PreTradeReflection, out["id"])
        row.cooldown_ends_at = _utc_now() - timedelta(seconds=1)
        db.session.commit()

        result = proceed(out["id"], user["id"])
        assert result["status"] == "proceeded"
        assert result["proceeded_at"] is not None


def test_cancel_works(app, make_user):
    user = _make_user(make_user, email="pt-cancel@test.com")
    with app.app_context():
        out = start_cooldown(
            user_id=user["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
        )
        result = cancel(out["id"], user["id"])
        assert result["status"] == "cancelled"
        assert result["cancelled_at"] is not None


def test_other_user_cannot_proceed(app, make_user):
    """Owner-isolation: a foreign user_id sees a LookupError, not the row."""
    owner = _make_user(make_user, email="owner@test.com")
    intruder = _make_user(make_user, email="intruder@test.com")
    with app.app_context():
        out = start_cooldown(
            user_id=owner["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
        )
        # Make cooldown elapsed so the failure is purely owner-mismatch.
        row = db.session.get(PreTradeReflection, out["id"])
        row.cooldown_ends_at = _utc_now() - timedelta(seconds=1)
        db.session.commit()
        with pytest.raises(LookupError):
            proceed(out["id"], intruder["id"])
        with pytest.raises(LookupError):
            check_status(out["id"], intruder["id"])


# ─────────────────────────────────────────────────────────────────────
# Route layer
# ─────────────────────────────────────────────────────────────────────

def test_route_start_returns_disclaimer(client, auth_user):
    resp = client.post("/api/pre-trade/start", json={
        "ticker": "AAPL",
        "side": "BUY",
        "shares": 10,
        "rationale": LONG_RATIONALE,
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert "disclaimer" in body
    assert "권유가 아닙니다" in body["disclaimer"]
    assert body["reflection"]["status"] == "pending"


def test_route_csrf_required(raw_client, make_user):
    """POST without the CSRF header is rejected by init_security."""
    u = make_user(email="csrf@pretrade.test", password="x")
    # Log in via raw client (no CSRF auto-attach).
    login = raw_client.post("/api/auth/login", json={
        "email": u["email"], "password": u["password"]
    })
    assert login.status_code == 200, f"login failed: {login.data!r}"
    resp = raw_client.post("/api/pre-trade/start", json={
        "ticker": "AAPL",
        "side": "BUY",
        "shares": 1,
        "rationale": LONG_RATIONALE,
    })
    # Security middleware returns 403 on missing/mismatched CSRF.
    assert resp.status_code in (400, 401, 403), (
        "Expected CSRF rejection; got %s" % resp.status_code
    )


def test_route_proceed_blocks_other_user(client, app, make_user, auth_user):
    """Even with valid auth, a foreign id resolves to 404 not the row."""
    # auth_user is logged in; create the reflection under a *different* user.
    other = _make_user(make_user, email="other@test.com")
    with app.app_context():
        out = start_cooldown(
            user_id=other["id"],
            ticker="AAPL",
            side="BUY",
            shares=1,
            rationale=LONG_RATIONALE,
        )
    resp = client.post(f"/api/pre-trade/{out['id']}/proceed")
    assert resp.status_code == 404


def test_rationale_min_chars_constant_holds():
    """Pin the rationale floor — any change must come with explicit migration."""
    assert MIN_RATIONALE_CHARS == 50
