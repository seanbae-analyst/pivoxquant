"""C-S1 §50 split-consent backend tests (Wave D Sub-wave 1).

Coverage:

1. Migration 037 column presence on the ``users`` table.
2. ``GET /api/consents/categories`` returns the per-category state.
3. ``POST /api/consents/categories`` records per-category timestamps
   and is idempotent + supports re-opt-in after revocation.
4. ``EmailSender`` behaviour:
   * Flag OFF — pre-CS1 baseline (no extra gating).
   * Flag ON  — INFORMATION / MARKETING blocked without category
     consent; TRANSACTIONAL always passes.

Note: prod deploy of the *enforcement* path stays gated by
``PIVOX_CS1_CONSENT_ENABLED=false`` until the lawyer's Q-S1 answer.
These tests pin the behaviour both modes promise.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


# ── 1. Migration column presence ──────────────────────────────────────


def test_migration_037_columns_present(app):
    """Migration 037 must add the four split-consent columns to users."""
    from extensions import db
    import sqlalchemy as sa
    with app.app_context():
        inspector = sa.inspect(db.engine)
        cols = {c["name"] for c in inspector.get_columns("users")}
        for required in (
            "marketing_consent_information_at",
            "marketing_consent_information_revoked_at",
            "marketing_consent_marketing_at",
            "marketing_consent_marketing_revoked_at",
        ):
            assert required in cols, (
                f"users.{required} missing — migration 037 not applied. "
                f"Existing cols: {sorted(cols)}"
            )


# ── 2. GET /api/consents/categories ───────────────────────────────────


def test_get_categories_initial_state(client, auth_user):
    """Fresh user — both categories opted_in=False, timestamps null."""
    resp = client.get("/api/consents/categories")
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["ok"] is True
    cats = body["categories"]
    assert cats["information"] == {
        "consent_at": None, "revoked_at": None, "opted_in": False,
    }
    assert cats["marketing"] == {
        "consent_at": None, "revoked_at": None, "opted_in": False,
    }


# ── 3. POST /api/consents/categories ──────────────────────────────────


def test_post_categories_opt_in_both(client, auth_user):
    """Opting both true sets timestamps + flips opted_in=True."""
    resp = client.post("/api/consents/categories",
                       json={"information": True, "marketing": True})
    assert resp.status_code == 200, resp.data
    cats = resp.get_json()["categories"]
    assert cats["information"]["opted_in"] is True
    assert cats["information"]["consent_at"] is not None
    assert cats["information"]["revoked_at"] is None
    assert cats["marketing"]["opted_in"] is True
    assert cats["marketing"]["consent_at"] is not None
    assert cats["marketing"]["revoked_at"] is None


def test_post_categories_partial_payload_leaves_other_untouched(
        client, auth_user):
    """Omitting a key must not mutate that category's columns."""
    # Step 1: opt in to marketing only.
    client.post("/api/consents/categories", json={"marketing": True})
    # Step 2: opt in to information without specifying marketing.
    resp = client.post("/api/consents/categories", json={"information": True})
    cats = resp.get_json()["categories"]
    assert cats["information"]["opted_in"] is True
    # Marketing should still be opted in from step 1 — not silently reset.
    assert cats["marketing"]["opted_in"] is True


def test_post_categories_revoke_then_reconsent(client, auth_user):
    """Opt-in → revoke → opt-in again must clear revoked_at."""
    client.post("/api/consents/categories", json={"information": True})
    resp = client.post("/api/consents/categories", json={"information": False})
    cats = resp.get_json()["categories"]
    assert cats["information"]["opted_in"] is False
    assert cats["information"]["revoked_at"] is not None
    # Re-opt-in — revoked_at should clear so opted_in derives true again.
    resp = client.post("/api/consents/categories", json={"information": True})
    cats = resp.get_json()["categories"]
    assert cats["information"]["opted_in"] is True
    assert cats["information"]["revoked_at"] is None


def test_post_categories_rejects_non_boolean(client, auth_user):
    """Strings / ints must 400 — avoid 'truthy string == opt-in' surprises."""
    resp = client.post("/api/consents/categories",
                       json={"information": "yes"})
    assert resp.status_code == 400
    body = resp.get_json()
    assert "information" in body["error"]


def test_post_categories_rejects_non_object_body(client, auth_user):
    """List / scalar body must 400."""
    resp = client.post("/api/consents/categories", json=[True, False])
    assert resp.status_code == 400


