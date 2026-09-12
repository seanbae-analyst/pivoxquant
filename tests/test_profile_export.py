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
from unittest.mock import patch


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
    # Every count is zero for a brand-new user (exact set, not subset — so a
    # newly-added section that fails to default-empty is caught here too).
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
        "artifacts": 0,
        "artifact_feedback": 0,
        "broker_connections": 0,
        "user_referrals": 0,
        "position_dd_checks": 0,
        "inquiries": 0,
        "companion_waitlist": 0,
        "portfolio_shares": 0,
        "push_subscriptions": 0,
        "scheduled_emails": 0,
        "checkout_expirations": 0,
        "portfolio_nav_snapshots": 0,
        "user_agent_audit": 0,
        "ai_twin_portfolios": 0,
        "ai_twin_positions": 0,
        "ai_twin_trades": 0,
        "ai_twin_weekly_reports": 0,
        "auth_events": 0,
        "funnel_events": 0,
    }
    # Each list-valued section is an empty list (never null / missing).
    for section in body["counts"]:
        assert body[section] == [], f"{section} should be [] for empty user"
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


# ─────────────────────────────────────────────────────────────────────
# 2026-05-30 — PIPA §35 §2: remaining user-owned tables (15 + 2 P1)
# ─────────────────────────────────────────────────────────────────────
#
# The export covered only 11 of 26 user-owned tables. These tests assert
# the newly-added sections (a) exist in the payload, (b) carry the caller's
# own data, and (c) never expose credential / token / endpoint secrets.

# The full registry of list-valued export sections, kept here as the test's
# source of truth so a section dropped from the route's `counts` is caught.
_EXPECTED_SECTIONS = {
    "portfolio_nav_snapshots", "user_agent_audit",
    "positions", "watchlist", "trade_history", "alerts",
    "behavioral_scores", "weekly_pulse", "persona_snapshots", "nps_feedback",
    "pre_trade_reflections", "artifacts", "artifact_feedback",
    "broker_connections", "user_referrals", "position_dd_checks", "inquiries",
    "companion_waitlist", "portfolio_shares", "push_subscriptions",
    "scheduled_emails", "checkout_expirations", "ai_twin_portfolios",
    "ai_twin_positions", "ai_twin_trades", "ai_twin_weekly_reports",
    "auth_events", "funnel_events",
}


def test_export_covers_all_expected_sections(client, auth_user):
    """Every expected user-owned section is present as a key + in counts.

    Coverage gate: 26 sections (was 11/26 before this change). If a new
    user-owned model is added without wiring it into the export, update
    this set (and the route + both delete paths) — the failure is the cue.
    """
    resp = client.get("/api/profile/export")
    assert resp.status_code == 200
    body = json.loads(resp.data)

    missing_keys = _EXPECTED_SECTIONS - set(body.keys())
    assert not missing_keys, f"Export missing section keys: {missing_keys}"

    missing_counts = _EXPECTED_SECTIONS - set(body["counts"].keys())
    assert not missing_counts, f"counts missing sections: {missing_counts}"


