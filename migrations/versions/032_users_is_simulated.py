"""Continuous User Simulation Phase 1 — users.is_simulated column.

Revision ID: 032_users_is_simulated
Revises: 031_user_birthdate
Create Date: 2026-05-13

Why this field
--------------
``docs/specs/continuous-user-sim-spec.md`` Phase 1 Q3 — Continuous User
Simulation (CAUS) 환경에서 시뮬레이션 user 와 실 user 를 영속적으로 격리
하기 위한 단일 BOOLEAN 플래그. 별도 schema/tenant 분리(추가 비용 + 운영
복잡도) 없이 ``users`` 테이블에 1 컬럼 추가만으로 격리를 달성한다.

플래그 동작
-----------
- 기본값 ``FALSE`` (서버 default + Python default) 로 모든 기존 row 가
  자동 backfill 된다 — 회원가입 flow 코드 변경 없이 안전하게 적용 가능.
- ``TRUE`` 인 row 는:
    * EmailSender 가 정통망법 §50 안전판으로 발송 스킵 (후속 PR).
    * Analytics / KPI 쿼리에서 ``WHERE is_simulated = FALSE`` 필터로
      제외 (후속 PR + lint 룰).
    * Sentry tag ``user_type=sim`` 로 분리 (후속 PR).
    * 일요일 04:30 KST cron 이 7일 이상 묵은 로그 / artifact truncate
      (후속 PR — 본 마이그레이션은 데이터 계층만 도입).

직렬화 정책
-----------
``User.to_dict`` 류 일반 user response 에는 노출 X (보안상 admin 전용).
본 마이그레이션은 컬럼만 추가하므로 응답 surface 변경 없음.

Idempotency
-----------
009 / 021 / 023 / 024 / 031 패턴을 그대로 따른다. inspector 로 컬럼
존재를 검사 후 ``ADD COLUMN`` 을 스킵 — 라이브 DB 재실행 안전.

``server_default=sa.false()``
-----------------------------
SQLite 와 PostgreSQL 모두에서 ``ADD COLUMN ... NOT NULL DEFAULT false``
구문이 기존 row 를 자동으로 ``FALSE`` 로 채워넣게 만든다. server default
없이 ``nullable=False`` 로만 두면 PostgreSQL 이 기존 row 백필 누락으로
실패한다.
"""
from alembic import op
import sqlalchemy as sa


revision = "032_users_is_simulated"
down_revision = "031_user_birthdate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "is_simulated" not in existing_user_cols:
        op.add_column(
            "users",
            sa.Column(
                "is_simulated",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "is_simulated" in existing_user_cols:
        op.drop_column("users", "is_simulated")
