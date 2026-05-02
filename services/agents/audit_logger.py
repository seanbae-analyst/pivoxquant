# Part of Journal Companion — see reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §6
"""Journal Companion audit persistence.

Wave B
------
Writes exactly one row per Companion request to ``user_agent_audit`` for
2-year regulatory retention. The raw user message is NEVER stored — only
its sha256 digest (length-prefixed for collision safety).

Design contract
---------------
Audit logging MUST NOT raise. A failure here must never break the user's
response. Every exception is swallowed and logged. The companion remains
operational even when the audit DB is down — at the cost of a
temporarily blind audit, which is recoverable (we still have structured
application logs).
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def message_hash(text: str) -> str:
    """Length-prefixed sha256 hex of ``text`` (``"{len}:{sha256}"``).

    Length prefix is cheap insurance against a future bug where two
    different messages collide on just the digest — they would still
    differ in length, and a simple string-equals comparison is enough
    for dedup and admin queries.

    Accepts ``None``-like inputs defensively: an empty string still
    hashes to the canonical sha256 of the empty string, so downstream
    queries never see a NULL digest.
    """
    text = text or ""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"{len(text)}:{digest}"


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def log_agent_request(
    *,
    request_id: str,
    user_id: int,
    persona_code: str,
    user_message: str,
    raw_output: str,
    gate_verdict: str,
    gate_reason: str,
    model: str,
    generated_at: Optional[datetime] = None,
) -> None:
    """Persist one ``UserAgentAudit`` row. Never raises.

    Called by :class:`services.agents.journal_companion.JournalCompanion`
    *after* the gate has run and *after* a safe response has been prepared
    for the user — so even a total DB outage only loses audit, not UX.

    Wave B: the UserAgentAudit model is present from migration 010. When
    the model or DB is unavailable (e.g. test harnesses that don't spin
    up SQLAlchemy), we silently no-op and log at INFO.
    """
    try:
        # Lazy imports: audit_logger is imported at the top of
        # journal_companion before the Flask app is built in some test
        # paths, so we defer the SQLAlchemy touch to call-time.
        from extensions import db
        from models.user_agent_audit import (
            UserAgentAudit,
            _default_purge_after,
        )

        row = UserAgentAudit(
            request_id=request_id[:12],
            user_id=user_id,
            persona_code=(persona_code or "")[:8],
            user_message_hash=message_hash(user_message),
            user_message_len=len(user_message or ""),
            raw_output_len=len(raw_output or ""),
            gate_verdict=(gate_verdict or "unknown")[:32],
            gate_reason=(gate_reason or "")[:120],
            model=(model or "")[:60],
            generated_at=generated_at or _utcnow_naive(),
            purge_after=_default_purge_after(),
        )
        db.session.add(row)
        db.session.commit()
        logger.info(
            "agent.audit.persisted request_id=%s verdict=%s",
            request_id,
            gate_verdict,
        )
    except Exception as exc:  # noqa: BLE001 — intentional broad catch
        # Never break the user. Log and move on — the structured logs in
        # journal_companion still capture the interaction for forensics.
        logger.warning(
            "agent.audit.persist_failed request_id=%s err=%s",
            request_id,
            exc,
        )
        try:
            from extensions import db

            db.session.rollback()
        except Exception:  # pragma: no cover — defensive cleanup
            logger.debug("silent-fallback: log_agent_request", exc_info=True)
            pass


def purge_expired() -> int:
    """Delete rows where ``purge_after < now``. Returns count deleted.

    Intended to run nightly via APScheduler / cron. Safe to invoke at
    any time — single indexed range scan thanks to
    ``idx_user_agent_audit_purge``.

    Returns ``0`` on any failure (logged). Never raises.
    """
    try:
        from extensions import db
        from models.user_agent_audit import UserAgentAudit

        cutoff = _utcnow_naive()
        deleted = (
            db.session.query(UserAgentAudit)
            .filter(UserAgentAudit.purge_after < cutoff)
            .delete(synchronize_session=False)
        )
        db.session.commit()
        logger.info("agent.audit.purged count=%d cutoff=%s", deleted, cutoff)
        return int(deleted or 0)
    except Exception as exc:  # noqa: BLE001
        logger.error("agent.audit.purge_failed err=%s", exc)
        try:
            from extensions import db

            db.session.rollback()
        except Exception:  # pragma: no cover
            logger.debug("silent-fallback: purge_expired", exc_info=True)
            pass
        return 0