def test_export_includes_new_user_owned_sections_with_data(
    app, client, auth_user,
):
    """Seed one row in each newly-added table and confirm it surfaces."""
    from datetime import date, datetime, timedelta, timezone

    from extensions import db
    from models import (
        Artifact, ArtifactFeedback, BrokerConnection, UserReferral,
        PositionDDCheck, Inquiry, CompanionWaitlist, PortfolioShare,
        PushSubscription, ScheduledEmail, CheckoutExpiration,
        AITwinPortfolio, AITwinPosition, AITwinTrade, AITwinWeeklyReport,
        Position,
    )

    uid = auth_user["id"]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with app.app_context():
        pos = Position(user_id=uid, ticker="AAPL", shares=1.0, avg_cost=100.0)
        db.session.add(pos)
        db.session.flush()

        db.session.add(Artifact(
            user_id=uid, type="weekly_memo", title="My Weekly Memo",
            data_json={"summary": "MY-ARTIFACT-DATA"},
        ))
        db.session.add(ArtifactFeedback(
            user_id=uid, artifact_id="memo-1", section="summary", vote="up",
        ))
        db.session.add(UserReferral(
            user_id=uid, referral_code="MYCODE01",
        ))
        db.session.add(PositionDDCheck(
            user_id=uid, position_id=pos.id, financials_checked=True,
            note="MY-DD-NOTE",
        ))
        db.session.add(Inquiry(
            user_id=uid, category="other", subject="MY-INQUIRY-SUBJECT",
            body="MY-INQUIRY-BODY",
        ))
        db.session.add(CompanionWaitlist(
            email_hash=CompanionWaitlist.hash_email(auth_user["email"]),
            email_plaintext=auth_user["email"], email_consent_at=now,
            user_id=uid, source="pricing-page",
        ))
        db.session.add(PortfolioShare(
            user_id=uid, token="share-secret-token",
            expires_at=now + timedelta(days=7),
        ))
        db.session.add(PushSubscription(
            user_id=uid, endpoint="https://push.example/SECRET-ENDPOINT",
            p256dh="SECRET-P256DH", auth="SECRET-PUSH-AUTH",
        ))
        db.session.add(ScheduledEmail.enqueue(
            user_id=uid, email_type="welcome",
            email_category="transactional", scheduled_send_at=now,
        ))
        db.session.add(CheckoutExpiration(
            user_id=uid, session_id="cs_test_SECRET_SESSION",
            expired_at=now, scheduled_send_at=now + timedelta(hours=1),
        ))

        # BrokerConnection with populated secret columns.
        db.session.add(BrokerConnection(
            user_id=uid, broker="kis", display_name="My KIS",
            encrypted_app_key="ENC-APP-KEY-SECRET",
            encrypted_app_secret="ENC-APP-SECRET-SECRET",
            encrypted_access_token="ENC-ACCESS-TOKEN-SECRET",
            access_token="LEGACY-ACCESS-TOKEN-SECRET",
            refresh_token="LEGACY-REFRESH-TOKEN-SECRET",
        ))

        # AI Twin chain (portfolio → positions/trades via twin_id).
        twin = AITwinPortfolio(user_id=uid, persona_at_init="growth")
        db.session.add(twin)
        db.session.flush()
        db.session.add(AITwinPosition(
            twin_id=twin.id, ticker="MSFT", shares=2.0, avg_cost=300.0,
        ))
        db.session.add(AITwinTrade(
            twin_id=twin.id, ticker="MSFT", side="BUY", shares=2.0,
            price=300.0, rationale="MY-TWIN-RATIONALE",
        ))
        db.session.add(AITwinWeeklyReport(
            user_id=uid, week_ending=date(2026, 5, 24),
        ))
        db.session.commit()

    resp = client.get("/api/profile/export")
    assert resp.status_code == 200, resp.data
    body = json.loads(resp.data)
    c = body["counts"]

    assert c["artifacts"] == 1
    assert c["artifact_feedback"] == 1
    assert c["broker_connections"] == 1
    assert c["user_referrals"] == 1
    assert c["position_dd_checks"] == 1
    assert c["inquiries"] == 1
    assert c["companion_waitlist"] == 1
    assert c["portfolio_shares"] == 1
    assert c["push_subscriptions"] == 1
    assert c["scheduled_emails"] == 1
    assert c["checkout_expirations"] == 1
    assert c["ai_twin_portfolios"] == 1
    assert c["ai_twin_positions"] == 1
    assert c["ai_twin_trades"] == 1
    assert c["ai_twin_weekly_reports"] == 1

    # The user's own free-text PII round-trips (the point of §35 access).
    assert body["artifacts"][0]["data"]["summary"] == "MY-ARTIFACT-DATA"
    assert body["inquiries"][0]["subject"] == "MY-INQUIRY-SUBJECT"
    assert body["inquiries"][0]["body"] == "MY-INQUIRY-BODY"
    assert body["position_dd_checks"][0]["note"] == "MY-DD-NOTE"
    assert body["ai_twin_trades"][0]["rationale"] == "MY-TWIN-RATIONALE"
    assert body["user_referrals"][0]["referral_code"] == "MYCODE01"


