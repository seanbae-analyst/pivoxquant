"""Tests for settings v2 notification-matrix persistence + enforcement.

Covers the new column / route / EmailSender gate that move the per-event ×
per-channel toggles off localStorage and onto the server (GAP-E):

  (a) ``User.notification_channel_enabled`` — default / stored / unknown-key.
  (b) ``GET /api/notifications/preferences`` — always all 7 events.
  (c) ``PUT`` then ``GET`` round-trip — stored value survives + merges.
  (d) ``PUT`` with an unknown event/channel/value key → 400.
  (e) ``EmailSender.send(event_id=...)`` skips when the user disabled the
      email channel for that event.

Following "거짓보고 금지": helper / route tests use real DB ``User`` rows;
the EmailSender test mocks only the network boundary so no email is sent.
"""
from __future__ import annotations

from unittest.mock import patch

from extensions import db
from models import User
from models.user import (
    NOTIFICATION_CHANNELS,
    NOTIFICATION_EVENT_CHANNELS,
    NOTIFICATION_EVENT_IDS,
    visible_notification_event_ids,
    NOTIFICATION_PREF_DEFAULTS,
)


# ── (a) model helper ─────────────────────────────────────────────────────


def test_channel_enabled_falls_back_to_defaults(app, make_user):
    """No stored prefs → defaults table is the source of truth."""
    user = make_user(email="np-default@test.com")
    with app.app_context():
        u = db.session.get(User, user["id"])
        assert u.notification_prefs is None
        # price_52w default: email=False, push=True, inapp=True
        assert u.notification_channel_enabled("price_52w", "email") is False
        assert u.notification_channel_enabled("price_52w", "push") is True
        # concentration default: push/in-app on, email off (no email sender)
        assert u.notification_channel_enabled("concentration", "push") is True
        assert u.notification_channel_enabled("concentration", "email") is False


def test_channel_enabled_honours_stored_value(app, make_user):
    """Stored value overrides the default for that event/channel only."""
    user = make_user(email="np-stored@test.com")
    with app.app_context():
        u = db.session.get(User, user["id"])
        u.notification_prefs = {"concentration": {"inapp": False}}
        db.session.commit()
        # overridden
        assert u.notification_channel_enabled("concentration", "inapp") is False
        # un-stored channel of same event → default (True)
        assert u.notification_channel_enabled("concentration", "push") is True
        # un-stored event → default
        assert u.notification_channel_enabled("price_52w", "push") is True


def test_channel_enabled_unknown_event_fails_open(app, make_user):
    """Unknown event id must fail-open (True) — never silently mute."""
    user = make_user(email="np-unknown@test.com")
    with app.app_context():
        u = db.session.get(User, user["id"])
        assert u.notification_channel_enabled("does_not_exist", "email") is True
        # unknown channel on a known event also fails open
        assert u.notification_channel_enabled("concentration", "sms") is True


# ── (b) GET defaults ─────────────────────────────────────────────────────


def test_get_preferences_returns_every_event(auth_user, client, market_display_on):
    """With every producer live, the matrix shows all canonical events."""
    resp = client.get("/api/notifications/preferences")
    assert resp.status_code == 200, resp.data
    prefs = resp.get_json()["prefs"]
    assert set(prefs.keys()) == set(NOTIFICATION_EVENT_IDS)
    for event_id, channels in prefs.items():
        assert set(channels.keys()) == set(NOTIFICATION_CHANNELS)
        assert channels == NOTIFICATION_PREF_DEFAULTS[event_id]


def test_get_preferences_hides_price_52w_when_display_off(
    auth_user, client, market_display_off,
):
    """SoT rule: only events that can actually SEND are shown.

    ``price_52w``'s only producer (``check_52w_highs_lows`` via the
    ``price_alerts_daily`` cron) is skipped while MARKET_DATA_DISPLAY_ENABLED
    is off, so its row must not render — otherwise it is a dead toggle.
    ``concentration`` is cost-basis only and keeps its row.
    """
    resp = client.get("/api/notifications/preferences")
    assert resp.status_code == 200, resp.data
    prefs = resp.get_json()["prefs"]
    assert "price_52w" not in prefs
    assert "concentration" in prefs
    assert set(prefs.keys()) == set(visible_notification_event_ids())
    # The canonical vocabulary itself is untouched — this is a display filter.
    assert "price_52w" in NOTIFICATION_EVENT_IDS


