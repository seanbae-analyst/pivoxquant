"""Alerts notification fields, watchlist note, position_dd_checks table.

Revision ID: 022_alerts_watchlist_dd_columns
Revises: 021_email_opt_out
Create Date: 2026-05-03

Why this migration
------------------
Three groups of schema additions were previously kept alive only by the
runtime ``_add_column_if_missing`` patch in ``app.py``:

1. ``alerts`` notification-bell columns
   (``kind`` / ``title`` / ``body`` / ``link`` / ``read_at``)
   added 2026-04-22 to power ``NotificationDropdown`` on the dashboard.

2. ``watchlist.note``
   500-char free-text memo added 2026-04-22.

3. ``position_dd_checks`` whole-table
   T+3 post-entry user-confirmation checklist (``models/position_dd_check.py``).
   Created from ``db.create_all()`` on first boot but with no Alembic
   history — fresh PG instances never went through ``create_all`` once
   migrations took over.

Promoting the runtime patch into an Alembic revision means:
  * ``alembic upgrade head`` on a brand-new PG instance lands the schema
    without depending on the boot-time patch.
  * The runtime patch can be retired in a future deploy once we confirm
    every environment is at-or-past this revision.
  * Schema state is reviewable in version control.

Idempotency
-----------
Each ``ADD COLUMN`` and ``CREATE TABLE`` step inspects current schema
first, mirroring the pattern used in 009 / 021. Re-running the migration
on a DB that already has the columns (because ``app.py``'s runtime
patch beat us to it) is a safe no-op.

Cross-DB safety
---------------
SQLite + PostgreSQL: both supported. We use Alembic's batch operation
implicitly only where strictly required (here we don't — every change
is purely additive ``ADD COLUMN`` / ``CREATE TABLE``).
"""
from alembic import op
import sqlalchemy as sa


revision = "022_alerts_watchlist_dd_columns"
down_revision = "021_email_opt_out"
branch_labels = None
depends_on = None


# Match the model: PositionDDCheck (`models/position_dd_check.py`).
# Keep the column list in lockstep with that file — adding a column here
# without updating the model (or vice versa) is a guaranteed source of
# "table exists but is missing X" boot warnings.
_DD_TABLE = "position_dd_checks"
_DD_COLUMNS = [
    ("financials_checked", "BOOLEAN", "false"),
    ("moat_checked",       "BOOLEAN", "false"),
    ("management_checked", "BOOLEAN", "false"),
    ("valuation_checked",  "BOOLEAN", "false"),
    ("risks_checked",      "BOOLEAN", "false"),
]


def _has_table(inspector, name: str) -> bool:
    try:
        return name in set(inspector.get_table_names())
    except Exception:
        return False


def _has_column(inspector, table: str, col: str) -> bool:
    try:
        return col in {c["name"] for c in inspector.get_columns(table)}
    except Exception:
        return False


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1) alerts — notification-bell columns ────────────────────────────
    if _has_table(inspector, "alerts"):
        if not _has_column(inspector, "alerts", "kind"):
            op.add_column(
                "alerts",
                sa.Column("kind", sa.String(length=40), nullable=True),
            )
        if not _has_column(inspector, "alerts", "title"):
            op.add_column(
                "alerts",
                sa.Column("title", sa.String(length=200), nullable=True),
            )
        if not _has_column(inspector, "alerts", "body"):
            op.add_column(
                "alerts",
                sa.Column("body", sa.Text(), nullable=True),
            )
        if not _has_column(inspector, "alerts", "link"):
            op.add_column(
                "alerts",
                sa.Column("link", sa.String(length=300), nullable=True),
            )
        if not _has_column(inspector, "alerts", "read_at"):
            op.add_column(
                "alerts",
                sa.Column("read_at", sa.DateTime(), nullable=True),
            )

    # 2) watchlist.note ────────────────────────────────────────────────
    if _has_table(inspector, "watchlist"):
        if not _has_column(inspector, "watchlist", "note"):
            op.add_column(
                "watchlist",
                sa.Column("note", sa.String(length=500), nullable=True),
            )

    # 3) position_dd_checks — full table create ────────────────────────
    if not _has_table(inspector, _DD_TABLE):
        op.create_table(
            _DD_TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id", sa.Integer(),
                sa.ForeignKey("users.id"), nullable=False, index=True,
            ),
            sa.Column(
                "position_id", sa.Integer(),
                sa.ForeignKey("positions.id"),
                nullable=False, unique=True, index=True,
            ),
            sa.Column(
                "financials_checked", sa.Boolean(),
                nullable=False, server_default=sa.false(),
            ),
            sa.Column(
                "moat_checked", sa.Boolean(),
                nullable=False, server_default=sa.false(),
            ),
            sa.Column(
                "management_checked", sa.Boolean(),
                nullable=False, server_default=sa.false(),
            ),
            sa.Column(
                "valuation_checked", sa.Boolean(),
                nullable=False, server_default=sa.false(),
            ),
            sa.Column(
                "risks_checked", sa.Boolean(),
                nullable=False, server_default=sa.false(),
            ),
            sa.Column("note", sa.String(length=500), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(), nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at", sa.DateTime(), nullable=False,
                server_default=sa.func.now(),
            ),
        )
    else:
        # Table existed (db.create_all did the work) — backfill any column
        # the model added later. Mirrors the runtime patch in app.py.
        for col, sql_type, default in _DD_COLUMNS:
            if not _has_column(inspector, _DD_TABLE, col):
                # Use Alembic's add_column with proper SQLAlchemy type so
                # both SQLite + PG accept the boolean default literal.
                op.add_column(
                    _DD_TABLE,
                    sa.Column(
                        col, sa.Boolean(),
                        nullable=False,
                        server_default=sa.text(default),
                    ),
                )
        if not _has_column(inspector, _DD_TABLE, "note"):
            op.add_column(
                _DD_TABLE,
                sa.Column("note", sa.String(length=500), nullable=True),
            )


def downgrade() -> None:
    """Reversible — drops only what we added.

    We do NOT touch ``position_dd_checks`` rows the user owns. The
    table is dropped only if the migration created it (we can't tell
    afterwards, so we drop unconditionally — same posture as 011 /
    015 etc.).
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Reverse 3) — drop the table outright.
    if _has_table(inspector, _DD_TABLE):
        op.drop_table(_DD_TABLE)

    # Reverse 2) — watchlist.note.
    if _has_table(inspector, "watchlist") and _has_column(
        inspector, "watchlist", "note"
    ):
        with op.batch_alter_table("watchlist") as batch:
            batch.drop_column("note")

    # Reverse 1) — alerts notification-bell columns.
    if _has_table(inspector, "alerts"):
        for col in ("kind", "title", "body", "link", "read_at"):
            if _has_column(inspector, "alerts", col):
                with op.batch_alter_table("alerts") as batch:
                    batch.drop_column(col)
