"""Email Compliance P0 — E1 + E2 test suite (정통망법 §50).

Covers:
  - The ``users.email_opt_out`` column exists with the correct shape (E1).
  - PATCH ``/api/profile/email-preferences`` happy path (E1).
  - PATCH unauthenticated → 401 (E1).
  - PATCH validation: non-bool body → 400 (E1).
  - End-to-end: setting opt_out=True makes a representative service's
    ``send_email`` return False before contacting any provider (E1).
  - ``services.email_token`` round-trip + tampering rejection (E2).
  - GET ``/api/email/unsubscribe?token=…&type=all`` flips the global flag (E2).
  - GET ``/api/email/unsubscribe?token=…&type=earnings`` flips only the
    per-channel flag (E2).
  - Invalid / missing token → 400 (E2).

All DB checks use the real test SQLite (``conftest`` autouse fixture truncates
between tests). Per the project's "거짓보고 금지" rule we deliberately
exercise the live commit path rather than mocking the session.
"""
from __future__ import annotations

import pytest
from sqlalchemy import inspect


# ── E1: column shape ────────────────────────────────────────────────────────


def test_email_opt_out_column_exists(app):
    """Migration 020 must have provisioned the column with the correct shape.

    We inspect the live ``users`` table — if the column is missing or
    nullable, every artefact email service's opt-out short-circuit is
    silently dead code.
    """
    from extensions import db

    with app.app_context():
        cols = {c["name"]: c for c in inspect(db.engine).get_columns("users")}
        assert "email_opt_out" in cols, (
            "users.email_opt_out missing — migration 020 did not run"
        )
        col = cols["email_opt_out"]
        # SQLAlchemy reports the SQL type — Boolean materialises as
        # BOOLEAN on SQLite.
        type_str = str(col["type"]).upper()
        assert "BOOL" in type_str, f"unexpected type: {type_str}"
        assert col["nullable"] is False, (
            "users.email_opt_out must be NOT NULL — opt-out reads must "
            "never see SQL NULL"
        )


def test_email_opt_out_default_false(app, make_user):
    """A freshly created user must default to receiving email."""
    from extensions import db
    from models import User

    user = make_user(email="default-optout@test.com")
    with app.app_context():
        u = db.session.get(User, user["id"])
        assert u is not None
        assert u.email_opt_out is False
        assert u.email_opt_out_earnings is False


# ── E1: PATCH /api/profile/email-preferences ────────────────────────────────


def test_patch_email_preferences_unauthenticated_401(client):
    """Unauthenticated PATCH must be blocked by ``@api_auth``."""
    resp = client.patch(
        "/api/profile/email-preferences",
        json={"email_opt_out": True},
    )
    assert resp.status_code == 401


def test_patch_email_preferences_happy_path(app, client, auth_user):
    """A logged-in user can flip both flags in one request."""
    from extensions import db
    from models import User

    resp = client.patch(
        "/api/profile/email-preferences",
        json={
            "email_opt_out": True,
            "email_opt_out_earnings": True,
        },
    )
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["ok"] is True
    assert body["preferences"]["email_opt_out"] is True
    assert body["preferences"]["email_opt_out_earnings"] is True

    # Verify the changes were committed (not just echoed back).
    with app.app_context():
        u = db.session.get(User, auth_user["id"])
        assert u.email_opt_out is True
        assert u.email_opt_out_earnings is True


def test_patch_email_preferences_partial_update(app, client, auth_user):
    """Omitted keys must leave the matching column unchanged."""
    from extensions import db
    from models import User

    # Pre-flight: set the earnings flag true (via PATCH so we go through
    # the same session the route uses — bypassing session-isolation
    # quirks between a direct ``db.session.get()`` write and the
    # request handler's own session).
    resp = client.patch(
        "/api/profile/email-preferences",
        json={"email_opt_out_earnings": True},
    )
    assert resp.status_code == 200, resp.data
    assert resp.get_json()["preferences"]["email_opt_out_earnings"] is True

    # Now PATCH only the GLOBAL flag — the earnings flag must stay True.
    resp = client.patch(
        "/api/profile/email-preferences",
        json={"email_opt_out": True},
    )
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["preferences"]["email_opt_out"] is True
    # The earnings flag was untouched by this second PATCH.
    assert body["preferences"]["email_opt_out_earnings"] is True

    # Sanity: changes persisted.
    with app.app_context():
        u = db.session.get(User, auth_user["id"])
        assert u.email_opt_out is True
        assert u.email_opt_out_earnings is True


