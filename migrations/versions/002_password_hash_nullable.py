"""Make password_hash nullable for OAuth users.

Revision ID: 002_password_nullable
Revises: 001_initial
Create Date: 2026-04-11

OAuth users (Google, Kakao) have no password, so password_hash must
accept NULL.  The SQLAlchemy model already declares nullable=True, but
the physical SQLite schema still has NOT NULL from the original
db.create_all().  This migration brings the database in sync.

SQLite does not support ALTER COLUMN, so we use Alembic batch mode
which recreates the table transparently.
"""
from alembic import op
import sqlalchemy as sa

revision = '002_password_nullable'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column(
            'password_hash',
            existing_type=sa.String(200),
            nullable=True,
        )


def downgrade():
    # Safety: OAuth users may have NULL password_hash.  Setting the column
    # back to NOT NULL without handling NULLs would cause a database error.
    # We fill NULLs with a sentinel value that can never match a real bcrypt
    # hash, so login remains impossible for those rows (preserving security).
    _PLACEHOLDER = '!oauth-no-password'
    op.execute(
        sa.text(
            "UPDATE users SET password_hash = :placeholder "
            "WHERE password_hash IS NULL"
        ).bindparams(placeholder=_PLACEHOLDER)
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column(
            'password_hash',
            existing_type=sa.String(200),
            nullable=False,
        )
