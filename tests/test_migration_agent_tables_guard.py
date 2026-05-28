"""Regression — _do_migrations() self-heal guard for agent_worker tables.

SHIP-BLOCKER (2026-05-28): The three agent_worker tables (``agent_tasks``,
``agent_decisions``, ``agent_budget``) have NO SQLAlchemy model class — the
background worker (``agent_worker/worker.py``, ``budget.py``, ``escalation.py``,
``admin_routes.py``, ``scenarios/daily_healthcheck.py``) reads/writes them via
SQLAlchemy Core / raw SQL. They are defined ONLY by alembic migration
004_add_agent_tables.py. Production runs the ``db.create_all() +
_do_migrations()`` self-heal pattern (alembic is not run at runtime), so
``db.create_all()`` never created these tables and every worker query hit a
non-existent table. Confirmed by prod inspector exists=False on Railway Postgres.

``app.py:_do_migrations()`` now creates the three tables (CREATE TABLE IF NOT
EXISTS) with the schema of migration 004. These tests verify:

  1. The guard creates all three tables when absent, with the expected columns.
  2. The guard is idempotent (running twice does not error).
  3. The self-referential ``agent_tasks.parent_task_id`` FK + the
     ``agent_decisions.task_id`` FK chain insert correctly.
  4. The ``risk_score BETWEEN 0 AND 100`` CheckConstraint is enforced.
"""
from __future__ import annotations

import datetime as _dt

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError


_AGENT_TABLES = {"agent_tasks", "agent_decisions", "agent_budget"}

# Column sets from migration 004_add_agent_tables.py.
_EXPECTED_COLUMNS = {
    "agent_tasks": {
        "id", "type", "status", "assigned_to", "payload", "result",
        "description", "parent_task_id", "chain_depth", "risk_score",
        "escalated_at", "approved_by", "created_at", "completed_at",
        "retry_count", "max_retries",
    },
    "agent_decisions": {
        "id", "task_id", "agent", "decision_type", "reasoning",
        "prompt_snapshot", "response_snapshot", "input_tokens",
        "output_tokens", "cost_usd", "confidence", "created_at",
    },
    "agent_budget": {
        "date", "tokens_used", "cost_usd", "daily_cap_usd", "halted",
    },
}


def _drop_agent_tables(db):
    with db.engine.begin() as conn:
        # decisions references tasks → drop child first.
        for t in ("agent_decisions", "agent_tasks", "agent_budget"):
            conn.execute(text(f"DROP TABLE IF EXISTS {t}"))


def test_do_migrations_creates_agent_tables(app):
    """_do_migrations() materialises all three agent_* tables with the 004 schema."""
    from extensions import db
    import app as app_module

    with app.app_context():
        _drop_agent_tables(db)

        app_module._do_migrations()

        insp = inspect(db.engine)
        names = set(insp.get_table_names())
        assert _AGENT_TABLES <= names, (
            f"missing agent tables: {_AGENT_TABLES - names}"
        )

        for table, expected in _EXPECTED_COLUMNS.items():
            cols = {c["name"] for c in insp.get_columns(table)}
            assert expected <= cols, (
                f"{table} schema drift vs migration 004: missing {expected - cols}"
            )


def test_do_migrations_agent_idempotent(app):
    """Running the guard twice is a no-op (no error, tables still present)."""
    from extensions import db
    import app as app_module

    with app.app_context():
        _drop_agent_tables(db)
        app_module._do_migrations()
        app_module._do_migrations()  # must not raise

        insp = inspect(db.engine)
        assert _AGENT_TABLES <= set(insp.get_table_names())


def test_agent_tasks_self_ref_and_decision_chain(app):
    """A child task referencing a parent task, and a decision referencing the
    task, both insert without FK error — verifies the self-ref + CASCADE FKs."""
    from extensions import db
    import app as app_module

    with app.app_context():
        _drop_agent_tables(db)
        app_module._do_migrations()

        with db.engine.begin() as conn:
            parent_id = conn.execute(
                text(
                    "INSERT INTO agent_tasks (type, status) "
                    "VALUES ('parent', 'pending')"
                )
            ).lastrowid
            # Child task with self-referential parent_task_id FK.
            child_id = conn.execute(
                text(
                    "INSERT INTO agent_tasks (type, status, parent_task_id) "
                    "VALUES ('child', 'pending', :p)"
                ),
                {"p": parent_id},
            ).lastrowid
            # Decision referencing the task (task_id FK ON DELETE CASCADE).
            conn.execute(
                text(
                    "INSERT INTO agent_decisions (task_id, agent, decision_type) "
                    "VALUES (:t, 'worker', 'analyze')"
                ),
                {"t": child_id},
            )

        with db.engine.connect() as conn:
            chain = conn.execute(
                text("SELECT parent_task_id FROM agent_tasks WHERE id = :i"),
                {"i": child_id},
            ).scalar()
            dcount = conn.execute(
                text("SELECT COUNT(*) FROM agent_decisions WHERE task_id = :t"),
                {"t": child_id},
            ).scalar()

        assert chain == parent_id
        assert dcount == 1


def test_agent_budget_defaults(app):
    """agent_budget inserts with server defaults (halted=false, caps)."""
    from extensions import db
    import app as app_module

    with app.app_context():
        _drop_agent_tables(db)
        app_module._do_migrations()

        day = _dt.date(2026, 5, 28)
        with db.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO agent_budget (date) VALUES (:d)"),
                {"d": day},
            )
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT tokens_used, daily_cap_usd, halted "
                    "FROM agent_budget WHERE date = :d"
                ),
                {"d": day},
            ).fetchone()

        assert row[0] == 0
        assert float(row[1]) == 5.00
        # halted default false → 0 / False depending on dialect.
        assert not row[2]


def test_agent_tasks_risk_score_check_constraint(app):
    """risk_score BETWEEN 0 AND 100 CheckConstraint rejects out-of-range values."""
    from extensions import db
    import app as app_module

    with app.app_context():
        _drop_agent_tables(db)
        app_module._do_migrations()

        with pytest.raises(IntegrityError):
            with db.engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO agent_tasks (type, status, risk_score) "
                        "VALUES ('bad', 'pending', 150)"
                    )
                )
