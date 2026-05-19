"""Anthropic Claude API usage logging table — Wave I G-3.

Revision ID: 042_anthropic_usage_log
Revises: 039_nps_feedback
Create Date: 2026-05-19

Wave I G-3 — Anthropic 비용 추적
================================

SWOT 500 root cause 는 2026-05-09 v28 세션에서 Anthropic 크레딧 소진으로
확정됐다. 당시 크레딧이 얼마나 남아있는지 사전에 알 수 있는 경로가 전혀
없었기 때문에 서비스가 조용히 무너졌다.

이 테이블은 services/ai/service.py 의 모든 Claude API 호출 직후 응답의
usage.input_tokens + usage.output_tokens 를 기록한다. 행 단위로 사용량이
쌓이면 scripts/nightly/anthropic_cost_estimate.py 가 매일 22:00 KST 에
집계해 일일 한도 대비 % 를 계산하고, 80% / 100% 시 Slack 경고를 발송한다.

설계 원칙
---------
- user_id: NULL 허용 (system/anonymous 호출 — SWOT, sector trend, streaming chat).
  기존 users.id FK 를 걸면 시스템 호출이나 batch 작업에서 INSERT 실패 위험.
  운영 모니터링 목적이므로 집계 레벨 정확도가 행 레벨 완전성보다 중요.
- endpoint: VARCHAR(64) — 호출 진입점 라벨 (예: 'swot', 'commentary',
  'chat_stream', 'coaching', 'morning_summary', 'sector_trend', 'competitor').
- model: VARCHAR(64) — 실제 호출 모델명 (MODEL 상수 변경 대비).
- 추가 비용 0원 — 기존 Railway PostgreSQL 에 테이블 추가만.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "042_anthropic_usage_log"
down_revision = "041_user_deletion_request"
branch_labels = None
depends_on = None

_TABLE = "anthropic_usage_log"


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if _TABLE in inspector.get_table_names():
        return  # 멱등 — 이미 존재하면 skip

    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        # NULL 허용 — 시스템/배치 호출은 user_id 가 없음
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        # 호출 모델 (예: claude-haiku-4-5-20251001)
        sa.Column("model", sa.String(64), nullable=False, index=True),
        # 진입점 라벨 (예: swot / commentary / chat_stream)
        sa.Column("endpoint", sa.String(64), nullable=False, index=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, default=0),
        sa.Column("output_tokens", sa.Integer(), nullable=False, default=0),
        # 수동 알림 / 나중에 캐시 miss rate 분석용
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
    )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if _TABLE in inspector.get_table_names():
        op.drop_table(_TABLE)