def test_export_never_leaks_credential_or_push_secrets(app, client, auth_user):
    """PIPA §35 §2 — the user may read their data but NOT self-exfiltrate
    their own credentials / tokens / push keys / Stripe session ids.

    Every secret column value seeded below must be absent from the raw
    response body (not as a value, not as a key)."""
    from datetime import datetime, timedelta, timezone

    from extensions import db
    from models import (
        BrokerConnection, PushSubscription, PortfolioShare, CheckoutExpiration,
    )

    uid = auth_user["id"]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    secrets_seeded = [
        "ENC-APP-KEY-SECRET", "ENC-APP-SECRET-SECRET",
        "ENC-ACCESS-TOKEN-SECRET", "LEGACY-ACCESS-TOKEN-SECRET",
        "LEGACY-REFRESH-TOKEN-SECRET", "https://push.example/SECRET-ENDPOINT",
        "SECRET-P256DH", "SECRET-PUSH-AUTH", "share-secret-token",
        "cs_test_SECRET_SESSION",
    ]
    with app.app_context():
        db.session.add(BrokerConnection(
            user_id=uid, broker="kis",
            encrypted_app_key="ENC-APP-KEY-SECRET",
            encrypted_app_secret="ENC-APP-SECRET-SECRET",
            encrypted_access_token="ENC-ACCESS-TOKEN-SECRET",
            access_token="LEGACY-ACCESS-TOKEN-SECRET",
            refresh_token="LEGACY-REFRESH-TOKEN-SECRET",
        ))
        db.session.add(PushSubscription(
            user_id=uid, endpoint="https://push.example/SECRET-ENDPOINT",
            p256dh="SECRET-P256DH", auth="SECRET-PUSH-AUTH",
        ))
        db.session.add(PortfolioShare(
            user_id=uid, token="share-secret-token",
            expires_at=now + timedelta(days=7),
        ))
        db.session.add(CheckoutExpiration(
            user_id=uid, session_id="cs_test_SECRET_SESSION",
            expired_at=now, scheduled_send_at=now + timedelta(hours=1),
        ))
        db.session.commit()

    resp = client.get("/api/profile/export")
    assert resp.status_code == 200
    raw = resp.get_data(as_text=True)

    for secret in secrets_seeded:
        assert secret not in raw, f"Secret leaked into export: {secret!r}"

    # The rows themselves DID export (existence flags), just not the secrets.
    body = json.loads(resp.data)
    assert body["counts"]["broker_connections"] == 1
    assert body["broker_connections"][0]["has_credentials"] is True
    assert body["counts"]["push_subscriptions"] == 1
    assert body["push_subscriptions"][0]["has_endpoint"] is True
    assert body["counts"]["portfolio_shares"] == 1
    assert body["portfolio_shares"][0]["has_token"] is True
    assert body["counts"]["checkout_expirations"] == 1


def test_export_ai_twin_chain_scoped_to_caller(
    app, client, make_user, auth_user,
):
    """AI-twin positions/trades are reached via twin_id (parent FK). Confirm
    another user's twin rows never leak through the .in_() filter."""
    from extensions import db
    from models import AITwinPortfolio, AITwinTrade

    other = make_user(email="othertwin@test.com", password="otherpw123")
    with app.app_context():
        other_twin = AITwinPortfolio(
            user_id=other["id"], persona_at_init="value",
        )
        db.session.add(other_twin)
        db.session.flush()
        db.session.add(AITwinTrade(
            twin_id=other_twin.id, ticker="TSLA", side="SELL", shares=1.0,
            price=999.0, rationale="OTHER-TWIN-SECRET-RATIONALE",
        ))
        db.session.commit()

    resp = client.get("/api/profile/export")
    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body["counts"]["ai_twin_portfolios"] == 0
    assert body["counts"]["ai_twin_trades"] == 0
    raw = json.dumps(body)
    assert "OTHER-TWIN-SECRET-RATIONALE" not in raw
    assert "TSLA" not in raw


def test_export_auth_events_scoped_by_email(app, client, make_user, auth_user):
    """auth_events keys on email (no user_id FK). Export must filter to the
    caller's own email and never surface another principal's login log."""
    from datetime import datetime, timezone

    from extensions import db
    from models import AuthEvent

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with app.app_context():
        db.session.add(AuthEvent(
            email=auth_user["email"], provider="google",
            event_type="success", created_at=now,
        ))
        db.session.add(AuthEvent(
            email="otherauth@test.com", provider="kakao",
            event_type="fail", fail_reason="OTHER-AUTH-SECRET", created_at=now,
        ))
        db.session.commit()

    resp = client.get("/api/profile/export")
    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body["counts"]["auth_events"] == 1
    assert body["auth_events"][0]["email"] == auth_user["email"]
    raw = json.dumps(body)
    assert "OTHER-AUTH-SECRET" not in raw
    assert "otherauth@test.com" not in raw


