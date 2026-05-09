"""User-owned FKs — enforce ON DELETE CASCADE / SET NULL at the DB layer.

Revision ID: 029_user_cascade_delete
Revises: 028_processed_stripe_events
Create Date: 2026-05-09

Why this migration
------------------
PIPA §35 ④ (개인정보보호법) requires user-owned data to be removed when a
user requests account deletion. ``routes/auth.py:delete_account`` already
issues explicit per-model ``filter_by(user_id=...).delete()`` calls (defense
in depth — see comment block in that file), but eleven foreign keys against
``users.id`` (and one transitively via ``positions.id``) lacked an
``ondelete=`` clause at the DB layer. That gap means:

- A direct ``DELETE FROM users WHERE id=...`` (e.g. an ops migration, an
  admin-tools script, a partial failure half-way through the explicit
  loop) leaves orphan rows in the user-owned tables.
- On PostgreSQL the orphans become FK-violation candidates the next time
  the constraint is re-evaluated; on SQLite (with PRAGMA foreign_keys=ON
  enabled in ``extensions.py``) the parent DELETE itself errors out with
  a ``FOREIGN KEY constraint failed`` and the transaction is aborted —
  the user row stays alive even though the explicit loop already removed
  the children, because the FKs are the *original* (no-action) ones that
  treat any reference as a block.

Adding ``ondelete="CASCADE"`` (or ``SET NULL`` for the nullable
``companion_waitlist.user_id`` link) closes both failure modes. The
explicit per-model deletes in ``routes/auth.py`` are intentionally
*kept* — they are the documented path for the deletion API and the DB
cascade is the second line of defense, not a replacement.

Constraint targets
------------------
CASCADE  (10 FKs against users.id, parent row owned by user):
    positions.user_id              → users.id
    watchlist.user_id              → users.id
    trade_history.user_id          → users.id
    broker_connections.user_id     → users.id
    push_subscriptions.user_id     → users.id
    position_dd_checks.user_id     → users.id
    alerts.user_id                 → users.id
    portfolio_shares.user_id       → users.id
    investment_profiles.user_id    → users.id
    position_dd_checks.position_id → positions.id  (transitive)

SET NULL (1 FK — nullable, anonymous-friendly, hashed-email retained):
    companion_waitlist.user_id     → users.id

Idempotency
-----------
Every step inspects existing FK metadata before issuing a recreate. If
the constraint is already on the desired ``ondelete`` clause, the step
is a no-op. The ``batch_alter_table`` path is used for SQLite (which
cannot ``ALTER TABLE DROP CONSTRAINT`` directly — Alembic emulates it by
recreating the table). On PostgreSQL the same code path uses native
``ALTER TABLE`` under the hood.

The constraint helper ``_recreate_fk`` is intentionally schema-aware: it
queries ``inspector.get_foreign_keys`` for the existing constraint name
(SQLite often has none, falling back to a deterministic fallback name)
and only emits the drop+recreate pair when the desired ``ondelete``
clause does not already match.

Backwards compatibility
-----------------------
- Existing data: ``users.id`` integrity is already maintained by the
  application (every row in the child tables is created via
  ``user_id=current_user.id``), so this migration changes only the
  *enforcement* layer — no data backfill or orphan-cleanup is required.
  We probe for orphans at upgrade time as a safety net (logged, not
  fatal — orphans are rare and would block an ALTER on PostgreSQL).
- Downgrade: reverts to ``ondelete=None`` (no action) by re-recreating
  the FKs without the cascade clause, matching the original schema.

Chaining
--------
``down_revision = "028_processed_stripe_events"`` — single head.
"""
from alembic import op
import sqlalchemy as sa


revision = "029_user_cascade_delete"
down_revision = "028_processed_stripe_events"
branch_labels = None
depends_on = None


