"""Email Compliance P0 — global users.email_opt_out column.

Revision ID: 021_email_opt_out
Revises: 020_growth_user_id
Create Date: 2026-05-03

Why this field
--------------
정통망법 §50 (Korean spam law) requires every transactional/marketing email
to honour a *global* opt-out. The 17 artefact email services in
``services/artifacts/*_service.py`` already gate sends on
``getattr(user, "email_opt_out", False)``, but the column never existed —
``getattr`` therefore always returned ``False`` and no user could ever
opt out, leaving us in violation.

This migration adds the missing column with ``server_default='0'`` so
existing rows materialize with the safe (still-receives) value, while
``nullable=False`` prevents future inserts from skipping the field.

Distinct from ``email_opt_out_earnings`` (added in 009): that column is
the per-channel opt-out for time-sensitive earnings pre-briefs; the
column added here is the *global kill switch* honoured by every email
sender.

Idempotency
-----------
Mirrors migration 009's pattern: inspect existing columns and skip the
``ADD COLUMN`` when already present. Re-running the migration on a live
DB is therefore a safe no-op.

Chaining
--------
``down_revision = "020_growth_user_id"`` (renamed from the original
``020_email_opt_out``) keeps the Alembic history strictly linear after
the SEC-005 PR landed `020_growth_user_id`.
"""
from alembic import op
import sqlalchemy as sa


revision = "021_email_opt_out"
down_revision = "020_growth_user_id"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "email_opt_out" not in existing_user_cols:
        op.add_column(
            "users",
            sa.Column(
                "email_opt_out",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "email_opt_out" in existing_user_cols:
        op.drop_column("users", "email_opt_out")
