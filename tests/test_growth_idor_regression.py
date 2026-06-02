"""SEC-005 — IDOR regression coverage for /api/growth.

Original schema (migration 005_add_growth_tables.py) keyed both
``growth_reflections`` and ``growth_scores`` on ``date`` only — without
a ``user_id`` column. That allowed any authenticated user to read or
update another user's reflection by guessing ``reflection_id``.

Migration 020_growth_user_id.py adds ``user_id`` to both tables and
``agent_worker/growth_routes.py`` now scopes every query by
``current_user.id``. This file pins that contract.

The Flask test app uses ``db.create_all()`` and Growth tables are not
exposed as SQLAlchemy models, so the test creates the two tables it
needs via raw DDL. We model the smallest schema required for the
endpoints under test (no JSONB / Computed columns — SQLite would not
recognise them anyway).
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import text


# ── Helpers ───────────────────────────────────────────────────────────────

_REFLECTIONS_DDL = """
CREATE TABLE IF NOT EXISTS growth_reflections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date DATE NOT NULL,
    questions TEXT NOT NULL,
    answers TEXT,
    mood INTEGER,
    answered_at DATETIME,
    raw_response TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

_SCORES_DDL = """
CREATE TABLE IF NOT EXISTS growth_scores (
    date DATE NOT NULL,
    user_id INTEGER NOT NULL,
    activity_score INTEGER NOT NULL DEFAULT 0,
    reflection_score INTEGER NOT NULL DEFAULT 0,
    streak_days INTEGER NOT NULL DEFAULT 0,
    total_score INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, date)
)
"""

# growth_daily_logs is read by /api/growth/today even though it isn't
# user-scoped (single-tenant founder data). Provision it as an empty
# table so the endpoint's SELECT doesn't blow up.
_DAILY_LOGS_DDL = """
CREATE TABLE IF NOT EXISTS growth_daily_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    type TEXT NOT NULL,
    priorities TEXT,
    motivation TEXT,
    actual_done TEXT,
    raw_response TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""


@pytest.fixture
def growth_tables(app):
    """Provision growth_reflections + growth_scores in the test DB.

    These are not SQLAlchemy models so the autouse ``_reset_db`` fixture
    in conftest cannot truncate them. We DROP-then-CREATE on entry and
    DROP on exit so each test starts from a known plain schema regardless
    of prior state.

    The DROP-before-CREATE is load-bearing, not belt-and-suspenders: the
    session-scoped ``app`` fixture runs ``app.py:_do_migrations()`` at build
    time, which creates ``growth_scores`` with a GENERATED ``total_score``
    column (``CAST(... AS INTEGER) STORED``). A bare ``CREATE TABLE IF NOT
    EXISTS`` would then be a no-op against that generated-column table, so
    the explicit ``INSERT ... total_score`` in ``test_growth_data_is_user_scoped``
    would raise ``cannot INSERT into generated column``. This test only passed
    in the full deterministic suite by accident — an earlier test's teardown
    DROP happened to leave the table absent. Dropping first makes the fixture
    authoritative under isolation and randomized order (pytest-randomly).
    """
    from extensions import db

    with app.app_context():
        # Mirror the teardown DROPs so entry is authoritative too.
        db.session.execute(text("DROP TABLE IF EXISTS growth_reflections"))
        db.session.execute(text("DROP TABLE IF EXISTS growth_scores"))
        db.session.execute(text("DROP TABLE IF EXISTS growth_daily_logs"))
        db.session.execute(text(_REFLECTIONS_DDL))
        db.session.execute(text(_SCORES_DDL))
        db.session.execute(text(_DAILY_LOGS_DDL))
        db.session.commit()
    yield
    with app.app_context():
        db.session.execute(text("DROP TABLE IF EXISTS growth_reflections"))
        db.session.execute(text("DROP TABLE IF EXISTS growth_scores"))
        db.session.execute(text("DROP TABLE IF EXISTS growth_daily_logs"))
        db.session.commit()


def _seed_reflection(app, *, user_id: int, day=None) -> int:
    """Insert a reflection row owned by ``user_id``; return its id.

    ``day`` may be a ``datetime.date`` or an ISO-string. SQLAlchemy will
    pass either form through to SQLite which stores it as TEXT either
    way; passing a ``date`` keeps round-trip parity with the production
    PostgreSQL code path that reads back as ``datetime.date``.
    """
    from datetime import date as _date

    from extensions import db

    if day is None:
        day = _date(2026, 5, 1)

    with app.app_context():
        result = db.session.execute(
            text(
                "INSERT INTO growth_reflections (user_id, date, questions) "
                "VALUES (:uid, :d, :q)"
            ),
            {
                "uid": user_id,
                "d": day,
                "q": json.dumps(["q1", "q2", "q3"]),
            },
        )
        db.session.commit()
        return int(result.lastrowid)


def _login_as(client, user_payload):
    """Log a user in via the standard /api/auth/login flow."""
    resp = client.post(
        "/api/auth/login",
        json={"email": user_payload["email"], "password": user_payload["password"]},
    )
    assert resp.status_code == 200, f"login failed: {resp.data!r}"


# ── Tests ─────────────────────────────────────────────────────────────────

def test_user_b_cannot_update_user_a_reflection(
    growth_tables, client, make_user, app
):
    """User A's reflection_id must be invisible to user B."""
    user_a = make_user(email="a@test.com", password="pw1234567890")
    user_b = make_user(email="b@test.com", password="pw1234567890")

    a_ref_id = _seed_reflection(app, user_id=user_a["id"])

    _login_as(client, user_b)

    resp = client.post(
        "/api/growth/reflect",
        json={
            "reflection_id": a_ref_id,
            "answers": ["hijack-attempt"],
            "mood": 3,
        },
    )
    assert resp.status_code == 404, (
        f"expected 404 for cross-user reflection update, got "
        f"{resp.status_code}: {resp.data!r}"
    )

    # Confirm A's row is unchanged
    from extensions import db
    with app.app_context():
        row = db.session.execute(
            text("SELECT answers FROM growth_reflections WHERE id = :id"),
            {"id": a_ref_id},
        ).fetchone()
    assert row.answers is None, "user B must not be able to mutate user A's reflection"


