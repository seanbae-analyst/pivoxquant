"""Add FK constraint + cascade to growth_reflections.user_id / growth_scores.user_id.

Revision ID: 036_growth_user_id_fk
Revises: 035_user_onboarding_draft
Create Date: 2026-05-19

External action #16 (HANDOVER v44.9, H-3 audit). Migration ``020`` (SEC-005
IDOR fix) added a ``user_id`` column to ``growth_reflections`` and
``growth_scores`` but left it as an unconstrained ``Integer`` — there is no
ForeignKey, no cascade, and existing rows were backfilled with
``user_id = 0`` (orphan / founder bucket) per the 020 docstring.

Today that means:

1. Account deletion (``routes/auth.py:delete_account``) cascades from
   ``users`` via the FKs migration ``029`` added to other user-owned
   tables, but growth_reflections / growth_scores are silently skipped —
   PIPA §35 ④ right-to-erasure leakage. The explicit per-model deletes in
   ``delete_account`` cover this in practice, but the DB-layer defense in
   depth that 029 established is missing here.
2. ``user_id = 0`` orphan rows accumulate forever and are unreachable
   from the application (no User with id=0). They show up in admin/SQL
   exports as ghost rows.

This migration closes both gaps:

- Hard-deletes any orphan rows (``user_id NOT IN (SELECT id FROM users)``)
  in both tables. ``user_id = 0`` rows from the 020 backfill are caught by
  the same predicate since no user has id=0.
- Adds an explicit FK constraint ``user_id -> users.id ON DELETE CASCADE``
  to mirror migration 029's pattern for every other user-owned table.

Idempotency
-----------
- Inspects existing FK metadata before issuing a recreate (see
  ``_existing_fk`` from 029 — replicated locally to keep this migration
  self-contained).
- Orphan DELETE is a no-op when no orphans exist; re-running the migration
  after a partial apply is safe.
- ``batch_alter_table`` is used so SQLite (test suite) and PostgreSQL
  (prod) take the same code path. The SqliteFkSuspender pattern from 029
  is reused — it disables ``PRAGMA foreign_keys`` for the duration of the
  batch table-recreate so child-table reflection doesn't trip on the
  half-rebuilt parent.

Downgrade
---------
Drops the FK constraint only. The orphan rows we deleted are NOT restored
— DELETE is not reversible at the schema level, and the orphans were
already unreachable from the application before the upgrade. Operators
who want a perfect rollback should restore from backup.

Postgres prep
-------------
See ``docs/ops/migration-036-prod-prep.md`` for the prod orphan-count
query operators should run before deploy + the rollback plan.
"""
from alembic import op
import sqlalchemy as sa


revision = "036_growth_user_id_fk"
down_revision = "035_user_onboarding_draft"
branch_labels = None
depends_on = None


# ── Constraint specification ────────────────────────────────────────────────
# Mirrors the (_CASCADE_FKS) shape from 029_user_cascade_delete.py:
# (table, column, ref_table, ref_column, ondelete, fk_name)
_FK_SPECS = [
    (
        "growth_reflections",
        "user_id",
        "users",
        "id",
        "CASCADE",
        "fk_growth_reflections_user_id_users",
    ),
    (
        "growth_scores",
        "user_id",
        "users",
        "id",
        "CASCADE",
        "fk_growth_scores_user_id_users",
    ),
]


_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


# ── Reflection helpers (kept local — no cross-migration import) ─────────────
def _table_exists(inspector, name: str) -> bool:
    try:
        return name in inspector.get_table_names()
    except Exception:
        return False


def _column_exists(inspector, table: str, column: str) -> bool:
    try:
        return any(c["name"] == column for c in inspector.get_columns(table))
    except Exception:
        return False


def _existing_fk(inspector, table: str, column: str):
    """Return the FK dict for ``table.column`` if present, else None."""
    try:
        fks = inspector.get_foreign_keys(table)
    except Exception:
        return None
    for fk in fks:
        cols = fk.get("constrained_columns") or []
        if column in cols:
            return fk
    return None


def _ondelete_matches(fk: dict, desired: str) -> bool:
    options = fk.get("options") or {}
    current = (options.get("ondelete") or "").strip().upper()
    return current == desired.strip().upper()


def _is_sqlite(conn) -> bool:
    return conn.dialect.name == "sqlite"