def test_categories_endpoints_require_auth(client):
    """Unauthenticated calls must be rejected by @api_auth."""
    for method, fn in (("GET", client.get), ("POST", client.post)):
        kw = {"json": {"information": True}} if method == "POST" else {}
        resp = fn("/api/consents/categories", **kw)
        assert resp.status_code in (401, 403), (
            f"{method} /api/consents/categories returned {resp.status_code} "
            f"for unauth (expected 401/403)"
        )


# ── 4. EmailSender feature-flag behaviour ─────────────────────────────


class _FakeUser:
    """Duck-typed user — EmailSender never touches the ORM directly."""
    def __init__(self, **kw):
        self.id = kw.get("id", 42)
        self.email = kw.get("email", "u@test.com")
        self.email_opt_out = False
        self.is_simulated = False
        # Global consent — set so the v1 gate passes; the C-S1 gate is
        # what we're isolating in these tests.
        self.marketing_consent_at = kw.get(
            "marketing_consent_at",
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1),
        )
        self.marketing_consent_information_at = kw.get(
            "marketing_consent_information_at", None)
        self.marketing_consent_information_revoked_at = kw.get(
            "marketing_consent_information_revoked_at", None)
        self.marketing_consent_marketing_at = kw.get(
            "marketing_consent_marketing_at", None)
        self.marketing_consent_marketing_revoked_at = kw.get(
            "marketing_consent_marketing_revoked_at", None)


def _patch_transport_always_succeed():
    """Patch sender's transport methods so we measure gating, not delivery."""
    return patch.multiple(
        "services.email.sender.EmailSender",
        _send_via_sendgrid=lambda *a, **kw: True,
        _send_via_brevo=lambda *a, **kw: True,
        _send_via_smtp=lambda *a, **kw: True,
    )


def _send(sender, user, app=None, **extra):
    """Invoke send() with neutral defaults; return the bool result.

    The sender's unsubscribe-URL builder needs the Flask app context
    (config["SECRET_KEY"]). Wrap the call accordingly when ``app`` is
    provided.
    """
    def _call():
        return sender.send(
            user,
            subject="hi",
            html_body="<p>x</p>",
            from_env_var="DOES_NOT_EXIST",
            from_default="from@test.com",
            **extra,
        )

    if app is None:
        return _call()
    with app.app_context():
        return _call()


def test_flag_off_no_category_arg_is_pre_cs1_baseline(monkeypatch, app):
    """Flag off + no category arg → no extra gating (pre-CS1 parity)."""
    from services.email.sender import EmailSender
    monkeypatch.setenv("PIVOX_CS1_CONSENT_ENABLED", "false")
    monkeypatch.setenv("SENDGRID_API_KEY", "test")
    user = _FakeUser()  # no category consents
    with _patch_transport_always_succeed():
        assert _send(EmailSender(), user, app=app) is True


def test_flag_off_category_arg_ignored(monkeypatch, app):
    """Flag off — category arg supplied — still no gating."""
    from services.email.sender import EmailSender, EmailCategory
    monkeypatch.setenv("PIVOX_CS1_CONSENT_ENABLED", "false")
    monkeypatch.setenv("SENDGRID_API_KEY", "test")
    user = _FakeUser()  # marketing_consent_marketing_at is None
    with _patch_transport_always_succeed():
        assert _send(EmailSender(), user, app=app,
                     email_category=EmailCategory.MARKETING) is True


def test_flag_on_marketing_blocked_without_category_consent(monkeypatch, app):
    """Flag on + MARKETING category + no consent → blocked.

    Blocked path never reaches the URL builder, so the app context is
    not strictly needed, but we still pass it for consistency.
    """
    from services.email.sender import EmailSender, EmailCategory
    monkeypatch.setenv("PIVOX_CS1_CONSENT_ENABLED", "true")
    monkeypatch.setenv("SENDGRID_API_KEY", "test")
    user = _FakeUser()  # marketing_consent_marketing_at is None
    with _patch_transport_always_succeed():
        assert _send(EmailSender(), user, app=app,
                     email_category=EmailCategory.MARKETING) is False