# ─────────────────────────────────────────────────────────────────────
# 2026-05-31 — CSV export (tabular raw-fact slice)
# ─────────────────────────────────────────────────────────────────────
#
# GET /api/profile/export?format=csv&dataset=trades|positions|watchlist
# returns a spreadsheet-friendly CSV of RAW stored fields only — no live
# price, no computed metric, no FX conversion, no advice. Same self-only
# scope and auth gate as the JSON export.

import csv as _csv
import io as _io


def _parse_csv(resp):
    """Decode a CSV download Response into (header, rows), stripping the
    UTF-8 BOM that Excel needs for Hangul. Asserts the CSV content-type."""
    ctype = resp.headers.get("Content-Type", "")
    assert "text/csv" in ctype, f"Expected text/csv, got {ctype!r}"
    text = resp.data.decode("utf-8-sig")  # utf-8-sig strips the BOM
    reader = list(_csv.reader(_io.StringIO(text)))
    assert reader, "CSV had no rows at all (not even a header)"
    return reader[0], reader[1:]


def test_csv_export_requires_auth(client):
    """Unauthenticated CSV request must 401 — never leak a default user."""
    resp = client.get("/api/profile/export?format=csv&dataset=trades")
    assert resp.status_code == 401, (
        f"Unauthenticated CSV export must 401, got {resp.status_code}"
    )


def test_csv_export_bad_dataset_rejected(client, auth_user):
    """An unknown / missing dataset is a 400, not a silent empty file."""
    resp = client.get("/api/profile/export?format=csv&dataset=bogus")
    assert resp.status_code == 400, (
        f"Bad dataset must 400, got {resp.status_code}: {resp.data!r}"
    )
    resp2 = client.get("/api/profile/export?format=csv")
    assert resp2.status_code == 400, "Missing dataset must 400"


def test_csv_export_trades_headers_rows_and_attachment(
    app, client, auth_user,
):
    """trades CSV: correct headers, attachment filename, one data row per
    stored trade, with the stored ``name`` surfaced (ticker preserved)."""
    from extensions import db
    from models import TradeHistory
    uid = auth_user["id"]
    with app.app_context():
        db.session.add(TradeHistory(
            user_id=uid, ticker="AAPL", name="Apple", action="BUY",
            shares=10.0, price_per_share=150.0, total_value=1500.0,
            currency="USD", pnl=0.0,
        ))
        db.session.commit()

    resp = client.get("/api/profile/export?format=csv&dataset=trades")
    assert resp.status_code == 200, resp.data

    # Attachment + correct filename.
    cd = resp.headers.get("Content-Disposition", "")
    assert "attachment" in cd.lower(), cd
    assert "pivoxquant-trades-" in cd, cd
    assert cd.endswith('.csv"'), cd
    # PII must not be cached by intermediaries.
    assert "no-store" in resp.headers.get("Cache-Control", "")

    header, rows = _parse_csv(resp)
    assert header == [
        "traded_at", "ticker", "name", "action", "shares",
        "price_per_share", "total_value", "currency", "pnl",
    ]
    assert len(rows) == 1
    row = dict(zip(header, rows[0]))
    assert row["ticker"] == "AAPL"
    assert row["name"] == "Apple"
    assert row["action"] == "BUY"
    assert row["shares"] == "10.0"
    assert row["price_per_share"] == "150.0"
    assert row["currency"] == "USD"


def test_csv_export_positions_and_watchlist(app, client, auth_user, add_position):
    """positions + watchlist CSVs render their raw columns."""
    from extensions import db
    from models import Watchlist
    uid = auth_user["id"]
    add_position(uid, ticker="MSFT", shares=5.0, avg_cost=300.0)
    with app.app_context():
        db.session.add(Watchlist(user_id=uid, ticker="NVDA", note="watching"))
        db.session.commit()

    # Positions
    resp = client.get("/api/profile/export?format=csv&dataset=positions")
    assert resp.status_code == 200
    header, rows = _parse_csv(resp)
    assert header == ["ticker", "name", "shares", "avg_cost", "currency", "added_at"]
    assert len(rows) == 1
    prow = dict(zip(header, rows[0]))
    assert prow["ticker"] == "MSFT"
    assert prow["shares"] == "5.0"
    assert prow["avg_cost"] == "300.0"
    assert prow["currency"] == "USD"

    # Watchlist
    resp2 = client.get("/api/profile/export?format=csv&dataset=watchlist")
    assert resp2.status_code == 200
    header2, rows2 = _parse_csv(resp2)
    assert header2 == ["ticker", "name", "note", "added_at"]
    assert len(rows2) == 1
    wrow = dict(zip(header2, rows2[0]))
    assert wrow["ticker"] == "NVDA"
    assert wrow["note"] == "watching"