def test_patch_email_preferences_rejects_non_bool(client, auth_user):
    """Non-bool inputs are rejected with HTTP 400."""
    resp = client.patch(
        "/api/profile/email-preferences",
        json={"email_opt_out": "yes"},
    )
    assert resp.status_code == 400
    assert "boolean" in resp.get_json()["error"]


def test_patch_email_preferences_rejects_empty_body(client, auth_user):
    """Empty body is rejected — at least one flag must be supplied."""
    resp = client.patch("/api/profile/email-preferences", json={})
    assert resp.status_code == 400


# ── E1: end-to-end — opt-out short-circuits a real service's send_email ─────


def test_send_email_short_circuits_when_opted_out(app, make_user):
    """When ``email_opt_out=True`` the service returns False before
    touching SendGrid / SMTP — no env vars, no network."""
    from extensions import db
    from models import User
    from services.artifacts.weekly_memo_service import WeeklyMemoService

    user = make_user(email="optout-e2e@test.com")
    with app.app_context():
        u = db.session.get(User, user["id"])
        u.email_opt_out = True
        db.session.commit()

        sent = WeeklyMemoService().send_email(
            u, pdf_bytes=None, html_body="<p>body</p>"
        )
        assert sent is False, (
            "send_email must return False when the user has opted out"
        )


# ── E2: token round-trip ────────────────────────────────────────────────────


def test_token_round_trip(app):
    """A freshly minted token verifies back to the same user-id."""
    from services.email_token import (
        make_unsubscribe_token,
        verify_unsubscribe_token,
    )

    with app.app_context():
        tok = make_unsubscribe_token(42)
        assert isinstance(tok, str)
        assert verify_unsubscribe_token(tok) == 42


def test_token_tamper_rejected(app):
    """A flipped character invalidates the signature → returns None."""
    from services.email_token import (
        make_unsubscribe_token,
        verify_unsubscribe_token,
    )

    with app.app_context():
        tok = make_unsubscribe_token(99)
        # Flip the first char to break the HMAC signature.
        bad = ("a" if tok[0] != "a" else "b") + tok[1:]
        assert verify_unsubscribe_token(bad) is None


def test_token_garbage_rejected(app):
    """Random garbage must return None, not raise."""
    from services.email_token import verify_unsubscribe_token

    with app.app_context():
        assert verify_unsubscribe_token("") is None
        assert verify_unsubscribe_token("not-a-real-token") is None


# ── E2: GET /api/email/unsubscribe ──────────────────────────────────────────


def test_unsubscribe_global_flips_email_opt_out(app, raw_client, make_user):
    """Hitting the unsubscribe link with ``type=all`` sets the global flag."""
    from extensions import db
    from models import User
    from services.email_token import make_unsubscribe_token

    user = make_user(email="unsub-all@test.com")
    with app.app_context():
        token = make_unsubscribe_token(user["id"])

    resp = raw_client.get(f"/api/email/unsubscribe?token={token}&type=all")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "수신거부 완료" in body
    assert resp.headers["Content-Type"].startswith("text/html")

    with app.app_context():
        u = db.session.get(User, user["id"])
        assert u.email_opt_out is True
        # Earnings flag should NOT be flipped — `type=all` is the global path.
        assert u.email_opt_out_earnings is False


def test_unsubscribe_earnings_flips_only_earnings(app, raw_client, make_user):
    """``type=earnings`` flips only the per-channel flag."""
    from extensions import db
    from models import User
    from services.email_token import make_unsubscribe_token

    user = make_user(email="unsub-earnings@test.com")
    with app.app_context():
        token = make_unsubscribe_token(user["id"])

    resp = raw_client.get(
        f"/api/email/unsubscribe?token={token}&type=earnings"
    )
    assert resp.status_code == 200

    with app.app_context():
        u = db.session.get(User, user["id"])
        assert u.email_opt_out is False
        assert u.email_opt_out_earnings is True