def test_put_accepts_price_52w_even_while_hidden(
    app, auth_user, client, market_display_off,
):
    """A hidden event stays VALID input, so a stored setting survives the
    gate being flipped back on."""
    resp = client.put(
        "/api/notifications/preferences",
        json={"prefs": {"price_52w": {"email": False, "push": False, "inapp": True}}},
    )
    assert resp.status_code == 200, resp.data
    # Hidden from the response body...
    assert "price_52w" not in resp.get_json()["prefs"]
    # ...but persisted: it reappears once display is enabled again.
    from models.user import User
    from extensions import db
    with app.app_context():
        u = db.session.get(User, auth_user["id"])
        assert u.notification_prefs["price_52w"]["push"] is False
        assert u.notification_prefs["price_52w"]["inapp"] is True


def test_get_preferences_requires_auth(client):
    resp = client.get("/api/notifications/preferences")
    assert resp.status_code == 401


# ── (c) PUT → GET round-trip ─────────────────────────────────────────────


def test_put_then_get_round_trip(auth_user, client, market_display_on):
    body = {"prefs": {"concentration": {"email": False, "push": False, "inapp": True}}}
    put = client.put("/api/notifications/preferences", json=body)
    assert put.status_code == 200, put.data
    put_prefs = put.get_json()["prefs"]
    # Response is merged — still every event.
    assert set(put_prefs.keys()) == set(NOTIFICATION_EVENT_IDS)
    assert put_prefs["concentration"] == {"email": False, "push": False, "inapp": True}
    # Untouched event keeps defaults.
    assert put_prefs["price_52w"] == NOTIFICATION_PREF_DEFAULTS["price_52w"]

    # Re-fetch — persisted value survives.
    get = client.get("/api/notifications/preferences")
    assert get.status_code == 200
    assert get.get_json()["prefs"]["concentration"] == {
        "email": False, "push": False, "inapp": True,
    }


# ── (d) PUT validation ───────────────────────────────────────────────────


