"""Bug NEW-D — positions (user_id, ticker) UNIQUE.

Revision ID: 027_position_unique_user_ticker
Revises: 026_db_integrity_constraints
Create Date: 2026-05-09

Why this migration
------------------
Closes a race window in ``routes/portfolio.py``:

- ``add_position`` (POST /api/portfolio/position)
- ``create_position_alias`` (POST /api/portfolio/positions)
- ``buy_new_position`` (POST /api/portfolio/position/buy-new)

All three handlers do ``Position.query.filter_by(user_id, ticker).first()``
and then either merge into the row or INSERT a new one. Two concurrent
POSTs (mobile retry, double-click, automation) can both pass the SELECT
and both INSERT — silently producing duplicate rows that double-count in
the /api/portfolio summary aggregations.

Migration 026 enforced the same invariant for ``watchlist`` and
``broker_connections``; this revision applies the missing
``positions (user_id, ticker)`` UNIQUE that was deferred at the time.

Pre-flight cleanup
------------------
Before adding the UNIQUE constraint we de-duplicate any existing rows
(very unlikely on prod, but possible if a user double-clicked Add
Position before NEW-D was found). The cleanup keeps the *oldest* row
per ``(user_id, ticker)`` and folds the duplicates into it:

- ``shares`` summed across duplicates
- ``avg_cost`` rebuilt as the share-weighted mean of all duplicates
  (matches the in-route merge math in ``add_position``)
- ``buy_fx_rate`` left at the survivor's value (best-effort; the route
  already special-cases zero / missing FX)
- ``thesis`` / ``thesis_*`` left at the survivor's value (don't lose
  the user's note)

This is a **data mutation**. Operators running ``alembic upgrade`` on
prod should snapshot the ``positions`` table first. The cleanup is
non-reversible — ``downgrade()`` only drops the UNIQUE constraint;
the merged duplicate rows stay merged.

Idempotency
-----------
Mirrors 021/024/025/026: every ``op.create_unique_constraint`` call is
guarded by an inspector lookup so re-running on a DB that already has
the constraint is a clean no-op. The cleanup query is a no-op when no
duplicates exist (``HAVING COUNT(*) > 1`` matches nothing).

Chaining
--------
``down_revision = "026_db_integrity_constraints"``.
"""
from alembic import op
import sqlalchemy as sa


revision = "027_position_unique_user_ticker"
down_revision = "026_db_integrity_constraints"
branch_labels = None
depends_on = None


_CONSTRAINT_NAME = "uq_positions_user_ticker"


def _existing_unique_names(inspector, table: str) -> set:
    """Return UNIQUE constraint *and* unique index names for ``table``.

    SQLite stores UNIQUE constraints as unique indexes, so checking
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


def _cleanup_duplicates(conn) -> int:
    """Merge duplicate (user_id, ticker) rows. Returns rows removed."""
    # Find duplicate keys and the survivor (oldest) row per key.
    dup_rows = conn.execute(sa.text(
        """
        SELECT user_id, ticker, MIN(id) AS survivor_id, COUNT(*) AS n
        FROM positions
        GROUP BY user_id, ticker
        HAVING COUNT(*) > 1
        """
    )).fetchall()

    removed_total = 0
    for user_id, ticker, survivor_id, _n in dup_rows:
        # Pull every row for this key (survivor + duplicates) so we can
        # rebuild a share-weighted avg_cost matching the in-app merge
        # math. Using SQLAlchemy text() so this works on both SQLite +
        # Postgres.
        rows = conn.execute(sa.text(
            """
            SELECT id, shares, avg_cost
            FROM positions
            WHERE user_id = :uid AND ticker = :tkr
            ORDER BY id ASC
            """
        ), {"uid": user_id, "tkr": ticker}).fetchall()

        total_shares = 0.0
        total_notional = 0.0
        for _id, shares, avg_cost in rows:
            s = float(shares or 0)
            c = float(avg_cost or 0)
            total_shares += s
            total_notional += s * c
        new_avg = (total_notional / total_shares) if total_shares else 0.0

        # Update survivor with merged numbers, then delete the rest.
        conn.execute(sa.text(
            """
            UPDATE positions
            SET shares = :shares, avg_cost = :avg_cost
            WHERE id = :sid
            """
        ), {"shares": total_shares, "avg_cost": new_avg, "sid": survivor_id})

        result = conn.execute(sa.text(
            """
            DELETE FROM positions
            WHERE user_id = :uid AND ticker = :tkr AND id <> :sid
            """
        ), {"uid": user_id, "tkr": ticker, "sid": survivor_id})
        # SQLite + Postgres both expose rowcount on DELETE.
        removed_total += result.rowcount or 0

    return removed_total


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # ── 1. Pre-flight cleanup ───────────────────────────────────────────
    # If the constraint is *already* in place we can skip cleanup entirely
    # (no duplicates can exist by construction). This keeps re-runs cheap.
    existing_uniques = _existing_unique_names(inspector, "positions")
    if _CONSTRAINT_NAME not in existing_uniques:
        removed = _cleanup_duplicates(conn)
        if removed:
            # No print() — alembic captures bind-level state. Operators
            # who care about the exact count can run the same SELECT
            # with HAVING COUNT(*) > 1 against a snapshot.
            pass

    # ── 2. Add UNIQUE constraint ────────────────────────────────────────
    if _CONSTRAINT_NAME not in existing_uniques:
        with op.batch_alter_table("positions") as batch_op:
            batch_op.create_unique_constraint(
                _CONSTRAINT_NAME, ["user_id", "ticker"],
            )


def downgrade() -> None:
    """Drop the UNIQUE constraint.

    NOTE: The pre-flight cleanup in ``upgrade()`` permanently merges any
    duplicate rows that existed at upgrade time. ``downgrade`` cannot
    restore them — only the constraint is reversible.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_uniques = _existing_unique_names(inspector, "positions")
    if _CONSTRAINT_NAME in existing_uniques:
        with op.batch_alter_table("positions") as batch_op:
            batch_op.drop_constraint(_CONSTRAINT_NAME, type_="unique")