def test_flag_on_marketing_allowed_with_category_consent(monkeypatch, app):
    """Flag on + MARKETING category + valid consent → delivered."""
    from services.email.sender import EmailSender, EmailCategory
    monkeypatch.setenv("PIVOX_CS1_CONSENT_ENABLED", "true")
    monkeypatch.setenv("SENDGRID_API_KEY", "test")
    user = _FakeUser(
        marketing_consent_marketing_at=datetime.now(timezone.utc)
            .replace(tzinfo=None) - timedelta(hours=1),
    )
    with _patch_transport_always_succeed():
        assert _send(EmailSender(), user, app=app,
                     email_category=EmailCategory.MARKETING) is True


def test_flag_on_information_independent_of_marketing(monkeypatch, app):
    """INFORMATION consent ≠ MARKETING consent — must not cross-grant."""
    from services.email.sender import EmailSender, EmailCategory
    monkeypatch.setenv("PIVOX_CS1_CONSENT_ENABLED", "true")
    monkeypatch.setenv("SENDGRID_API_KEY", "test")
    # Only INFORMATION opted in.
    user = _FakeUser(
        marketing_consent_information_at=datetime.now(timezone.utc)
            .replace(tzinfo=None) - timedelta(hours=1),
    )
    with _patch_transport_always_succeed():
        assert _send(EmailSender(), user, app=app,
                     email_category=EmailCategory.INFORMATION) is True
        assert _send(EmailSender(), user, app=app,
                     email_category=EmailCategory.MARKETING) is False


def test_flag_on_transactional_bypasses_gate(monkeypatch, app):
    """TRANSACTIONAL always delivers — §50 ① 적용 제외."""
    from services.email.sender import EmailSender, EmailCategory
    monkeypatch.setenv("PIVOX_CS1_CONSENT_ENABLED", "true")
    monkeypatch.setenv("SENDGRID_API_KEY", "test")
    user = _FakeUser()  # no category consents
    with _patch_transport_always_succeed():
        assert _send(EmailSender(), user, app=app,
                     email_category=EmailCategory.TRANSACTIONAL) is True


def test_revoked_consent_blocks_send_even_if_consent_at_set(monkeypatch, app):
    """Revoked-after-consent must NOT satisfy the gate."""
    from services.email.sender import EmailSender, EmailCategory
    monkeypatch.setenv("PIVOX_CS1_CONSENT_ENABLED", "true")
    monkeypatch.setenv("SENDGRID_API_KEY", "test")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user = _FakeUser(
        marketing_consent_marketing_at=now - timedelta(hours=2),
        marketing_consent_marketing_revoked_at=now - timedelta(hours=1),
    )
    with _patch_transport_always_succeed():
        assert _send(EmailSender(), user, app=app,
                     email_category=EmailCategory.MARKETING) is False



# ── 5. Baseline gate honours revocation (2026-09-10) ─────────────────


def test_baseline_gate_blocks_after_revocation(monkeypatch, app):
    """consent_at set but revoked_at later → no marketing send, flag on or off.
    Before 2026-09-10 only ``marketing_consent_at IS NOT NULL`` was checked."""
    from services.email.sender import EmailSender, EmailCategory
    monkeypatch.setenv("PIVOX_CS1_CONSENT_ENABLED", "false")
    monkeypatch.setenv("SENDGRID_API_KEY", "test")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user = _FakeUser(marketing_consent_at=now - timedelta(days=3))
    user.marketing_consent_revoked_at = now - timedelta(days=1)
    with _patch_transport_always_succeed():
        assert _send(EmailSender(), user, app=app,
                     email_category=EmailCategory.MARKETING) is False
        assert _send(EmailSender(), user, app=app) is False


def test_baseline_gate_allows_reconsent_after_revocation(monkeypatch, app):
    from services.email.sender import EmailSender
    monkeypatch.setenv("PIVOX_CS1_CONSENT_ENABLED", "false")
    monkeypatch.setenv("SENDGRID_API_KEY", "test")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user = _FakeUser(marketing_consent_at=now - timedelta(hours=1))
    user.marketing_consent_revoked_at = now - timedelta(days=2)
    with _patch_transport_always_succeed():
        assert _send(EmailSender(), user, app=app) is True


def test_transactional_ignores_revocation(monkeypatch, app):
    from services.email.sender import EmailSender, EmailCategory
    monkeypatch.setenv("SENDGRID_API_KEY", "test")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user = _FakeUser(marketing_consent_at=now - timedelta(days=3))
    user.marketing_consent_revoked_at = now - timedelta(days=1)
    with _patch_transport_always_succeed():
        assert _send(EmailSender(), user, app=app,
                     email_category=EmailCategory.TRANSACTIONAL) is True
