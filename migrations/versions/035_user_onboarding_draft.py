"""User onboarding draft column for partial-save / device-handoff.

Revision ID: 035_user_onboarding_draft
Revises: 034_flag_implausible_avg_cost
Create Date: 2026-05-17

Why this field
--------------
Wave 12 UX P0 finding: the onboarding wizard (20+ questions) stored progress
in localStorage only. A user who answered 15 questions on mobile and then
opened the site on desktop saw the wizard at question 0 — progress lost.
ITP / private-browsing sessions also evict localStorage opportunistically.

This column gives the backend a server-side draft slot per user. The
frontend writes after every 5 answered questions; the next session reads it
during mount and merges with localStorage (whichever is fresher wins).

Shape
-----
``onboarding_draft_json TEXT NULL`` — opaque JSON object holding whatever
answer dict the frontend wizard currently maintains. Schema-less on
purpose: the wizard evolves frequently and a strict schema would force
a backfill migration on every question change. Nullable: NULL means
"no draft" (brand-new user or one who already completed onboarding —
``onboarding_completed`` is the authoritative completion flag).

Cleared after successful ``POST /api/profile/onboarding`` so we never
store stale drafts past completion.

Idempotency
-----------
Mirrors the 032 / 033 / 034 pattern — inspect ``users`` columns first,
``ADD COLUMN`` only when missing. Safe on prod redeploys.

PIPA / privacy
--------------
The draft contains the same fields the final answers do (risk tolerance,
preferred sectors, etc.) — no new categories of personal data introduced.
``routes/profile.py:delete_account`` already deletes the User row, so the
column travels with it. ``_serialize_user`` (the export endpoint) is
extended in a separate change so the user can read their own draft.
"""
from alembic import op
import sqlalchemy as sa


revision = "035_user_onboarding_draft"
down_revision = "034_flag_implausible_avg_cost"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "onboarding_draft_json" not in existing_user_cols:
        op.add_column(
            "users",
            sa.Column(
                "onboarding_draft_json",
                sa.Text(),
                nullable=True,
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "onboarding_draft_json" in existing_user_cols:
        op.drop_column("users", "onboarding_draft_json")
