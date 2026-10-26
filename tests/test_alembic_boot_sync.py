"""Boot-time alembic record sync — ``app.py::_sync_alembic_version`` (2026-10-26).

Why
===
Render never runs ``flask db upgrade`` (the Procfile ``release:`` line is
Heroku-only), so prod's ``alembic_version`` sat at ``049`` from the 2026-09-01
stamp while the schema itself was kept current by ``db.create_all()`` +
``_do_migrations()``. Only the app's own role owns ``alembic_version``, so the
app fixes the record at boot: stamp head on a create_all-built DB, ``upgrade
head`` when the record is behind.

The rehearsal on a prod-shaped PostgreSQL also showed ``upgrade`` dying at
060 with ``StringDataRightTruncation``: alembic creates ``version_num`` as
VARCHAR(32) and revisions 060/061/062 are 33–38 characters. The boot step
widens the column first (PostgreSQL only — SQLite does not enforce length).

These tests run on the conftest SQLite app. The ``alembic_version`` table is
dropped after each test so the rest of the suite sees the DB it had before.
"""
from __future__ import annotations

import logging
import os
import re
from contextlib import contextmanager

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql

import app as app_module
from extensions import db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSIONS_DIR = os.path.join(PROJECT_ROOT, "migrations", "versions")


def _head(app) -> str:
    from alembic.script import ScriptDirectory

    cfg = app.extensions["migrate"].migrate.get_config()
    return ScriptDirectory.from_config(cfg).get_current_head()


def _versions():
    if not inspect(db.engine).has_table("alembic_version"):
        return None
    with db.engine.connect() as conn:
        return [r[0] for r in conn.execute(text("SELECT version_num FROM alembic_version"))]


def _set_version(version: str) -> None:
    with db.engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"
        ))
        conn.execute(text("DELETE FROM alembic_version"))
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": version})


@pytest.fixture(autouse=True)
def _alembic_table_sandbox(app):
    with app.app_context():
        with db.engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        try:
            yield
        finally:
            with db.engine.begin() as conn:
                conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


def test_a_create_all_schema_is_stamped_at_head(app):
    assert _versions() is None
    root_handlers_before = list(logging.getLogger().handlers)

    app_module._sync_alembic_version(app)

    assert _versions() == [_head(app)]
    # migrations/env.py skips fileConfig() for the in-process run: the app's
    # loggers stay enabled and the root handlers are the ones we had.
    assert logging.getLogger("app").disabled is False
    assert list(logging.getLogger().handlers) == root_handlers_before


def test_a_record_behind_head_is_upgraded(app):
    _set_version("068_monthly_report_sends")

    app_module._sync_alembic_version(app)

    assert _versions() == [_head(app)]
    # 069 adds doorway_checks.opened_at only when missing — create_all already
    # made it, so the upgrade was a no-op on the schema and did not fail.
    cols = {c["name"] for c in inspect(db.engine).get_columns("doorway_checks")}
    assert "opened_at" in cols


def test_at_head_nothing_is_run(app, monkeypatch):
    import alembic.command as alembic_command

    head = _head(app)
    _set_version(head)

    def _boom(*_a, **_k):
        raise AssertionError("alembic command must not run when already at head")

    monkeypatch.setattr(alembic_command, "stamp", _boom)
    monkeypatch.setattr(alembic_command, "upgrade", _boom)

    app_module._sync_alembic_version(app)

    assert _versions() == [head]


def test_a_failing_upgrade_is_logged_and_boot_goes_on(app, monkeypatch, caplog):
    import alembic.command as alembic_command

    _set_version("068_monthly_report_sends")

    def _fail(*_a, **_k):
        raise RuntimeError("simulated migration failure")

    monkeypatch.setattr(alembic_command, "upgrade", _fail)

    with caplog.at_level(logging.ERROR, logger="app"):
        app_module._sync_alembic_version(app)  # must not raise

    assert _versions() == ["068_monthly_report_sends"]
    assert any("alembic: sync failed" in r.getMessage() for r in caplog.records)


def test_two_version_rows_are_left_alone(app, monkeypatch, caplog):
    import alembic.command as alembic_command

    _set_version("068_monthly_report_sends")
    with db.engine.begin() as conn:
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('049_reflection_observed_context')"))

    def _boom(*_a, **_k):
        raise AssertionError("must not run against an ambiguous record")

    monkeypatch.setattr(alembic_command, "stamp", _boom)
    monkeypatch.setattr(alembic_command, "upgrade", _boom)

    with caplog.at_level(logging.ERROR, logger="app"):
        app_module._sync_alembic_version(app)

    assert sorted(_versions()) == ["049_reflection_observed_context", "068_monthly_report_sends"]
    assert any("expected one" in r.getMessage() for r in caplog.records)


