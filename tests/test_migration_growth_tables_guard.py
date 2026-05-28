"""Regression — _do_migrations() self-heal guard for Growth OS tables.

SHIP-BLOCKER (2026-05-28): The four Growth OS tables (``growth_daily_logs``,
``growth_reflections``, ``growth_scores``, ``growth_weekly_reports``) have NO
SQLAlchemy model class — ``agent_worker/growth_routes.py`` reads/writes them via
raw SQL. They are defined ONLY by alembic migrations 005/020/036. Production runs
the ``db.create_all() + _do_migrations()`` self-heal pattern (alembic is not run
at runtime), so ``db.create_all()`` never created these tables and the raw SQL in
growth_routes hit non-existent tables → ``/api/growth/{data,today,weekly}`` all
500 → the Growth OS page showed only the "데이터 못 불러왔다" panel. Confirmed by
prod ``to_regclass`` = NULL on Railway Postgres.

``app.py:_do_migrations()`` now creates the four tables (CREATE TABLE IF NOT
EXISTS) with the merged schema of migrations 005 + 020 + 036. These tests verify:

  1. The guard creates all four tables when absent, with the expected columns.
  2. The guard is idempotent (running twice does not error).
  3. ``growth_scores`` has UNIQUE(user_id, date) so the route's
     ``ON CONFLICT (user_id, date)`` upsert works.
  4. The GENERATED ``total_score`` column auto-computes on insert.
  5. The /api/growth endpoints return 200 (empty data) after the guard runs.
"""
from __future__ import annotations

import datetime as _dt

from sqlalchemy import inspect, text


_GROWTH_TABLES = {
    "growth_daily_logs",
    "growth_reflections",
    "growth_scores",
    "growth_weekly_reports",
}

# Merged schema (005 + 020 + 036). Column sets the routes depend on.
_EXPECTED_COLUMNS = {
    "growth_daily_logs": {
        "id", "date", "type", "priorities", "motivation",
        "actual_done", "raw_response", "created_at",
    },
    "growth_reflections": {
        "id", "date", "questions", "answers", "mood",
        "answered_at", "raw_response", "created_at", "user_id",
    },
    "growth_scores": {
        "date", "activity_score", "reflection_score", "streak_days",
        "total_score", "created_at", "user_id",
    },
    "growth_weekly_reports": {
        "id", "week_start", "summary", "patterns", "growth_areas",
        "next_week_suggestions", "week_score", "raw_response", "created_at",
    },
}


def _drop_growth_tables(db):
    with db.engine.begin() as conn:
        for t in _GROWTH_TABLES:
            conn.execute(text(f"DROP TABLE IF EXISTS {t}"))


def test_do_migrations_creates_growth_tables(app):
    """_do_migrations() materialises all four growth_* tables with the merged schema."""
    from extensions import db
    import app as app_module

    with app.app_context():
        _drop_growth_tables(db)

        app_module._do_migrations()

        insp = inspect(db.engine)
        names = set(insp.get_table_names())
        assert _GROWTH_TABLES <= names, (
            f"missing growth tables: {_GROWTH_TABLES - names}"
        )

        for table, expected in _EXPECTED_COLUMNS.items():
            cols = {c["name"] for c in insp.get_columns(table)}
            assert expected <= cols, (
                f"{table} schema drift vs migrations 005/020/036: "
                f"missing {expected - cols}"
            )


def test_do_migrations_growth_idempotent(app):
    """Running the guard twice is a no-op (no error, tables still present)."""
    from extensions import db
    import app as app_module

    with app.app_context():
        _drop_growth_tables(db)
        app_module._do_migrations()
        app_module._do_migrations()  # must not raise

        insp = inspect(db.engine)
        assert _GROWTH_TABLES <= set(insp.get_table_names())


