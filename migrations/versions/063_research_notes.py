"""research_notes — 리서치 양식 + 정한 날 다시 채점.

Revision ID: 063_research_notes
Revises: 062_investment_profile_rules_confirmed
Create Date: 2026-10-15

Why
===
docs/design/research-notes_2026-10-15.md. 일반 개인투자자는 리포트·유튜브·
지인의 결론을 모아서 산다. 모든 종목에 같은 다섯 칸 양식(뭘로 돈을 버나 ·
가정 1~3개 · 틀렸다는 신호 · 큰 위험 · 확인한 숫자)과 "어디서 알게 됐나",
"다시 볼 날"을 받아 두고, 그날 유저가 가정마다 맞음/틀림/모름을 고른다.

Legal / privacy posture
-----------------------
유저 본인의 사적 기록. 서술 칸은 ORM 층에서 EncryptedText 로 암호화되므로
DB 타입은 TEXT(암호문)다. ``user_id`` FK ``ON DELETE CASCADE`` + 두 삭제 경로
(services/account_erasure._explicit_ops)에 명시 등록. 시세 컬럼 없음 —
결과는 읽기 시점에 본인 체결(trade_history)에서 계산한다.

Idempotency
-----------
``app.py`` 의 ``db.create_all()`` 이 먼저 만들었을 수 있으므로 Inspector 로
존재를 보고 없을 때만 만든다 (054 와 같은 관례).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "063_research_notes"
down_revision = "062_investment_profile_rules_confirmed"
branch_labels = None
depends_on = None

_TABLE = "research_notes"
_INDEXES = {
    "ix_research_notes_user_id": ["user_id"],
    "idx_research_notes_user_created": ["user_id", "created_at"],
    "idx_research_notes_user_review_on": ["user_id", "review_on"],
}


def _inspector():
    return inspect(op.get_bind())


def _tables() -> set[str]:
    return set(_inspector().get_table_names())


def _indexes(table: str) -> set[str]:
    return {i["name"] for i in _inspector().get_indexes(table)}


def upgrade():
    if _TABLE not in _tables():
        op.create_table(
            _TABLE,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("ticker", sa.String(length=20), nullable=False),
            # EncryptedText persists as TEXT (ciphertext).
            sa.Column("business", sa.Text(), nullable=False),
            sa.Column("theses_json", sa.Text(), nullable=False),
            sa.Column("invalidation", sa.Text(), nullable=True),
            sa.Column("risk", sa.Text(), nullable=True),
            sa.Column("numbers", sa.Text(), nullable=True),
            sa.Column("info_source", sa.String(length=20), nullable=True),
            sa.Column("surface", sa.String(length=20), nullable=True),
            sa.Column("review_on", sa.Date(), nullable=False),
            sa.Column("verdicts_json", sa.Text(), nullable=True),
            sa.Column("review_note", sa.Text(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
    if _TABLE in _tables():
        existing = _indexes(_TABLE)
        for name, cols in _INDEXES.items():
            if name not in existing:
                op.create_index(name, _TABLE, cols)


def downgrade():
    if _TABLE not in _tables():
        return
    existing = _indexes(_TABLE)
    for name in _INDEXES:
        if name in existing:
            op.drop_index(name, table_name=_TABLE)
    op.drop_table(_TABLE)
