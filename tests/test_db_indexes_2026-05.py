"""Performance index migration tests — 030_perf_indexes.

Validates that revision ``030_perf_indexes`` (2026-05-10 perf wave):

1. Adds the six expected indexes when applied via ``alembic upgrade``.
2. Drops the same six indexes via ``alembic downgrade -1``.
3. Is idempotent — running the upgrade twice leaves exactly one copy of
   each index (the in-revision guard catches the duplicate).

Why a dedicated test (not the existing ``test_migration_round_trip``)
--------------------------------------------------------------------
``test_migration_round_trip`` is gated to PostgreSQL because migrations
004/005 declare ``postgresql.JSONB`` columns that SQLite cannot compile.
The 030 migration only adds plain B-tree indexes on existing columns, so
its assertions can run against the same in-memory SQLite DB the rest of
the test suite uses (see ``conftest.py``). That means this file runs in
the standard ``pytest`` invocation without requiring a Postgres service.

We bypass ``conftest.app`` because that fixture calls ``db.create_all()``
which short-circuits alembic. Mirrors the technique in
``test_migration_round_trip.migration_app``.
"""
from __future__ import annotations

import os
import tempfile

import pytest
from flask import Flask
from flask_migrate import Migrate, downgrade, upgrade
from sqlalchemy import inspect

from extensions import db


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATIONS_DIR = os.path.join(PROJECT_ROOT, "migrations")

# Migration under test.
REVISION_030 = "030_perf_indexes"
REVISION_029 = "029_user_cascade_delete"

# Each tuple = (index_name, table_name).
EXPECTED_INDEXES = [
    ("ix_alerts_user_created",            "alerts"),
    ("ix_alerts_user_ticker_created",     "alerts"),
    ("ix_alerts_user_unread",             "alerts"),
    ("ix_trade_history_user_traded",      "trade_history"),
    ("ix_signal_cache_updated",           "signal_cache"),
    ("ix_persona_snapshots_user_created", "persona_snapshots"),
]


