"""Boot-time table creation — one existence query, same tables (2026-10-10).

``app._create_missing_tables`` replaces the bare ``db.create_all()`` on the
boot path. It must still create every model table a database lacks, and it
must not ask the database about each table in turn: on Render Free each of
those questions is a network round trip inside the cold start.
"""
from __future__ import annotations

import flask
import pytest
from sqlalchemy import event, inspect

import app as app_module
from extensions import db


@pytest.fixture()
def boot_app(tmp_path):
    a = flask.Flask("boot-create-missing-tables")
    a.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path / 'boot.sqlite'}"
    a.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(a)
    with a.app_context():
        yield a
        db.session.remove()
        db.engine.dispose()


def _model_tables() -> set[str]:
    return {t.name for t in db.metadata.sorted_tables}


def _count_statements(fn) -> int:
    seen: list[str] = []

    def _before(conn, cursor, statement, params, context, executemany):
        seen.append(statement)

    event.listen(db.engine, "before_cursor_execute", _before)
    try:
        fn()
    finally:
        event.remove(db.engine, "before_cursor_execute", _before)
    return len(seen)


def test_fresh_database_gets_every_model_table(boot_app):
    assert not inspect(db.engine).get_table_names()
    app_module._create_missing_tables()
    assert _model_tables() <= set(inspect(db.engine).get_table_names())


def test_a_missing_table_is_created_again(boot_app):
    app_module._create_missing_tables()
    victim = db.metadata.sorted_tables[-1]  # nothing depends on the last one
    victim.drop(db.engine)
    assert victim.name not in inspect(db.engine).get_table_names()

    app_module._create_missing_tables()
    assert victim.name in inspect(db.engine).get_table_names()


def test_all_present_costs_one_query_not_one_per_table(boot_app):
    app_module._create_missing_tables()
    tables = len(_model_tables())
    assert tables > 30

    batched = _count_statements(app_module._create_missing_tables)
    per_table = _count_statements(db.create_all)
    assert batched <= 2
    assert per_table >= tables


def test_a_failed_batched_check_falls_back_to_create_all(boot_app, monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("catalog read failed")

    # _create_missing_tables imports sqlalchemy.inspect at call time.
    monkeypatch.setattr("sqlalchemy.inspect", _boom)
    app_module._create_missing_tables()
    monkeypatch.undo()
    assert _model_tables() <= set(inspect(db.engine).get_table_names())