def test_user_b_today_endpoint_does_not_leak_user_a(
    growth_tables, client, make_user, app
):
    """GET /api/growth/today must only return the caller's reflection."""
    from datetime import date as _date

    user_a = make_user(email="a2@test.com", password="pw1234567890")
    user_b = make_user(email="b2@test.com", password="pw1234567890")

    today_iso = _date.today().isoformat()
    _seed_reflection(app, user_id=user_a["id"], day=today_iso)

    _login_as(client, user_b)

    resp = client.get("/api/growth/today")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["reflection"] is None, (
        f"user B saw user A's reflection: {data['reflection']!r}"
    )


def test_user_can_update_own_reflection(growth_tables, client, make_user, app):
    """The owner of a reflection_id can still submit answers (positive case)."""
    from datetime import date as _date

    user = make_user(email="own@test.com", password="pw1234567890")
    today_iso = _date.today().isoformat()
    ref_id = _seed_reflection(app, user_id=user["id"], day=today_iso)

    _login_as(client, user)

    resp = client.post(
        "/api/growth/reflect",
        json={
            "reflection_id": ref_id,
            "answers": ["a deeply considered reply about today's work"],
            "mood": 4,
        },
    )
    assert resp.status_code == 200, f"owner update failed: {resp.data!r}"
    payload = resp.get_json()
    assert payload["ok"] is True
    assert payload["reflection_id"] == ref_id

    # Verify the answers landed
    from extensions import db
    with app.app_context():
        row = db.session.execute(
            text("SELECT answers, mood FROM growth_reflections WHERE id = :id"),
            {"id": ref_id},
        ).fetchone()
    assert row.answers is not None
    assert row.mood == 4


def test_growth_data_is_user_scoped(growth_tables, client, make_user, app):
    """GET /api/growth/data must only return rows belonging to the caller."""
    from datetime import date as _date

    from extensions import db

    user_a = make_user(email="a3@test.com", password="pw1234567890")
    user_b = make_user(email="b3@test.com", password="pw1234567890")

    today_iso = _date.today().isoformat()
    with app.app_context():
        # User A has a high score
        db.session.execute(
            text(
                "INSERT INTO growth_scores "
                "(user_id, date, activity_score, reflection_score, streak_days, total_score) "
                "VALUES (:uid, :d, 80, 90, 7, 85)"
            ),
            {"uid": user_a["id"], "d": today_iso},
        )
        # User B has nothing
        db.session.commit()

    _login_as(client, user_b)
    resp = client.get("/api/growth/data?range=7d")
    assert resp.status_code == 200
    rows = resp.get_json()
    assert rows == [], f"user B saw user A's score row: {rows!r}"
