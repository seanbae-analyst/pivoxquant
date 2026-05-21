"""Settings v2 per-event × per-channel notification preferences.

Revision ID: 043_notification_prefs
Revises: 042_anthropic_usage_log
Create Date: 2026-05-21

Settings v2 알림 매트릭스 영속화
================================

``frontend/src/components/settings/v2/notifications-matrix.tsx`` 의 7개 이벤트
× 3개 채널 (email/push/inapp) 토글은 그동안 localStorage 에만 저장되어 서버에
영속화되지 않았다 (GAP-E). 본 마이그레이션은 ``users.notification_prefs`` JSON
컬럼을 추가해 GET/PUT ``/api/notifications/preferences`` 가 사용자별 설정을
저장·조회할 수 있게 한다.

- nullable JSON. NULL = "한 번도 커스터마이즈 안 함" → 코드 레벨에서
  ``NOTIFICATION_PREF_DEFAULTS`` 로 fallback. 기존 row backfill 불필요.
- 부분 dict 저장 ({event_id: {channel: bool}}). 라우트가 defaults 위에 merge.
- 추가 비용 0원 — 기존 PostgreSQL/SQLite 에 컬럼 추가만.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "043_notification_prefs"
down_revision = "042_anthropic_usage_log"
branch_labels = None
depends_on = None

_TABLE = "users"
_COLUMN = "notification_prefs"


def _has_column(conn) -> bool:
    inspector = sa.inspect(conn)
    try:
        return _COLUMN in {c["name"] for c in inspector.get_columns(_TABLE)}
    except Exception:
        return False


def upgrade():
    conn = op.get_bind()
    if _has_column(conn):
        return  # 멱등 — 이미 존재하면 skip
    op.add_column(_TABLE, sa.Column(_COLUMN, sa.JSON(), nullable=True))


def downgrade():
    conn = op.get_bind()
    if _has_column(conn):
        op.drop_column(_TABLE, _COLUMN)
