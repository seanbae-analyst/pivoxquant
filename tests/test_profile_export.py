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
        "behavioral_scores": 0,
        "weekly_pulse": 0,
        "persona_snapshots": 0,
        "nps_feedback": 0,
        "pre_trade_reflections": 0,
    }
    assert body["positions"] == []
    assert body["watchlist"] == []
    assert body["trade_history"] == []
    assert body["alerts"] == []
    assert body["behavioral_scores"] == []
    assert body["weekly_pulse"] == []
    assert body["persona_snapshots"] == []
    assert body["nps_feedback"] == []
    assert body["pre_trade_reflections"] == []
    assert body["investment_profile"] is None
    assert body["user"]["email"] == auth_user["email"]


# ─────────────────────────────────────────────────────────────────────
# Wave 10 P2 — email opt-out flag must round-trip into the export
# ─────────────────────────────────────────────────────────────────────


def test_export_reflects_email_opt_out_state(app, client, auth_user):
    """The export's ``user.email_opt_out`` must mirror the live DB column.

    Why: PIPA §35 열람권 requires the user be able to *see* every
    recorded consent state. Marketing opt-out is one of those — if
    the export lies about it, the user cannot audit their own consents.
    """
    from extensions import db
    from models import User

    # Default: opt-out flags are False — confirm export agrees.
    resp = client.get("/api/profile/export")
    body = json.loads(resp.data)
    assert body["user"]["email_opt_out"] is False
    assert body["user"]["email_opt_out_earnings"] is False

    # Flip both flags directly in DB (mimics a one-click unsubscribe).
    with app.app_context():
        u = db.session.get(User, auth_user["id"])
        u.email_opt_out = True
        u.email_opt_out_earnings = True
        db.session.commit()

    resp = client.get("/api/profile/export")
    body = json.loads(resp.data)
    assert body["user"]["email_opt_out"] is True
    assert body["user"]["email_opt_out_earnings"] is True


# ─────────────────────────────────────────────────────────────────────
# 2026-05-22 — PIPA §35 behavioural/pulse PII sections
# ─────────────────────────────────────────────────────────────────────
#
# Pre-fix the export omitted BehavioralScore / WeeklyPulse /
# PersonaSnapshot / NpsFeedback — all user PII (they're purged on
# deletion, confirming they're personal data; WeeklyPulse holds free-text
# worry/learn). §35 열람권 requires the user be able to see all recorded
# personal data, so these must be in the export.

def test_export_includes_behavioral_pulse_sections_with_data(
    app, client, auth_user,
):
    """Seed one row in each of the four new PII tables and confirm they
    surface in the export with their meaningful (incl. free-text) fields."""
    import json as _json
    from datetime import date, datetime, timezone

    from extensions import db
    from models import (
        BehavioralScore, WeeklyPulse, PersonaSnapshot, NpsFeedback,
    )

    uid = auth_user["id"]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with app.app_context():
        db.session.add(BehavioralScore(
            user_id=uid,
            week_ending=date(2026, 5, 17),
            overall_score=72.5,
            sub_scores=_json.dumps({"loss_cut": 80, "fomo_resistance": 65}),
            notes="held through the dip well this week",
            trade_count=4,
        ))
        db.session.add(WeeklyPulse(
            user_id=uid,
            mood=4,
            confidence=3,
            worry="worried about a tech selloff next week",
            topics=_json.dumps(["tech", "rates"]),
            learn="learned to size positions smaller",
            cadence="weekly",
            submitted_at=now,
        ))
        db.session.add(PersonaSnapshot(
            user_id=uid,
            computed_at=now,
            persona="growth",
            confidence=80,
            features=_json.dumps({"turnover": 0.3}),
            present_mask=_json.dumps({"turnover": True}),
            ranking=_json.dumps(["growth", "value"]),
        ))
        db.session.add(NpsFeedback(
            user_id=uid, score=9, weekly_memo_id="memo-2026-05-17",
        ))
        db.session.commit()

    resp = client.get("/api/profile/export")
    assert resp.status_code == 200, resp.data
    body = json.loads(resp.data)

    # Sections present and populated.
    assert body["counts"]["behavioral_scores"] == 1
    assert body["counts"]["weekly_pulse"] == 1
    assert body["counts"]["persona_snapshots"] == 1
    assert body["counts"]["nps_feedback"] == 1

    assert len(body["behavioral_scores"]) == 1
    assert body["behavioral_scores"][0]["overall_score"] == 72.5
    assert body["behavioral_scores"][0]["notes"] == "held through the dip well this week"

    # Free-text PII must round-trip (the whole point of §35 access).
    assert len(body["weekly_pulse"]) == 1
    assert body["weekly_pulse"][0]["worry"] == "worried about a tech selloff next week"
    assert body["weekly_pulse"][0]["learn"] == "learned to size positions smaller"

    assert len(body["persona_snapshots"]) == 1
    assert body["persona_snapshots"][0]["persona"] == "growth"

    assert len(body["nps_feedback"]) == 1
    assert body["nps_feedback"][0]["score"] == 9


