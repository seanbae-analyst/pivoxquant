"""Marketing-consent endpoint tests (정통망법 §50 ①).

Covers the new ``/api/consents/marketing`` blueprint added in
``hotfix/marketing-consent-server-persist`` and the corresponding
``users.marketing_consent_at`` / ``users.marketing_consent_revoked_at``
columns provisioned by migration 023.

The contract checked here:

  * GET unauthenticated → 401.
  * GET authenticated → ok, ``opted_in=False`` for a fresh user.
  * POST → opted_in flips to True, ``marketing_consent_at`` stamped.
  * DELETE → opted_in flips to False, ``marketing_consent_revoked_at``
    stamped.
  * 2026-09-29 — neither touches ``email_opt_out``. Consent (the legal
    basis, "may") and delivery (the user's mute switch, "do") are separate
    facts with separate owners: ``email_opt_out`` belongs to the Settings
    email-delivery toggle (PATCH /api/profile/email-preferences) and the
    token unsubscribe link. POST used to force it False (silently undoing an
    explicit "email off") and DELETE forced it True. Revocation still stops
    every non-transactional send immediately because ``EmailSender`` checks
    ``revoked_at >= consent_at`` itself — asserted below.
  * Re-POST after DELETE → ``opted_in`` is True again because the new
    consent timestamp is *after* the revocation timestamp (effective
    consent is derived, not stored, so history survives).
"""
from __future__ import annotations

from sqlalchemy import inspect


def test_marketing_consent_columns_exist(app):
    """Migration 023 must have added both timestamp columns."""
    with app.app_context():
        from extensions import db
        cols = {c["name"] for c in inspect(db.engine).get_columns("users")}
    assert "marketing_consent_at" in cols
    assert "marketing_consent_revoked_at" in cols


def test_get_marketing_consent_unauthenticated_returns_401(client):
    resp = client.get("/api/consents/marketing")
    assert resp.status_code == 401


def test_get_marketing_consent_default_state(client, auth_user):
    resp = client.get("/api/consents/marketing")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["opted_in"] is False
    assert body["marketing_consent_at"] is None
    assert body["marketing_consent_revoked_at"] is None


def test_post_marketing_consent_records_opt_in(app, client, auth_user):
    resp = client.post("/api/consents/marketing")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["opted_in"] is True
    assert body["marketing_consent_at"] is not None
    assert body["marketing_consent_revoked_at"] is None

    with app.app_context():
        from extensions import db
        from models import User
        u = db.session.get(User, auth_user["id"])
        assert u.marketing_consent_at is not None
        assert u.marketing_consent_revoked_at is None


def _email_opt_out(app, user_id):
    with app.app_context():
        from extensions import db
        from models import User
        return bool(db.session.get(User, user_id).email_opt_out)


def test_post_consent_does_not_undo_explicit_email_off(app, client, auth_user):
    """Email delivery switched off in Settings stays off after opting in."""
    r = client.patch("/api/profile/email-preferences", json={"email_opt_out": True})
    assert r.status_code == 200
    assert client.post("/api/consents/marketing").status_code == 200
    assert _email_opt_out(app, auth_user["id"]) is True


def test_delete_marketing_consent_records_revocation(app, client, auth_user):
    # Opt in first so we have something to revoke.
    client.post("/api/consents/marketing")

    resp = client.delete("/api/consents/marketing")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["opted_in"] is False
    assert body["marketing_consent_at"] is not None  # preserved as audit trail
    assert body["marketing_consent_revoked_at"] is not None

    # The delivery switch is not the consent route's to flip.
    assert _email_opt_out(app, auth_user["id"]) is False


def test_revocation_blocks_sends_without_email_opt_out(app, client, auth_user):
    """정통망법 §50 — withdrawal is honoured "without delay" by the sender's
    own consent check, not by a side effect on ``email_opt_out``."""
    from unittest.mock import patch

    from services.email.sender import EmailCategory, EmailSender

    client.post("/api/consents/marketing")
    client.delete("/api/consents/marketing")

    with app.app_context():
        from extensions import db
        from models import User
        u = db.session.get(User, auth_user["id"])
        assert u.email_opt_out is False
        with patch("services.email.sender.build_unsubscribe_url") as unsub:
            ok = EmailSender().send(
                u, subject="s", html_body="<p>x</p>",
                from_env_var="X_FROM", from_default="reports@pivoxquant.com",
                email_category=EmailCategory.INFORMATION,
            )
        assert ok is False
        unsub.assert_not_called()  # stopped at the consent gate, pre-transport


def test_email_toggle_does_not_touch_consent(app, client, auth_user):
    """The other direction: PATCH email-preferences leaves the §50 record alone."""
    client.post("/api/consents/marketing")
    client.patch("/api/profile/email-preferences", json={"email_opt_out": True})
    client.patch("/api/profile/email-preferences", json={"email_opt_out": False})
    body = client.get("/api/consents/marketing").get_json()
    assert body["opted_in"] is True
    assert body["marketing_consent_revoked_at"] is None


def test_post_after_delete_re_opts_in(client, auth_user):
    """Effective consent is derived, so re-posting after revoke flips back."""
    client.post("/api/consents/marketing")
    client.delete("/api/consents/marketing")

    resp = client.post("/api/consents/marketing")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["opted_in"] is True
    # Revocation cleared on re-consent so the new state is unambiguous.
    assert body["marketing_consent_revoked_at"] is None