def test_csv_export_empty_emits_header_only(client, auth_user):
    """A user with no rows still gets a valid CSV — header, zero data rows.
    Honest: an empty CSV, never fabricated data."""
    # Datasets without a leading disclaimer row → _parse_csv reads header at row0.
    for dataset, expected_cols in (
        ("trades", 9), ("positions", 6), ("watchlist", 4),
        ("journal", 8), ("pulse", 6),
    ):
        resp = client.get(f"/api/profile/export?format=csv&dataset={dataset}")
        assert resp.status_code == 200, (dataset, resp.data)
        header, rows = _parse_csv(resp)
        assert len(header) == expected_cols, (dataset, header)
        assert rows == [], f"{dataset} should have zero data rows for empty user"

    # Capital-gains datasets carry a leading disclaimer comment row, then the
    # header, then zero data rows for an empty user (honest empty file).
    for dataset, expected_cols in (
        ("capital_gains", 15), ("capital_gains_summary", 8),
    ):
        resp = client.get(f"/api/profile/export?format=csv&dataset={dataset}")
        assert resp.status_code == 200, (dataset, resp.data)
        text = resp.data.decode("utf-8-sig")
        rows = list(_csv.reader(_io.StringIO(text)))
        assert rows[0][0].startswith("# "), (dataset, rows[0])
        assert len(rows[1]) == expected_cols, (dataset, rows[1])
        assert rows[2:] == [], f"{dataset} should have zero data rows for empty user"


def _seed_us_round_trip(app, uid, *, buy_px=100.0, sell_px=200.0,
                        buy_dt, sell_dt, ticker="AAPL", shares=10.0):
    """Insert a BUY+SELL pair so FIFO produces one closed lot."""
    from extensions import db
    from models import TradeHistory
    with app.app_context():
        db.session.add(TradeHistory(
            user_id=uid, ticker=ticker, name=ticker, action="BUY",
            shares=shares, price_per_share=buy_px,
            total_value=buy_px * shares, currency="USD", traded_at=buy_dt,
        ))
        db.session.add(TradeHistory(
            user_id=uid, ticker=ticker, name=ticker, action="SELL",
            shares=shares, price_per_share=sell_px,
            total_value=sell_px * shares, currency="USD", traded_at=sell_dt,
        ))
        db.session.commit()


def test_csv_export_capital_gains_lot_detail_with_fx_and_disclaimer(
    app, client, auth_user,
):
    """capital_gains CSV: disclaimer comment row, per-lot KRW from trade-date
    FX (mocked deterministically), correct attribution year, no fabricated FX."""
    from datetime import datetime
    uid = auth_user["id"]
    _seed_us_round_trip(
        app, uid, buy_px=100.0, sell_px=150.0,
        buy_dt=datetime(2024, 1, 2), sell_dt=datetime(2024, 6, 3),
    )

    # Inject deterministic strict FX (no live FMP). Buy FX 1000, sell FX 1200.
    def _strict(d):
        return {"2024-01-02": 1000.0, "2024-06-03": 1200.0}.get(
            d.isoformat()[:10]
        )

    with patch("services.fx_service.get_rate_at_strict", side_effect=_strict):
        resp = client.get("/api/profile/export?format=csv&dataset=capital_gains")
    assert resp.status_code == 200, resp.data

    cd = resp.headers.get("Content-Disposition", "")
    assert "pivoxquant-capital_gains-" in cd, cd
    text = resp.data.decode("utf-8-sig")
    # legal-confirmed disclaimer (§5-B) markers: 참고용 추정 framing + the
    # §20③-protective "세무대리·세무자문 아님" + KR 비과세 carve-out.
    assert "참고용" in text and "추정" in text
    assert "세무자문" in text  # NOT tax advisory — 세무사법 §20③ protection
    assert "비과세" in text  # KR carve-out language in disclaimer

    rows = list(_csv.reader(_io.StringIO(text)))
    # row0 = disclaimer (single cell, leading "# "), row1 = header, row2 = data
    assert rows[0][0].startswith("# "), rows[0]
    header = rows[1]
    assert header[0] == "귀속연도"
    data = dict(zip(header, rows[2]))
    assert data["귀속연도"] == "2024"
    assert data["종목코드"] == "AAPL"
    assert data["과세대상"] == "과세"
    # cost = 100*10*1000 = 1,000,000 ; proceeds = 150*10*1200 = 1,800,000
    assert data["취득가KRW"] == "1000000"
    assert data["양도가KRW"] == "1800000"
    assert data["실현손익KRW"] == "800000"


