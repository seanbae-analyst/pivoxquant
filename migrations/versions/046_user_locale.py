"""Add users.locale (i18n preference column).

Revision ID: 046_user_locale
Revises: 045_funnel_events
Create Date: 2026-05-28

Wave F (i18n backend infrastructure)
====================================
Server-side source of truth for PDF/email/UI locale preference.
Frontend cookie ``sp_locale`` (lib/locale.tsx) syncs into this column via
``PUT /api/profile/locale``. Artifact services (17 PDF templates) and
EmailSender read ``user.locale`` to branch ko/en strings + subject lines.

Idempotency
-----------
- Column existence check via SQLAlchemy Inspector (mirrors 045_funnel_events).
- NOT NULL DEFAULT 'ko' backfills every existing row to Korean (safest default
  — pre-Wave F users were all Korean-speaking).
- app.py ``_do_migrations`` self-heal guard duplicates this for alembic-less
  prod boxes (Railway). Both paths are idempotent.

Compliance
----------
``locale`` is a UI preference, NOT personal information (PIPA §2.1):
- Not derived from IP / geolocation
- Not shared with third parties
- User-controlled (settings page toggle)
No PIPA §17 / §28-8 implications.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "046_user_locale"
down_revision = "045_funnel_events"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    try:
        return any(c["name"] == column for c in insp.get_columns(table))
    except Exception:
        return False


def upgrade():
    if not _has_column("users", "locale"):
        op.add_column(
            "users",
            sa.Column(
                "locale",
                sa.String(length=2),
                nullable=False,
                server_default="ko",
            ),
        )


def downgrade():
    # Defensive: only drop if present.
    if _has_column("users", "locale"):
        op.drop_column("users", "locale")