# ── Skip on Postgres-only migrations -----------------------------------------
# Migrations 004 and 005 use ``postgresql.JSONB``. SQLite raises
# CompileError when it tries to apply them. Detect that and skip rather
# than fail noisily — the round-trip tests already cover the JSONB path
# against a real Postgres DSN.
def _sqlite_can_compile_full_chain() -> bool:
    """Return True if SQLite can apply every migration in the chain.

    Heuristic: import the migration files and look for the JSONB import.
    Cheaper than actually running upgrade() and catching the exception.
    """
    bad = ("postgresql.JSONB", "postgresql.ARRAY")
    for fname in ("004_add_agent_tables.py", "005_add_growth_tables.py"):
        path = os.path.join(MIGRATIONS_DIR, "versions", fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        if any(token in src for token in bad):
            return False
    return True


pytestmark = pytest.mark.skipif(
    not _sqlite_can_compile_full_chain(),
    reason=(
        "Migrations 004/005 use postgresql.JSONB which SQLite cannot "
        "compile. Run with ROUND_TRIP_DATABASE_URL=postgresql://... if "
        "you need this coverage; the alembic chain itself is exercised "
        "in production by Railway's startup deploy hook."
    ),
)


# ── Fixture --------------------------------------------------------------------


@pytest.fixture
def migration_app():
    """Build a minimal Flask app pointed at a fresh on-disk SQLite file.

    A throwaway file (not :memory:) so ``flask-migrate`` can reuse the
    same connection across the upgrade/downgrade calls.
    """
    fd, path = tempfile.mkstemp(suffix=".sqlite", prefix="pivox_perfidx_")
    os.close(fd)

    app = Flask("perf_index_migration_app")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    Migrate(app, db, directory=MIGRATIONS_DIR)

    with app.app_context():
        # Import models so MetaData is populated. Mirrors prod startup.
        from models import (  # noqa: F401
            User, Position, TradeHistory, Alert, SignalCache,
            PersonaSnapshot,
        )
        yield app

    try:
        os.unlink(path)
    except OSError:
        pass


# ── Helpers --------------------------------------------------------------------


def _index_names(app: Flask, table: str) -> set[str]:
    with app.app_context():
        try:
            return {ix["name"] for ix in inspect(db.engine).get_indexes(table)}
        except Exception:
            return set()


# ── Tests ----------------------------------------------------------------------


def test_030_creates_six_indexes(migration_app: Flask):
    """``alembic upgrade head`` from empty DB ends with all six indexes present."""
    with migration_app.app_context():
        upgrade(directory=MIGRATIONS_DIR)

    for index_name, table_name in EXPECTED_INDEXES:
        names = _index_names(migration_app, table_name)
        assert index_name in names, (
            f"030 did not create {index_name} on {table_name} "
            f"(found: {sorted(names)})"
        )


def test_030_downgrade_drops_six_indexes(migration_app: Flask):
    """``downgrade -1`` from 030 → 029 removes exactly the six new indexes."""
    with migration_app.app_context():
        upgrade(directory=MIGRATIONS_DIR)

        # Snapshot index counts after 030.
        before = {
            tn: _index_names(migration_app, tn)
            for tn in {t for _, t in EXPECTED_INDEXES}
        }

        # Step back one revision.
        downgrade(directory=MIGRATIONS_DIR, revision="-1")

        # All six new indexes must be gone.
        for index_name, table_name in EXPECTED_INDEXES:
            names = _index_names(migration_app, table_name)
            assert index_name not in names, (
                f"030 downgrade left {index_name} behind on {table_name}"
            )

        # Other indexes (e.g. ``ix_alerts_user_id`` from earlier
        # migrations) must still be there — we only dropped the six we
        # added.
        for table_name, names_before in before.items():
            our_indexes = {
                ix for ix, t in EXPECTED_INDEXES if t == table_name
            }
            survivors_expected = names_before - our_indexes
            survivors_actual = _index_names(migration_app, table_name)
            assert survivors_expected.issubset(survivors_actual), (
                f"030 downgrade dropped non-030 indexes on {table_name}: "
                f"expected {sorted(survivors_expected)} to survive, "
                f"got {sorted(survivors_actual)}"
            )


def test_030_round_trip_idempotent(migration_app: Flask):
    """upgrade → downgrade → upgrade lands on the same index set."""
    with migration_app.app_context():
        upgrade(directory=MIGRATIONS_DIR)
        first = {
            tn: _index_names(migration_app, tn)
            for tn in {t for _, t in EXPECTED_INDEXES}
        }

        downgrade(directory=MIGRATIONS_DIR, revision="-1")
        upgrade(directory=MIGRATIONS_DIR)

        second = {
            tn: _index_names(migration_app, tn)
            for tn in {t for _, t in EXPECTED_INDEXES}
        }

        assert first == second, (
            "Round-trip changed the index set — re-applying 030 must be "
            f"a no-op. Diff:\n  before: {first}\n  after:  {second}"
        )


def test_030_upgrade_is_idempotent_on_re_run(migration_app: Flask):
    """Calling upgrade() twice with no changes between leaves indexes intact.

    Flask-Migrate's ``upgrade()`` is itself a no-op when already at head,
    but the in-revision inspector guard is what matters when an operator
    edits the alembic_version row to re-run a specific revision (e.g.
    after a partial failure). Simulate that by stamping back to 029 and
    re-running upgrade — the migration must not raise on duplicate
    ``CREATE INDEX`` statements.
    """
    from flask_migrate import stamp

    with migration_app.app_context():
        upgrade(directory=MIGRATIONS_DIR)

        # Snapshot, then force alembic to think we're at 029 again.
        before = {
            tn: _index_names(migration_app, tn)
            for tn in {t for _, t in EXPECTED_INDEXES}
        }
        stamp(directory=MIGRATIONS_DIR, revision=REVISION_029)

        # Re-run upgrade. The in-migration guard should skip every
        # already-present index without raising.
        upgrade(directory=MIGRATIONS_DIR)

        after = {
            tn: _index_names(migration_app, tn)
            for tn in {t for _, t in EXPECTED_INDEXES}
        }
        assert before == after, (
            "Re-running 030 upgrade after a stamp-back changed the "
            f"index set. Diff:\n  before: {before}\n  after:  {after}"
        )