def test_the_scoped_session_is_released_before_alembic_runs(app, monkeypatch):
    """The FX backfill at the end of _do_migrations() leaves db.session in an
    open transaction; its ACCESS SHARE lock on positions hung 056's ALTER TABLE
    in the 2026-10-26 Postgres rehearsal. The sync must hand the session back
    first, and run alembic with a lock timeout and without reconfiguring logs."""
    import alembic.command as alembic_command

    db.session.execute(text("SELECT 1"))  # autobegin — like the backfill's SELECT
    assert db.session().in_transaction()

    seen: dict = {}

    def _stamp(config, revision, **_k):
        seen["in_transaction"] = db.session().in_transaction()
        seen["lock_timeout"] = config.attributes.get("lock_timeout")
        seen["skip_logging_config"] = config.attributes.get("skip_logging_config")
        seen["revision"] = revision

    monkeypatch.setattr(alembic_command, "stamp", _stamp)

    app_module._sync_alembic_version(app)

    assert seen == {
        "in_transaction": False,
        "lock_timeout": app_module.ALEMBIC_LOCK_TIMEOUT,
        "skip_logging_config": True,
        "revision": _head(app),
    }


def test_kill_switch_skips_everything(app, monkeypatch):
    monkeypatch.setenv("ALEMBIC_SYNC_ON_BOOT", "0")

    app_module._sync_alembic_version(app)

    assert _versions() is None


def test_run_migrations_calls_the_sync_after_do_migrations(app, monkeypatch):
    order: list[str] = []
    monkeypatch.setattr(app_module, "_do_migrations", lambda: order.append("do_migrations"))
    monkeypatch.setattr(app_module, "_sync_alembic_version", lambda a: order.append("sync"))

    app_module._run_migrations(app)

    assert order == ["do_migrations", "sync"]


# ── version_num width ───────────────────────────────────────────────────────

class _FakeEngine:
    """Records SQL; answers the width query with ``length``."""

    def __init__(self, length, dialect="postgresql"):
        self.length = length
        self.dialect = postgresql.dialect() if dialect == "postgresql" else type("D", (), {"name": dialect})()
        self.statements: list[str] = []

    @contextmanager
    def begin(self):
        engine = self

        class _Conn:
            def execute(self, clause, *a, **k):
                sql = str(clause)
                engine.statements.append(sql)

                class _R:
                    def scalar(_s):
                        return engine.length
                return _R()

        yield _Conn()


def test_narrow_version_column_is_widened_on_postgres():
    engine = _FakeEngine(32)
    app_module._widen_alembic_version_column(engine)
    alters = [s for s in engine.statements if s.startswith("ALTER TABLE")]
    assert alters == [
        f"ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR({app_module.ALEMBIC_VERSION_COLUMN_LENGTH})"
    ]
    # The ALTER waits for its lock only this long (same transaction → SET LOCAL).
    timeouts = [s for s in engine.statements if s.startswith("SET LOCAL lock_timeout")]
    assert timeouts == [f"SET LOCAL lock_timeout = '{app_module.ALEMBIC_LOCK_TIMEOUT}'"]
    assert engine.statements.index(timeouts[0]) < engine.statements.index(alters[0])


@pytest.mark.parametrize("length", [128, 255, None])
def test_wide_or_missing_version_column_is_not_altered(length):
    engine = _FakeEngine(length)
    app_module._widen_alembic_version_column(engine)
    assert not any(s.startswith("ALTER TABLE") for s in engine.statements)


def test_widening_is_postgres_only():
    engine = _FakeEngine(32, dialect="sqlite")
    app_module._widen_alembic_version_column(engine)
    assert engine.statements == []


def test_every_revision_id_fits_the_widened_column():
    ids = []
    for name in sorted(os.listdir(VERSIONS_DIR)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(VERSIONS_DIR, name), encoding="utf-8") as fh:
            m = re.search(r"^revision\s*=\s*['\"]([^'\"]+)['\"]", fh.read(), re.M)
        assert m, name
        ids.append(m.group(1))
    too_long = [i for i in ids if len(i) > app_module.ALEMBIC_VERSION_COLUMN_LENGTH]
    assert too_long == []
    # The reason the column has to be widened at all — keep this list honest.
    over_32 = sorted(i for i in ids if len(i) > 32)
    assert over_32 == [
        "033_normalize_kr_position_tickers",
        "060_trade_history_reflection_link",
        "061_trade_history_reflection_declined",
        "062_investment_profile_rules_confirmed",
    ]