def test_export_behavioral_sections_scoped_to_caller(
    app, client, make_user, auth_user,
):
    """The new sections must never leak another user's behavioural PII."""
    from datetime import datetime, timezone

    from extensions import db
    from models import WeeklyPulse

    other = make_user(email="otherpulse@test.com", password="otherpw123")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with app.app_context():
        db.session.add(WeeklyPulse(
            user_id=other["id"], mood=2, confidence=2,
            worry="OTHER-USER-SECRET-WORRY", topics="[]", learn="",
            cadence="weekly", submitted_at=now,
        ))
        db.session.commit()

    resp = client.get("/api/profile/export")
    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body["counts"]["weekly_pulse"] == 0
    raw = json.dumps(body)
    assert "OTHER-USER-SECRET-WORRY" not in raw, (
        "another user's WeeklyPulse free-text leaked into export"
    )


def test_export_includes_pre_trade_reflections_scoped_to_caller(
    app, client, make_user, auth_user,
):
    """PIPA §35 — PreTradeReflection (free-text rationale + devil's-advocate
    flag = PII purged on deletion) must be in the export, and only the
    caller's own rows."""
    from datetime import datetime, timedelta, timezone

    from extensions import db
    from models import PreTradeReflection

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with app.app_context():
        # Caller's own reflection — must appear.
        db.session.add(PreTradeReflection(
            user_id=auth_user["id"],
            intended_ticker="AAPL",
            intended_side="BUY",
            rationale="MY-OWN-RATIONALE",
            devil_advocate_seen="saw the counter-argument",
            cooldown_started_at=now,
            cooldown_ends_at=now + timedelta(minutes=2),
        ))
        # Another user's reflection — must NOT leak.
        other = make_user(email="otherrefl@test.com", password="otherpw123")
        db.session.add(PreTradeReflection(
            user_id=other["id"],
            intended_ticker="TSLA",
            intended_side="SELL",
            rationale="OTHER-USER-SECRET-RATIONALE",
            cooldown_started_at=now,
            cooldown_ends_at=now + timedelta(minutes=2),
        ))
        db.session.commit()

    resp = client.get("/api/profile/export")
    assert resp.status_code == 200
    body = json.loads(resp.data)

    assert body["counts"]["pre_trade_reflections"] == 1
    reflections = body["pre_trade_reflections"]
    assert len(reflections) == 1
    assert reflections[0]["rationale"] == "MY-OWN-RATIONALE"
    assert reflections[0]["devil_advocate_seen"] == "saw the counter-argument"

    raw = json.dumps(body)
    assert "OTHER-USER-SECRET-RATIONALE" not in raw, (
        "another user's PreTradeReflection free-text leaked into export"
    )


def test_export_excludes_password_and_payment_secrets_strictly(
    app, client, auth_user,
):
    """Belt-and-braces — even when a user has an oauth_provider set, the
    export must not leak any of the documented sensitive fields.

    Complements the existing 'forbidden set' check by exercising a row
    that actually has values for the secret columns rather than relying
    on them being None on a freshly-built test user.
    """
    from extensions import db
    from models import User

    with app.app_context():
        u = db.session.get(User, auth_user["id"])
        # Populate every documented-excluded field to make sure the
        # serializer does not pick them up via __dict__ iteration.
        u.stripe_customer_id = "cus_TEST_DO_NOT_LEAK"
        u.oauth_provider = "google"
        u.oauth_id = "google_TEST_DO_NOT_LEAK"
        db.session.commit()

    resp = client.get("/api/profile/export")
    assert resp.status_code == 200
    body = json.loads(resp.data)
    raw = resp.get_data(as_text=True)
    # No sensitive *values* appear anywhere in the body — not in the
    # user block, not in metadata, not as JSON keys.
    assert "cus_TEST_DO_NOT_LEAK" not in raw
    assert "google_TEST_DO_NOT_LEAK" not in raw
    # The user block must not contain ANY of the secret keys. Note: the
    # ``notes.excluded_fields`` array deliberately *names* these fields
    # in plain text — that's a metadata documentation array, not a leak.
    user_keys = set(body["user"].keys())
    forbidden = {
        "password_hash", "stripe_customer_id", "oauth_id",
        "oauth_refresh_token", "refresh_token",
    }
    leaked = forbidden & user_keys
    assert not leaked, f"Secret keys leaked into user block: {leaked}"