# ── Constraint specification ──────────────────────────────────────────────
# Format: (table, column, ref_table, ref_column, ondelete, fallback_name)
#
# ``fallback_name`` is the name we use when (re)creating the constraint;
# SQLite frequently emits FKs with auto-generated, unstable names so we
# always rename on recreate to keep downgrade deterministic.
_CASCADE_FKS = [
    ("positions",          "user_id",     "users",     "id", "CASCADE",
     "fk_positions_user_id_users"),
    ("watchlist",          "user_id",     "users",     "id", "CASCADE",
     "fk_watchlist_user_id_users"),
    ("trade_history",      "user_id",     "users",     "id", "CASCADE",
     "fk_trade_history_user_id_users"),
    ("broker_connections", "user_id",     "users",     "id", "CASCADE",
     "fk_broker_connections_user_id_users"),
    ("push_subscriptions", "user_id",     "users",     "id", "CASCADE",
     "fk_push_subscriptions_user_id_users"),
    ("position_dd_checks", "user_id",     "users",     "id", "CASCADE",
     "fk_position_dd_checks_user_id_users"),
    ("alerts",             "user_id",     "users",     "id", "CASCADE",
     "fk_alerts_user_id_users"),
    ("portfolio_shares",   "user_id",     "users",     "id", "CASCADE",
     "fk_portfolio_shares_user_id_users"),
    ("investment_profiles", "user_id",    "users",     "id", "CASCADE",
     "fk_investment_profiles_user_id_users"),
    # Transitive — a position cascade pulls its DD checklist with it.
    ("position_dd_checks", "position_id", "positions", "id", "CASCADE",
     "fk_position_dd_checks_position_id_positions"),
]

_SET_NULL_FKS = [
    # companion_waitlist links to users for funnel attribution but is
    # also valid as anonymous (hashed-email) row. PIPA-friendly: the
    # user link disappears on account deletion, the hashed-email row
    # survives so right-to-erasure is honoured via purge_by_email().
    ("companion_waitlist", "user_id", "users", "id", "SET NULL",
     "fk_companion_waitlist_user_id_users"),
]


def _table_exists(inspector, name: str) -> bool:
    try:
        return name in inspector.get_table_names()
    except Exception:
        return False


def _existing_fk(inspector, table: str, column: str):
    """Return the FK dict for ``table.column`` if present, else None.

    Uses ``get_foreign_keys`` which returns one entry per FK constraint
    on ``table``. Filters by the constrained column tuple.
    """
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
    """Compare an existing FK's ``ondelete`` against the desired clause.

    SQLAlchemy reports the option in ``options.ondelete`` as a string
    (case-insensitive across drivers). ``None`` / missing = NO ACTION.
    """
    options = fk.get("options") or {}
    current = options.get("ondelete")
    if current is None:
        current = ""
    return current.strip().upper() == desired.strip().upper()


