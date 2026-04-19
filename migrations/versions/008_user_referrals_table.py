"""Create user_referrals table.

Revision ID: 008_user_referrals_table
Revises: 007_artifacts_table
Create Date: 2026-04-18

One row per user — side-table so we don't have to modify `users` (which
is treated as immutable per the project conventions). The `referral_code`
is an 8-char URL-safe token (de-confused alphabet). Both `user_id` and
`referral_code` are UNIQUE; callers must handle collisions via retry
(see `UserReferral.get_or_create`).

Used by the Monthly Brag Card viral loop: the shared PNG carries
`pivoxquant.com/r/{referral_code}` as a watermark + share-link target.
"""
from alembic import op
import sqlalchemy as sa


revision = "008_user_referrals_table"
down_revision = "007_artifacts_table"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_referrals",
        sa.Column("id",            sa.Integer(),   primary_key=True),
        sa.Column("user_id",       sa.Integer(),   sa.ForeignKey("users.id"),
                  nullable=False),
        sa.Column("referral_code", sa.String(16),  nullable=False),
        sa.Column("created_at",    sa.DateTime(),  nullable=False,
                  server_default=sa.func.now()),
        sa.Column("invited_count", sa.Integer(),   nullable=False,
                  server_default="0"),
        sa.UniqueConstraint("user_id",       name="uq_user_referrals_user_id"),
        sa.UniqueConstraint("referral_code", name="uq_user_referrals_code"),
    )
    op.create_index("ix_user_referrals_user_id",
                    "user_referrals", ["user_id"])
    op.create_index("ix_user_referrals_referral_code",
                    "user_referrals", ["referral_code"])


def downgrade():
    op.drop_index("ix_user_referrals_referral_code",
                  table_name="user_referrals")
    op.drop_index("ix_user_referrals_user_id",
                  table_name="user_referrals")
    op.drop_table("user_referrals")