def test_growth_scores_unique_user_date_supports_upsert(app, make_user):
    """growth_scores has UNIQUE(user_id, date) so ON CONFLICT upsert is valid."""
    from extensions import db
    import app as app_module

    with app.app_context():
        _drop_growth_tables(db)
        app_module._do_migrations()

        uid = make_user(email="growth-upsert@test.com")["id"]
        day = _dt.date(2026, 5, 28)

        with db.engine.begin() as conn:
            # First insert.
            conn.execute(
                text(
                    "INSERT INTO growth_scores (user_id, date, reflection_score, streak_days) "
                    "VALUES (:uid, :d, :s, :k)"
                ),
                {"uid": uid, "d": day, "s": 40, "k": 1},
            )
            # ON CONFLICT (user_id, date) upsert — the exact shape used by
            # agent_worker/growth_routes.py:submit_reflection.
            conn.execute(
                text(
                    "INSERT INTO growth_scores (user_id, date, reflection_score, streak_days) "
                    "VALUES (:uid, :d, :s, :k) "
                    "ON CONFLICT (user_id, date) DO UPDATE "
                    "SET reflection_score = :s, streak_days = :k"
                ),
                {"uid": uid, "d": day, "s": 90, "k": 3},
            )

        with db.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT reflection_score, streak_days FROM growth_scores")
            ).fetchall()

        assert len(rows) == 1, "upsert must not create a duplicate row"
        assert rows[0][0] == 90
        assert rows[0][1] == 3


def test_growth_scores_two_users_same_date_no_pk_collision(app, make_user):
    """Two different users submitting on the SAME date must each get their own
    row — no PRIMARY KEY collision.

    Regression for the v1 self-heal DDL bug: ``growth_scores`` used a sole
    ``PRIMARY KEY (date)`` (copied from migration 005). In multi-user prod, the
    second user's ``submit_reflection`` on a shared date hit
    ``UNIQUE constraint failed: growth_scores.date`` → 500. Row identity must be
    the composite ``(user_id, date)``.
    """
    from extensions import db
    import app as app_module

    with app.app_context():
        _drop_growth_tables(db)
        app_module._do_migrations()

        uid_a = make_user(email="growth-multiuser-a@test.com")["id"]
        uid_b = make_user(email="growth-multiuser-b@test.com")["id"]
        day = _dt.date(2026, 5, 28)

        with db.engine.begin() as conn:
            # User A submits first — same upsert shape as submit_reflection.
            conn.execute(
                text(
                    "INSERT INTO growth_scores (user_id, date, reflection_score, streak_days) "
                    "VALUES (:uid, :d, :s, :k) "
                    "ON CONFLICT (user_id, date) DO UPDATE "
                    "SET reflection_score = :s, streak_days = :k"
                ),
                {"uid": uid_a, "d": day, "s": 40, "k": 1},
            )
            # User B submits on the SAME date — must NOT raise a PK collision.
            conn.execute(
                text(
                    "INSERT INTO growth_scores (user_id, date, reflection_score, streak_days) "
                    "VALUES (:uid, :d, :s, :k) "
                    "ON CONFLICT (user_id, date) DO UPDATE "
                    "SET reflection_score = :s, streak_days = :k"
                ),
                {"uid": uid_b, "d": day, "s": 70, "k": 5},
            )

        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT user_id, reflection_score FROM growth_scores "
                    "ORDER BY user_id"
                )
            ).fetchall()

        scores = {r[0]: r[1] for r in rows}
        assert len(rows) == 2, (
            f"both users must keep their own row, got {rows!r}"
        )
        assert scores[uid_a] == 40
        assert scores[uid_b] == 70


def test_growth_scores_total_score_is_generated(app, make_user):
    """total_score is a GENERATED STORED column auto-computed from the inputs."""
    from extensions import db
    import app as app_module

    with app.app_context():
        _drop_growth_tables(db)
        app_module._do_migrations()

        uid = make_user(email="growth-gen@test.com")["id"]
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO growth_scores "
                    "(user_id, date, activity_score, reflection_score, streak_days) "
                    "VALUES (:uid, :d, :a, :r, :k)"
                ),
                {"uid": uid, "d": _dt.date(2026, 5, 28), "a": 50, "r": 60, "k": 40},
            )
            total = conn.execute(
                text("SELECT total_score FROM growth_scores")
            ).scalar()

        # CAST(50*0.4 + 60*0.4 + min(40,30)*0.67) = CAST(20 + 24 + 20.1) = 64
        assert total == 64, f"GENERATED total_score wrong: {total}"


def test_growth_endpoints_200_after_guard(app, client, make_user):
    """The 3 read endpoints that powered the broken panel return 200 once the
    guard has created the tables (empty data, not 500)."""
    from extensions import db
    import app as app_module

    with app.app_context():
        _drop_growth_tables(db)
        app_module._do_migrations()

    user = make_user(email="growth-endpoints@test.com")
    login = client.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"],
    })
    assert login.status_code == 200, login.data

    for path in ("/api/growth/data", "/api/growth/today", "/api/growth/weekly"):
        resp = client.get(path)
        assert resp.status_code == 200, (
            f"{path} returned {resp.status_code}: {resp.data!r}"
        )