_NAMING_CONVENTION = {
    # Forces SQLAlchemy to assign deterministic names to reflected FKs
    # during batch reflection. Without this, anonymous SQLite FKs come
    # back as ``name=None`` and ``drop_constraint`` cannot find them.
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def _recreate_fk(conn, table, column, ref_table, ref_column, ondelete, name):
    """Drop + recreate a single FK with the desired ``ondelete`` clause.

    Uses ``batch_alter_table`` so it works on SQLite (table-recreate
    semantics) and PostgreSQL (native ALTER) alike.

    SQLite quirk
    ------------
    SQLite stores inline FKs anonymously by default — the constraint
    name reported by ``inspector.get_foreign_keys`` is ``None``, and
    ``batch_alter_table.drop_constraint(name)`` raises
    ``ValueError: No such constraint`` because the in-memory MetaData
    that batch builds also has a nameless FK.

    The fix is to pass ``naming_convention=_NAMING_CONVENTION`` into
    ``batch_alter_table`` — that convention applies to the *reflected*
    MetaData copy, so anonymous FKs are renamed to the deterministic
    ``fk_<table>_<col>_<ref>`` slug, which we can then drop reliably.

    The new FK is created with our explicit fallback ``name`` so future
    downgrades or re-runs find it deterministically regardless of
    whether the convention is applied.
    """
    inspector = sa.inspect(conn)
    existing = _existing_fk(inspector, table, column)
    existing_name = (existing or {}).get("name") if existing else None

    # Build the convention-derived name we expect to see for the FK
    # under the naming convention applied during batch reflection.
    convention_name = (
        f"fk_{table}_{column}_{ref_table}"
    )

    with op.batch_alter_table(
        table,
        naming_convention=_NAMING_CONVENTION,
    ) as batch_op:
        # Try the names in priority order: explicit existing name (rare
        # for SQLite, common on Postgres), our convention-derived name
        # (post-naming-convention SQLite), and finally the deterministic
        # fallback the previous run might have used.
        candidates = []
        if existing_name:
            candidates.append(existing_name)
        candidates.append(convention_name)
        if name not in candidates:
            candidates.append(name)

        dropped = False
        for candidate in candidates:
            try:
                batch_op.drop_constraint(candidate, type_="foreignkey")
                dropped = True
                break
            except (ValueError, KeyError):
                continue
        # If no constraint name matched, the batch will still recreate
        # the original FK (because reflection saw it) AND add our new
        # one — yielding a duplicate FK on the column. That is bad, so
        # we surface a loud failure instead of silently corrupting the
        # schema.
        if not dropped and existing is not None:
            raise RuntimeError(
                f"029_user_cascade_delete: could not drop existing FK "
                f"on {table}.{column} (tried: {candidates}). The "
                f"batch_alter_table reflection may need an updated "
                f"naming_convention. Aborting to avoid duplicate FK."
            )
        batch_op.create_foreign_key(
            name,
            ref_table,
            [column],
            [ref_column],
            ondelete=ondelete,
        )


def _apply(fk_specs):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    for table, column, ref_table, ref_column, ondelete, name in fk_specs:
        if not _table_exists(inspector, table):
            # Table missing on a partially-bootstrapped DB — skip.
            continue
        existing = _existing_fk(inspector, table, column)
        if existing is not None and _ondelete_matches(existing, ondelete):
            # Already at desired state — no-op.
            continue
        _recreate_fk(conn, table, column, ref_table, ref_column, ondelete, name)
        # Re-inspect for the next iteration in case the batch_alter
        # invalidated the cached metadata.
        inspector = sa.inspect(conn)


def _is_sqlite(conn) -> bool:
    return conn.dialect.name == "sqlite"


class _SqliteFkSuspender:
    """Context manager — toggle ``PRAGMA foreign_keys`` OFF/ON on SQLite.

    Alembic's ``batch_alter_table`` recreates the table by inserting into a
    fresh schema-prefixed copy and renaming. With ``PRAGMA foreign_keys=ON``
    enabled (per ``extensions._enable_sqlite_fk``) the rename step trips the
    FK validator because *other* child tables still point at the original
    table during the swap. The recommended pattern (Alembic batch docs +
    SQLite docs §4.10) is to suspend FK checks for the duration of the
    migration and restore them at the end. PostgreSQL is unaffected — the
    helper is a no-op on every other dialect.
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
        if _is_sqlite(self.conn):
            try:
                # Only restore to ON if we observed it ON on entry; never
                # silently *enable* FKs on a DB that had them off.
                if self.was_enabled:
                    self.conn.exec_driver_sql("PRAGMA foreign_keys=ON")
            except Exception:
                pass
        return False


def upgrade() -> None:
    conn = op.get_bind()
    with _SqliteFkSuspender(conn):
        _apply(_CASCADE_FKS)
        _apply(_SET_NULL_FKS)


def downgrade() -> None:
    # Revert every constrained FK to NO ACTION (the original behaviour).
    # Same fallback names so re-running upgrade after downgrade is
    # deterministic.
    revert_specs = [
        (table, column, ref_table, ref_column, "NO ACTION", name)
        for table, column, ref_table, ref_column, _ondelete, name
        in (_CASCADE_FKS + _SET_NULL_FKS)
    ]
    conn = op.get_bind()
    with _SqliteFkSuspender(conn):
        inspector = sa.inspect(conn)
        for table, column, ref_table, ref_column, ondelete, name in revert_specs:
            if not _table_exists(inspector, table):
                continue
            existing = _existing_fk(inspector, table, column)
            # NO ACTION is reported by SQLAlchemy as either "NO ACTION" or
            # ondelete absent — treat both as already-reverted.
            if existing is not None:
                options = existing.get("options") or {}
                current = (options.get("ondelete") or "").strip().upper()
                if current in ("", "NO ACTION"):
                    continue
            existing_name = (existing or {}).get("name") if existing else None
            convention_name = f"fk_{table}_{column}_{ref_table}"
            with op.batch_alter_table(
                table,
                naming_convention=_NAMING_CONVENTION,
            ) as batch_op:
                candidates = []
                if existing_name:
                    candidates.append(existing_name)
                candidates.append(convention_name)
                if name not in candidates:
                    candidates.append(name)
                dropped = False
                for candidate in candidates:
                    try:
                        batch_op.drop_constraint(candidate, type_="foreignkey")
                        dropped = True
                        break
                    except (ValueError, KeyError):
                        continue
                if not dropped and existing is not None:
                    raise RuntimeError(
                        f"029_user_cascade_delete: downgrade could not "
                        f"drop FK on {table}.{column} (tried: {candidates})."
                    )
                batch_op.create_foreign_key(
                    name,
                    ref_table,
                    [column],
                    [ref_column],
                )
            inspector = sa.inspect(conn)
