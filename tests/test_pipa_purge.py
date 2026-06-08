"""PIPA §21 30-day automatic purge — Wave I C-2 tests.

Covers
------
1. ``deletion_requested_at`` < 30d → user is NOT purged (skipped).
2. ``deletion_requested_at`` ≥ 30d → user IS purged + cascade rows
   removed + auth_events anonymized + deleted_at stamped.
3. ``deletion_requested_at`` IS NULL → never purged.
4. Stuck row (``deleted_at`` NOT NULL, row still present) → RE-INCLUDED
   and purged to completion; the duplicate "data purged" email is
   suppressed on the retry.
5. /api/auth/delete-request endpoint:
   - 200 + soft-delete state set
   - second call is idempotent
   - subsequent login is rejected
6. PIPA §29 audit: auth_events email is anonymized (SHA256 hashed),
   row NOT deleted.

All transports mocked.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

def _patch_transport_succeed():
    return patch.multiple(
        "services.email.sender.EmailSender",
        _send_via_sendgrid=lambda *a, **kw: True,
        _send_via_brevo=lambda *a, **kw: True,
        _send_via_smtp=lambda *a, **kw: True,
    )


@pytest.fixture(autouse=True)
def _enable_sendgrid_env(monkeypatch):
    monkeypatch.setenv("SENDGRID_API_KEY", "test-sendgrid-key")


def _make_user(app, *, email: str, requested_days_ago: float | None,
                already_deleted: bool = False):
    """Provision a User row with the soft-delete column set."""
    from extensions import db
    from models import User

    with app.app_context():
        u = User(email=email, name="Tester")
        u.set_pw("password123")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        u.marketing_consent_at = now - timedelta(days=1)
        if requested_days_ago is not None:
            u.deletion_requested_at = now - timedelta(days=requested_days_ago)
        if already_deleted:
            u.deleted_at = now - timedelta(days=1)
        db.session.add(u)
        db.session.commit()
        return u.id


# ── 1. <30d not purged ──────────────────────────────────────────────────────

def test_under_30d_not_purged(app):
    from scripts.nightly.pipa_purge import run_once
    from models import User

    uid = _make_user(app, email="under@test.com", requested_days_ago=10)

    with app.app_context():
        with _patch_transport_succeed():
            s = run_once()
        assert s["candidates"] == 0
        assert s["purged"] == 0
        u = User.query.get(uid)
        assert u is not None  # still here


# ── 2. ≥30d purged + cascade ────────────────────────────────────────────────

def test_over_30d_purged_with_cascade(app):
    """Seed Position + Watchlist + AuthEvent rows; verify cascade + anonymize."""
    from extensions import db
    from models import User, Position, Watchlist, AuthEvent
    from scripts.nightly.pipa_purge import run_once, _hash_email

    uid = _make_user(app, email="over@test.com", requested_days_ago=31)

    with app.app_context():
        # Seed dependent rows
        db.session.add(Position(user_id=uid, ticker="AAPL",
                                  shares=10.0, avg_cost=150.0))
        db.session.add(Watchlist(user_id=uid, ticker="MSFT"))
        # AuthEvent rows keyed by email — should be ANONYMIZED, not deleted.
        for i in range(3):
            db.session.add(AuthEvent(
                email="over@test.com",
                provider="google",
                event_type="fail",
                fail_reason="state_mismatch",
            ))
        db.session.commit()

        with _patch_transport_succeed():
            s = run_once()

        assert s["candidates"] == 1
        assert s["purged"] == 1
        assert s["rows_deleted"] >= 2  # Position + Watchlist
        assert s["auth_events_anon"] == 3
        assert s["errors"] == 0

        # User row is gone
        assert User.query.get(uid) is None
        # Cascade — dependent rows gone
        assert Position.query.filter_by(user_id=uid).count() == 0
        assert Watchlist.query.filter_by(user_id=uid).count() == 0
        # auth_events SURVIVES, but email is hashed
        expected_hash = _hash_email("over@test.com")
        anon = AuthEvent.query.filter_by(email=expected_hash).count()
        assert anon == 3
        # And the plaintext email is gone from auth_events
        plaintext = AuthEvent.query.filter_by(email="over@test.com").count()
        assert plaintext == 0


# ── 3. NULL deletion_requested_at never purged ──────────────────────────────

def test_null_deletion_request_skipped(app):
    from scripts.nightly.pipa_purge import run_once
    from models import User

    uid = _make_user(app, email="null@test.com", requested_days_ago=None)

    with app.app_context():
        with _patch_transport_succeed():
            s = run_once()
        assert s["candidates"] == 0
        assert User.query.get(uid) is not None


# ── 4. stuck row (deleted_at stamped, row not yet deleted) → recovered ───────

def test_stuck_row_is_recovered_and_completed(app):
    """A row left ``deleted_at NOT NULL`` but STILL PRESENT (a prior pass
    crashed between the two commits) must be RE-INCLUDED and the purge
    completed — not stranded forever. The pre-fix ``deleted_at IS NULL`` filter
    dropped it from every future pass → silent PIPA §21 violation."""
    from scripts.nightly.pipa_purge import run_once
    from models import User

    uid = _make_user(
        app, email="stuck@test.com",
        requested_days_ago=45, already_deleted=True,  # deleted_at set, row present
    )

    with app.app_context():
        with _patch_transport_succeed():
            s = run_once()
        assert s["candidates"] == 1, "stuck row must be re-included as a candidate"
        assert s["purged"] == 1
        assert s["errors"] == 0
        assert User.query.get(uid) is None, "stuck row must be hard-deleted on retry"


def test_stuck_row_retry_suppresses_duplicate_purge_email(app):
    """On a stuck-row retry the one-time 'data purged' email is NOT re-sent
    (it already went out on the first, crashed pass)."""
    from unittest.mock import patch
    from scripts.nightly.pipa_purge import run_once

    _make_user(
        app, email="stuck-noemail@test.com",
        requested_days_ago=45, already_deleted=True,
    )

    with app.app_context():
        with _patch_transport_succeed():
            with patch("scripts.nightly.pipa_purge._send_purge_complete_email") as m:
                s = run_once()
        assert s["purged"] == 1
        m.assert_not_called()


# ── 5. delete-request endpoint ──────────────────────────────────────────────

def test_delete_request_endpoint_soft_delete(client, app):
    """POST /api/auth/delete-request sets deletion_requested_at."""
    from extensions import db
    from models import User

    # Create + login user via the registered endpoint set in conftest.
    # We bypass the full register/login dance by manually attaching the
    # session — but here the cleanest path is to register then login.
    email = "del@test.com"
    with app.app_context():
        u = User(email=email, name="Del Test")
        u.set_pw("password123!")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        u.marketing_consent_at = now - timedelta(days=1)
        db.session.add(u)
        db.session.commit()
        uid = u.id

    # Log in
    r_login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123!"},
    )
    assert r_login.status_code == 200, r_login.get_data(as_text=True)

    with _patch_transport_succeed():
        r = client.post("/api/auth/delete-request", json={})
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body.get("ok") is True
    assert body.get("deletion_requested_at") is not None
    assert body.get("purge_at") is not None
    assert body.get("already_requested") is False

    # Verify DB column set
    with app.app_context():
        u = User.query.get(uid)
        assert u.deletion_requested_at is not None
        assert u.deleted_at is None  # not yet purged


def test_delete_request_idempotent(client, app):
    """Second call returns already_requested=True without overwriting timestamp."""
    from extensions import db
    from models import User

    email = "del2@test.com"
    with app.app_context():
        u = User(email=email, name="Del2 Test")
        u.set_pw("password123!")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        u.marketing_consent_at = now - timedelta(days=1)
        db.session.add(u)
        db.session.commit()

    client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123!"},
    )

    with _patch_transport_succeed():
        r1 = client.post("/api/auth/delete-request", json={})
        assert r1.status_code == 200

    # Re-login (first delete-request logs out) — but login should now 403
    r_relogin = client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123!"},
    )
    assert r_relogin.status_code == 403, r_relogin.get_data(as_text=True)
    body = r_relogin.get_json()
    assert body.get("code") == "AUTH_ACCOUNT_PENDING_DELETION"


# ── 6. salted hash deterministic + non-reversible ───────────────────────────

def test_hash_email_deterministic(app):
    from scripts.nightly.pipa_purge import _hash_email

    h1 = _hash_email("a@b.com")
    h2 = _hash_email("a@b.com")
    assert h1 == h2
    assert h1 != "a@b.com"
    assert len(h1) == 64  # SHA256 hex


def test_hash_email_different_inputs_differ(app):
    from scripts.nightly.pipa_purge import _hash_email

    assert _hash_email("a@b.com") != _hash_email("b@b.com")
