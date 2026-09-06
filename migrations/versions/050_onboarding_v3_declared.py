"""Questionnaire V3 — keep the user's own onboarding words.

Revision ID: 050_onboarding_v3_declared
Revises: 049_reflection_observed_context
Create Date: 2026-09-06

Why
===
docs/strategy/onboarding-questionnaire-v3_2026-09-06.md — V2 asked 19
questions and discarded the answers after deriving ``profile_type``; the
mirror then compared observed behaviour against a persona *centroid*, never
against what the user said. V3 (5 questions) persists the answers verbatim
and their projection onto the observed feature scale so ``/mirror`` can put
"what you said" next to "what you did" on the same ruler.

Columns (all nullable — skip-path users and pre-V3 rows stay NULL):
  investment_profiles.questionnaire_version   INTEGER
  investment_profiles.onboarding_answers_json TEXT   {question_id: value}
  investment_profiles.declared_vector_json    TEXT   {feature_key: 0..1}

Compliance
----------
The stored answers are the user's own statements about their own habits
(holding, frequency, positions, drawdown response, record habit). Nothing
here is a score, grade or recommendation; ``routes/profile.py`` never
returns a derived label from these columns except through the existing
3-bucket surface.

Idempotency
-----------
Each column is added only if absent (Inspector check) so re-running after
the app.py boot self-heal already added it is safe. Plain nullable
INTEGER/TEXT: identical DDL on SQLite (dev/test) and PostgreSQL (prod).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "050_onboarding_v3_declared"
down_revision = "049_reflection_observed_context"
branch_labels = None
depends_on = None

_TABLE = "investment_profiles"
_COLUMNS = (
    ("questionnaire_version", sa.Integer()),
    ("onboarding_answers_json", sa.Text()),
    ("declared_vector_json", sa.Text()),
)


def _existing() -> set[str] | None:
    bind = op.get_bind()
    insp = inspect(bind)
    if _TABLE not in insp.get_table_names():
        return None
    return {c["name"] for c in insp.get_columns(_TABLE)}


def upgrade():
    have = _existing()
    if have is None:
        return
    for name, col_type in _COLUMNS:
        if name not in have:
            op.add_column(_TABLE, sa.Column(name, col_type, nullable=True))


def downgrade():
    have = _existing()
    if have is None:
        return
    for name, _ in _COLUMNS:
        if name in have:
            op.drop_column(_TABLE, name)