def test_csv_export_capital_gains_fx_miss_blanks_krw_never_fabricated(
    app, client, auth_user,
):
    """When strict FX returns None (weekend / data gap), KRW columns are blank
    and a note is set — NEVER a fabricated rate or 0."""
    from datetime import datetime
    uid = auth_user["id"]
    _seed_us_round_trip(
        app, uid, buy_dt=datetime(2024, 1, 2), sell_dt=datetime(2024, 6, 3),
    )

    with patch("services.fx_service.get_rate_at_strict", return_value=None):
        resp = client.get("/api/profile/export?format=csv&dataset=capital_gains")
    assert resp.status_code == 200
    text = resp.data.decode("utf-8-sig")
    rows = list(_csv.reader(_io.StringIO(text)))
    header = rows[1]
    data = dict(zip(header, rows[2]))
    assert data["취득가KRW"] == "", "FX miss must leave KRW blank"
    assert data["양도가KRW"] == ""
    assert data["실현손익KRW"] == ""
    assert "환율" in data["note"]
    # No fabricated zero rate anywhere in the KRW/FX columns.
    assert data["취득일환율"] == ""
    assert data["양도일환율"] == ""


def test_csv_export_capital_gains_kr_stock_non_taxable(app, client, auth_user):
    """A KR round trip appears as 비과세 with blank KRW (never dropped)."""
    from datetime import datetime
    uid = auth_user["id"]
    _seed_us_round_trip(
        app, uid, ticker="005930.KS", buy_px=70000.0, sell_px=80000.0,
        buy_dt=datetime(2024, 1, 2), sell_dt=datetime(2024, 3, 4),
    )
    with patch("services.fx_service.get_rate_at_strict", return_value=1300.0):
        resp = client.get("/api/profile/export?format=csv&dataset=capital_gains")
    assert resp.status_code == 200
    text = resp.data.decode("utf-8-sig")
    rows = list(_csv.reader(_io.StringIO(text)))
    data = dict(zip(rows[1], rows[2]))
    assert data["과세대상"] == "비과세"
    assert "비과세" in data["note"]
    assert data["실현손익KRW"] == ""


def test_csv_export_capital_gains_summary_deduction_and_rate(
    app, client, auth_user,
):
    """capital_gains_summary: 손익통산, 250만 공제, 22% 세액 on a single year."""
    from datetime import datetime
    uid = auth_user["id"]
    # proceeds 150*10*1000=1,500,000 ; cost 100*10*1000=1,000,000 → +500,000.
    # Below the 2,500,000 deduction → base 0, tax 0.
    _seed_us_round_trip(
        app, uid, buy_px=100.0, sell_px=150.0,
        buy_dt=datetime(2024, 1, 2), sell_dt=datetime(2024, 6, 3),
    )
    with patch("services.fx_service.get_rate_at_strict", return_value=1000.0):
        resp = client.get(
            "/api/profile/export?format=csv&dataset=capital_gains_summary"
        )
    assert resp.status_code == 200
    text = resp.data.decode("utf-8-sig")
    assert "참고용" in text and "추정" in text  # disclaimer also on the summary
    assert "세무자문" in text  # §20③-protective framing present on summary too
    rows = list(_csv.reader(_io.StringIO(text)))
    header = rows[1]
    assert header == [
        "귀속연도", "거래수", "환율결손제외수", "취득가결손제외수",
        "합산실현손익KRW", "기본공제KRW", "과세표준KRW", "예상세액KRW(22%)",
    ]
    data = dict(zip(header, rows[2]))
    assert data["귀속연도"] == "2024"
    assert data["합산실현손익KRW"] == "500000"
    assert data["기본공제KRW"] == "2500000"
    assert data["과세표준KRW"] == "0"
    assert data["예상세액KRW(22%)"] == "0"


