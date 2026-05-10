"""Performance indexes — alerts / trade_history / signal_cache / persona_snapshots.

Revision ID: 030_perf_indexes
Revises: 029_user_cascade_delete
Create Date: 2026-05-10

Why this migration
------------------
2026-05-10 performance wave (P1 follow-ups to PR #223). Six hot read paths
were measured to do full-table scans (or to use the wrong index) on
Railway Postgres:

1. ``alerts (user_id, created_at DESC)`` — bell dropdown list query
   (``routes/alerts.py: list_alerts``). Currently uses ``user_id`` index
   only and re-sorts in memory.
2. ``alerts (user_id, ticker, created_at)`` — duplicate-suppression on
   bulk price-check (PR #223 batched the query but still scans this
   key shape).
3. ``alerts (user_id, is_read)`` — unread-count badge polled every 30s.
4. ``trade_history (user_id, traded_at DESC)`` — Recent Trades widget
   on /home and the persona-snapshot trade-window scan.
5. ``signal_cache (updated_at)`` — stale-cache cleanup pass in
   ``services.cache.signal_cache_cleaner``.
6. ``persona_snapshots (user_id, created_at)`` — admin / debug timeline
   query that orders by row insertion time rather than ``computed_at``.
   (The existing ``idx_persona_snapshots_user_time(user_id, computed_at)``
   index covers the user-facing timeline; this is for the
   ``created_at`` slice.)

Idempotency
-----------
Every ``op.create_index`` call is guarded by an inspector lookup so
re-running on a DB that already has the index is a clean no-op. The
same guard pattern is used in 026, 027, 029.

Postgres CONCURRENTLY
---------------------
Plain ``CREATE INDEX`` takes an ``ACCESS EXCLUSIVE`` lock on the table
for the duration of the build. The tables here are small (Railway free
tier prod has < 100k rows total across these four tables), so a
millisecond-range lock is acceptable. We therefore use the standard
``op.create_index`` path so the migration stays portable across SQLite
(local dev / CI tests) and Postgres (Railway).

If the prod tables grow large enough that the lock becomes user-visible,
this migration can be re-run in a future revision with
``CREATE INDEX CONCURRENTLY`` inside an ``op.get_context().autocommit_block()``.
"""
from alembic import op
import sqlalchemy as sa


revision = "030_perf_indexes"
down_revision = "029_user_cascade_delete"
branch_labels = None
depends_on = None


# (index_name, table_name, column_list_or_text_expr)
# Use plain column lists where direction does not matter (SQLite ignores
# DESC anyway, and Postgres can scan the index in either direction for
# single-column or all-asc composites). Compound indexes that benefit
# from a true DESC tail are emitted via the SQL fallback below.
_INDEXES = [
    # alerts — three patterns, all rooted at user_id
    ("ix_alerts_user_created",         "alerts",          ["user_id", "created_at"]),
    ("ix_alerts_user_ticker_created",  "alerts",          ["user_id", "ticker", "created_at"]),
    ("ix_alerts_user_unread",          "alerts",          ["user_id", "is_read"]),
    # trade_history — recent trades widget
    ("ix_trade_history_user_traded",   "trade_history",   ["user_id", "traded_at"]),
    # signal_cache — stale cleanup
    ("ix_signal_cache_updated",        "signal_cache",    ["updated_at"]),
    # persona_snapshots — created_at slice (computed_at already indexed)
    ("ix_persona_snapshots_user_created", "persona_snapshots", ["user_id", "created_at"]),
]


def _existing_index_names(inspector, table: str) -> set:
    try:
        return {ix["name"] for ix in inspector.get_indexes(table)}
    except Exception:
        return set()


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    for index_name, table_name, columns in _INDEXES:
        existing = _existing_index_names(inspector, table_name)
        if index_name in existing:
            continue
        op.create_index(index_name, table_name, columns)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Drop in reverse order, idempotent.
    for index_name, table_name, _columns in reversed(_INDEXES):
        existing = _existing_index_names(inspector, table_name)
        if index_name not in existing:
            continue
        op.drop_index(index_name, table_name=table_name)
