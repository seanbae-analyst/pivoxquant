"""Marketing consent proof-of-opt-in (정통망법 §50 ①).

Revision ID: 023_marketing_consent
Revises: 022_alerts_watchlist_dd_columns
Create Date: 2026-05-03

Why these columns
-----------------
정통망법 §50 ① places the burden of proving prior opt-in on the *sender*
of every commercial/marketing email. The signup flow already collects a
checkbox in ``frontend/src/app/(auth)/signup/_v2/page-v2.tsx`` and stores
the resulting bundle as ``localStorage.setItem("pivox_signup_consents", …)``,
but that store is purely client-side: it disappears the moment the user
clears site data or reinstalls a browser, leaving the company without an
evidentiary record. §76 ①4호 escalates this from a paperwork issue to a
₩30M-cap administrative fine per offending send.

This migration backs the consent record with two server-side timestamps:

  * ``marketing_consent_at``         — UTC instant of the most recent
    explicit opt-in (NULL = never consented).
  * ``marketing_consent_revoked_at`` — UTC instant of the most recent
    revocation (NULL = never revoked, or revoked then re-consented and
    therefore irrelevant).

Effective consent is derived in application code rather than denormalized
into a third column, so the audit trail stays single-source-of-truth.

Distinction from ``email_opt_out`` (021)
----------------------------------------
``email_opt_out`` is a runtime *kill-switch* honoured by every email
sender service. The columns added here are the *legal evidence* that
the consent was (or was not) granted in the first place. A user who
never opted in must never be sent marketing email regardless of the
boolean's value, and the timestamps prove that distinction in any
정통망법 §50 dispute.

Idempotency
-----------
Mirrors the inspector pattern already used by 009 / 021: skip the
``ADD COLUMN`` when the column is already present. Re-running the
migration on a live DB is a safe no-op.

Chaining
--------
``down_revision = "022_alerts_watchlist_dd_columns"`` keeps the Alembic
history strictly linear after the backend-wave2 PR landed 022.
"""
from alembic import op
import sqlalchemy as sa


revision = "023_marketing_consent"
down_revision = "022_alerts_watchlist_dd_columns"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "marketing_consent_at" not in existing_user_cols:
        op.add_column(
            "users",
            sa.Column("marketing_consent_at", sa.DateTime(), nullable=True),
        )
    if "marketing_consent_revoked_at" not in existing_user_cols:
        op.add_column(
            "users",
            sa.Column(
                "marketing_consent_revoked_at",
                sa.DateTime(),
                nullable=True,
            ),
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "marketing_consent_revoked_at" in existing_user_cols:
        op.drop_column("users", "marketing_consent_revoked_at")
    if "marketing_consent_at" in existing_user_cols:
        op.drop_column("users", "marketing_consent_at")
