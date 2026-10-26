"""Regression — _enable_rls_on_owned_tables(), the boot-time twin of alembic 056.

Render never runs ``flask db upgrade``, so prod sat at alembic 049 with RLS off
on all 52 public tables (measured 2026-10-25). The boot step enables RLS on
every owned public table that still has it off. PostgreSQL-only, so these tests
drive it with a fake engine that records the SQL it is sent.
"""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy.dialects import postgresql


class _FakeEngine:
    def __init__(self, rls_off, fail_on=()):
        self.rls_off = list(rls_off)
        self.fail_on = set(fail_on)
        self.dialect = postgresql.dialect()
        self.statements = []

    @contextmanager
    def _conn(self):
        engine = self

        class _Conn:
            def execute(self, clause):
                sql = str(clause)
                engine.statements.append(sql)
                if sql.startswith("SELECT tablename"):
                    return [(t,) for t in engine.rls_off]
                for name in engine.fail_on:
                    if f"public.{name} ENABLE" in sql:
                        raise RuntimeError("lock timeout")
                return None

        yield _Conn()

    def connect(self):
        return self._conn()

    def begin(self):
        return self._conn()


def _alters(engine):
    return [s for s in engine.statements if s.startswith("ALTER TABLE")]


def test_enables_rls_on_each_table_reported_off():
    import app as app_module

    engine = _FakeEngine(["users", "trade_history"])
    app_module._enable_rls_on_owned_tables(engine)

    select = engine.statements[0]
    assert "tableowner = current_user" in select
    assert "NOT rowsecurity" in select
    assert _alters(engine) == [
        "ALTER TABLE public.users ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE public.trade_history ENABLE ROW LEVEL SECURITY",
    ]
    assert not any("FORCE" in s for s in engine.statements)


def test_no_alter_when_every_table_already_has_rls():
    import app as app_module

    engine = _FakeEngine([])
    app_module._enable_rls_on_owned_tables(engine)

    assert _alters(engine) == []


def test_quotes_identifiers_that_need_it():
    import app as app_module

    engine = _FakeEngine(["User Notes"])
    app_module._enable_rls_on_owned_tables(engine)

    assert _alters(engine) == [
        'ALTER TABLE public."User Notes" ENABLE ROW LEVEL SECURITY'
    ]


def test_one_failing_table_does_not_stop_the_rest():
    import app as app_module

    engine = _FakeEngine(["alerts", "positions"], fail_on={"alerts"})
    app_module._enable_rls_on_owned_tables(engine)

    assert "ALTER TABLE public.positions ENABLE ROW LEVEL SECURITY" in _alters(engine)


def test_do_migrations_skips_rls_on_sqlite(app, monkeypatch):
    import app as app_module
    from extensions import db

    calls = []
    monkeypatch.setattr(app_module, "_enable_rls_on_owned_tables", calls.append)
    with app.app_context():
        assert db.engine.dialect.name == "sqlite"
        app_module._do_migrations()

    assert calls == []
