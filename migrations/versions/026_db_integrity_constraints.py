"""DB integrity P1 — composite unique constraints + FK indexes.

Revision ID: 026_db_integrity_constraints
Revises: 025_artifact_email_tracking
Create Date: 2026-05-03

Why this migration
------------------
Aligns the on-disk schema with what the application has always assumed
but never explicitly enforced:

1. ``watchlist (user_id, ticker)`` UNIQUE — duplicate watchlist entries
   were possible because no DB-level uniqueness existed. Routes deduped
   in Python which races on concurrent inserts and silently leaves
   duplicates.

2. ``broker_connections (user_id, broker)`` UNIQUE — a user can have
   exactly one Alpaca + one KIS row (paper/live distinction lives on
   ``is_paper``). The current code path uses ``.first()`` which would
   pick an arbitrary duplicate if one ever leaked in.

3. FK index coverage — ``user_id`` columns on ``alerts``, ``positions``,
   ``trade_history``, ``broker_connections``, ``watchlist``,
   ``portfolio_shares`` were declared as plain ``ForeignKey`` without
   ``index=True``. Every per-user query (``filter_by(user_id=...)``)
   therefore did a sequential scan on the larger tables. Adding the
   indexes is cheap on SQLite and modest on Postgres; the per-request
   speedup is significant once user count grows.

Why no ``sg_message_id`` UNIQUE
-------------------------------
Migration 025 already created a non-unique ``ix_artifacts_sg_message_id``
index. Promoting it to UNIQUE in this migration would require dropping
+ recreating the index, and the SendGrid webhook contract does not yet
guarantee one event per message id (re-deliveries, retries). Holding off
until the dedupe story is proven in prod — tracked separately.

Idempotency
-----------
Mirrors 021_email_opt_out / 024_cross_border_consent / 025: every
``op.create_*`` call is guarded by an inspector lookup so re-running on
a DB that already has the constraint/index is a clean no-op. SQLite
``op.batch_alter_table`` is used for the UNIQUE constraints because
SQLite cannot ``ALTER TABLE ADD CONSTRAINT`` directly.

Chaining
--------
``down_revision = "025_artifact_email_tracking"``.
"""
from alembic import op
import sqlalchemy as sa


revision = "026_db_integrity_constraints"
down_revision = "025_artifact_email_tracking"
branch_labels = None
depends_on = None


# Indexes to add on FK columns. Naming follows ``ix_<table>_<col>`` —
# the same convention already in use across earlier migrations.
_USER_ID_INDEXES = [
    ("alerts",             "ix_alerts_user_id"),
    ("positions",          "ix_positions_user_id"),
    ("trade_history",      "ix_trade_history_user_id"),
    ("broker_connections", "ix_broker_connections_user_id"),
    ("watchlist",          "ix_watchlist_user_id"),
    ("portfolio_shares",   "ix_portfolio_shares_user_id"),
]


def _existing_index_names(inspector, table: str) -> set:
    try:
        return {ix["name"] for ix in inspector.get_indexes(table)}
    except Exception:
        return set()


def _existing_unique_names(inspector, table: str) -> set:
    """Return UNIQUE constraint *and* unique index names for ``table``.

    SQLite represents UNIQUE constraints as unique indexes, so checking
    ``get_unique_constraints`` alone misses some cases.
    """
    out: set = set()
    try:
        out |= {uc["name"] for uc in inspector.get_unique_constraints(table)}
    except Exception:
        pass
    try:
        out |= {ix["name"] for ix in inspector.get_indexes(table)
                if ix.get("unique")}
    except Exception:
        pass
    return out


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    bind_dialect = conn.dialect.name

    # ── 1. watchlist (user_id, ticker) UNIQUE ──────────────────────────
    wl_uniques = _existing_unique_names(inspector, "watchlist")
    if "uq_watchlist_user_ticker" not in wl_uniques:
        with op.batch_alter_table("watchlist") as batch_op:
            batch_op.create_unique_constraint(
                "uq_watchlist_user_ticker",
                ["user_id", "ticker"],
            )

    # ── 2. broker_connections (user_id, broker) UNIQUE ─────────────────
    bc_uniques = _existing_unique_names(inspector, "broker_connections")
    if "uq_broker_connections_user_broker" not in bc_uniques:
        with op.batch_alter_table("broker_connections") as batch_op:
            batch_op.create_unique_constraint(
                "uq_broker_connections_user_broker",
                ["user_id", "broker"],
            )

    # ── 3. FK indexes on user_id ───────────────────────────────────────
    for table, ix_name in _USER_ID_INDEXES:
        try:
            existing = _existing_index_names(inspector, table)
        except sa.exc.NoSuchTableError:
            # Table missing on a partially-bootstrapped DB — migration
            # for that table runs in an earlier revision; safe to skip
            # since the index would be created by the create_table call
            # rather than this migration.
            continue
        if ix_name in existing:
            continue
        op.create_index(ix_name, table, ["user_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Drop indexes (reverse order, mirror upgrade)
    for table, ix_name in reversed(_USER_ID_INDEXES):
        existing = _existing_index_names(inspector, table)
        if ix_name in existing:
            op.drop_index(ix_name, table_name=table)

    # Drop UNIQUE constraints
    bc_uniques = _existing_unique_names(inspector, "broker_connections")
    if "uq_broker_connections_user_broker" in bc_uniques:
        with op.batch_alter_table("broker_connections") as batch_op:
            batch_op.drop_constraint(
                "uq_broker_connections_user_broker", type_="unique",
            )

    wl_uniques = _existing_unique_names(inspector, "watchlist")
    if "uq_watchlist_user_ticker" in wl_uniques:
        with op.batch_alter_table("watchlist") as batch_op:
            batch_op.drop_constraint(
                "uq_watchlist_user_ticker", type_="unique",
            )
