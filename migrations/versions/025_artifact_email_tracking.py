"""Artifact — SendGrid Event Webhook tracking columns.

Revision ID: 025_artifact_email_tracking
Revises: 024_cross_border_consent
Create Date: 2026-05-03

Why these fields
----------------
PR #86 wires up the SendGrid Event Webhook so that open / bounce /
unsubscribe events emitted by SendGrid can be mapped back to the
``artifacts`` row that triggered the outbound email. Until now we
only tracked ``sent_at`` (set by the artefact services right after
``EmailSender.send`` returned ``True``) and ``opened_at`` (a UI-side
download click — *not* an inbox open).

Four new columns:

* ``opened_at``       — already existed; now also populated by the
                        SendGrid ``open`` event (real inbox-open).
* ``bounced_at``      — SendGrid ``bounce`` event timestamp.
* ``unsubscribed_at`` — SendGrid ``unsubscribe`` / ``group_unsubscribe``
                        event timestamp.
* ``sg_message_id``   — the SendGrid ``X-Message-Id`` header value of
                        the outbound message; used by the webhook to
                        look up the right artefact row. Indexed for
                        the per-event lookup (one webhook batch carries
                        up to ~1000 events, all on the hot path).

Idempotency
-----------
Inspector-guarded ``ADD COLUMN`` matches the project pattern
(009_earnings_prebrief / 021_email_opt_out / 024_cross_border_consent).
Re-running on a DB that already has the columns is a no-op.

Chaining
--------
``down_revision = "024_cross_border_consent"``.
"""
from alembic import op
import sqlalchemy as sa


revision = "025_artifact_email_tracking"
down_revision = "024_cross_border_consent"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = {c["name"] for c in inspector.get_columns("artifacts")}
    existing_idx = {ix["name"] for ix in inspector.get_indexes("artifacts")}

    if "bounced_at" not in existing_cols:
        op.add_column(
            "artifacts",
            sa.Column("bounced_at", sa.DateTime(), nullable=True),
        )

    if "unsubscribed_at" not in existing_cols:
        op.add_column(
            "artifacts",
            sa.Column("unsubscribed_at", sa.DateTime(), nullable=True),
        )

    if "sg_message_id" not in existing_cols:
        op.add_column(
            "artifacts",
            sa.Column("sg_message_id", sa.String(length=128), nullable=True),
        )

    if "ix_artifacts_sg_message_id" not in existing_idx:
        op.create_index(
            "ix_artifacts_sg_message_id",
            "artifacts",
            ["sg_message_id"],
            unique=False,
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = {c["name"] for c in inspector.get_columns("artifacts")}
    existing_idx = {ix["name"] for ix in inspector.get_indexes("artifacts")}

    if "ix_artifacts_sg_message_id" in existing_idx:
        op.drop_index("ix_artifacts_sg_message_id", table_name="artifacts")

    if "sg_message_id" in existing_cols:
        op.drop_column("artifacts", "sg_message_id")
    if "unsubscribed_at" in existing_cols:
        op.drop_column("artifacts", "unsubscribed_at")
    if "bounced_at" in existing_cols:
        op.drop_column("artifacts", "bounced_at")
