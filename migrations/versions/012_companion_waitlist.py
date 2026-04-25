# Part of Journal Companion — see reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §6
"""companion_waitlist — Journal Companion Closed Beta signup table.

Revision ID: 012_companion_waitlist
Revises: 011_layer2_profile_tables
Create Date: 2026-04-24

Why
---
The landing-page teaser (``frontend/src/components/landing/companion-teaser.tsx``)
and the /companion dashboard page (``frontend/src/app/(dashboard)/companion/page.tsx``)
both POST to ``/api/agent/waitlist`` when the viewer isn't yet entitled.
Until this migration lands, that endpoint 404s and every waitlist
submission is silently dropped — matching the backlog item P0-2.

Privacy posture
---------------
See ``reports/legal/DRAFT_PRIVACY_POLICY_COMPANION_2026-04-23.md §9.1``.
The canonical identifier is ``email_hash`` (sha256 of the normalized
email); the raw email is kept only when the user explicitly opts in to
direct notification (``email_plaintext`` + ``email_consent_at``). Right-
to-erasure is O(1) through the unique ``email_hash`` index.

Chaining
--------
``down_revision="011_layer2_profile_tables"`` continues the strictly
linear history. Downgrade drops every object created here in the
reverse order Alembic prefers.
"""
from alembic import op
import sqlalchemy as sa


revision = "012_companion_waitlist"
down_revision = "011_layer2_profile_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "companion_waitlist",
        sa.Column("id", sa.Integer(), primary_key=True),
        # SHA256(email) — unique dedup + right-to-delete lookup key.
        sa.Column("email_hash", sa.String(length=64), nullable=False),
        # Raw email only when the user opts in to direct notification.
        sa.Column("email_plaintext", sa.String(length=255), nullable=True),
        sa.Column("email_consent_at", sa.DateTime(), nullable=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source",
            sa.String(length=40),
            nullable=False,
            server_default="landing-teaser",
        ),
        sa.Column("persona_interest", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("invited_at", sa.DateTime(), nullable=True),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
    )

    # Unique dedup index — idempotent POST relies on this.
    op.create_index(
        "idx_companion_waitlist_email_hash",
        "companion_waitlist",
        ["email_hash"],
        unique=True,
    )

    # user_id lookup index — admin filters + account-deletion cleanup.
    op.create_index(
        "idx_companion_waitlist_user_id",
        "companion_waitlist",
        ["user_id"],
    )

    # created_at index — admin listing is ORDER BY created_at ASC (FIFO).
    op.create_index(
        "idx_companion_waitlist_created_at",
        "companion_waitlist",
        ["created_at"],
    )


def downgrade():
    op.drop_index(
        "idx_companion_waitlist_created_at", table_name="companion_waitlist"
    )
    op.drop_index(
        "idx_companion_waitlist_user_id", table_name="companion_waitlist"
    )
    op.drop_index(
        "idx_companion_waitlist_email_hash", table_name="companion_waitlist"
    )
    op.drop_table("companion_waitlist")
