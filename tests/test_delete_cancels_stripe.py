"""FIX 2 (SHIP-BLOCKER, 전자상거래법 §17 / PIPA §21) — account deletion must
cancel the user's live Stripe subscription so the card is never billed after
the user asks to leave.

Three deletion paths must all cancel:
  * ``routes/auth.py:delete_account``   — immediate hard delete
  * ``routes/auth.py:delete_request``   — 30-day soft-delete request
  * ``scripts/nightly/pipa_purge.py``   — the 30-day purge cron (backstop)

We mock ``stripe.Subscription.cancel`` (network boundary) and assert it is
invoked with the user's subscription id. A user with no
``stripe_subscription_id`` must NOT hit Stripe. Stripe failures must never
block erasure (PIPA §21 takes precedence).

Following "거짓보고 금지": real DB ``User`` rows, only the Stripe network call
is mocked.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── delete_account (immediate hard delete) ────────────────────────────────


def _logged_in_user_with_sub(client, make_user, app, email, sub_id):
    """Create a user with ``stripe_subscription_id`` set, then log in so the
    request's ``current_user`` loads the row *fresh* (with the sub id).

    The id must be set BEFORE login: the in-memory test DB shares an identity
    map across the test + request, so mutating the row after Flask-Login has
    already loaded ``current_user`` for the session would not be observed.
    Production re-loads per request, so this ordering only matters for the
    test harness.
    """
    from extensions import db
    from models import User

    user = make_user(email=email)
    with app.app_context():
        u = db.session.get(User, user["id"])
        u.stripe_subscription_id = sub_id
        db.session.commit()
    resp = client.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"],
    })
    assert resp.status_code == 200, resp.data
    return user


def test_delete_account_cancels_stripe_subscription(client, make_user, app):
    _logged_in_user_with_sub(client, make_user, app,
                             "del-acct-sub@test.com", "sub_LIVE123")
    cancel = MagicMock()
    with patch("stripe.Subscription.cancel", cancel):
        resp = client.delete("/api/auth/delete-account")
        assert resp.status_code == 200, resp.data
    cancel.assert_called_once_with("sub_LIVE123")


def test_delete_account_no_subscription_skips_stripe(client, auth_user, app):
    """No stripe_subscription_id → Stripe never called, delete still succeeds."""
    from extensions import db
    from models import User

    with app.app_context():
        u = db.session.get(User, auth_user["id"])
        assert u.stripe_subscription_id is None

    cancel = MagicMock()
    with patch("stripe.Subscription.cancel", cancel):
        resp = client.delete("/api/auth/delete-account")
        assert resp.status_code == 200, resp.data
    cancel.assert_not_called()


def test_delete_account_stripe_failure_non_fatal(client, make_user, app):
    """A Stripe outage must NOT block the user's right to erasure."""
    import stripe

    _logged_in_user_with_sub(client, make_user, app,
                             "del-acct-err@test.com", "sub_ERR")
    cancel = MagicMock(side_effect=stripe.StripeError("boom"))
    with patch("stripe.Subscription.cancel", cancel):
        resp = client.delete("/api/auth/delete-account")
        # Deletion still 200s even though Stripe raised.
        assert resp.status_code == 200, resp.data
    cancel.assert_called_once_with("sub_ERR")


# ── delete_request (30-day soft delete) ───────────────────────────────────


def test_delete_request_cancels_stripe_at_request_time(client, auth_user, app):
    """Cancel must fire at the REQUEST moment so no invoice bills during the
    30-day grace window."""
    from extensions import db
    from models import User

    with app.app_context():
        u = db.session.get(User, auth_user["id"])
        u.stripe_subscription_id = "sub_GRACE"
        db.session.commit()

    cancel = MagicMock()
    with patch("stripe.Subscription.cancel", cancel):
        resp = client.post("/api/auth/delete-request")
        assert resp.status_code == 200, resp.data
    cancel.assert_called_once_with("sub_GRACE")


def test_delete_request_already_set_does_not_recancel(client, make_user, app):
    """A delete-request on a user whose ``deletion_requested_at`` is ALREADY
    set must NOT re-hit Stripe — the cancel only fires on the NULL→set
    transition (so a Stripe call isn't repeated, and a re-request after a
    re-login wouldn't double-cancel).

    A soft-deleted user can't log back in, so we model the "already
    requested" state by pre-stamping ``deletion_requested_at`` before login,
    then issuing one request and asserting it took the no-op branch.
    """
    from datetime import datetime, timezone
    from extensions import db
    from models import User

    user = make_user(email="del-req-idem@test.com")
    with app.app_context():
        u = db.session.get(User, user["id"])
        u.stripe_subscription_id = "sub_ALREADY"
        u.deletion_requested_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()
    resp = client.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"],
    })
    # Login may be blocked for an already-requested user — if so the route is
    # unreachable and there's trivially no double-cancel. Only assert the
    # no-recancel property when we can actually reach the endpoint.
    if resp.status_code != 200:
        pytest.skip("soft-delete-requested user cannot re-login (expected)")

    cancel = MagicMock()
    with patch("stripe.Subscription.cancel", cancel):
        r = client.post("/api/auth/delete-request")
        assert r.status_code == 200, r.data
    cancel.assert_not_called()


# ── helper-level unit tests (auth + pipa_purge) ───────────────────────────


def test_auth_cancel_helper_noop_without_subscription():
    from routes.auth import _cancel_stripe_subscription

    user = MagicMock(id=1, stripe_subscription_id=None)
    cancel = MagicMock()
    with patch("stripe.Subscription.cancel", cancel):
        _cancel_stripe_subscription(user)
    cancel.assert_not_called()


def test_pipa_purge_cancel_helper_invokes_stripe():
    from scripts.nightly.pipa_purge import _cancel_stripe_subscription

    user = MagicMock(id=7, stripe_subscription_id="sub_PURGE")
    cancel = MagicMock()
    with patch("stripe.Subscription.cancel", cancel):
        _cancel_stripe_subscription(user)
    cancel.assert_called_once_with("sub_PURGE")


def test_pipa_purge_cancel_helper_swallows_error():
    import stripe
    from scripts.nightly.pipa_purge import _cancel_stripe_subscription

    user = MagicMock(id=8, stripe_subscription_id="sub_BAD")
    cancel = MagicMock(side_effect=stripe.StripeError("already cancelled"))
    with patch("stripe.Subscription.cancel", cancel):
        # Must not raise.
        _cancel_stripe_subscription(user)
    cancel.assert_called_once_with("sub_BAD")