def test_csv_export_journal_and_pulse_self_record(app, client, auth_user):
    """journal (PreTradeReflection) + pulse (WeeklyPulse) render the user's
    own free-text records."""
    from datetime import datetime
    from extensions import db
    from models import PreTradeReflection, WeeklyPulse
    uid = auth_user["id"]
    now = datetime(2024, 5, 1)
    with app.app_context():
        db.session.add(PreTradeReflection(
            user_id=uid, intended_ticker="AAPL", intended_side="BUY",
            intended_shares=3, rationale="long-term conviction",
            devil_advocate_seen="valuation stretched",
            cooldown_started_at=now, cooldown_ends_at=now,
        ))
        db.session.add(WeeklyPulse(
            user_id=uid, mood=4, confidence=3,
            worry="macro headwinds", learn="size smaller",
            topics='["fed", "earnings"]',
        ))
        db.session.commit()

    # Journal
    resp = client.get("/api/profile/export?format=csv&dataset=journal")
    assert resp.status_code == 200, resp.data
    jheader, jrows = _parse_csv(resp)
    assert jheader == [
        "작성일", "종목코드", "종목명", "의도", "수량", "rationale",
        "devil_advocate_seen", "상태",
    ]
    assert len(jrows) == 1
    jrow = dict(zip(jheader, jrows[0]))
    assert jrow["종목코드"] == "AAPL"
    assert jrow["의도"] == "BUY"
    assert jrow["rationale"] == "long-term conviction"
    assert jrow["devil_advocate_seen"] == "valuation stretched"

    # Pulse
    resp2 = client.get("/api/profile/export?format=csv&dataset=pulse")
    assert resp2.status_code == 200
    pheader, prows = _parse_csv(resp2)
    assert pheader == ["제출일", "mood", "confidence", "worry", "learn", "topics"]
    assert len(prows) == 1
    prow = dict(zip(pheader, prows[0]))
    assert prow["mood"] == "4"
    assert prow["confidence"] == "3"
    assert prow["worry"] == "macro headwinds"
    assert prow["learn"] == "size smaller"
    assert "fed" in prow["topics"] and "earnings" in prow["topics"]


def test_csv_export_capital_gains_scopes_to_caller(
    app, client, make_user, auth_user,
):
    """CRITICAL: another user's trades must never appear in the caller's
    capital-gains CSV."""
    from datetime import datetime
    uid = auth_user["id"]
    other = make_user(email="cgother@test.com", password="otherpw123")
    _seed_us_round_trip(
        app, uid, ticker="AAPL",
        buy_dt=datetime(2024, 1, 2), sell_dt=datetime(2024, 6, 3),
    )
    _seed_us_round_trip(
        app, other["id"], ticker="TSLAOTHER",
        buy_dt=datetime(2024, 1, 2), sell_dt=datetime(2024, 6, 3),
    )
    with patch("services.fx_service.get_rate_at_strict", return_value=1000.0):
        resp = client.get("/api/profile/export?format=csv&dataset=capital_gains")
    assert resp.status_code == 200
    raw = resp.data.decode("utf-8-sig")
    assert "TSLAOTHER" not in raw, "Other user's trade leaked into capital_gains"
    assert "AAPL" in raw


def test_csv_export_scopes_strictly_to_caller(
    app, client, make_user, auth_user, add_position,
):
    """CRITICAL: CSV export must contain ONLY the caller's rows. Seed another
    user's trade/position/watchlist and confirm none leak into the CSV."""
    from extensions import db
    from models import TradeHistory, Watchlist
    uid = auth_user["id"]
    add_position(uid, ticker="AAPL", shares=1.0, avg_cost=100.0)

    other = make_user(email="csvother@test.com", password="otherpw123")
    with app.app_context():
        add_position  # noqa — other position added via direct insert below
        from models import Position
        db.session.add(Position(
            user_id=other["id"], ticker="TSLA", shares=99.0, avg_cost=999.0,
        ))
        db.session.add(TradeHistory(
            user_id=other["id"], ticker="TSLA", name="OTHER-SECRET-NAME",
            action="BUY", shares=10.0, price_per_share=999.0,
            total_value=9990.0, currency="USD",
        ))
        db.session.add(Watchlist(
            user_id=other["id"], ticker="NVDA", note="OTHER-SECRET-NOTE",
        ))
        db.session.commit()

    for dataset in ("trades", "positions", "watchlist"):
        resp = client.get(f"/api/profile/export?format=csv&dataset={dataset}")
        assert resp.status_code == 200
        raw = resp.data.decode("utf-8-sig")
        assert "TSLA" not in raw, f"Other user's ticker leaked in {dataset} CSV"
        assert "NVDA" not in raw, f"Other user's watchlist leaked in {dataset} CSV"
        assert "OTHER-SECRET-NAME" not in raw, f"Other user's trade name leaked in {dataset}"
        assert "OTHER-SECRET-NOTE" not in raw, f"Other user's note leaked in {dataset}"


