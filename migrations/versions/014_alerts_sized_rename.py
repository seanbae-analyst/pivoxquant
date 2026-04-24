"""alerts — replace legacy "Rec:" messages with "Sized:".

Revision ID: 014_alerts_sized_rename
Revises: 013_persona_group_stats
Create Date: 2026-04-24

Why
---
services/alert_service.py was updated on 2026-04-24 to emit "Sized:"
instead of "Rec:" (compliance: "Rec" abbreviates "Recommendation" which
triggered the 자본시장법 §17 미등록 투자자문업 flag in the legal filter
sweep). Rows persisted prior to that code deploy still contain the old
"Rec: …" substring — this migration rewrites them in place so the
frontend notification dropdown never surfaces the non-compliant wording.

Operation is idempotent: SQL `REPLACE` only rewrites rows that still
contain the literal "Rec:" prefix, so re-running the migration is safe.

Chaining
--------
``down_revision="013_persona_group_stats"`` continues the strictly
linear Alembic history.

Downgrade
---------
No-op. The original content is lossy (we don't know which "Rec:"
occurrences were ours vs. user text, though user text can't reach this
column), and re-emitting the non-compliant string would re-open the
legal filter violation. Treat this as a forward-only rewrite.
"""
from alembic import op


revision = "014_alerts_sized_rename"
down_revision = "013_persona_group_stats"
branch_labels = None
depends_on = None


def upgrade():
    # REPLACE(column, search, replacement) is standard in both SQLite and
    # PostgreSQL, so the same statement works across dev/prod DBs.
    op.execute(
        "UPDATE alerts SET message = REPLACE(message, 'Rec:', 'Sized:') "
        "WHERE message LIKE '%Rec:%'"
    )


def downgrade():
    # Intentional no-op — see module docstring.
    pass
