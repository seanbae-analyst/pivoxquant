"""Checkout abandonment follow-up — checkout_expirations table.

Revision ID: 038_checkout_expirations
Revises: 037_marketing_consent_split
Create Date: 2026-05-19

Wave G C-M1 — Stripe ``checkout.session.expired`` 1h transactional follow-up
============================================================================

Stripe 가 발행한 Checkout Session 이 만료(``checkout.session.expired``,
기본 24h 만료) 되면 사용자가 결제 페이지에 진입했다가 이탈한 시점을 알
수 있다. 이 시점부터 1시간 뒤에 transactional 안내 메일을 보내 카드
문제를 디버깅하거나 Customer Portal 로 이동하도록 유도한다.

본 마이그레이션은 dispatcher 가 "발송 예정 시각이 도래했고 아직
미발송" row 를 polling 할 수 있도록 작은 큐 테이블을 추가한다.

Columns
-------
* ``id``                — PK
* ``user_id``           — FK → users.id (CASCADE — 사용자 삭제 시 정리)
* ``session_id``        — Stripe Checkout Session ID (cs_test_..., cs_live_...).
  ``UNIQUE`` — Stripe 가 동일 session 에 대해 expired 를 재발행할 일은
  없지만, 회선 재전송으로 webhook 가 두 번 도달할 가능성이 있으므로
  idempotency 키로 사용. ``processed_stripe_events.event_id`` 와는
  별도 — Stripe event id 는 retry 별로 stable 하지만 session id 는
  session 별로 stable.
* ``expired_at``        — Stripe 가 알린 만료 시각 (UTC naive — 본 프로젝트
  컨벤션, Position.opened_at 등 동일).
* ``scheduled_send_at`` — ``expired_at + 1h``. dispatcher 가 ``NOW()`` 와
  비교하여 도래 여부 판단.
* ``sent_at``           — 실제 발송 성공 시각. NULL = 미발송. UPDATE 후
  재호출 시 short-circuit.
* ``skipped_reason``    — 발송 skip 사유 (feature flag off / 이미 active
  구독 / 이메일 미보유 / provider fail 등). dispatcher 가 row 를 영구
  닫을 때 기록. NULL = 미시도 또는 정상 발송.

Idempotency
-----------
023 / 024 / 028 의 inspector 패턴 그대로. 컬럼/인덱스 존재 시 ADD 스킵.
재실행 안전한 no-op.

Feature flag
------------
본 마이그레이션은 *스키마만* 추가. dispatcher 의 실제 발송은
``PIVOX_CHECKOUT_FOLLOWUP_ENABLED`` env (default false) 게이트.
변호사 Q-S1 답변 후 flag flip. transactional 분류라 §50 면제이지만
일관성 + 안전성으로 deploy 단계 게이트.

Chaining
--------
``down_revision = "037_marketing_consent_split"``. 동시 작업 wave 에서
두 형제 sibling 마이그레이션(``038_scheduled_emails`` C-S5,
``038_inactive_nudge_sent_at`` C-S2) 이 같은 부모를 공유한다. 이는
의도된 mergepoint 패턴 — 후속 마이그레이션(``039_nps_feedback`` 등)이
``down_revision = ("038_checkout_expirations", "038_scheduled_emails")``
tuple 로 형제들을 통합한다. 본 마이그레이션은 분기를 만들지만 단독으로
새 head 를 누적시키지는 않는다.
"""
from alembic import op
import sqlalchemy as sa


revision = "038_checkout_expirations"
down_revision = "037_marketing_consent_split"
branch_labels = None
depends_on = None


_TABLE_NAME = "checkout_expirations"
_UNIQUE_SESSION_NAME = "uq_checkout_expirations_session_id"
_INDEX_SEND_AT_NAME = "ix_checkout_expirations_scheduled_send_at"
_INDEX_USER_NAME = "ix_checkout_expirations_user_id"


def _table_exists(inspector, name: str) -> bool:
    try:
        return name in inspector.get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if _table_exists(inspector, _TABLE_NAME):
        return

    op.create_table(
        _TABLE_NAME,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("expired_at", sa.DateTime(), nullable=False),
        sa.Column(
            "scheduled_send_at",
            sa.DateTime(),
            nullable=False,
            index=False,  # explicit index created below
        ),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("skipped_reason", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("session_id", name=_UNIQUE_SESSION_NAME),
    )
    # Dispatcher hot-path: ORDER BY scheduled_send_at WHERE sent_at IS NULL.
    op.create_index(
        _INDEX_SEND_AT_NAME,
        _TABLE_NAME,
        ["scheduled_send_at"],
        unique=False,
    )
    # User-facing lookup ("did we already follow up with this user?").
    op.create_index(
        _INDEX_USER_NAME,
        _TABLE_NAME,
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not _table_exists(inspector, _TABLE_NAME):
        return
    for idx in (_INDEX_SEND_AT_NAME, _INDEX_USER_NAME):
        try:
            op.drop_index(idx, table_name=_TABLE_NAME)
        except Exception:
            pass
    op.drop_table(_TABLE_NAME)
