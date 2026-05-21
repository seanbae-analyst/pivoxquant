"""Regression — _do_migrations() self-heal guard for anthropic_usage_log.

FIX 2 (2026-05-22): ``anthropic_usage_log`` is NOT an ORM model — it is written
via raw SQL INSERT in services/ai/service.py:_log_usage and is created ONLY by
alembic migration 042_anthropic_usage_log. Production runs the
``db.create_all() + _do_migrations()`` self-heal pattern (alembic is not always
applied), so without a guard in ``_do_migrations()`` the table can be absent on
prod → every INSERT silently fails (except: pass) → nightly Anthropic cost
aggregation is dead.

``app.py:_do_migrations()`` now creates the table (CREATE TABLE IF NOT EXISTS)
with the exact column schema of migration 042. These tests verify:

  1. The guard creates the table when absent, with the migration-042 columns.
  2. The guard is idempotent (running twice does not error).
  3. The raw INSERT used by _log_usage succeeds against the created table.
"""
from __future__ import annotations

import datetime as _dt

import pytest
from sqlalchemy import inspect, text


# Column schema must match migrations/versions/042_anthropic_usage_log.py.
_EXPECTED_COLUMNS = {
    "id",
    "user_id",
    "model",
    "endpoint",
    "input_tokens",
    "output_tokens",
    "created_at",
}


def test_do_migrations_creates_anthropic_usage_log(app):
    """_do_migrations() materialises anthropic_usage_log with the 042 columns."""
    from extensions import db
    import app as app_module

    with app.app_context():
        # Drop the table if a prior test/create_all made it, to assert the
        # guard does the creation itself.
        with db.engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS anthropic_usage_log"))

        app_module._do_migrations()

        insp = inspect(db.engine)
        assert "anthropic_usage_log" in insp.get_table_names()

        cols = {c["name"] for c in insp.get_columns("anthropic_usage_log")}
        assert cols == _EXPECTED_COLUMNS, (
            f"schema drift vs migration 042: {cols ^ _EXPECTED_COLUMNS}"
        )


def test_do_migrations_idempotent(app):
    """Running the guard twice is a no-op (no error, table still present)."""
    from extensions import db
    import app as app_module

    with app.app_context():
        app_module._do_migrations()
        app_module._do_migrations()  # must not raise

        insp = inspect(db.engine)
        assert "anthropic_usage_log" in insp.get_table_names()


def test_log_usage_insert_succeeds_after_guard(app):
    """The raw INSERT shape used by services/ai/service.py:_log_usage works."""
    from extensions import db
    import app as app_module

    with app.app_context():
        app_module._do_migrations()

        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO anthropic_usage_log "
                    "(user_id, model, endpoint, input_tokens, output_tokens, created_at) "
                    "VALUES (:uid, :model, :ep, :in_tok, :out_tok, :ts)"
                ),
                {
                    "uid": None,  # system call — user_id is nullable
                    "model": "claude-haiku-4-5-20251001",
                    "ep": "swot",
                    "in_tok": 123,
                    "out_tok": 45,
                    "ts": _dt.datetime.utcnow(),
                },
            )

        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT user_id, model, endpoint, input_tokens, output_tokens "
                    "FROM anthropic_usage_log"
                )
            ).fetchone()

        assert row is not None
        assert row[0] is None
        assert row[1] == "claude-haiku-4-5-20251001"
        assert row[2] == "swot"
        assert row[3] == 123
        assert row[4] == 45
