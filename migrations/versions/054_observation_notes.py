"""observation_notes — 거래 없이 적어 두는 관찰 기록.

Revision ID: 054_observation_notes
Revises: 053_age_self_declaration
Create Date: 2026-09-22

Why
===
docs/design/observation-notes_2026-09-22.md §2. 유저 텍스트가 저장되는 자리가
거래에 묶인 순간(pre_trade_reflections.rationale · positions.thesis ·
pending_trades.approved_thesis)뿐이라, 관찰만 하고 있는 동안에는 기록할 곳이
없었다. 이 테이블이 기록의 진입 장벽을 거래 밖으로 낮춘다.

Legal posture
-------------
전적으로 관찰·기록용이다. ``tickers_json`` 은 유저가 적어 둔 관찰 대상일 뿐
우리가 내는 지시가 아니고(자본시장법 §49 분리), 본문은 유저 본인에게만
렌더된다. 시세는 관여하지 않는다 — 가격 스냅숏 컬럼을 두지 않은 것은 의도다
(설계 §0, FMP §2.2.2 Display Agreement 미체결).

Privacy posture
---------------
``user_id`` FK ``ON DELETE CASCADE`` — 탈퇴 시 모든 노트가 사라진다
(PIPA §36). 두 삭제 경로(routes/auth.py:delete_account 의 ``purge_ops`` 와
scripts/nightly/pipa_purge._delete_user_cascade)에도 명시적으로 등록했다.
``body`` 는 ORM 층에서 EncryptedText 로 암호화되므로 DB 타입은 평문과 같은
TEXT(암호문)다 — 048 에서 겪은 폭 문제가 없다.

Idempotency
-----------
``app.py`` 의 ``db.create_all()`` 이 조건 없이 돌기 때문에, 이 리비전이
적용되기 전에 테이블이 이미 만들어져 있을 수 있다. 그래서 Inspector 로
존재 여부를 먼저 보고 없을 때만 만든다 (053 과 같은 관례). DDL 은 SQLite
(dev/test)와 PostgreSQL(prod)에서 동일하게 렌더된다.

Chaining
--------
``down_revision="053_age_self_declaration"`` — 선형 alembic 히스토리 유지.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "054_observation_notes"
down_revision = "053_age_self_declaration"
branch_labels = None
depends_on = None

_TABLE = "observation_notes"
_INDEX = "idx_observation_notes_user_created"


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
            # EncryptedText persists as TEXT (ciphertext) — same DDL as a
            # plaintext column, no width to get wrong.
            sa.Column("body", sa.Text(), nullable=False),
            # JSON arrays. Plain text so by-ticker / tag filtering can run in
            # SQL; neither column holds free-form personal narrative.
            sa.Column("tickers_json", sa.Text(), nullable=True),
            sa.Column("tags_json", sa.Text(), nullable=True),
            # 'journal' / 'portfolio' / 'pre_trade' — which surface the note
            # was written from. Instrumentation for the beta question
            # ("어디서 기록하나"), never a directive.
            sa.Column("source", sa.String(length=20), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
    if _TABLE in _tables():
        # The model declares ``index=True`` on user_id, so create_all may have
        # made this one already; the composite is what the read paths use.
        _create_index_if_missing("ix_observation_notes_user_id", ["user_id"])
        # 모든 읽기 경로가 (user_id, created_at desc) 다 — list · by-ticker.
        _create_index_if_missing(_INDEX, ["user_id", "created_at"])


def _create_index_if_missing(name: str, columns: list[str]) -> None:
    if name not in _indexes(_TABLE):
        op.create_index(name, _TABLE, columns)


def downgrade():
    if _TABLE not in _tables():
        return
    for name in (_INDEX, "ix_observation_notes_user_id"):
        # The inspector guard already makes this idempotent. No try/except:
        # a swallowed failure on Postgres leaves the transaction aborted and
        # every later statement fails with a confusing InFailedSqlTransaction
        # instead of the real error.
        if name in _indexes(_TABLE):
            op.drop_index(name, table_name=_TABLE)
    op.drop_table(_TABLE)
