"""tests/test_email_preferences_route.py — Wave 10 P2 supplementary coverage.

Existing tests in ``test_email_opt_out.py`` already cover the happy paths
(token round-trip, type=all/earnings flips, missing/invalid token). This
file adds the residual edge cases that were not covered:

  - Expired token (older than ``_MAX_AGE``) → 400.
  - Replay after the user account is deleted → 400 (token still HMAC-valid
    but the embedded uid no longer resolves).
  - Idempotent re-click — second hit on the same link must not error and
    must not produce a different DB state than the first hit.
"""
from __future__ import annotations

import time
from unittest.mock import patch


def test_unsubscribe_expired_token_returns_400(app, raw_client, make_user):
    """A token older than ``_MAX_AGE`` must be rejected.

    We force expiry by reducing ``_MAX_AGE`` for the verify call rather
    than fast-forwarding wall-clock time, which would be flaky.
    """
    from services.email_token import make_unsubscribe_token

    user = make_user(email="expired-token@test.com")
    with app.app_context():
        token = make_unsubscribe_token(user["id"])

    # Patch verify to simulate "token older than max_age" — the
    # serializer raises SignatureExpired which the route must coerce to
    # the same 400 response shape as a tampered token.
    from itsdangerous import SignatureExpired

    def _expired(*args, **kwargs):
        raise SignatureExpired("token expired")

    with patch("services.email_token._serializer") as mock_ser:
        mock_ser.return_value.loads.side_effect = _expired
        resp = raw_client.get(f"/api/email/unsubscribe?token={token}&type=all")

    assert resp.status_code == 400, resp.data
    body = resp.get_data(as_text=True)
    assert "유효하지 않은" in body or "expired" in body.lower()


def test_unsubscribe_replay_after_user_deleted(app, raw_client, make_user):
    """Token mints fine, then the user row is deleted. Replay must 400 cleanly.

    Verifies the route's ``db.session.get(User, uid) is None`` branch
    rather than 500'ing on the missing FK.
    """
    from extensions import db
    from models import User
    from services.email_token import make_unsubscribe_token

    user = make_user(email="deleted-user@test.com")
    with app.app_context():
        token = make_unsubscribe_token(user["id"])
        # Hard-delete the user.
        u = db.session.get(User, user["id"])
        db.session.delete(u)
        db.session.commit()

    resp = raw_client.get(f"/api/email/unsubscribe?token={token}&type=all")
    assert resp.status_code == 400


def test_unsubscribe_idempotent_replay(app, raw_client, make_user):
    """Re-clicking the same link must keep ``email_opt_out = True`` — never
    accidentally toggle it back to False, and never raise."""
    from extensions import db
    from models import User
    from services.email_token import make_unsubscribe_token

    user = make_user(email="idempotent@test.com")
    with app.app_context():
        token = make_unsubscribe_token(user["id"])

    # First click — flips to True.
    r1 = raw_client.get(f"/api/email/unsubscribe?token={token}&type=all")
    assert r1.status_code == 200

    # Second click — must remain True and must not error.
    r2 = raw_client.get(f"/api/email/unsubscribe?token={token}&type=all")
    assert r2.status_code == 200

    with app.app_context():
        u = db.session.get(User, user["id"])
        assert u.email_opt_out is True


def test_unsubscribe_post_with_empty_token_returns_400(raw_client):
    """RFC 8058 POST shape with no token at all → 400, not 500."""
    resp = raw_client.post(
        "/api/email/unsubscribe",
        data="List-Unsubscribe=One-Click",
        content_type="application/x-www-form-urlencoded",
    )
    assert resp.status_code == 400
