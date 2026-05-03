"""tests/test_profile_export.py — PIPA §35 정보주체 열람권 export endpoint.

Covers GET /api/profile/export, the self-service personal-data download
that satisfies 개인정보보호법 §35 ① (열람권) + §35 ④ (10일 이내).

Hard requirements:
  - Unauthenticated callers → 401 (no leakage).
  - Authenticated callers → 200 + JSON body + Content-Disposition: attachment.
  - Body contains ONLY the caller's own data — never another user's row.
  - Sensitive fields (password_hash, stripe_customer_id) are absent.
  - Counts match what was actually persisted.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─────────────────────────────────────────────────────────────────────
# Auth gate
# ─────────────────────────────────────────────────────────────────────

def test_export_requires_auth(client):
    """Unauthenticated request must be rejected — never leak a default user."""
    resp = client.get("/api/profile/export")
    assert resp.status_code == 401, (
        f"Unauthenticated /api/profile/export must 401, got {resp.status_code}"
    )


# ─────────────────────────────────────────────────────────────────────
# Happy path — authenticated user gets their own data
# ─────────────────────────────────────────────────────────────────────

def test_export_returns_own_data_with_attachment_header(
    client, app, auth_user, add_position,
):
    """Authenticated request returns 200 + JSON download + own positions."""
    add_position(auth_user["id"], ticker="AAPL", shares=10.0, avg_cost=150.0)
    add_position(auth_user["id"], ticker="MSFT", shares=5.0, avg_cost=300.0)

    resp = client.get("/api/profile/export")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.data!r}"

    # Content-Disposition: attachment + filename includes user id.
    cd = resp.headers.get("Content-Disposition", "")
    assert "attachment" in cd.lower(), f"Missing attachment disposition: {cd!r}"
    assert f"_{auth_user['id']}_" in cd, f"Filename missing user id: {cd!r}"
    assert cd.endswith('.json"'), f"Filename should end with .json: {cd!r}"

    # Cache-Control prevents intermediates from storing PII.
    cache_ctrl = resp.headers.get("Cache-Control", "")
    assert "no-store" in cache_ctrl, f"Cache-Control missing no-store: {cache_ctrl!r}"

    body = json.loads(resp.data)

    # Top-level shape.
    assert body["format_version"] == "1.0"
    assert body["scope"] == "self_only"
    assert "exported_at" in body
    assert "legal_basis" in body and "§35" in body["legal_basis"]

    # User block has identity but NOT secrets.
    user_block = body["user"]
    assert user_block["id"] == auth_user["id"]
    assert user_block["email"] == auth_user["email"]
    forbidden = {"password_hash", "stripe_customer_id", "oauth_id",
                 "oauth_refresh_token", "refresh_token"}
    leaked = forbidden & set(user_block.keys())
    assert not leaked, f"Sensitive fields leaked into user block: {leaked}"

    # Positions present and match.
    assert body["counts"]["positions"] == 2
    tickers = {p["ticker"] for p in body["positions"]}
    assert tickers == {"AAPL", "MSFT"}

    # Other collections exist but empty.
    assert body["counts"]["watchlist"] == 0
    assert body["counts"]["trade_history"] == 0
    assert body["counts"]["alerts"] == 0


# ─────────────────────────────────────────────────────────────────────
# Isolation — never leak another user's data
# ─────────────────────────────────────────────────────────────────────

def test_export_does_not_include_other_users_data(
    client, app, make_user, auth_user, add_position,
):
    """Critical: /export must scope STRICTLY to the calling user.

    Insert positions for both the logged-in user AND a different user.
    Confirm the response carries ONLY the logged-in user's positions.
    """
    # Logged-in user has AAPL.
    add_position(auth_user["id"], ticker="AAPL", shares=10.0, avg_cost=150.0)

    # Other user (NOT logged in here) has secret position TSLA.
    other = make_user(email="other@test.com", password="otherpw123")
    add_position(other["id"], ticker="TSLA", shares=99.0, avg_cost=999.0)

    # Also seed a watchlist + trade for the other user (must not leak).
    from extensions import db
    from models import Watchlist, TradeHistory, Alert
    with app.app_context():
        db.session.add(Watchlist(
            user_id=other["id"], ticker="NVDA", note="other-secret",
        ))
        db.session.add(TradeHistory(
            user_id=other["id"], ticker="TSLA", action="BUY",
            shares=10.0, price_per_share=999.0, total_value=9990.0,
        ))
        db.session.add(Alert(
            user_id=other["id"], ticker="TSLA", kind="other_only",
            title="other-secret-alert", body="should not appear",
            message="other-secret-alert",
        ))
        db.session.commit()

    resp = client.get("/api/profile/export")
    assert resp.status_code == 200

    body = json.loads(resp.data)

    # User block belongs to the caller only.
    assert body["user"]["id"] == auth_user["id"]
    assert body["user"]["email"] == auth_user["email"]

    # Counts reflect only the caller's rows.
    assert body["counts"]["positions"] == 1
    assert body["counts"]["watchlist"] == 0
    assert body["counts"]["trade_history"] == 0
    assert body["counts"]["alerts"] == 0

    # No secret-marker strings from the other user appear anywhere in body.
    raw = json.dumps(body)
    assert "TSLA" not in raw, "Other user's ticker leaked into export"
    assert "NVDA" not in raw, "Other user's watchlist leaked into export"
    assert "other-secret" not in raw, "Other user's note leaked"
    assert "other-secret-alert" not in raw, "Other user's alert leaked"


# ─────────────────────────────────────────────────────────────────────
# Empty user (newly registered) — must still return a valid payload
# ─────────────────────────────────────────────────────────────────────

def test_export_empty_user_returns_valid_payload(client, auth_user):
    """Brand-new user with zero records still gets a valid export."""
    resp = client.get("/api/profile/export")
    assert resp.status_code == 200

    body = json.loads(resp.data)
    assert body["counts"] == {
        "positions": 0,
        "watchlist": 0,
        "trade_history": 0,
        "alerts": 0,
    }
    assert body["positions"] == []
    assert body["watchlist"] == []
    assert body["trade_history"] == []
    assert body["alerts"] == []
    assert body["investment_profile"] is None
    assert body["user"]["email"] == auth_user["email"]
