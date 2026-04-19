"""Add per-user encrypted broker credentials to broker_connections.

Revision ID: 006_broker_encrypted_columns
Revises: 005_growth_tables
Create Date: 2026-04-18

Week 1 of the Auto-Sync Tech Plan (docs/launch/AUTO_SYNC_TECH_PLAN.md).

Adds AES-256-GCM encrypted fields to the existing `broker_connections` table
so each user can bind their personal KIS (Korea Investment & Securities) APP
KEY / APP SECRET / account number without touching the legacy global singleton
at `kis_service.py`.

All new columns are nullable to avoid breaking the existing Alpaca flow that
populates only the legacy `access_token` / `refresh_token` fields.
"""
from alembic import op
import sqlalchemy as sa


revision = "006_broker_encrypted_columns"
down_revision = "005_growth_tables"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("broker_connections") as batch:
        batch.add_column(sa.Column("encrypted_app_key", sa.Text(), nullable=True))
        batch.add_column(sa.Column("encrypted_app_secret", sa.Text(), nullable=True))
        batch.add_column(sa.Column("encrypted_account_no", sa.Text(), nullable=True))
        batch.add_column(sa.Column("account_prod", sa.String(length=4), nullable=True, server_default="01"))
        batch.add_column(sa.Column("encrypted_access_token", sa.Text(), nullable=True))
        batch.add_column(sa.Column("token_expires_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column(
            "encryption_key_version",
            sa.SmallInteger(),
            nullable=False,
            server_default="1",
        ))
        batch.add_column(sa.Column("display_name", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("last_sync_status", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("last_sync_error", sa.Text(), nullable=True))
        batch.add_column(sa.Column(
            "consecutive_failures",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ))


def downgrade():
    with op.batch_alter_table("broker_connections") as batch:
        batch.drop_column("consecutive_failures")
        batch.drop_column("last_sync_error")
        batch.drop_column("last_sync_status")
        batch.drop_column("display_name")
        batch.drop_column("encryption_key_version")
        batch.drop_column("token_expires_at")
        batch.drop_column("encrypted_access_token")
        batch.drop_column("account_prod")
        batch.drop_column("encrypted_account_no")
        batch.drop_column("encrypted_app_secret")
        batch.drop_column("encrypted_app_key")
