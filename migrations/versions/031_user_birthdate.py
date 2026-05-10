"""PIPA §22 ⑥ — users.birthdate column.

Revision ID: 031_user_birthdate
Revises: 030_perf_indexes
Create Date: 2026-05-10

Why this field
--------------
개인정보 보호법 (PIPA) §22 ⑥ — 만 14세 미만 아동의 개인정보를 수집할
때에는 법정대리인의 동의를 받아야 한다. PivoxQuant 출시 시점에는
법정대리인 동의 절차가 구축되어 있지 않으므로, 만 14세 미만 가입을
서버단에서 fail-fast 한다. 이를 위해 사용자의 생년월일을 영속화해
나이 기준 가입 시점뿐 아니라 향후 감사 / 동의 철회 시점 검증에도
활용한다.

기존 ``frontend/src/lib/age-verification.ts`` + signup 폼은 클라이언트
측 fail-fast 만 적용했으므로, curl 직접 호출 시 만 13세 가입이 가능
했다 (audit 부서 W1.4 P0 결함 보고). 본 마이그레이션은 그 우회를
영구 차단하기 위한 데이터 계층이다.

Idempotency
-----------
009 / 021 / 023 / 024 와 동일한 inspector 기반 idempotent 패턴.
이미 컬럼이 존재하면 ``ADD COLUMN`` 을 스킵하므로 라이브 DB 에서
재실행해도 안전한 no-op.

Nullable 정책
-------------
초기 ``nullable=True`` 로 도입한다. 이유:

1. 기존 사용자 (PR 머지 전 가입) 의 birthdate 가 NULL 이므로
   ``nullable=False`` 로 시작하면 마이그레이션이 실패한다.
2. OAuth 신규 가입 플로우가 별도 ``/oauth-finalize`` 단계로 분리
   되어 있어, OAuth 콜백 → User row 생성 사이에 일시적으로 NULL
   상태가 존재할 수 있다.
3. 백필 default 값 (예: 1990-01-01) 은 *false 정보* 이므로 권고하지
   않는다. legacy user 는 다음 로그인 시 interstitial 로 birthdate
   입력을 강제한다 (routes/auth.py 의 ``/oauth-finalize`` + 신규
   사용자 가입 시 모두 검증).

후속 PR 권고: 모든 row 가 backfill 된 시점에 ``nullable=False`` 로
전환하는 별도 마이그레이션 (032_user_birthdate_required).
"""
from alembic import op
import sqlalchemy as sa


revision = "031_user_birthdate"
down_revision = "030_perf_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "birthdate" not in existing_user_cols:
        op.add_column(
            "users",
            sa.Column(
                "birthdate",
                sa.Date(),
                nullable=True,
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "birthdate" in existing_user_cols:
        op.drop_column("users", "birthdate")
