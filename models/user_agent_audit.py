# Part of Journal Companion — see reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §6
"""UserAgentAudit — regulatory retention audit for Journal Companion.

Every call into ``services.agents.journal_companion.JournalCompanion.query``
produces exactly one row here. Rows exist for **2 years** (regulatory
inquiry response + post-incident review) and are purged by a cron that
reads the ``purge_after`` timestamp.

Privacy
-------
This table NEVER stores the raw user message. Only:
  - ``user_message_hash``  — sha256 hex (length-prefixed, see
    :func:`services.agents.audit_logger.message_hash`)
  - ``user_message_len``   — character count (for anomaly dashboards)
  - ``raw_output_len``     — Claude response length pre-gate
  - ``gate_verdict`` / ``gate_reason`` — did the legal gate pass?
  - ``persona_code``       — one of 8 deterministic buckets

Deliberately NOT stored (would create a PII footprint we'd have to
notify regulators about in a breach):
  - Real user message text
  - User email, name, IP
  - Raw LLM response
  - Any ticker / amount / price from the context

Wave B
------
The table ships disabled until legal counsel sign-off on Journal Companion
itself. Until then, ``audit_logger.log_agent_request`` is a no-op; this
model exists so the migration can land and rollback plans are reversible.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from extensions import db


# Retention window — 2 years is the FSC / 금융감독원 regulatory ceiling for
# retail advisory records. Keeping this constant here (rather than a
# config-time knob) makes the audit policy readable inside the model.
RETENTION_DAYS = 365 * 2


def _default_purge_after() -> datetime:
    """``generated_at + 2 years``, computed at insert time.

    Stored rather than derived so the purge cron can do a single indexed
    range scan (``WHERE purge_after < NOW()``) instead of scanning every
    row on every night.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        days=RETENTION_DAYS
    )


def _utcnow_naive() -> datetime:
    """UTC now without tzinfo, matching the rest of the codebase."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UserAgentAudit(db.Model):
    """Immutable audit row. Never updated after insert."""

    __tablename__ = "user_agent_audit"

    id = db.Column(db.Integer, primary_key=True)

    # Correlation id shared with structured logs (Sentry breadcrumbs,
    # Railway log stream). 12-char uuid4 prefix — long enough for uniqueness
    # across a multi-year horizon of expected volume (<1M rows), short
    # enough to paste into Slack.
    request_id = db.Column(db.String(12), nullable=False, index=True)

    # Linked for join-to-user — still indexed despite pseudonymization,
    # because admin support tickets start with a user id and we need to
    # fetch their last N agent interactions quickly.
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # One of services.agents.journal_companion.VALID_PERSONAS, 8 codes.
    persona_code = db.Column(db.String(8), nullable=False)

    # sha256 hex of the user's message, length-prefixed
    # (``"{len}:{sha256}"``). Prefix is cheap insurance against a future
    # bug where two different messages collide on just the digest.
    user_message_hash = db.Column(db.String(80), nullable=False)
    user_message_len = db.Column(db.Integer, nullable=False)

    # Pre-gate Claude output length. 0 means the LLM call failed and we
    # short-circuited to T5 — useful distinct from "gate refused a 400-char
    # reply".
    raw_output_len = db.Column(db.Integer, nullable=False, default=0)

    # Populated from services.agents.legal_gate.GateVerdict.
    # "pass" | "refused" | "deny_advice" | "deny_opinion" | ...
    gate_verdict = db.Column(db.String(32), nullable=False)
    gate_reason = db.Column(db.String(120), nullable=False, default="")

    # Claude model id — useful when we roll Haiku → Sonnet.
    model = db.Column(db.String(60), nullable=False, default="")

    generated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=_utcnow_naive,
        index=True,
    )

    # Pre-computed purge horizon. A nightly cron drops rows where
    # ``purge_after < NOW()``.
    purge_after = db.Column(
        db.DateTime,
        nullable=False,
        default=_default_purge_after,
    )

    __table_args__ = (
        # Composite indexes for the two common dashboards:
        #   1. "recent requests for user X" (admin support path)
        #   2. "recent refusals across all users" (ops kill-switch trigger)
        db.Index(
            "idx_user_agent_audit_user_time",
            "user_id",
            "generated_at",
        ),
        db.Index(
            "idx_user_agent_audit_verdict_time",
            "gate_verdict",
            "generated_at",
        ),
        db.Index(
            "idx_user_agent_audit_purge",
            "purge_after",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover — debug only
        return (
            f"<UserAgentAudit id={self.id} request_id={self.request_id} "
            f"verdict={self.gate_verdict}>"
        )


class AgentKillSwitch(db.Model):
    """Singleton-row kill switch — distributed-safe ``AGENT_ENABLED`` override.

    Only one row exists (``id=1``). Every Railway dyno reads the same row;
    the route layer caches it for 5 seconds so the read is essentially free.

    Why not an env var
    ------------------
    Env vars require a redeploy to change, and in a multi-dyno setup you'd
    have to wait for every worker to pick up the new value. A DB row flips
    atomically and takes effect within the cache TTL (5s) across the whole
    fleet.

    Why not ``settings.py``
    -----------------------
    ``config.py`` is loaded once at process start. A kill switch must be
    hot-readable — this table is the only place that meets that bar
    without wiring Redis.
    """

    __tablename__ = "agent_kill_switch"

    id = db.Column(db.Integer, primary_key=True)
    killed = db.Column(db.Boolean, nullable=False, default=False)

    killed_at = db.Column(db.DateTime, nullable=True)
    killed_by = db.Column(db.String(120), nullable=True)
    killed_reason = db.Column(db.String(500), nullable=True)

    revived_at = db.Column(db.DateTime, nullable=True)
    revived_by = db.Column(db.String(120), nullable=True)
    # Required: must attach counsel approval reference when reviving.
    revived_note = db.Column(db.String(500), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AgentKillSwitch killed={self.killed}>"