def test_csv_export_neutralises_formula_injection(app, client, auth_user):
    """CSV/formula injection (CWE-1236): a watchlist note that leads with a
    spreadsheet formula char (=, +, -, @) must be quoted with a leading '
    so it cannot execute when the file is opened in Excel / Sheets."""
    from extensions import db
    from models import Watchlist
    uid = auth_user["id"]
    with app.app_context():
        db.session.add(Watchlist(
            user_id=uid, ticker="AAPL", note="=cmd|'/c calc'!A1",
        ))
        db.session.commit()

    resp = client.get("/api/profile/export?format=csv&dataset=watchlist")
    assert resp.status_code == 200
    raw = resp.data.decode("utf-8-sig")
    # The leader is neutralised with a prepended single quote …
    assert "'=cmd" in raw, "formula-injection note was not neutralised"
    # … and a BARE formula never starts a cell (no ',=cmd' at a delimiter).
    assert ",=cmd" not in raw, "bare formula reached a cell boundary"


def test_csv_export_has_utf8_bom_for_excel(client, auth_user, app):
    """The CSV body must start with the UTF-8 BOM so Excel renders Hangul
    company names (삼성전자) instead of mojibake."""
    from extensions import db
    from models import Watchlist
    with app.app_context():
        db.session.add(Watchlist(
            user_id=auth_user["id"], ticker="005930.KS", note="한글메모",
        ))
        db.session.commit()
    resp = client.get("/api/profile/export?format=csv&dataset=watchlist")
    assert resp.status_code == 200
    # Raw bytes begin with the UTF-8 BOM.
    assert resp.data.startswith(b"\xef\xbb\xbf"), "Missing UTF-8 BOM"
    # Hangul note round-trips intact.
    text = resp.data.decode("utf-8-sig")
    assert "한글메모" in text


def test_json_export_still_default_when_no_format(client, auth_user):
    """Regression guard: with no ?format the endpoint still returns the full
    §35 JSON export unchanged (CSV branch must not hijack the default)."""
    resp = client.get("/api/profile/export")
    assert resp.status_code == 200
    assert "application/json" in resp.headers.get("Content-Type", "")
    body = json.loads(resp.data)
    assert body["format_version"] == "1.0"
    assert body["scope"] == "self_only"



def test_export_includes_consent_trail_birthdate_and_nav_history(app, client, auth_user):
    """2026-09-10 (PIPA §35): birthdate, the consent timestamps and the NAV
    snapshot history belong to the user and were missing from the export."""
    from datetime import date, datetime, timezone
    from extensions import db
    from models import PortfolioNavSnapshot, User

    uid = auth_user["id"]
    with app.app_context():
        u = db.session.get(User, uid)
        u.marketing_consent_at = datetime(2026, 9, 1, 1, 0, 0)
        db.session.add(PortfolioNavSnapshot(
            user_id=uid, as_of_date=date(2026, 9, 1),
            nav_total_usd=1234, nav_us_usd=1234, nav_kr_krw=0,
        ))
        db.session.commit()

    body = json.loads(client.get("/api/profile/export").data)
    assert body["user"]["birthdate"] is not None
    assert body["user"]["consents"]["marketing_consent_at"].startswith("2026-09-01")
    assert body["counts"]["portfolio_nav_snapshots"] == 1
    assert body["portfolio_nav_snapshots"][0]["as_of_date"].startswith("2026-09-01")
    assert "user_message_hash" not in json.dumps(body["user_agent_audit"])
