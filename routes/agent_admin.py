# Part of Journal Companion — see reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §6
"""Admin API for the Journal Companion (kill switch + audit query).

All endpoints are gated by ``ADMIN_EMAILS`` — same env var the other
admin routes (``admin_fmp``, ``admin_preview``) use. Non-admin sessions
receive 403. Unauthenticated sessions receive 401.

Endpoints
---------
``POST /api/admin/agent/kill``
    Flip the distributed kill switch to ON. Every subsequent
    ``/api/agent/query`` call returns 503 within the cache TTL (5s).
``POST /api/admin/agent/revive``
    Flip the kill switch OFF. Body MUST include ``legal_approval`` text
    (counsel reference — stored on the kill switch row for audit).
``GET /api/admin/agent/audit/recent``
    Recent ``UserAgentAudit`` rows. Filters: ``limit``, ``verdict``.
    Never returns the raw user message — only the hash.
``GET /api/admin/agent/stats``
    24h / 7d / 30d volume + refusal rate + persona distribution.
``POST /api/admin/agent/purge-expired``
    Manually trigger the 2-year retention purge (nightly cron normally).

Every kill/revive operation is logged with ``actor_email`` so a
breach response can reconstruct the operator timeline.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Blueprint, jsonify, request
from flask_login import current_user

from extensions import db
from routes.decorators import api_auth
from security import general_rate_limit

logger = logging.getLogger(__name__)

agent_admin_bp = Blueprint(
    "agent_admin", __name__, url_prefix="/api/admin/agent"
)


# ── Access control ───────────────────────────────────────────────────────────


# 2026-05-17 wave 13 P2 (PR #442): centralized parser; alias kept.
from services.admin_emails import get_admin_emails as _admin_emails  # noqa: E402


def _deny_non_admin():
    """Return a JSON error response if the caller isn't an admin.

    Returns ``None`` when the caller IS admin, so the route body runs.
    Fails closed: no ``ADMIN_EMAILS`` env var → everyone is denied.
    """
    if not getattr(current_user, "is_authenticated", False):
        return jsonify({"error": "Login required", "error_kr": "로그인이 필요합니다.", "code": "SESSION_EXPIRED"}), 401
    admins = _admin_emails()
    if not admins:
        logger.warning(
            "ADMIN_EMAILS not configured — denying /api/admin/agent"
        )
        return jsonify({"error": "Admin access not configured"}), 403
    email = (getattr(current_user, "email", "") or "").lower()
    if email not in admins:
        return jsonify({"error": "Forbidden"}), 403
    return None


def _current_admin_email() -> str:
    return (getattr(current_user, "email", "") or "").lower()


# ── Kill switch (cached read, 5s TTL) ────────────────────────────────────────
#
# Writes are rare; reads are on every /api/agent/query call. A 5-second
# TTL balances hot-flip responsiveness (ops flips, effect within 5s
# fleet-wide) with avoiding a SELECT per LLM call.

_KILL_CACHE: dict[str, Any] = {"killed": False, "expires_at": 0.0}
_KILL_CACHE_TTL_SEC = 5.0


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _read_kill_switch_row() -> Any:
    """Return the singleton kill switch row (creating it on first read)."""
    from models.user_agent_audit import AgentKillSwitch

    row = db.session.get(AgentKillSwitch, 1)
    if row is None:
        row = AgentKillSwitch(id=1, killed=False)
        db.session.add(row)
        db.session.commit()
    return row


def is_agent_killed() -> bool:
    """Return True if the kill switch is currently ON. Cached for 5s.

    Safe to call from any route (including ``/api/agent/query``). On any
    DB error it fails CLOSED — returning True — because the goal is to
    stop agent traffic in the face of an outage we can't diagnose.
    """
    import time

    now = time.monotonic()
    if now < _KILL_CACHE.get("expires_at", 0.0):
        return bool(_KILL_CACHE.get("killed", False))

    try:
        row = _read_kill_switch_row()
        killed = bool(getattr(row, "killed", False))
    except Exception as exc:  # noqa: BLE001
        logger.error("agent_admin.kill_read_failed err=%s", exc)
        try:
            db.session.rollback()
        except Exception:
            logger.debug("silent-fallback: is_agent_killed", exc_info=True)
            pass
        # Fail closed — better to refuse than to leak responses while
        # the operator's kill signal is stuck.
        return True

    _KILL_CACHE["killed"] = killed
    _KILL_CACHE["expires_at"] = now + _KILL_CACHE_TTL_SEC
    return killed


def _invalidate_kill_cache() -> None:
    _KILL_CACHE["expires_at"] = 0.0


# ── Routes ───────────────────────────────────────────────────────────────────


@agent_admin_bp.route("/kill", methods=["POST"])
@api_auth                # 2026-05-08 (PR #148 follow-up): block unauth before
                         # the rate_limit bucket spends. _deny_non_admin() still
                         # runs inside for the non-admin authenticated case.
@general_rate_limit
def kill() -> Any:
    """POST /api/admin/agent/kill

    Body (optional): {"reason": str}

    Flip the kill switch to ON immediately. Effect fleet-wide within 5s.
    """
    denied = _deny_non_admin()
    if denied is not None:
        return denied

    payload = request.get_json(silent=True) or {}
    reason = (payload.get("reason") or "").strip()[:500]

    try:
        row = _read_kill_switch_row()
        row.killed = True
        row.killed_at = _utcnow_naive()
        row.killed_by = _current_admin_email()[:120]
        row.killed_reason = reason
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        logger.exception("agent_admin.kill_write_failed err=%s", exc)
        return jsonify({"error": "kill-switch-write-failed"}), 500

    _invalidate_kill_cache()
    logger.warning(
        "agent.kill_switch.engaged actor=%s reason=%s",
        _current_admin_email(),
        reason,
    )
    return jsonify(
        {
            "ok": True,
            "killed": True,
            "killed_at": _utcnow_naive().isoformat(),
            "killed_by": _current_admin_email(),
        }
    )


@agent_admin_bp.route("/revive", methods=["POST"])
@api_auth                # PR #148 follow-up — see /kill above.
@general_rate_limit
def revive() -> Any:
    """POST /api/admin/agent/revive

    Body (required): {"legal_approval": "<counsel-ref>"}

    Reviving the companion without legal sign-off is a liability event —
    we force the operator to paste a counsel reference, and store it on
    the kill switch row for audit.
    """
    denied = _deny_non_admin()
    if denied is not None:
        return denied

    payload = request.get_json(silent=True) or {}
    note = (payload.get("legal_approval") or "").strip()
    if len(note) < 3:
        return (
            jsonify(
                {
                    "error": "legal-approval-required",
                    "message": (
                        "Provide a legal_approval reference "
                        "(counsel email, memo id, etc) before revival."
                    ),
                }
            ),
            400,
        )
    note = note[:500]

    try:
        row = _read_kill_switch_row()
        row.killed = False
        row.revived_at = _utcnow_naive()
        row.revived_by = _current_admin_email()[:120]
        row.revived_note = note
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        logger.exception("agent_admin.revive_write_failed err=%s", exc)
        return jsonify({"error": "kill-switch-write-failed"}), 500

    _invalidate_kill_cache()
    logger.warning(
        "agent.kill_switch.revived actor=%s note=%s",
        _current_admin_email(),
        note,
    )
    return jsonify(
        {
            "ok": True,
            "killed": False,
            "revived_at": _utcnow_naive().isoformat(),
            "revived_by": _current_admin_email(),
            "legal_approval": note,
        }
    )


@agent_admin_bp.route("/audit/recent", methods=["GET"])
@api_auth                # PR #148 follow-up — uniform auth gate across
                         # agent_admin_bp; _deny_non_admin() still gates
                         # the admin-vs-non-admin distinction below.
def audit_recent() -> Any:
    """GET /api/admin/agent/audit/recent?limit=50&verdict=deny_*

    Returns recent audit rows (newest first). User message is returned
    only as hash + length — never verbatim.
    """
    denied = _deny_non_admin()
    if denied is not None:
        return denied

    from models.user_agent_audit import UserAgentAudit

    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 500))
    except ValueError:
        limit = 50

    verdict_filter = (request.args.get("verdict") or "").strip()

    query = db.session.query(UserAgentAudit).order_by(
        UserAgentAudit.generated_at.desc()
    )
    if verdict_filter:
        # Allow prefix filters: "deny_*" → SQL LIKE
        if verdict_filter.endswith("*"):
            query = query.filter(
                UserAgentAudit.gate_verdict.like(verdict_filter[:-1] + "%")
            )
        else:
            query = query.filter(UserAgentAudit.gate_verdict == verdict_filter)

    rows = query.limit(limit).all()

    return jsonify(
        {
            "ok": True,
            "count": len(rows),
            "rows": [
                {
                    "id": r.id,
                    "request_id": r.request_id,
                    # Mask user_id: send only the last 4 digits so admin
                    # can correlate on a ticket but casual log leaks don't
                    # expose the full id space.
                    "user_id_suffix": str(r.user_id)[-4:] if r.user_id else "",
                    "persona_code": r.persona_code,
                    "gate_verdict": r.gate_verdict,
                    "gate_reason": r.gate_reason,
                    "user_message_len": r.user_message_len,
                    "raw_output_len": r.raw_output_len,
                    "model": r.model,
                    "generated_at": (
                        r.generated_at.isoformat() if r.generated_at else None
                    ),
                }
                for r in rows
            ],
        }
    )


@agent_admin_bp.route("/stats", methods=["GET"])
@api_auth                # PR #148 follow-up — see /audit/recent.
def stats() -> Any:
    """GET /api/admin/agent/stats

    24h / 7d / 30d totals + refusal rate + persona distribution.
    Safe to poll — all queries are indexed.
    """
    denied = _deny_non_admin()
    if denied is not None:
        return denied

    from sqlalchemy import func

    from models.user_agent_audit import UserAgentAudit

    now = _utcnow_naive()
    windows = {
        "24h": now - timedelta(hours=24),
        "7d": now - timedelta(days=7),
        "30d": now - timedelta(days=30),
    }

    def _window_stats(since: datetime) -> dict[str, Any]:
        q = db.session.query(UserAgentAudit).filter(
            UserAgentAudit.generated_at >= since
        )
        total = q.count()
        refused = q.filter(
            UserAgentAudit.gate_verdict != "pass"
        ).count()
        rate = (refused / total) if total else 0.0
        return {
            "total": int(total),
            "refused": int(refused),
            "refusal_rate": round(rate, 4),
        }

    persona_rows = (
        db.session.query(
            UserAgentAudit.persona_code, func.count(UserAgentAudit.id)
        )
        .filter(UserAgentAudit.generated_at >= windows["30d"])
        .group_by(UserAgentAudit.persona_code)
        .all()
    )
    persona_distribution = {code: int(count) for code, count in persona_rows}

    return jsonify(
        {
            "ok": True,
            "as_of": now.isoformat(),
            "windows": {k: _window_stats(v) for k, v in windows.items()},
            "persona_distribution_30d": persona_distribution,
            "kill_switch_on": is_agent_killed(),
        }
    )


@agent_admin_bp.route("/waitlist", methods=["GET"])
@api_auth                # PR #148 follow-up — see /audit/recent.
def waitlist_list() -> Any:
    """GET /api/admin/agent/waitlist

    Full FIFO-ordered list of Closed Beta signups. Admin-only.

    Query params:
        limit   (int, optional, default 500, max 2000)
        source  (str, optional)  — exact-match attribution filter.

    Response:
        {
          "ok": true,
          "total": <int>,            # count of all rows in DB
          "count": <int>,            # count in this response
          "rows": [
            {"id": ..., "email": ..., "persona": ..., "source": ...,
             "created_at": ..., "invited_at": ..., "activated_at": ...,
             "position": ...}
          ]
        }

    The ``email`` field is the plaintext address when the user consented to
    direct notification (which, per ``routes.agent.waitlist``, is every
    row) and ``<hashed>`` otherwise. The raw hash is never leaked to the
    admin UI — that's a PII amplifier.
    """
    denied = _deny_non_admin()
    if denied is not None:
        return denied

    from models.companion_waitlist import CompanionWaitlist

    try:
        limit = max(1, min(int(request.args.get("limit", 500)), 2000))
    except ValueError:
        limit = 500

    source_filter = (request.args.get("source") or "").strip()

    query = CompanionWaitlist.query.order_by(CompanionWaitlist.created_at.asc())
    if source_filter:
        query = query.filter(CompanionWaitlist.source == source_filter[:40])

    rows = query.limit(limit).all()
    total = CompanionWaitlist.query.count()

    def _masked_email(row: CompanionWaitlist) -> str:
        """Return the display string for a waitlist row's email column.

        NOTE — name vs. behaviour (audit GAP-2):
        In closed beta, direct consent implies plaintext for operational
        outreach; this helper therefore returns the raw email verbatim
        (not a masked form) when consent was given, and the literal
        sentinel ``"<hashed>"`` otherwise. The function name is retained
        for call-site stability; rename pending post-GA when we introduce
        real masking (e.g. ``al***@example.com``) for non-admin surfaces.
        """
        if row.email_plaintext:
            return row.email_plaintext
        return "<hashed>"

    return jsonify(
        {
            "ok": True,
            "total": int(total),
            "count": len(rows),
            "rows": [
                {
                    "id": r.id,
                    "email": _masked_email(r),
                    "persona": r.persona_interest,
                    "source": r.source,
                    # 2026-05-18 Wave G-4 P1-C: mask user_id to last-4-digits,
                    # mirrors the audit/recent endpoint pattern (lines 298-301).
                    # Sequential PK exposure → user-count estimation + DB scan
                    # attack surface. Audit endpoint already comments "casual
                    # log leaks don't expose the full id space" — waitlist
                    # endpoint needs the same protection.
                    "user_id_suffix": str(r.user_id)[-4:] if r.user_id else "",
                    "created_at": (
                        r.created_at.isoformat() if r.created_at else None
                    ),
                    "invited_at": (
                        r.invited_at.isoformat() if r.invited_at else None
                    ),
                    "activated_at": (
                        r.activated_at.isoformat() if r.activated_at else None
                    ),
                    # Position among returned rows; the row is already ordered
                    # by created_at ASC so this matches the FIFO queue number
                    # visible to the submitter.
                    "position": idx + 1,
                }
                for idx, r in enumerate(rows)
            ],
        }
    )


@agent_admin_bp.route("/purge-expired", methods=["POST"])
@api_auth                # PR #148 follow-up — see /kill.
@general_rate_limit
def purge_expired_route() -> Any:
    """POST /api/admin/agent/purge-expired

    Manually trigger the 2-year retention purge. Normally runs via cron;
    this exists so ops can confirm the job is functional without waiting
    overnight.
    """
    denied = _deny_non_admin()
    if denied is not None:
        return denied

    from services.agents.audit_logger import purge_expired

    deleted = purge_expired()
    logger.info(
        "agent.audit.manual_purge actor=%s deleted=%d",
        _current_admin_email(),
        deleted,
    )
    return jsonify({"ok": True, "deleted": int(deleted)})