def test_unsubscribe_unknown_type_defaults_to_all(app, raw_client, make_user):
    """Unknown ``type`` values are coerced to the safer 'all' default."""
    from extensions import db
    from models import User
    from services.email_token import make_unsubscribe_token

    user = make_user(email="unsub-unknown@test.com")
    with app.app_context():
        token = make_unsubscribe_token(user["id"])

    resp = raw_client.get(f"/api/email/unsubscribe?token={token}&type=foo")
    assert resp.status_code == 200

    with app.app_context():
        u = db.session.get(User, user["id"])
        assert u.email_opt_out is True


def test_unsubscribe_missing_token_400(raw_client):
    """No token → 400, no DB writes."""
    resp = raw_client.get("/api/email/unsubscribe")
    assert resp.status_code == 400
    assert "유효하지 않은" in resp.get_data(as_text=True)


def test_unsubscribe_invalid_token_400(raw_client):
    """Garbage token → 400."""
    resp = raw_client.get("/api/email/unsubscribe?token=clearly-bogus")
    assert resp.status_code == 400


def test_unsubscribe_unknown_user_400(app, raw_client):
    """A token for a user-id that no longer exists must yield 400."""
    from services.email_token import make_unsubscribe_token

    with app.app_context():
        token = make_unsubscribe_token(999_999_999)

    resp = raw_client.get(f"/api/email/unsubscribe?token={token}&type=all")
    assert resp.status_code == 400


def test_unsubscribe_post_one_click(app, raw_client, make_user):
    """RFC 8058 'List-Unsubscribe-Post: List-Unsubscribe=One-Click' POST."""
    from extensions import db
    from models import User
    from services.email_token import make_unsubscribe_token

    user = make_user(email="unsub-post@test.com")
    with app.app_context():
        token = make_unsubscribe_token(user["id"])

    # Mail clients (Gmail) POST with the same query-param shape.
    resp = raw_client.post(
        f"/api/email/unsubscribe?token={token}&type=all",
        data="List-Unsubscribe=One-Click",
        content_type="application/x-www-form-urlencoded",
    )
    assert resp.status_code == 200

    with app.app_context():
        u = db.session.get(User, user["id"])
        assert u.email_opt_out is True


# ── E2: helper module ───────────────────────────────────────────────────────


def test_inject_unsubscribe_footer_idempotent(app):
    """A body that already contains the URL is left unchanged."""
    from services.email_token import inject_unsubscribe_footer

    url = "https://pivoxquant.com/api/email/unsubscribe?token=abc&type=all"
    html = f"<html><body><a href='{url}'>x</a></body></html>"
    out = inject_unsubscribe_footer(html, url)
    # Idempotent — only one reference to the URL after injection.
    assert out.count(url) == 1


def test_inject_unsubscribe_footer_inserts_before_body_close(app):
    """Footer is inserted right before ``</body>``."""
    from services.email_token import inject_unsubscribe_footer

    url = "https://pivoxquant.com/api/email/unsubscribe?token=def&type=all"
    html = "<html><body><p>hi</p></body></html>"
    out = inject_unsubscribe_footer(html, url)
    assert url in out
    assert out.endswith("</body></html>")
    # The inserted snippet sits before </body>, not after.
    assert out.index(url) < out.index("</body>")


def test_build_unsubscribe_url_shape(app):
    """The built URL must contain the type query and a non-empty token."""
    from services.email_token import build_unsubscribe_url

    with app.app_context():
        url = build_unsubscribe_url(7, kind="all")

    assert "/api/email/unsubscribe?token=" in url
    assert "&type=all" in url
    # The token must be non-empty (it sits between `token=` and `&type=`).
    token_part = url.split("token=", 1)[1].split("&", 1)[0]
    assert len(token_part) > 10
