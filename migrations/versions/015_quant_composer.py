"""quant_composer — per-user enabled quant model + weight composition.

Revision ID: 015_quant_composer
Revises: 014_alerts_sized_rename
Create Date: 2026-04-25

Why
---
Backs Feature 1 (Quant Composer) + Feature 2 (Persona → Quant Auto-Apply)
of LAUNCH_BUNDLE_SPEC.md. Each user can independently enable a subset of
the 40-model catalog (``services.quant.model_catalog``) and assign a
per-model weight multiplier. The columns default to an empty list and
empty dict respectively so every existing user is in a backward-compatible
"no composition" state — :func:`services.quant.composer.apply_user_composition`
short-circuits to the unmodified ``base_quant_score`` whenever
``enabled_quant_models`` is empty.

Storage shape
-------------
Both columns are stored as TEXT (JSON-as-text) so SQLite + PostgreSQL
stay portable — the same approach used by ``persona_group_stats.metrics``
and ``persona_snapshots.features``. Read/write callers serialize/parse
via ``json.loads / json.dumps`` at the service boundary.

Privacy posture
---------------
Free of PII: the column only stores model class names and floats. No
trade history or ticker mention is ever written here. Cascade deletion
is inherited from the existing ``investment_profiles.user_id`` FK.

Chaining
--------
``down_revision="014_alerts_sized_rename"`` continues the strictly
linear Alembic history. The next migration in the chain
(``016_persona_snapshots``) declares us as its parent.

Backward compatibility
----------------------
- Existing rows: both columns are nullable with safe JSON defaults.
- Engine: :func:`services.quant.composer.apply_user_composition`
  treats ``[]`` as "no override" and returns the input score unchanged.
- Tests: 1118 existing tests must continue to pass. We add columns only;
  no existing column is renamed or dropped.
"""
from alembic import op
import sqlalchemy as sa


revision = "015_quant_composer"
down_revision = "014_alerts_sized_rename"
branch_labels = None
depends_on = None


def upgrade():
    # ALTER TABLE ADD COLUMN with a JSON default — TEXT here for portability.
    # SQLite & PostgreSQL both accept TEXT with a string default; Alembic batch
    # mode is not required for simple column additions.
    op.add_column(
        "investment_profiles",
        sa.Column(
            "enabled_quant_models",
            sa.Text(),
            nullable=True,
            server_default="[]",
        ),
    )
    op.add_column(
        "investment_profiles",
        sa.Column(
            "model_weights",
            sa.Text(),
            nullable=True,
            server_default="{}",
        ),
    )


def downgrade():
    op.drop_column("investment_profiles", "model_weights")
    op.drop_column("investment_profiles", "enabled_quant_models")