def test_put_rejects_unknown_event(auth_user, client):
    resp = client.put(
        "/api/notifications/preferences",
        json={"prefs": {"not_an_event": {"email": True}}},
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "NOTIF_PREFS_UNKNOWN_EVENT"


def test_put_rejects_unknown_channel(auth_user, client):
    resp = client.put(
        "/api/notifications/preferences",
        json={"prefs": {"concentration": {"sms": True}}},
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "NOTIF_PREFS_UNKNOWN_CHANNEL"


def test_put_rejects_non_bool_value(auth_user, client):
    resp = client.put(
        "/api/notifications/preferences",
        json={"prefs": {"concentration": {"email": "yes"}}},
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "NOTIF_PREFS_BAD_VALUE"


def test_put_rejects_bad_body(auth_user, client):
    resp = client.put("/api/notifications/preferences", json={"nope": 1})
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "NOTIF_PREFS_BAD_BODY"


# ── (e) EmailSender enforcement ──────────────────────────────────────────


def test_send_skips_when_event_email_disabled(app, make_user, monkeypatch):
    """``event_id`` whose email channel the user disabled → skip, no transport."""
    from services.email import EmailSender

    user = make_user(email="np-skip@test.com")
    with app.app_context():
        u = db.session.get(User, user["id"])
        # Pass the legacy consent/opt-out gates so we isolate the new gate.
        from datetime import datetime, timezone
        u.marketing_consent_at = datetime.now(timezone.utc).replace(tzinfo=None)
        u.email_opt_out = False
        u.notification_prefs = {"monthly_mirror": {"email": False}}
        db.session.commit()

        monkeypatch.setenv("SENDGRID_API_KEY", "sg-xxx")
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        with patch("sendgrid.SendGridAPIClient",
                   side_effect=AssertionError("event-disabled leaked to SendGrid")), \
             patch("smtplib.SMTP",
                   side_effect=AssertionError("event-disabled leaked to SMTP")):
            sent = EmailSender().send(
                u,
                subject="x",
                html_body="<p>body</p>",
                from_env_var="WEEKLY_MEMO_FROM_EMAIL",
                from_default="reports@pivoxquant.com",
                event_id="monthly_mirror",
            )
        assert sent is False


def test_send_proceeds_when_event_email_enabled(app, make_user, monkeypatch):
    """Same gates passing + event email enabled → transport IS attempted."""
    from services.email import EmailSender

    user = make_user(email="np-proceed@test.com")
    with app.app_context():
        u = db.session.get(User, user["id"])
        from datetime import datetime, timezone
        u.marketing_consent_at = datetime.now(timezone.utc).replace(tzinfo=None)
        u.email_opt_out = False
        # monthly_mirror email is opt-in (default False) — opt in.
        u.notification_prefs = {"monthly_mirror": {"email": True}}
        db.session.commit()

        monkeypatch.setenv("SENDGRID_API_KEY", "sg-xxx")
        monkeypatch.delenv("SMTP_HOST", raising=False)
        monkeypatch.delenv("BREVO_API_KEY", raising=False)
        monkeypatch.delenv("SENDINBLUE_API_KEY", raising=False)
        with patch.object(EmailSender, "_send_via_sendgrid", return_value=True) as sg:
            sent = EmailSender().send(
                u,
                subject="x",
                html_body="<p>body</p>",
                from_env_var="WEEKLY_MEMO_FROM_EMAIL",
                from_default="reports@pivoxquant.com",
                event_id="monthly_mirror",
            )
        assert sent is True
        sg.assert_called_once()


# ── (f) 채널 허용 목록 — 발신자가 없는 칸은 끄지도 켜지도 못한다 (2026-09-29) ──
# 설정 매트릭스가 모든 이벤트에 email/push/inapp 세 칸을 다 그렸다. 실제 발신자는
# price_52w·concentration → 벨+푸시 (services/alert.create_alert) 뿐, monthly_mirror →
# 이메일 (services/reports_delivery) 뿐이다. concentration×email 은 기본 ON 인데
# 아무것도 보내지 않았다.


def test_event_channels_allowlist_matches_the_senders():
    assert set(NOTIFICATION_EVENT_CHANNELS) == set(NOTIFICATION_EVENT_IDS)
    assert NOTIFICATION_EVENT_CHANNELS["price_52w"] == ("push", "inapp")
    assert NOTIFICATION_EVENT_CHANNELS["concentration"] == ("push", "inapp")
    assert NOTIFICATION_EVENT_CHANNELS["monthly_mirror"] == ("email",)
    for event_id, live in NOTIFICATION_EVENT_CHANNELS.items():
        assert set(live) <= set(NOTIFICATION_CHANNELS)
        # A channel with no sender must not default on.
        for ch in NOTIFICATION_CHANNELS:
            if ch not in live:
                assert NOTIFICATION_PREF_DEFAULTS[event_id][ch] is False, (
                    event_id, ch)


def test_get_preferences_exposes_live_channels(auth_user, client, market_display_off):
    resp = client.get("/api/notifications/preferences")
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["channels"] == {
        e: list(NOTIFICATION_EVENT_CHANNELS[e])
        for e in visible_notification_event_ids()
    }


def test_get_preferences_reports_dead_channel_off_even_if_stored_on(
    app, auth_user, client,
):
    """옛 기본값(concentration×email=True)이 저장돼 있어도 보낼 수 없으니 False."""
    with app.app_context():
        u = db.session.get(User, auth_user["id"])
        u.notification_prefs = {"concentration": {"email": True}}
        db.session.commit()
    prefs = client.get("/api/notifications/preferences").get_json()["prefs"]
    assert prefs["concentration"]["email"] is False


def test_put_ignores_dead_channels(app, auth_user, client):
    """죽은 칸은 저장하지 않는다 — 옛 클라이언트가 세 칸을 다 보내도 200."""
    resp = client.put(
        "/api/notifications/preferences",
        json={"prefs": {
            "concentration": {"email": True, "push": False, "inapp": True},
            "monthly_mirror": {"email": True, "push": True, "inapp": True},
        }},
    )
    assert resp.status_code == 200, resp.data
    prefs = resp.get_json()["prefs"]
    assert prefs["concentration"] == {"email": False, "push": False, "inapp": True}
    assert prefs["monthly_mirror"] == {"email": True, "push": False, "inapp": False}
    with app.app_context():
        stored = db.session.get(User, auth_user["id"]).notification_prefs
    assert stored["concentration"] == {"push": False, "inapp": True}
    assert stored["monthly_mirror"] == {"email": True}
