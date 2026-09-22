"""Migration round-trip integrity tests (Wave 10 P3).

Validates that the alembic migration chain is internally consistent:

1. ``alembic upgrade head`` succeeds from an empty DB and produces all
   expected tables/columns.
2. The most recent migrations (024, 025, 026) each support a clean
   ``downgrade -1`` followed by a fresh ``upgrade head`` — i.e. they
   are reversible.

Known limitation — PostgreSQL JSONB columns
-------------------------------------------
Migrations 004 (agent_tasks.payload/result) and 005 (multiple growth
tables) declare columns as ``postgresql.JSONB`` directly via
``sa.Column(postgresql.JSONB(), ...)``. SQLite cannot compile that type,
so this test is **skipped automatically when DATABASE_URL points at
SQLite** (which is the dev/test default). It runs only when an
explicit PostgreSQL ``ROUND_TRIP_DATABASE_URL`` is provided in the
environment, e.g. on a CI job with a Postgres service.

The CI guard for "all migrations apply cleanly" against PostgreSQL
already exists implicitly via the Railway deploy log — this file is
the unit-test counterpart that any developer can run locally once they
have a Postgres DB at hand.
"""
from __future__ import annotations

import os

import pytest
from flask import Flask
from flask_migrate import Migrate, downgrade, upgrade
from sqlalchemy import inspect

from extensions import db


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATIONS_DIR = os.path.join(PROJECT_ROOT, "migrations")


def _round_trip_db_url() -> str | None:
    """Return a Postgres DSN if available, else None.

    We never reuse the ambient DATABASE_URL for this test because the
    standard pytest run uses SQLite (see conftest.py) and the JSONB
    migrations can't be applied there.
    """
    url = os.environ.get("ROUND_TRIP_DATABASE_URL")
    if not url:
        return None
    if not url.startswith(("postgresql://", "postgresql+psycopg2://", "postgresql+psycopg://")):
        return None
    return url


pytestmark = pytest.mark.skipif(
    _round_trip_db_url() is None,
    reason=(
        "Migration round-trip requires PostgreSQL — set "
        "ROUND_TRIP_DATABASE_URL=postgresql://... to run. "
        "SQLite cannot compile postgresql.JSONB columns from "
        "migrations 004 and 005."
    ),
)


@pytest.fixture
def migration_app():
    """Build a minimal Flask app wired only for Flask-Migrate.

    Deliberately *not* using the conftest ``app`` fixture — that one
    calls ``db.create_all()`` which would short-circuit alembic.
    """
    url = _round_trip_db_url()
    assert url, "guarded by pytestmark"

    app = Flask("migration_round_trip_app")
    app.config["SQLALCHEMY_DATABASE_URI"] = url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    Migrate(app, db, directory=MIGRATIONS_DIR)

    # Import models so MetaData is populated (mirrors prod startup).
    with app.app_context():
        from models import User, Position, TradeHistory  # noqa: F401

        # Best-effort clean slate. Round-trip tests need an empty DB.
        engine = db.engine
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"
            )

        yield app

        # Tear down so the next test starts clean.
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"
            )


def _table_names(app: Flask) -> set[str]:
    with app.app_context():
        return set(inspect(db.engine).get_table_names())


def _columns(app: Flask, table: str) -> set[str]:
    with app.app_context():
        return {c["name"] for c in inspect(db.engine).get_columns(table)}


# ── Tests ──────────────────────────────────────────────────────────────────


def test_migration_chain_upgrades_to_head(migration_app: Flask):
    """`alembic upgrade head` from empty DB applies every revision."""
    with migration_app.app_context():
        upgrade(directory=MIGRATIONS_DIR)

    tables = _table_names(migration_app)

    # Spot-check across the chain — one table from early, mid, late.
    assert "users" in tables, "001_initial_schema users table missing"
    assert "artifacts" in tables, "007_artifacts_table missing"
    assert "agent_tasks" in tables, "004_add_agent_tables missing"
    assert "broker_connections" in tables, "broker_connections missing"
    # 054 — 관찰 노트. body 는 EncryptedText(=TEXT 암호문)라 048 류의 폭
    # 문제가 여기서 재발하면 이 줄에서 먼저 걸린다.
    assert "observation_notes" in tables, "054_observation_notes missing"

    # 023 marketing consent + 024 cross-border consent column adds.
    user_cols = _columns(migration_app, "users")
    assert "marketing_consent_at" in user_cols, (
        "023_marketing_consent did not apply"
    )
    assert "cross_border_consent_at" in user_cols, (
        "024_cross_border_consent did not apply"
    )

    # 025 artifact email tracking columns.
    artifact_cols = _columns(migration_app, "artifacts")
    for col in ("opened_at", "bounced_at", "unsubscribed_at", "sg_message_id"):
        assert col in artifact_cols, (
            f"025_artifact_email_tracking missing column {col}"
        )


