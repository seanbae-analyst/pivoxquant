"""Wave I C-2 — PIPA §21 30-day deletion request columns.

Revision ID: 041_user_deletion_request
Revises: 040_auth_events
Create Date: 2026-05-19

Wave I C-2 — 30일 자동 파기 (PIPA §21)
======================================

PIPA §21 ① 위탁 종료 / 회원 탈퇴 시 *지체 없이 (without delay)* 파기
의무를 부담한다. 다만 시행령 §16 ① 은 보관·복구 목적의 30일 grace
period 를 허용한다 — 사용자가 실수 탈퇴를 철회할 수 있는 창. 본
마이그레이션은 그 두 시점을 분리해 기록한다.

신규 컬럼
----------
``deletion_requested_at``
    회원이 ``POST /api/auth/delete-request`` 를 호출한 시점 (UTC, naive).
    NULL = 탈퇴 요청 없음. 값 설정 = "soft delete" 상태 — login 거부 +
    모든 데이터 read API 401. 30일 후 ``pipa_purge`` cron 이 hard delete.

``deleted_at``
    실제 hard delete 가 끝난 시점. 보통 row 자체가 사라지므로 *별도의
    감사 로그 row* 에서만 의미를 갖지만, 마이그레이션 단계에서는 안전판
    으로 컬럼만 추가한다. ``pipa_purge`` 가 row 를 ``DELETE FROM users``
    하기 직전 마지막 commit 직전에 stamp.

왜 ``deleted_at`` 컬럼인가 (row 삭제 전인데)
----------------------------------------------
PIPA 검사 대응 시 "탈퇴 요청 후 30일 만에 실제로 지운다는 증거" 가
필요하다. row 자체가 사라지면 그 증거가 없으므로, ``pipa_purge`` 는
hard delete 직전 ``deleted_at`` 을 stamp + commit + 5초 뒤 별도
audit-log table 에 ``(user_id, email_sha256, deleted_at)`` 를 append
한다. ``users`` row 자체는 그 다음 트랜잭션에서 삭제. (다음 PR 에서
``user_deletion_audit`` 테이블 추가 예정 — 본 PR 은 컬럼만.)

Idempotency
-----------
Inspector-pattern (mirrors 038_inactive_nudge_sent_at) — skips ADD
COLUMN if the column already exists.
"""
from alembic import op
import sqlalchemy as sa


revision = "041_user_deletion_request"
down_revision = "040_auth_events"
branch_labels = None
depends_on = None


_NEW_COLS = ("deletion_requested_at", "deleted_at")


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = {c["name"] for c in inspector.get_columns("users")}

    for col_name in _NEW_COLS:
        if col_name not in existing:
            op.add_column(
                "users",
                sa.Column(col_name, sa.DateTime(), nullable=True),
            )

    # Partial index: only rows pending purge (deletion_requested_at IS NOT NULL
    # AND deleted_at IS NULL) — keeps the daily cron scan O(pending) not O(users).
    # SQLite 3.8+ and PostgreSQL both support partial indexes; column-only
    # fallback used otherwise.
    try:
        op.create_index(
            "ix_users_deletion_requested_at",
            "users",
            ["deletion_requested_at"],
            postgresql_where=sa.text("deletion_requested_at IS NOT NULL"),
            sqlite_where=sa.text("deletion_requested_at IS NOT NULL"),
        )
    except Exception:
        # Older backends — fall back to a plain column index. Slower scan
        # but functionally correct.
        op.create_index(
            "ix_users_deletion_requested_at",
            "users",
            ["deletion_requested_at"],
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = {c["name"] for c in inspector.get_columns("users")}

    try:
        op.drop_index("ix_users_deletion_requested_at", table_name="users")
    except Exception:
        pass

    for col_name in _NEW_COLS:
        if col_name in existing:
            op.drop_column("users", col_name)
