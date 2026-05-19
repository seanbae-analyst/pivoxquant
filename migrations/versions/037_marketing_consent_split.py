"""Split marketing consent into Information vs Marketing buckets (정통망법 §50 ①).

Revision ID: 037_marketing_consent_split
Revises: 036_growth_user_id_fk
Create Date: 2026-05-19

Wave D Sub-wave 1 — C-S1 §50 separate consent backend
=====================================================

정통망법 §50 ① 의 핵심은 "광고성 정보 전송 시 사전 명시적 동의". 그러나 §50
시행령 및 KISA 가이드라인은 "정보성"과 "광고성"을 구분하며 동의 항목을 분리
징수할 것을 권고한다. 기존 ``marketing_consent_at`` (migration 023) 컬럼은
이 두 카테고리를 하나로 묶어 두었기 때문에 향후 변호사 자문 (Q-S1) 답변
이후의 분리 동의 UI 와 1:1 매핑되지 않는다.

본 마이그레이션은 023 의 컬럼을 *건드리지 않고* (하위 호환), 두 카테고리의
별도 동의 시각/철회 시각을 신규 컬럼 4종으로 추가한다. 023 의 컬럼은
"global 일반 동의" 로서 default-deny 1차 게이트 역할을 유지한다.

신규 컬럼
---------

* ``marketing_consent_information_at``         — 정보성 메일 (서비스 업데이트,
  계정 공지 등 비광고성) 동의 시각. NULL = 미동의.
* ``marketing_consent_information_revoked_at`` — 정보성 메일 동의 철회 시각.
  NULL = 철회 없음 또는 재동의로 무효화.
* ``marketing_consent_marketing_at``           — 광고성 메일 (할인 / 프로모션 /
  교차판매) 동의 시각. NULL = 미동의.
* ``marketing_consent_marketing_revoked_at``   — 광고성 메일 동의 철회 시각.

타임스탬프 페어 패턴은 023 의 audit-trail 원칙과 동일하다 — 단일 BOOLEAN 이
아니라 동의/철회 history 가 row 에 보존된다.

Feature-flag 관계
-----------------

본 마이그레이션은 *스키마만* 추가한다. 신규 동의 검사 경로는 application
레이어의 ``PIVOX_CS1_CONSENT_ENABLED`` env (default false) 에 게이트되어
변호사 Q-S1 답변까지 비활성화 상태로 deploy 가능하다. flag=false 동안에는
기존 ``marketing_consent_at`` 단일 컬럼 경로가 그대로 운영된다.

Idempotency
-----------

023 / 024 / 030 의 inspector 패턴을 그대로 따라 컬럼 존재 시 ADD COLUMN 을
스킵한다. 재실행은 안전한 no-op.
"""
from alembic import op
import sqlalchemy as sa


revision = "037_marketing_consent_split"
down_revision = "036_growth_user_id_fk"
branch_labels = None
depends_on = None


_NEW_COLS = (
    "marketing_consent_information_at",
    "marketing_consent_information_revoked_at",
    "marketing_consent_marketing_at",
    "marketing_consent_marketing_revoked_at",
)


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = {c["name"] for c in inspector.get_columns("users")}

    for col in _NEW_COLS:
        if col not in existing:
            op.add_column(
                "users",
                sa.Column(col, sa.DateTime(), nullable=True),
            )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = {c["name"] for c in inspector.get_columns("users")}
    # Drop in reverse order to mirror upgrade() — purely cosmetic for
    # SQLAlchemy but keeps the diff readable in alembic history.
    for col in reversed(_NEW_COLS):
        if col in existing:
            op.drop_column("users", col)
