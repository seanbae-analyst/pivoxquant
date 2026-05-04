"""Flask extensions — shared across the app."""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()


# ─── SQLite FK enforcement (P0) ────────────────────────────────────────────
# SQLite does NOT enforce FOREIGN KEY constraints by default — every new
# DBAPI connection must run ``PRAGMA foreign_keys=ON`` for ``ondelete``
# CASCADE / SET NULL behaviour to actually trigger.
#
# The dev/test environment uses SQLite (Railway prod uses PostgreSQL where
# this PRAGMA is a no-op / not applicable), so without this listener the
# ``ondelete="CASCADE"`` clauses on ``artifacts.user_id`` and
# ``user_referrals.user_id`` (and any future FK tightening) silently no-op
# locally. That divergence is what hid the orphaned-row bugs that this
# fix wave addresses.
#
# Listening on the global ``Engine`` class catches every connection across
# every Flask-SQLAlchemy bind. The ``isinstance`` guard skips Postgres /
# MySQL connections — the PRAGMA is SQLite-only.
@event.listens_for(Engine, "connect")
def _enable_sqlite_fk(dbapi_connection, _connection_record):
    """Turn on PRAGMA foreign_keys=ON for every SQLite connection."""
    try:
        from sqlite3 import Connection as SQLiteConnection
    except ImportError:  # pragma: no cover — sqlite3 ships with cpython
        return
    if isinstance(dbapi_connection, SQLiteConnection):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()
