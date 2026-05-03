"""PIPA §28-8 — users.cross_border_consent_* columns.

Revision ID: 024_cross_border_consent
Revises: 023_marketing_consent
Create Date: 2026-05-03

Why this field
--------------
개인정보보호법 (PIPA) §28-8 (2024-09 시행) 은 개인정보의 국외이전 시
*명시적 별도* 동의를 요구한다. PivoxQuant 는 Anthropic PBC (미국,
Claude API), Stripe Inc. (미국, 결제), Vercel Inc. / Railway Inc. (미국,
호스팅) 으로 개인정보를 이전·위탁하므로 §28-8 적용 대상이다.

현 ``frontend/.../legal/privacy-ko.md`` L184 는 위 위탁처를 고시하지만
L189 의 "서비스 가입 시 아래 이전에 동의한 것으로 간주" 문구는
§28-8 이 요구하는 "별도 동의" 기준을 충족하지 못한다. 가입 플로우의
4 개 동의 체크박스 (terms / non_advisory / age / marketing) 어디에도
국외이전 별도 동의 항목이 없는 상태다.

이 마이그레이션은 별도 동의 인프라의 *데이터 계층* 만 추가한다:

* ``cross_border_consent_at`` — 사용자가 별도 동의 체크박스를 제출한
  시각 (UTC). NULL 이면 동의 미수령. 이전·위탁 코드 경로는 본 컬럼이
  NULL 인 사용자에 대해 국외이전을 차단하는 가드를 향후 도입한다.
* ``cross_border_consent_revoked_at`` — 사용자가 동의를 철회한 시각.
  값이 채워지면 ``_at`` 가 set 되어 있어도 동의 효력이 없다.

엔드포인트와 가입 폼 5 번째 체크박스는 *별도 후속 PR* (PR #73 머지 후)
에서 추가한다.

Idempotency
-----------
009_earnings_prebrief / 021_email_opt_out 패턴을 그대로 따른다 —
inspector 로 기존 컬럼을 조회하여 이미 존재하면 ``ADD COLUMN`` 을
스킵한다. 라이브 DB 에서 재실행해도 안전한 no-op.

Chaining
--------
``down_revision = "023_marketing_consent"`` (PR #73) 에 체이닝한다.
PR #73 머지 후 본 PR 을 머지하는 것이 권장 순서다. PR #73 미머지
상태에서 alembic 을 실행하면 down_revision 이 존재하지 않아 실패하므로,
검증 시 PR #73 의 023_marketing_consent.py 를 cherry-pick 해서
체인을 완성한 뒤 upgrade 를 돌린다.
"""
from alembic import op
import sqlalchemy as sa


revision = "024_cross_border_consent"
down_revision = "023_marketing_consent"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "cross_border_consent_at" not in existing_user_cols:
        op.add_column(
            "users",
            sa.Column(
                "cross_border_consent_at",
                sa.DateTime(),
                nullable=True,
            ),
        )

    if "cross_border_consent_revoked_at" not in existing_user_cols:
        op.add_column(
            "users",
            sa.Column(
                "cross_border_consent_revoked_at",
                sa.DateTime(),
                nullable=True,
            ),
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "cross_border_consent_revoked_at" in existing_user_cols:
        op.drop_column("users", "cross_border_consent_revoked_at")
    if "cross_border_consent_at" in existing_user_cols:
        op.drop_column("users", "cross_border_consent_at")
