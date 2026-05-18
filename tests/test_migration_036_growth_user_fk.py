"""Tests for migrations/versions/036_growth_user_id_fk_constraint.py.

Verifies external action #16 (HANDOVER v44.9, H-3 audit) end-to-end:

  * Orphan rows (``user_id`` not in ``users.id``) are deleted on upgrade.
  * After upgrade, ``growth_reflections`` + ``growth_scores`` have a real
    FK on ``user_id`` (``ON DELETE CASCADE``).
  * ``DELETE FROM users WHERE id=...`` cascades to both tables.
  * Downgrade drops the FK without restoring the orphan rows.

Test strategy
-------------
The full migration chain (001..036) cannot run against SQLite — migrations
004/005 declare ``postgresql.JSONB`` columns and SQLite can't compile that
type (see ``tests/test_migration_round_trip.py`` for the same gate).

So instead we invoke 036's ``upgrade`` / ``downgrade`` functions directly
against a fresh in-memory SQLite engine that only knows about the three
tables 036 actually touches (``users`` / ``growth_reflections`` /
``growth_scores``). This is the same pattern used by Alembic's own
integration tests when isolating a single revision.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import inspect


# Ensure project root is on sys.path so ``migrations.versions...`` imports.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ── Schema fixture ──────────────────────────────────────────────────────────
@pytest.fixture
def isolated_engine():
    """In-memory SQLite engine with only the tables 036 cares about."""
    engine = sa.create_engine(
        "sqlite:///:memory:",
        future=True,
    )
    # Turn FKs on so cascade behaviour mirrors prod Postgres semantics.
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")

    metadata = sa.MetaData()
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
    )
    # Pre-036 shape (post-020): user_id is a bare Integer, NO FK constraint.
    sa.Table(
        "growth_reflections",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("date", sa.Date(), nullable=False),
    )
    sa.Table(
        "growth_scores",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("date", sa.Date(), nullable=False),
    )
    metadata.create_all(engine)

    yield engine
    engine.dispose()


# ── Migration invocation helpers ────────────────────────────────────────────
def _run_migration(engine, *, direction: str):
    """Drive ``upgrade()`` or ``downgrade()`` from the 036 module.

    Alembic's ``op.*`` helpers need a live ``MigrationContext`` bound to a
    connection. We build one ad-hoc with ``EnvironmentContext`` so we don't
    depend on the full ``flask db ...`` plumbing.
    """
    # Import inside the helper so the module isn't loaded at collection time
    # (which would happen before sys.path is patched on some pytest setups).
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    if "migrations.versions.036_growth_user_id_fk_constraint" in sys.modules:
        mod = importlib.reload(
            sys.modules["migrations.versions.036_growth_user_id_fk_constraint"]
        )
    else:
        mod = importlib.import_module(
            "migrations.versions.036_growth_user_id_fk_constraint"
        )

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        ops = Operations(ctx)
        # Bind the module-global op.* proxy to our local context for the
        # duration of the call. ``Operations.context()`` is the documented
        # entrypoint for this exact use case (per alembic test suite).
        with Operations.context(ctx):
            if direction == "upgrade":
                mod.upgrade()
            elif direction == "downgrade":
                mod.downgrade()
            else:
                raise ValueError(direction)
        conn.commit()


def _has_fk(engine, table: str, column: str) -> bool:
    insp = inspect(engine)
    for fk in insp.get_foreign_keys(table):
        if column in (fk.get("constrained_columns") or []):
            return True
    return False


def _fk_ondelete(engine, table: str, column: str):
    insp = inspect(engine)
    for fk in insp.get_foreign_keys(table):
        if column in (fk.get("constrained_columns") or []):
            return ((fk.get("options") or {}).get("ondelete") or "").upper()
    return None


def _row_count(engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0


# ── Tests ────────────────────────────────────────────────────────────────────
def test_upgrade_adds_fk_with_cascade(isolated_engine):
    """After upgrade, both tables have an ON DELETE CASCADE FK on user_id."""
    # Sanity: pre-upgrade there is no FK.
    assert not _has_fk(isolated_engine, "growth_reflections", "user_id")
    assert not _has_fk(isolated_engine, "growth_scores", "user_id")

    # Seed a real user + one row per table.
    with isolated_engine.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO users (id, email) VALUES (1, 'real@example.com')")
        )
        conn.execute(
            sa.text(
                "INSERT INTO growth_reflections (user_id, date) "
                "VALUES (1, '2026-05-01')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO growth_scores (user_id, date) "
                "VALUES (1, '2026-05-01')"
            )
        )

    _run_migration(isolated_engine, direction="upgrade")

    assert _fk_ondelete(isolated_engine, "growth_reflections", "user_id") == "CASCADE"
    assert _fk_ondelete(isolated_engine, "growth_scores", "user_id") == "CASCADE"
    # Real rows survived.
    assert _row_count(isolated_engine, "growth_reflections") == 1
    assert _row_count(isolated_engine, "growth_scores") == 1


def test_upgrade_deletes_orphan_user_id_zero_rows(isolated_engine):
    """020 backfilled ``user_id=0`` orphans — 036 must delete them on upgrade."""
    with isolated_engine.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO users (id, email) VALUES (1, 'real@example.com')")
        )
        # Real row.
        conn.execute(
            sa.text(
                "INSERT INTO growth_reflections (user_id, date) VALUES "
                "(1, '2026-05-01')"
            )
        )
        # Orphans — both ``user_id=0`` (the 020 backfill marker) and a stray
        # ``user_id=999`` that points at nothing.
        conn.execute(
            sa.text(
                "INSERT INTO growth_reflections (user_id, date) VALUES "
                "(0, '2026-04-01'), (999, '2026-04-02')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO growth_scores (user_id, date) VALUES "
                "(1, '2026-05-01'), (0, '2026-04-01'), (999, '2026-04-02')"
            )
        )

    assert _row_count(isolated_engine, "growth_reflections") == 3
    assert _row_count(isolated_engine, "growth_scores") == 3

    _run_migration(isolated_engine, direction="upgrade")

    # Only the user_id=1 rows survived.
    assert _row_count(isolated_engine, "growth_reflections") == 1
    assert _row_count(isolated_engine, "growth_scores") == 1
    with isolated_engine.connect() as conn:
        surviving = conn.execute(
            sa.text("SELECT user_id FROM growth_reflections")
        ).scalar()
        assert surviving == 1


def test_user_delete_cascades_after_upgrade(isolated_engine):
    """Post-upgrade, deleting a user removes their growth_* rows automatically."""
    with isolated_engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO users (id, email) VALUES "
                "(10, 'a@example.com'), (11, 'b@example.com')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO growth_reflections (user_id, date) VALUES "
                "(10, '2026-05-01'), (10, '2026-05-02'), (11, '2026-05-01')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO growth_scores (user_id, date) VALUES "
                "(10, '2026-05-01'), (11, '2026-05-01')"
            )
        )

    _run_migration(isolated_engine, direction="upgrade")

    # Re-enable PRAGMA foreign_keys on a fresh connection so cascade fires
    # (SQLite's pragma is per-connection).
    with isolated_engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        conn.execute(sa.text("DELETE FROM users WHERE id=10"))
        conn.commit()

        remaining_reflections = conn.execute(
            sa.text("SELECT COUNT(*) FROM growth_reflections")
        ).scalar()
        remaining_scores = conn.execute(
            sa.text("SELECT COUNT(*) FROM growth_scores")
        ).scalar()

    # User 10's 2 reflections + 1 score should be gone; user 11's survives.
    assert remaining_reflections == 1
    assert remaining_scores == 1


def test_upgrade_is_idempotent(isolated_engine):
    """Running upgrade() twice produces the same schema — no duplicate FK."""
    with isolated_engine.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO users (id, email) VALUES (1, 'a@example.com')")
        )

    _run_migration(isolated_engine, direction="upgrade")
    _run_migration(isolated_engine, direction="upgrade")  # 2nd run = no-op path

    # Still exactly one FK on user_id for each table.
    insp = inspect(isolated_engine)
    for table in ("growth_reflections", "growth_scores"):
        user_fks = [
            fk for fk in insp.get_foreign_keys(table)
            if "user_id" in (fk.get("constrained_columns") or [])
        ]
        assert len(user_fks) == 1, (
            f"{table} should have exactly one user_id FK after re-run "
            f"(got {len(user_fks)})"
        )


def test_downgrade_drops_fk_but_keeps_data(isolated_engine):
    """Downgrade removes the FK; surviving rows stay put."""
    with isolated_engine.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO users (id, email) VALUES (1, 'a@example.com')")
        )
        conn.execute(
            sa.text(
                "INSERT INTO growth_reflections (user_id, date) VALUES "
                "(1, '2026-05-01')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO growth_scores (user_id, date) VALUES "
                "(1, '2026-05-01')"
            )
        )

    _run_migration(isolated_engine, direction="upgrade")
    assert _has_fk(isolated_engine, "growth_reflections", "user_id")

    _run_migration(isolated_engine, direction="downgrade")
    assert not _has_fk(isolated_engine, "growth_reflections", "user_id")
    assert not _has_fk(isolated_engine, "growth_scores", "user_id")
    # Data preserved — downgrade does NOT restore deleted orphans, but it
    # also must NOT delete legitimate rows.
    assert _row_count(isolated_engine, "growth_reflections") == 1
    assert _row_count(isolated_engine, "growth_scores") == 1
