"""funnel_events table + viral-loop attribution columns.

Revision ID: 045_funnel_events
Revises: 044_inquiries
Create Date: 2026-05-26

Viral loop backend (Wave B input)
==================================
Three schema additions, all idempotent (Inspector-pattern, mirrors
044_inquiries / 039_nps_feedback):

1. ``funnel_events`` — 0원 자체 퍼널 추적 테이블. ``POST /api/track`` 가
   비로그인 랜딩 이벤트까지 적재한다. user_id NULL 허용 (익명 랜딩 뷰).
   외부 전송 없음 — 자체 DB 만 사용 (PIPA). anon_id 는 식별가능 최소화한
   클라이언트 난수 (이메일/IP 아님).

2. ``users.referred_by`` — 가입 시 ``?ref=`` 로 들어온 추천인 코드.
   ``users.referral_code`` (이미 008b 에서 추가) 와 짝. 정수 ID 노출 금지
   원칙에 따라 코드 문자열만 기록.

3. ``artifacts.is_public`` — 공개 카드 토글. 기본 비공개(False).
   ``GET /api/card/<share_token>`` 는 ``is_public=True`` 인 카드만 노출 →
   임의 토큰 enumeration 으로 타인 포트폴리오 노출 차단 (PIPA §29).

Idempotency
-----------
테이블 존재 / 컬럼 존재 시 skip. 재실행 안전한 no-op. app.py
``_do_migrations`` self-heal 가드(CREATE TABLE IF NOT EXISTS + ADD COLUMN
guard) 와 중복돼도 양쪽 모두 멱등이다.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "045_funnel_events"
# 2026-05-26: repointed from 043_notification_prefs → 044_inquiries so the
# support-tickets migration (044) wedges in cleanly and the head stays single.
down_revision = "044_inquiries"
branch_labels = None
depends_on = None


_TABLE = "funnel_events"


def _has_column(inspector, table: str, column: str) -> bool:
    try:
        return column in {c["name"] for c in inspector.get_columns(table)}
    except Exception:
        return False


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    is_pg = conn.dialect.name == "postgresql"

    # ── 1. funnel_events ──────────────────────────────────────────────────────
    if _TABLE not in inspector.get_table_names():
        op.create_table(
            _TABLE,
            sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
                      primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), nullable=True),
            sa.Column("anon_id", sa.Text(), nullable=True),
            sa.Column("event", sa.Text(), nullable=False),
            sa.Column("channel", sa.Text(), nullable=True),
            sa.Column("ref_code", sa.Text(), nullable=True),
            # JSONB on PG, JSON elsewhere (SQLite stores as TEXT).
            sa.Column(
                "meta",
                postgresql.JSONB() if is_pg else sa.JSON(),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_funnel_events_event_created",
                        _TABLE, ["event", "created_at"])
        op.create_index("ix_funnel_events_ref_code", _TABLE, ["ref_code"])

    # ── 2. users.referred_by ──────────────────────────────────────────────────
    if not _has_column(inspector, "users", "referred_by"):
        op.add_column("users", sa.Column("referred_by", sa.String(16),
                                         nullable=True))
        op.create_index("ix_users_referred_by", "users", ["referred_by"])

    # ── 3. artifacts.is_public ────────────────────────────────────────────────
    if not _has_column(inspector, "artifacts", "is_public"):
        op.add_column(
            "artifacts",
            sa.Column("is_public", sa.Boolean(), nullable=False,
                      server_default=sa.false()),
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if _has_column(inspector, "artifacts", "is_public"):
        op.drop_column("artifacts", "is_public")

    if _has_column(inspector, "users", "referred_by"):
        try:
            op.drop_index("ix_users_referred_by", table_name="users")
        except Exception:
            pass
        op.drop_column("users", "referred_by")

    if _TABLE in inspector.get_table_names():
        op.drop_table(_TABLE)
