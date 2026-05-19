"""Onboarding email sequence — scheduled_emails queue table.

Revision ID: 038_scheduled_emails
Revises: 037_marketing_consent_split
Create Date: 2026-05-19

Wave G S5 — D+0 / D+3 / D+7 onboarding sequence
================================================

After a user signs up (password or OAuth-finalize) we enqueue three
rows here:

* ``welcome`` — D+0 (immediate) TRANSACTIONAL — §50 ③ 면제.
* ``d3_guide`` — D+3 INFORMATION — §50 ① 분리 동의 필수.
* ``d7_pro_nudge`` — D+7 INFORMATION — §50 ① 분리 동의 필수.

A 15-minute cron (``scripts/nightly/email_scheduler_dispatcher.py``)
drains rows whose ``scheduled_send_at <= NOW()`` and ``sent_at IS NULL``
and ``skipped_reason IS NULL``. The whole pipeline is feature-flagged
behind ``PIVOX_ONBOARDING_SEQUENCE_ENABLED`` (default false) — variance
flip after the lawyer's Q-S1 answer arrives.

Columns
-------
* ``id``                — PK.
* ``user_id``           — FK → users.id (CASCADE — 사용자 탈퇴 시 정리).
* ``email_type``        — short slug (``welcome``, ``d3_guide``,
  ``d7_pro_nudge``). Together with ``user_id`` forms the
  per-user-per-email idempotency anchor; see ``idempotency_key``.
* ``email_category``    — ``transactional`` / ``information`` matching
  ``services.email.sender.EmailCategory``. Persists the §50 classification
  so we can re-render an audit log without re-deriving it from email_type.
* ``scheduled_send_at`` — UTC naive (project convention) — dispatcher
  polls ``WHERE scheduled_send_at <= NOW() AND sent_at IS NULL``.
* ``sent_at``           — NULL = pending. Set on provider accept.
* ``skipped_reason``    — short enum-ish string (``feature_flag_off``,
  ``no_user_or_email``, ``no_consent``, ``provider_failed``). NULL =
  pending or successfully sent.
* ``idempotency_key``   — UNIQUE. Format ``"u{user_id}:{email_type}"``.
  Survives re-signup-on-same-email + cron double-fire + webhook retries.
  Equivalent in spirit to the ``session_id`` UNIQUE in
  ``checkout_expirations`` — different shape because the anchor is
  ``(user, email_type)`` not a single Stripe id.

Idempotency
-----------
023 / 024 / 028 / 038_checkout_expirations inspector pattern. No-ops
on re-run.

Chaining
--------
``down_revision = "037_marketing_consent_split"``. Joins the existing
sibling 038s (``038_checkout_expirations``, ``038_inactive_nudge_sent_at``)
under the same parent. A future ``039_*`` will merge the three heads
via a tuple ``down_revision``.
"""
from alembic import op
import sqlalchemy as sa


revision = "038_scheduled_emails"
down_revision = "037_marketing_consent_split"
branch_labels = None
depends_on = None


_TABLE_NAME = "scheduled_emails"
_UNIQUE_IDEMPOTENCY_NAME = "uq_scheduled_emails_idempotency_key"
_INDEX_SEND_AT_NAME = "ix_scheduled_emails_scheduled_send_at"
_INDEX_USER_NAME = "ix_scheduled_emails_user_id"


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
        sa.Column("email_type", sa.String(length=40), nullable=False),
        sa.Column("email_category", sa.String(length=20), nullable=False),
        sa.Column("scheduled_send_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("skipped_reason", sa.String(length=80), nullable=True),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("idempotency_key", name=_UNIQUE_IDEMPOTENCY_NAME),
    )
    op.create_index(
        _INDEX_SEND_AT_NAME,
        _TABLE_NAME,
        ["scheduled_send_at"],
        unique=False,
    )
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