class _SqliteFkSuspender:
    """Mirrors 029's helper — toggle PRAGMA foreign_keys for SQLite only.

    Without this, batch_alter_table's table-recreate tries to copy rows
    into the staging table while child-table FKs still point at the
    original, tripping ``FOREIGN KEY constraint failed`` mid-batch. The
    pragma is a no-op on every other dialect (Postgres et al.).
    """

    def __init__(self, conn):
        self.conn = conn
        self.was_enabled = False

    def __enter__(self):
        if _is_sqlite(self.conn):
            try:
                self.was_enabled = bool(
                    self.conn.exec_driver_sql("PRAGMA foreign_keys").scalar()
                )
                self.conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            except Exception:
                self.was_enabled = False
        return self

    def __exit__(self, exc_type, exc, tb):
        if _is_sqlite(self.conn) and self.was_enabled:
            try:
                self.conn.exec_driver_sql("PRAGMA foreign_keys=ON")
            except Exception:
                pass
        return False


# ── Orphan cleanup ──────────────────────────────────────────────────────────
def _delete_orphans(conn, table: str) -> int:
    """Delete rows whose user_id has no matching ``users.id``. Returns count."""
    # Probe count first (for the operator-visible structured log).
    count_sql = sa.text(
        f"SELECT COUNT(*) FROM {table} WHERE user_id NOT IN (SELECT id FROM users)"
    )
    try:
        orphan_count = conn.execute(count_sql).scalar() or 0
    except Exception:
        # If the probe itself fails (table missing, etc.) bubble up — the
        # caller's _table_exists guard should have prevented it.
        raise

    if orphan_count == 0:
        return 0

    op.execute(
        sa.text(
            f"DELETE FROM {table} WHERE user_id NOT IN (SELECT id FROM users)"
        )
    )
    return int(orphan_count)


# ── Up / Down ───────────────────────────────────────────────────────────────
def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    with _SqliteFkSuspender(conn):
        for table, column, ref_table, ref_column, ondelete, fk_name in _FK_SPECS:
            if not _table_exists(inspector, table):
                # Empty / partially-bootstrapped DB — skip silently.
                continue
            if not _column_exists(inspector, table, column):
                # 020 didn't run? Bail loudly — we depend on its column.
                raise RuntimeError(
                    f"036_growth_user_id_fk: {table}.{column} missing — "
                    f"migration 020_growth_user_id must run first."
                )
            if not _table_exists(inspector, ref_table):
                # No users table — nothing to reference.
                continue

            # Orphan cleanup BEFORE the FK is applied, otherwise the FK
            # creation itself fails on Postgres ("violates FK constraint").
            _delete_orphans(conn, table)

            existing = _existing_fk(inspector, table, column)
            if existing is not None and _ondelete_matches(existing, ondelete):
                # Already at desired state (a re-run hits this path).
                continue

            existing_name = (existing or {}).get("name") if existing else None
            convention_name = f"fk_{table}_{column}_{ref_table}"

            with op.batch_alter_table(
                table,
                naming_convention=_NAMING_CONVENTION,
            ) as batch_op:
                # If a same-column FK exists (under any name), drop it first.
                if existing is not None:
                    candidates = []
                    if existing_name:
                        candidates.append(existing_name)
                    candidates.append(convention_name)
                    if fk_name not in candidates:
                        candidates.append(fk_name)
                    dropped = False
                    for candidate in candidates:
                        try:
                            batch_op.drop_constraint(candidate, type_="foreignkey")
                            dropped = True
                            break
                        except (ValueError, KeyError):
                            continue
                    if not dropped:
                        raise RuntimeError(
                            f"036_growth_user_id_fk: could not drop existing "
                            f"FK on {table}.{column} (tried: {candidates}). "
                            f"Aborting to avoid a duplicate FK."
                        )

                batch_op.create_foreign_key(
                    fk_name,
                    ref_table,
                    [column],
                    [ref_column],
                    ondelete=ondelete,
                )

            inspector = sa.inspect(conn)


def downgrade() -> None:
    """Drop the FK constraints only.

    Orphan rows we deleted on upgrade are NOT restored (DELETE is not
    reversible). The 020 backfill ``user_id = 0`` semantics are also NOT
    restored — operators who need that shape should restore from backup.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    with _SqliteFkSuspender(conn):
        for table, column, ref_table, _ref_column, _ondelete, fk_name in _FK_SPECS:
            if not _table_exists(inspector, table):
                continue
            existing = _existing_fk(inspector, table, column)
            if existing is None:
                continue
            existing_name = existing.get("name")
            convention_name = f"fk_{table}_{column}_{ref_table}"

            with op.batch_alter_table(
                table,
                naming_convention=_NAMING_CONVENTION,
            ) as batch_op:
                candidates = []
                if existing_name:
                    candidates.append(existing_name)
                candidates.append(convention_name)
                if fk_name not in candidates:
                    candidates.append(fk_name)
                for candidate in candidates:
                    try:
                        batch_op.drop_constraint(candidate, type_="foreignkey")
                        break
                    except (ValueError, KeyError):
                        continue

            inspector = sa.inspect(conn)