def test_round_trip_026_db_integrity_constraints(migration_app: Flask):
    """026 adds composite unique constraints + FK indexes; round-trip cleanly."""
    with migration_app.app_context():
        upgrade(directory=MIGRATIONS_DIR)

        # Snapshot post-head state for the constraint we expect 026 to add.
        insp = inspect(db.engine)
        watchlist_uniques = {
            tuple(sorted(uc["column_names"]))
            for uc in insp.get_unique_constraints("watchlist")
        }
        assert ("ticker", "user_id") in watchlist_uniques or (
            "user_id",
            "ticker",
        ) in watchlist_uniques, "026 should add (user_id, ticker) UNIQUE on watchlist"

        # Step back one revision (026 → 025).
        downgrade(directory=MIGRATIONS_DIR, revision="-1")

        insp = inspect(db.engine)
        watchlist_uniques_after = {
            tuple(sorted(uc["column_names"]))
            for uc in insp.get_unique_constraints("watchlist")
        }
        assert ("ticker", "user_id") not in watchlist_uniques_after and (
            "user_id",
            "ticker",
        ) not in watchlist_uniques_after, (
            "026 downgrade left (user_id, ticker) UNIQUE behind"
        )

        # Re-apply head; we should be back to the same shape.
        upgrade(directory=MIGRATIONS_DIR)
        insp = inspect(db.engine)
        watchlist_uniques_final = {
            tuple(sorted(uc["column_names"]))
            for uc in insp.get_unique_constraints("watchlist")
        }
        assert watchlist_uniques == watchlist_uniques_final, (
            "Re-applying 026 produced a different schema than the first run"
        )


def test_round_trip_025_artifact_email_tracking(migration_app: Flask):
    """025 adds 4 columns to artifacts; round-trip cleanly."""
    with migration_app.app_context():
        upgrade(directory=MIGRATIONS_DIR)

        # Move 026 → 025 (so head = 025) — we want to round-trip 025 itself.
        downgrade(directory=MIGRATIONS_DIR, revision="-1")  # 026 → 025
        cols_at_025 = _columns(migration_app, "artifacts")
        assert "sg_message_id" in cols_at_025

        downgrade(directory=MIGRATIONS_DIR, revision="-1")  # 025 → 024
        cols_at_024 = _columns(migration_app, "artifacts")
        assert "sg_message_id" not in cols_at_024, (
            "025 downgrade left sg_message_id behind"
        )
        assert "bounced_at" not in cols_at_024
        assert "unsubscribed_at" not in cols_at_024

        # Walk forward again and confirm we land on the same shape.
        upgrade(directory=MIGRATIONS_DIR)
        cols_final = _columns(migration_app, "artifacts")
        # head adds 026 changes too, but the 025 columns must all be back.
        for col in ("opened_at", "bounced_at", "unsubscribed_at", "sg_message_id"):
            assert col in cols_final, (
                f"Re-upgrade past 025 missing {col}"
            )


def test_round_trip_024_cross_border_consent(migration_app: Flask):
    """024 adds users.cross_border_consent_at; round-trip cleanly."""
    with migration_app.app_context():
        upgrade(directory=MIGRATIONS_DIR)

        # 026 → 025 → 024 → 023.
        downgrade(directory=MIGRATIONS_DIR, revision="-1")
        downgrade(directory=MIGRATIONS_DIR, revision="-1")
        downgrade(directory=MIGRATIONS_DIR, revision="-1")

        cols_at_023 = _columns(migration_app, "users")
        assert "cross_border_consent_at" not in cols_at_023, (
            "024 downgrade left cross_border_consent_at behind"
        )
        assert "marketing_consent_at" in cols_at_023, (
            "023 should still be applied"
        )

        # Walk forward.
        upgrade(directory=MIGRATIONS_DIR)
        cols_final = _columns(migration_app, "users")
        assert "cross_border_consent_at" in cols_final
        assert "marketing_consent_at" in cols_final
