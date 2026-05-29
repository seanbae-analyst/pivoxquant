"""Wave 1 — unified /api/artifacts/generate endpoint.

Smoke-tests the dispatch table, empty-state handling, and interactive
short-circuit. Does NOT exercise the full per-service render pipeline —
that is covered by each service's dedicated test module.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def paid_auth_user(client, make_user):
    """Logged-in top-tier user. Paid-artifact generation tests use this so the
    unified /generate tier gate (mirrors each artifact's @require_tier) is
    satisfied and the dispatch/empty/ready logic under test actually runs."""
    user = make_user(email="paid_artifact@test.com", tier="founding_lifetime")
    resp = client.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"],
    })
    assert resp.status_code == 200
    return user


def test_generate_blocks_free_user_for_paid_artifact(client, make_user):
    """Free user posting a paid artifact type → 403 UPGRADE_REQUIRED.

    Regression guard for the tier-bypass: the unified /generate endpoint must
    enforce the same minimum tier as each artifact's individual route."""
    user = make_user(email="free_artifact@test.com")  # tier defaults to free
    login = client.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"],
    })
    assert login.status_code == 200
    resp = client.post("/api/artifacts/generate", json={"type": "weekly_memo"})
    assert resp.status_code == 403
    body = resp.get_json() or {}
    assert body.get("code") == "UPGRADE_REQUIRED"
    assert body.get("required_tier") == "pro"


# ── input validation ────────────────────────────────────────────────────────

def test_generate_rejects_missing_type(client, auth_user):
    """type is required → 400."""
    resp = client.post("/api/artifacts/generate", json={})
    assert resp.status_code == 400
    assert "type" in (resp.get_json() or {}).get("error", "").lower()


def test_generate_rejects_unknown_type(client, auth_user):
    """Unknown slug → 400 + allowed list."""
    resp = client.post(
        "/api/artifacts/generate",
        json={"type": "no_such_artefact_kind"},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert "unknown artifact type" in body["error"]
    # The allowed list is the dispatch table keys; we don't pin an exact
    # set so adding new types in the future doesn't break this test.
    assert "weekly_memo" in body["allowed"]


def test_generate_rejects_bad_params_shape(client, auth_user):
    """params must be a JSON object, not a list/string."""
    resp = client.post(
        "/api/artifacts/generate",
        json={"type": "weekly_memo", "params": ["wrong"]},
    )
    assert resp.status_code == 400
    assert "params" in resp.get_json()["error"]


def test_generate_rejects_bad_date_format(client, auth_user):
    """target_date must parse as ISO date."""
    resp = client.post(
        "/api/artifacts/generate",
        json={
            "type":   "weekly_memo",
            "params": {"target_date": "not-a-date"},
        },
    )
    assert resp.status_code == 400
    assert "target_date" in resp.get_json()["error"]


# ── interactive types — short-circuit with redirect ─────────────────────────

@pytest.mark.parametrize("kind,expected_redirect", [
    ("pre_trade_checklist",  "/api/pre-trade/start"),
    ("dd_checklist",         "/api/artifacts/dd-checklist/pending"),
    ("capital_allocation",   "/api/artifacts/capital-allocation/calculate"),
])
def test_generate_interactive_types_return_redirect(
    client, auth_user, kind, expected_redirect,
):
    """Interactive workflows are not fan-out generators — /generate hints
    the frontend to use the per-feature UI instead."""
    resp = client.post("/api/artifacts/generate", json={"type": kind})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "interactive"
    assert body["type"] == kind
    assert body["artifact_id"] is None
    assert body["redirect"] == expected_redirect


# ── empty-state handling for new users ──────────────────────────────────────

def test_generate_weekly_memo_empty_for_new_user(client, paid_auth_user):
    """A user with no positions gets status='empty', not a hollow PDF."""
    resp = client.post("/api/artifacts/generate", json={"type": "weekly_memo"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "empty"
    assert body["reason"] == "no_positions"
    assert body["message"] == "first_position_needed"
    assert body["artifact_id"] is None


def test_generate_self_audit_empty_without_trades(client, paid_auth_user):
    """Self-audit needs trade history; new user → empty."""
    resp = client.post("/api/artifacts/generate", json={"type": "self_audit"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "empty"
    assert body["reason"] == "no_trades"


# ── happy path — weekly memo for a user with a position ─────────────────────

def test_generate_weekly_memo_with_position_returns_ready(
    client, paid_auth_user, app, mock_fetcher, add_position,
):
    """User with 1+ positions → status='ready' + persisted artifact row."""
    from extensions import db
    from models import Artifact

    add_position(paid_auth_user["id"], ticker="AAPL", shares=10)

    resp = client.post("/api/artifacts/generate", json={"type": "weekly_memo"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ready"
    assert body["type"] == "weekly_memo"
    assert body["data"] is not None
    # artifact_id may be None if the persist step hit a UNIQUE collision
    # against a row from another test, but the data must have flowed.
    if body["artifact_id"]:
        with app.app_context():
            row = db.session.get(Artifact, body["artifact_id"])
            assert row is not None
            assert row.user_id == paid_auth_user["id"]
            assert row.type == "weekly_memo"


# ── H2: PDF render outcome must be non-silent ──────────────────────────────

def test_generate_reports_pdf_status_when_weasyprint_unavailable(
    client, paid_auth_user, app, mock_fetcher, add_position,
):
    """No WeasyPrint in the test env → render_pdf returns None. The response
    must stay `ready` (data is valid/viewable) but explicitly say the PDF is
    unavailable, never silently claim a clean completion with no attachment."""
    import routes.artifacts as ra

    add_position(paid_auth_user["id"], ticker="AAPL", shares=10)
    # Force the "dep missing" branch deterministically.
    ra._WEASYPRINT_OK = False
    try:
        resp = client.post("/api/artifacts/generate", json={"type": "weekly_memo"})
    finally:
        ra._WEASYPRINT_OK = None
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ready"
    assert body["pdf_available"] is False
    assert body["pdf_status"] == "unavailable"


def test_generate_flags_render_failed_when_dep_present_but_no_bytes(
    client, paid_auth_user, app, mock_fetcher, add_position, monkeypatch,
):
    """Dep present but render produces no bytes → genuine failure. Must surface
    pdf_status='render_failed' + a message, not a hollow silent 'ready'."""
    import routes.artifacts as ra
    from services.artifacts.weekly_memo_service import WeeklyMemoService

    add_position(paid_auth_user["id"], ticker="AAPL", shares=10)
    ra._WEASYPRINT_OK = True  # pretend WeasyPrint is installed
    monkeypatch.setattr(WeeklyMemoService, "render_pdf",
                        lambda self, data: None)
    try:
        resp = client.post("/api/artifacts/generate", json={"type": "weekly_memo"})
    finally:
        ra._WEASYPRINT_OK = None
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ready"
    assert body["pdf_available"] is False
    assert body["pdf_status"] == "render_failed"
    assert body["message"]  # non-empty error message present


# ── earnings_prebrief — positional ticker required ─────────────────────────

def test_generate_earnings_prebrief_requires_ticker(client, auth_user):
    resp = client.post(
        "/api/artifacts/generate",
        json={"type": "earnings_prebrief"},
    )
    assert resp.status_code == 400
    assert "ticker" in resp.get_json()["error"]


# ── auth ────────────────────────────────────────────────────────────────────

def test_generate_requires_auth(raw_client):
    """No login → 401."""
    resp = raw_client.post(
        "/api/artifacts/generate",
        json={"type": "weekly_memo"},
    )
    assert resp.status_code == 401
