"""Earnings Pre-Brief (MVP #3) — users.email_opt_out_earnings.

Revision ID: 009_earnings_prebrief
Revises: 008_brag_card_fields
Create Date: 2026-04-19

Why this field
--------------
- `users.email_opt_out_earnings` (Boolean, default False, NOT NULL) —
  per-channel opt-out for the Pre-Brief emails. When True, the user is
  excluded from the earnings pre-brief email path only (web push and
  other artefact emails remain on). This is distinct from the global
  `email_opt_out` flag: a user can mute time-sensitive earnings alerts
  without muting every transactional message. `EarningsPrebriefService
  ._send_email` honors the flag and logs the skip.

No Artifact schema change
-------------------------
The `artifacts` table is polymorphic via the `type` string column. MVP
#3 persists under `type="earnings_prebrief"` (already listed in
`models/artifact.py::ARTIFACT_TYPES`). No DDL is needed on that table.

Chaining
--------
`down_revision="008_brag_card_fields"` keeps the Alembic history strictly
linear. The preceding Wave introduced `users.privacy_mode`,
`users.referral_code`, `artifacts.share_token`; chaining off it avoids
creating a branch that would force merge-before-upgrade on every
subsequent migration.

Idempotency
-----------
The app.py boot-time `_do_migrations()` loop also idempotently adds
missing columns via `ALTER TABLE ... ADD COLUMN`. This Alembic file is
the authoritative source for fresh databases; the runtime hook covers
live boxes upgrading in place. We guard with the inspector before
issuing the DDL so re-running this migration is a no-op.
"""
from alembic import op
import sqlalchemy as sa


revision = "009_earnings_prebrief"
down_revision = "008_brag_card_fields"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "email_opt_out_earnings" not in existing_user_cols:
        op.add_column(
            "users",
            sa.Column(
                "email_opt_out_earnings",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "email_opt_out_earnings" in existing_user_cols:
        op.drop_column("users", "email_opt_out_earnings")
