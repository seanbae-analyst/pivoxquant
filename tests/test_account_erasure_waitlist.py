"""Erasure removes the user's companion_waitlist email (PIPA §21, 2026-10-09).

``services/account_erasure.purge_user_rows`` used to only NULL
``companion_waitlist.user_id``, leaving ``email_plaintext`` (the raw email)
and ``email_hash`` (unsalted SHA256 — reversible by dictionary) behind.
"""
from __future__ import annotations

from datetime import datetime, timezone


def _waitlist(email, *, user_id=None, plaintext=True):
    from models import CompanionWaitlist
    return CompanionWaitlist(
        email_hash=CompanionWaitlist.hash_email(email),
        email_plaintext=email if plaintext else None,
        email_consent_at=datetime.now(timezone.utc) if plaintext else None,
        user_id=user_id,
    )


def test_erasure_deletes_linked_and_same_email_waitlist_rows(app, make_user):
    from extensions import db
    from models import CompanionWaitlist
    from services.account_erasure import purge_user_rows

    user = make_user(email="erase_me@test.com")
    uid = user["id"]
    with app.app_context():
        db.session.add_all([
            # Signed up while logged in, under another address.
            _waitlist("alias@test.com", user_id=uid),
            # Signed up on the landing page before login — no user_id, but the
            # same address (case/space differences hash the same).
            _waitlist("  Erase_Me@Test.com ", user_id=None),
            # Somebody else — must survive.
            _waitlist("other@test.com", user_id=None),
        ])
        db.session.commit()

        counts, failures = purge_user_rows(uid, "erase_me@test.com")
        db.session.commit()

        assert failures == []
        assert counts["companion_waitlist"] == 2
        left = CompanionWaitlist.query.all()
        assert [w.email_plaintext for w in left] == ["other@test.com"]
        hashes = {w.email_hash for w in left}
        assert CompanionWaitlist.hash_email("erase_me@test.com") not in hashes
        assert CompanionWaitlist.hash_email("alias@test.com") not in hashes


def test_erasure_without_email_still_deletes_linked_rows(app, make_user):
    from extensions import db
    from models import CompanionWaitlist
    from services.account_erasure import purge_user_rows

    user = make_user(email="noemail_path@test.com")
    uid = user["id"]
    with app.app_context():
        db.session.add(_waitlist("linked@test.com", user_id=uid))
        db.session.commit()

        counts, failures = purge_user_rows(uid, None)
        db.session.commit()

        assert failures == []
        assert counts["companion_waitlist"] == 1
        assert CompanionWaitlist.query.count() == 0


def test_erasure_does_not_commit_the_waitlist_delete(app, make_user):
    """purge_user_rows leaves the commit to its caller — so it must not call
    CompanionWaitlist.purge_by_email (which commits) or Session.commit.

    A rollback-based check is impossible here: under pysqlite a released
    SAVEPOINT persists even past ``rollback()`` (the untouched ``watchlist``
    delete behaves the same), so the commit call itself is what we watch.
    """
    from unittest.mock import patch

    from extensions import db
    from models import CompanionWaitlist
    from services.account_erasure import purge_user_rows

    user = make_user(email="nocommit@test.com")
    uid = user["id"]
    with app.app_context():
        db.session.add(_waitlist("nocommit@test.com", user_id=uid))
        db.session.commit()

        session_cls = type(db.session())
        with patch.object(session_cls, "commit", autospec=True) as commit, \
             patch.object(CompanionWaitlist, "purge_by_email",
                          side_effect=AssertionError("commits — not allowed here")):
            counts, failures = purge_user_rows(uid, "nocommit@test.com")
        db.session.rollback()

    assert failures == []
    assert counts["companion_waitlist"] == 1
    assert commit.call_count == 0, "purge_user_rows committed the session"


def test_delete_account_route_purges_waitlist_email(app, client, make_user):
    """End to end through POST /api/auth/delete-account ("지금 삭제")."""
    from extensions import db
    from models import CompanionWaitlist

    user = make_user(email="route_erase@test.com")
    with app.app_context():
        db.session.add(_waitlist("route_erase@test.com", user_id=None))
        db.session.commit()

    login = client.post("/api/auth/login",
                        json={"email": user["email"], "password": user["password"]})
    assert login.status_code == 200, login.data
    resp = client.delete("/api/auth/delete-account")
    assert resp.status_code == 200, resp.get_json()

    with app.app_context():
        assert CompanionWaitlist.query.filter_by(
            email_hash=CompanionWaitlist.hash_email(user["email"])).count() == 0
