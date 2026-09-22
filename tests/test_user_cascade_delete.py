"""Integration tests — User row cascade delete (PIPA §35 ④).

Migration ``029_user_cascade_delete`` adds ``ON DELETE CASCADE`` to ten
user-owned FKs and ``ON DELETE SET NULL`` to one. The
``routes/auth.py:delete_account`` handler still issues explicit per-model
deletes (defense in depth), but the DB-level cascade covers:

  - Race conditions where a half-failed explicit delete leaves orphans.
  - Direct ``DELETE FROM users WHERE id=...`` from ops scripts or
    admin tools that bypass the application layer.
  - Future model additions whose explicit-delete entry someone forgets
    to add to ``delete_account`` (the FK still pulls them along).

The tests below seed a row in each user-owned table, issue a *raw*
``DELETE FROM users`` (bypassing the application loop), and assert that
all dependent rows are removed (CASCADE) or anonymised (SET NULL).

Why a raw DELETE
----------------
Going through ``delete_account`` would test the explicit loop, not the
DB cascade. To prove the DB-level safety net works, we have to exercise
the path that bypasses the loop entirely.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text


# ────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────

@pytest.fixture
def cascade_user(app):
    """Create a fresh User and yield (id, email).

    Cleanup is handled by the autouse ``_reset_db`` fixture in conftest.
    """
    from extensions import db
    from models import User

    with app.app_context():
        u = User(
            email=f"cascade-{secrets.token_hex(4)}@example.com",
            name="Cascade Test User",
        )
        u.set_pw("test-password-123!")
        db.session.add(u)
        db.session.commit()
        yield u.id, u.email


@pytest.fixture
def seeded_user(app, cascade_user):
    """User with one row in every user-owned model. Returns (user_id, counts).

    ``counts`` is a dict ``{table_name: 1}`` — every dependent table has
    exactly one row keyed on this user. Used by the cascade tests to
    diff before/after.
    """
    from extensions import db
    from models import (
        Position, Watchlist, TradeHistory, BrokerConnection,
        PushSubscription, PositionDDCheck, Alert, PortfolioShare,
        InvestmentProfile, ObservationNote,
    )
    from models.companion_waitlist import CompanionWaitlist

    user_id, email = cascade_user

    with app.app_context():
        # Position FIRST — PositionDDCheck FKs onto its id.
        position = Position(
            user_id=user_id, ticker="TEST", shares=10.0, avg_cost=100.0,
        )
        db.session.add(position)
        db.session.flush()  # need position.id for the DD check

        rows = [
            Watchlist(user_id=user_id, ticker="WATCH"),
            TradeHistory(user_id=user_id, ticker="TEST", action="BUY",
                          shares=10.0, price_per_share=100.0,
                          total_value=1000.0),
            BrokerConnection(user_id=user_id, broker="alpaca"),
            PushSubscription(
                user_id=user_id,
                endpoint=f"https://example.com/push/{secrets.token_hex(4)}",
                p256dh="dummy_p256dh",
                auth="dummy_auth",
            ),
            PositionDDCheck(user_id=user_id, position_id=position.id),
            ObservationNote(user_id=user_id, body="관찰 노트 캐스케이드 확인",
                            tickers_json='["TEST"]', tags_json="[]",
                            source="journal"),
            Alert(user_id=user_id, ticker="TEST", title="T", message="M"),
            PortfolioShare(
                user_id=user_id,
                token=secrets.token_urlsafe(16),
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            ),
            InvestmentProfile(user_id=user_id),
            CompanionWaitlist(
                email_hash=CompanionWaitlist.hash_email(email),
                user_id=user_id,
            ),
        ]
        db.session.add_all(rows)
        db.session.commit()
        yield user_id


# ────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────

# Table name → "expected behaviour after parent DELETE"
#   "cascade"  — every row referencing the user must vanish.
#   "set_null" — rows survive but ``user_id`` is anonymised to NULL.
_USER_OWNED_TABLES = {
    "positions":           "cascade",
    "watchlist":           "cascade",
    "trade_history":       "cascade",
    "broker_connections":  "cascade",
    "push_subscriptions":  "cascade",
    "position_dd_checks":  "cascade",
    "observation_notes":   "cascade",
    "alerts":              "cascade",
    "portfolio_shares":    "cascade",
    "investment_profiles": "cascade",
    "companion_waitlist":  "set_null",
}


def _row_count(db, table: str, user_id: int) -> int:
    """Count rows in ``table`` whose ``user_id`` column == user_id."""
    sql = text(f"SELECT COUNT(*) FROM {table} WHERE user_id = :uid")
    return db.session.execute(sql, {"uid": user_id}).scalar()


def _row_count_by_id_anywhere(db, table: str, user_id: int) -> int:
    """Count *all* rows that were ever associated with this user.

    Useful for SET NULL tables — after the cascade, ``user_id`` is NULL
    so a normal ``WHERE user_id = :uid`` would miss them. We rely on
    other identifying columns (e.g. email_hash for companion_waitlist).
    """
    if table == "companion_waitlist":
        sql = text("SELECT COUNT(*) FROM companion_waitlist WHERE user_id IS NULL")
        return db.session.execute(sql).scalar()
    return _row_count(db, table, user_id)


# ────────────────────────────────────────────────────────────────────────
# Tests — one per table for clear failure attribution
# ────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("table_name", [
    "positions", "watchlist", "trade_history", "broker_connections",
    "push_subscriptions", "position_dd_checks", "alerts",
    "portfolio_shares", "investment_profiles", "observation_notes",
])
def test_cascade_delete_user_removes(seeded_user, app, table_name):
    """Each user-owned CASCADE table loses its rows when the User is deleted.

    Bypasses ``routes/auth.py:delete_account`` and issues a raw
    ``DELETE FROM users`` so the DB-level cascade is the only thing
    keeping the schema consistent — exactly the "ops script" / partial
    failure path that motivated migration 029.
    """
    from extensions import db

    user_id = seeded_user
    with app.app_context():
        # Pre-condition: exactly one dependent row exists.
        before = _row_count(db, table_name, user_id)
        assert before == 1, (
            f"Test fixture broken — expected 1 row in {table_name} "
            f"for user_id={user_id}, found {before}."
        )

        # Trigger the cascade with a raw DELETE.
        db.session.execute(
            text("DELETE FROM users WHERE id = :uid"), {"uid": user_id},
        )
        db.session.commit()

        after = _row_count(db, table_name, user_id)
        assert after == 0, (
            f"FK ondelete=CASCADE not honoured: {table_name} still has "
            f"{after} row(s) referencing deleted user_id={user_id}."
        )


def test_cascade_delete_user_anonymises_companion_waitlist(seeded_user, app):
    """``companion_waitlist`` retains the row but anonymises ``user_id``.

    Rationale: the waitlist supports anonymous (hashed-email) sign-ups
    and is used for funnel analysis / right-to-erasure via
    ``purge_by_email``. Deleting a user shouldn't drop their waitlist
    expression of interest — only sever the personally-identifying
    link. PIPA-friendly: hashed email survives, user FK does not.
    """
    from extensions import db

    user_id = seeded_user
    with app.app_context():
        # Pre-condition: one row linked to the user.
        before_linked = _row_count(db, "companion_waitlist", user_id)
        assert before_linked == 1

        db.session.execute(
            text("DELETE FROM users WHERE id = :uid"), {"uid": user_id},
        )
        db.session.commit()

        # SET NULL: row is still there but user_id has gone NULL.
        still_linked = _row_count(db, "companion_waitlist", user_id)
        assert still_linked == 0, (
            "user_id should have been NULL'd, not the row dropped."
        )

        anonymised = db.session.execute(
            text(
                "SELECT COUNT(*) FROM companion_waitlist WHERE user_id IS NULL"
            )
        ).scalar()
        assert anonymised == 1, (
            f"Expected 1 anonymised waitlist row after user delete, "
            f"got {anonymised}."
        )


def test_position_cascade_pulls_dd_check(app, cascade_user):
    """Deleting a Position cascades to its DD check (transitive FK).

    ``position_dd_checks.position_id`` → ``positions.id`` is also
    declared ``ondelete=CASCADE`` so a position cleanup pulls the
    checklist along even when the user row stays alive (e.g. user
    closes a position but keeps their account).
    """
    from extensions import db
    from models import Position, PositionDDCheck

    user_id, _ = cascade_user
    with app.app_context():
        position = Position(
            user_id=user_id, ticker="DDX", shares=5.0, avg_cost=50.0,
        )
        db.session.add(position)
        db.session.flush()
        position_id = position.id

        dd = PositionDDCheck(user_id=user_id, position_id=position_id)
        db.session.add(dd)
        db.session.commit()

        before = db.session.execute(
            text("SELECT COUNT(*) FROM position_dd_checks "
                 "WHERE position_id = :pid"),
            {"pid": position_id},
        ).scalar()
        assert before == 1

        # Delete the position (NOT the user) — DD check should vanish.
        db.session.execute(
            text("DELETE FROM positions WHERE id = :pid"),
            {"pid": position_id},
        )
        db.session.commit()

        after = db.session.execute(
            text("SELECT COUNT(*) FROM position_dd_checks "
                 "WHERE position_id = :pid"),
            {"pid": position_id},
        ).scalar()
        assert after == 0, (
            f"position_dd_checks.position_id cascade broken — "
            f"{after} orphan(s) remain after position delete."
        )


def test_explicit_delete_loop_still_works(seeded_user, app):
    """``routes/auth.py:delete_account`` path remains operational.

    The explicit per-model deletes are kept as defense in depth (see the
    comment block in delete_account). This test exercises the same
    sequence in-process to confirm it still works after the FK changes
    — i.e. the explicit deletes don't trip over the new cascade.
    """
    from extensions import db
    from models import (
        Position, Watchlist, TradeHistory, Alert, BrokerConnection,
        PushSubscription, PortfolioShare, InvestmentProfile,
    )
    from models.position_dd_check import PositionDDCheck

    user_id = seeded_user
    with app.app_context():
        # Mirror routes/auth.py:delete_account ordering — DD checks before
        # positions because the test seed creates them paired.
        PositionDDCheck.query.filter_by(user_id=user_id).delete()
        Position.query.filter_by(user_id=user_id).delete()
        Watchlist.query.filter_by(user_id=user_id).delete()
        TradeHistory.query.filter_by(user_id=user_id).delete()
        Alert.query.filter_by(user_id=user_id).delete()
        BrokerConnection.query.filter_by(user_id=user_id).delete()
        PushSubscription.query.filter_by(user_id=user_id).delete()
        PortfolioShare.query.filter_by(user_id=user_id).delete()
        InvestmentProfile.query.filter_by(user_id=user_id).delete()

        # Now delete the user — should succeed (no FK violations).
        db.session.execute(
            text("DELETE FROM users WHERE id = :uid"), {"uid": user_id},
        )
        db.session.commit()

        survivors = db.session.execute(
            text("SELECT COUNT(*) FROM users WHERE id = :uid"),
            {"uid": user_id},
        ).scalar()
        assert survivors == 0


def test_no_orphans_after_user_delete(seeded_user, app):
    """End-to-end sweep — after a user delete, zero orphans across all
    user-owned CASCADE tables.

    This is the PIPA §35 ④ acceptance test: a single ``DELETE FROM users``
    must remove (or anonymise) every record traceable to that user.
    """
    from extensions import db

    user_id = seeded_user
    with app.app_context():
        db.session.execute(
            text("DELETE FROM users WHERE id = :uid"), {"uid": user_id},
        )
        db.session.commit()

        offenders = []
        for table, mode in _USER_OWNED_TABLES.items():
            if mode == "cascade":
                count = _row_count(db, table, user_id)
                if count != 0:
                    offenders.append(f"{table}={count}")
            elif mode == "set_null":
                # Row should still exist but user_id NULL.
                still_linked = _row_count(db, table, user_id)
                if still_linked != 0:
                    offenders.append(
                        f"{table} still linked={still_linked}"
                    )

        assert not offenders, (
            "PIPA §35 ④ violation — user-owned rows survived user delete: "
            f"{offenders}"
        )
