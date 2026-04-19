"""Create artifacts table.

Revision ID: 007_artifacts_table
Revises: 006_broker_encrypted_columns
Create Date: 2026-04-18

Generic artefact store — one row per generated artefact (weekly memo,
brag card, earnings brief, ...). Shape is intentionally polymorphic so
new artefact classes can share the same table without a schema
migration. Application code validates `type` against the known-types
set in `models/artifact.py`.

Idempotency: unique(user_id, type, title) guards the scheduler against
duplicate rows on retry (a week's memo has a deterministic title like
"Week 16 Investor Memo").
"""
from alembic import op
import sqlalchemy as sa


revision = "007_artifacts_table"
down_revision = "006_broker_encrypted_columns"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "artifacts",
        sa.Column("id",         sa.Integer(),   primary_key=True),
        sa.Column("user_id",    sa.Integer(),   sa.ForeignKey("users.id"),
                  nullable=False),
        sa.Column("type",       sa.String(40),  nullable=False),
        sa.Column("title",      sa.String(200), nullable=False),
        sa.Column("data_json",  sa.JSON(),      nullable=True),
        sa.Column("pdf_path",   sa.String(500), nullable=True),
        sa.Column("sent_at",    sa.DateTime(),  nullable=True),
        sa.Column("opened_at",  sa.DateTime(),  nullable=True),
        sa.Column("created_at", sa.DateTime(),  nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "type", "title",
                             name="uq_artifact_user_type_title"),
    )
    op.create_index("ix_artifacts_user_id", "artifacts", ["user_id"])
    op.create_index("ix_artifacts_type",    "artifacts", ["type"])


def downgrade():
    op.drop_index("ix_artifacts_type",    table_name="artifacts")
    op.drop_index("ix_artifacts_user_id", table_name="artifacts")
    op.drop_table("artifacts")
