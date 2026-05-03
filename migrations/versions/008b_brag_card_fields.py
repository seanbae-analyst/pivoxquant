"""Brag Card (MVP #2) — users.privacy_mode / users.referral_code /
artifacts.share_token.

Revision ID: 008_brag_card_fields
Revises: 008_user_referrals_table
Create Date: 2026-04-19

Why these fields
----------------
- `users.privacy_mode` (Boolean, default False) — when True the monthly
  brag card masks ticker names as "A 종목" on rendered PNGs. Toggled
  via `/api/artifacts/brag-card/privacy`.

- `users.referral_code` (String(16), unique, nullable) — forward-looking
  dedicated column for the viral loop referral code. The `user_referrals`
  side-table (migration 008_user_referrals_table, shipped in a parallel
  Wave) remains the authoritative store during the transition; new
  referral codes should be mirrored here on creation so join-heavy
  queries can skip the side-table.

- `artifacts.share_token` (String(32), unique, nullable, indexed) —
  unguessable public-share handle for brag cards (and, in the future,
  any artefact that opts into public sharing). UNIQUE guarantees the
  share URL space doesn't collide; the index accelerates the lookup
  `WHERE share_token = ?` used by the public share route.

Chaining note
-------------
The parent revision is `008_user_referrals_table` — we could have chained
off `007_artifacts_table` directly, but that would create two siblings
at 008 (a branching tree) and force every subsequent migration to
merge-before-upgrade. Chaining linearly keeps the history simple.

Idempotency
-----------
This project's runtime also runs `_do_migrations()` in app.py which
adds columns via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`. This
Alembic file is the authoritative source for fresh DBs; the runtime
hook covers live boxes that upgrade in place.
"""
from alembic import op
import sqlalchemy as sa


revision = "008_brag_card_fields"
down_revision = "008_user_referrals_table"
branch_labels = None
depends_on = None


def upgrade():
    # ── users ──────────────────────────────────────────────────────────────
    # Skip the privacy_mode / referral_code adds when the columns already
    # exist (common in local dev where `db.create_all()` + the runtime
    # migration loop already provisioned them). Alembic's batch helper is
    # overkill for SQLite here; inspector is enough.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "privacy_mode" not in existing_user_cols:
        op.add_column(
            "users",
            sa.Column("privacy_mode", sa.Boolean(),
                      nullable=False, server_default=sa.false()),
        )

    if "referral_code" not in existing_user_cols:
        op.add_column(
            "users",
            sa.Column("referral_code", sa.String(16), nullable=True),
        )
        # UNIQUE as a separate index — SQLite can't add UNIQUE inline.
        op.create_index(
            "uq_users_referral_code",
            "users", ["referral_code"], unique=True,
        )

    # ── artifacts ──────────────────────────────────────────────────────────
    existing_artifact_cols = {
        c["name"] for c in inspector.get_columns("artifacts")
    }
    if "share_token" not in existing_artifact_cols:
        op.add_column(
            "artifacts",
            sa.Column("share_token", sa.String(32), nullable=True),
        )
        op.create_index(
            "uq_artifacts_share_token",
            "artifacts", ["share_token"], unique=True,
        )
        op.create_index(
            "ix_artifacts_share_token",
            "artifacts", ["share_token"],
        )


def downgrade():
    # Drop in reverse order. `IF EXISTS` not uniformly supported, so we
    # guard with the inspector.
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    existing_artifact_cols = {
        c["name"] for c in inspector.get_columns("artifacts")
    }
    if "share_token" in existing_artifact_cols:
        try:
            op.drop_index("ix_artifacts_share_token", table_name="artifacts")
        except Exception:
            pass
        try:
            op.drop_index("uq_artifacts_share_token", table_name="artifacts")
        except Exception:
            pass
        op.drop_column("artifacts", "share_token")

    existing_user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "referral_code" in existing_user_cols:
        try:
            op.drop_index("uq_users_referral_code", table_name="users")
        except Exception:
            pass
        op.drop_column("users", "referral_code")
    if "privacy_mode" in existing_user_cols:
        op.drop_column("users", "privacy_mode")
