"""Marketing-consent endpoint tests (정통망법 §50 ①).

Covers the new ``/api/consents/marketing`` blueprint added in
``hotfix/marketing-consent-server-persist`` and the corresponding
``users.marketing_consent_at`` / ``users.marketing_consent_revoked_at``
columns provisioned by migration 023.

The contract checked here:

  * GET unauthenticated → 401.
  * GET authenticated → ok, ``opted_in=False`` for a fresh user.
  * POST → opted_in flips to True, ``marketing_consent_at`` stamped,
    ``email_opt_out`` re-enabled in lock-step.
  * DELETE → opted_in flips to False, ``marketing_consent_revoked_at``
    stamped, ``email_opt_out`` set to True so the runtime kill-switch
    matches the legal state.
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

    # Verify DB-level state and the email_opt_out lock-step.
    with app.app_context():
        from extensions import db
        from models import User
        u = db.session.get(User, auth_user["id"])
        assert u.marketing_consent_at is not None
        assert u.marketing_consent_revoked_at is None
        assert u.email_opt_out is False


def test_delete_marketing_consent_records_revocation(app, client, auth_user):
    # Opt in first so we have something to revoke.
    client.post("/api/consents/marketing")

    resp = client.delete("/api/consents/marketing")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["opted_in"] is False
    assert body["marketing_consent_at"] is not None  # preserved as audit trail
    assert body["marketing_consent_revoked_at"] is not None

    # email_opt_out kill-switch must be engaged in lock-step so subsequent
    # sends short-circuit immediately (no nightly-job lag).
    with app.app_context():
        from extensions import db
        from models import User
        u = db.session.get(User, auth_user["id"])
        assert u.email_opt_out is True


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
