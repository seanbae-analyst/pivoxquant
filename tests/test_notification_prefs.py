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
    NOTIFICATION_EVENT_IDS,
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
        # concentration default: all True
        assert u.notification_channel_enabled("concentration", "email") is True


def test_channel_enabled_honours_stored_value(app, make_user):
    """Stored value overrides the default for that event/channel only."""
    user = make_user(email="np-stored@test.com")
    with app.app_context():
        u = db.session.get(User, user["id"])
        u.notification_prefs = {"concentration": {"email": False}}
        db.session.commit()
        # overridden
        assert u.notification_channel_enabled("concentration", "email") is False
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


def test_get_preferences_returns_every_event(auth_user, client):
    resp = client.get("/api/notifications/preferences")
    assert resp.status_code == 200, resp.data
    prefs = resp.get_json()["prefs"]
    assert set(prefs.keys()) == set(NOTIFICATION_EVENT_IDS)
    for event_id, channels in prefs.items():
        assert set(channels.keys()) == set(NOTIFICATION_CHANNELS)
        assert channels == NOTIFICATION_PREF_DEFAULTS[event_id]


def test_get_preferences_requires_auth(client):
    resp = client.get("/api/notifications/preferences")
    assert resp.status_code == 401


# ── (c) PUT → GET round-trip ─────────────────────────────────────────────


def test_put_then_get_round_trip(auth_user, client):
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
        u.notification_prefs = {"concentration": {"email": False}}
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
                event_id="concentration",
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
        # concentration email default is True; leave prefs untouched.
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
                event_id="concentration",
            )
        assert sent is True
        sg.assert_called_once()
