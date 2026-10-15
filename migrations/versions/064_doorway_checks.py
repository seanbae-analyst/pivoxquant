"""doorway_checks — 증권 앱을 여는 순간 남긴 한 줄 (문 앞의 한 줄).

Revision ID: 064_doorway_checks
Revises: 063_research_notes
Create Date: 2026-10-15

Why
===
docs/design/doorway-pause_2026-10-15.md. 「멈춤」은 유저가 사기 전에
PivoxQuant 를 스스로 열어야 작동한다. 충동은 증권 앱을 여는 순간 시작되므로,
유저 폰의 자동화(아이폰 단축어 '앱 → 열 때' · MacroDroid '앱 실행')가 그 순간
"뭘 하러 왔어요?"(그냥 보기 / 살 게 있음 / 팔 게 있음 + 한 줄)를 묻고 본인
가져오기 토큰으로 보낸다. 이어진 체결은 읽기 시점에 본인 체결에서 맞춘다.

Legal / privacy posture
-----------------------
유저 본인의 사적 기록. ``note`` 는 ORM 층에서 EncryptedText 로 암호화되므로
DB 타입은 TEXT(암호문)다. ``user_id`` FK ``ON DELETE CASCADE`` + 두 삭제 경로
(services/account_erasure._explicit_ops)에 명시 등록. 시세 컬럼 없음.

Also adds ``import_tokens.doorway_consent_at`` (nullable): the token-issuance
consent names door answers from this revision on; older tokens (NULL) are
refused by the doorway webhook until the user issues a new one
(legal-kr-fintech review 2026-10-15, PIPA §15·§22).

Idempotency
-----------
``app.py`` 의 ``db.create_all()`` 이 먼저 만들었을 수 있으므로 Inspector 로
존재를 보고 없을 때만 만든다 (054 · 063 과 같은 관례).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "064_doorway_checks"
down_revision = "063_research_notes"
branch_labels = None
depends_on = None

_TABLE = "doorway_checks"
_INDEXES = {
    "ix_doorway_checks_user_id": ["user_id"],
    "idx_doorway_checks_user_created": ["user_id", "created_at"],
}


def _inspector():
    return inspect(op.get_bind())


def _tables() -> set[str]:
    return set(_inspector().get_table_names())


def _indexes(table: str) -> set[str]:
    return {i["name"] for i in _inspector().get_indexes(table)}


def _columns(table: str) -> set[str]:
    return {c["name"] for c in _inspector().get_columns(table)}


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
            sa.Column("intent", sa.String(length=8), nullable=False),
            sa.Column("ticker", sa.String(length=20), nullable=True),
            # EncryptedText persists as TEXT (ciphertext).
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("app", sa.String(length=20), nullable=True),
            sa.Column("source", sa.String(length=12), nullable=False),
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
    if "import_tokens" in _tables() and "doorway_consent_at" not in _columns("import_tokens"):
        op.add_column("import_tokens", sa.Column("doorway_consent_at", sa.DateTime(), nullable=True))


def downgrade():
    if "import_tokens" in _tables() and "doorway_consent_at" in _columns("import_tokens"):
        with op.batch_alter_table("import_tokens") as batch:
            batch.drop_column("doorway_consent_at")
    if _TABLE not in _tables():
        return
    existing = _indexes(_TABLE)
    for name in _INDEXES:
        if name in existing:
            op.drop_index(name, table_name=_TABLE)
    op.drop_table(_TABLE)
