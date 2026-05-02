"""
routes/agent.py — Personal Journal Companion API (Closed Beta).

Single public endpoint: POST /api/agent/query

Gates (in order, first failure short-circuits):
  1. Feature flag        AGENT_ENABLED env var (default OFF)
  2. Auth                user must be logged in (Flask-Login)
  3. Entitlement         user.plan in {"premium_plus", "founding_lifetime"}
  4. Rate limit          conservative — one query per 20s per user
  5. Legal gate          applied inside services.agents.journal_companion

Every request is audit-logged for 2-year regulatory retention.

References:
  - reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §6
  - services/agents/prompts/companion_system.md
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from typing import Any, Optional

from flask import Blueprint, jsonify, request
from flask_login import current_user

from models.investment_profile import InvestmentProfile
from security import ai_rate_limit, limiter
from services.agents.data_bridge import (
    load_ips_statements as _db_load_ips,
    load_journal_entries as _db_load_journal,
    load_trade_history_proxy as _db_load_trade_proxy,
)
from services.agents.journal_companion import (
    AgentContext,
    JournalCompanion,
    VALID_PERSONAS,
)

logger = logging.getLogger(__name__)

agent_bp = Blueprint("agent", __name__, url_prefix="/api/agent")


# ── Email validation (no external dep) ───────────────────────────────────────
#
# RFC 5322 in full is notoriously hairy; this regex is the pragmatic subset
# used by the HTML5 ``<input type="email">`` spec, which is what the teaser
# form enforces on the client. Keeping server + client in lockstep means we
# never reject an email the form accepted.
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)
_MAX_EMAIL_LEN = 254  # RFC 5321 §4.5.3.1.3.

_VALID_SOURCES = frozenset({
    "landing-teaser", "landing_teaser",
    "companion-gate", "companion_gate",
    "pricing-page", "pricing_page",
    "manual", "other",
})


# ── Singleton companion (stateless) ──────────────────────────────────────────

_companion: Optional[JournalCompanion] = None


def _get_companion() -> JournalCompanion:
    global _companion
    if _companion is None:
        _companion = JournalCompanion()
    return _companion


# ── Simple in-memory rate limit ──────────────────────────────────────────────
# Good enough for Closed Beta (single Railway dyno). Production will swap for
# Redis-backed limiter — keeps interface identical.

_RATE_WINDOW_SEC = 20
_last_request: dict[int, float] = {}


def _rate_limit_ok(user_id: int) -> bool:
    now = time.monotonic()
    prev = _last_request.get(user_id, 0.0)
    if now - prev < _RATE_WINDOW_SEC:
        return False
    _last_request[user_id] = now
    return True


# ── Entitlement ──────────────────────────────────────────────────────────────

_ENTITLED_PLANS = frozenset({"premium_plus", "founding_lifetime"})


def _entitled(user: Any) -> bool:
    # 2026-05-02: prefer `effective_tier` so DEV_FOUNDING_EMAILS dev
    # backdoor + future Stripe overrides flow through cleanly.
    # Falls through to raw `plan` / `subscription_tier` for legacy
    # callers / tests that mock a User without the property.
    plan = (
        getattr(user, "effective_tier", None)
        or getattr(user, "plan", None)
        or getattr(user, "subscription_tier", None)
    )
    return plan in _ENTITLED_PLANS


# ── Pseudonymization ─────────────────────────────────────────────────────────

def _user_hash(user_id: int) -> str:
    """Stable sha256 — same user always hashes to the same 16-char prefix."""
    return hashlib.sha256(f"pq-user:{user_id}".encode("utf-8")).hexdigest()[:16]


def _load_context(user: Any) -> AgentContext:
    """Build a pseudonymized context payload for one user.

    Closed Beta: pull journal / IPS / trade proxy from existing tables. The
    surface is deliberately minimal — only what the three allowed operations
    (Remember, Mirror, Question) need.
    """
    persona = _resolve_persona(user)

    # Placeholder loaders — wire to concrete tables in Wave B. Empty lists are
    # safe: the system prompt handles empty context with T5 refusal.
    journal_entries = _load_journal_entries(user)
    ips = _load_ips_statements(user)
    trade_proxy = _load_trade_history_proxy(user)

    return AgentContext(
        user_hash=_user_hash(user.id),
        persona_code=persona,
        journal_entries=journal_entries,
        trade_history_proxy=trade_proxy,
        ips_statements=ips,
        user_id=user.id,
    )


def _resolve_persona(user: Any) -> str:
    """Map the user's InvestmentProfile into one of 8 persona codes.

    Falls back to "balanced" when no profile exists (new users, pre-onboarding).
    """
    profile = InvestmentProfile.query.filter_by(user_id=user.id).first()
    if profile is None:
        return "balanced"

    # `profile_type` is the canonical persona code in models/investment_profile.py
    code = (profile.profile_type or "balanced").lower().strip()
    return code if code in VALID_PERSONAS else "balanced"


def _load_journal_entries(user: Any) -> list[dict[str, Any]]:
    """Wave B: delegate to services.agents.data_bridge.

    Empty journal is a valid state — the companion responds with T5
    asking what the user would like to discuss.
    """
    return _db_load_journal(user.id, limit=20)


def _load_ips_statements(user: Any) -> list[dict[str, Any]]:
    """Wave B: delegate to services.agents.data_bridge."""
    return _db_load_ips(user.id)


def _load_trade_history_proxy(user: Any) -> list[dict[str, Any]]:
    """Wave B: delegate to services.agents.data_bridge.

    Ticker / price / amount NEVER leaves the data_bridge module — the
    returned dicts contain only sector_bucket + amount_bin + hold_days.
    """
    return _db_load_trade_proxy(user.id, days=90)


# ── Routes ───────────────────────────────────────────────────────────────────

@agent_bp.route("/query", methods=["POST"])
@ai_rate_limit
def query() -> Any:
    """POST /api/agent/query

    Body: {"message": str}
    Response (always 200 except gate failures below):
      {
        "text": str,                  # always safe — T1–T6 only
        "gate_verdict": str,
        "request_id": str,
        "generated_at": ISO8601
      }

    Failure responses:
      401 — not authenticated
      403 — not entitled (requires Premium Plus or Founding Lifetime)
      429 — rate-limited
      503 — AGENT_ENABLED flag is off (Closed Beta gate)
    """
    companion = _get_companion()

    if not companion.is_enabled():
        return jsonify({
            "error": "agent-disabled",
            "message": "Journal Companion is in Closed Beta. Not yet available.",
        }), 503

    # Distributed kill switch (admin-controlled). Cached 5s per dyno; fails
    # closed on DB outage so refusal > leaky response.
    try:
        from routes.agent_admin import is_agent_killed
        if is_agent_killed():
            return jsonify({
                "error": "agent-killed",
                "message": "Journal Companion temporarily offline (ops kill switch).",
            }), 503
    except Exception:  # pragma: no cover — import-time safety
        pass

    if not current_user.is_authenticated:
        return jsonify({"error": "Login required"}), 401

    if not _entitled(current_user):
        return jsonify({
            "error": "not-entitled",
            "message": "Journal Companion requires Premium Plus or Founding Lifetime.",
        }), 403

    if not _rate_limit_ok(current_user.id):
        return jsonify({
            "error": "rate-limited",
            "message": f"One query per {_RATE_WINDOW_SEC}s during Closed Beta.",
            "retry_after_sec": _RATE_WINDOW_SEC,
        }), 429

    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"error": "missing-message"}), 400

    ctx = _load_context(current_user)
    request_id = uuid.uuid4().hex[:12]

    resp = companion.query(
        user_message=message,
        ctx=ctx,
        request_id=request_id,
    )

    return jsonify({
        "text": resp.text,
        "gate_verdict": resp.gate_verdict,
        "gate_reason": resp.gate_reason,
        "request_id": resp.request_id,
        "generated_at": resp.generated_at.isoformat(),
        "model": resp.model,
        "disclaimer": (
            "본 응답은 유저 본인의 과거 기록에 기반한 정보 제공일 뿐, "
            "투자자문(자본시장법 §6②)이 아닙니다. "
            "모든 매매 결정과 그 결과에 대한 책임은 유저 본인에게 있습니다."
        ),
    })


# ── Waitlist ────────────────────────────────────────────────────────────────
#
# Intentionally unauthenticated and independent of AGENT_ENABLED / kill-switch
# state: collecting interest from anonymous landing visitors is the entire
# point, and the whole feature being gated during Closed Beta is *precisely*
# why the waitlist must stay open. See task P0-2 / HANDOVER.md v6 §3-D #2.
#
# Storage posture is dictated by the pending privacy policy draft —
# ``reports/legal/DRAFT_PRIVACY_POLICY_COMPANION_2026-04-23.md §9.1`` — which
# treats ``email_hash`` as the canonical identifier and the raw email as
# opt-in. Because the submitter typed the email into a form whose headline
# promises "we'll email when your seat opens", we treat the submission
# itself as the opt-in signal and persist ``email_plaintext`` via
# ``consent_direct_email=True``. The waitlist row is the *only* record of
# the email — no ancillary marketing logs, no analytics fan-out.


def _normalize_source(raw: Any) -> str:
    """Clamp the source string to the known allowlist — attackers don't get
    to stuff attribution fields. Unknown values collapse to ``"other"``."""
    if not isinstance(raw, str):
        return "landing-teaser"
    cleaned = raw.strip().lower().replace("_", "-")[:40]
    if not cleaned:
        return "landing-teaser"
    if cleaned in {s.replace("_", "-") for s in _VALID_SOURCES}:
        return cleaned
    return "other"


def _normalize_persona(raw: Any) -> Optional[str]:
    """Accept one of the eight canonical personas or drop the field.

    Free-form persona text is explicitly out of scope (legal_gate bypass
    prevention) — unknown values return ``None`` rather than echoing back
    attacker-controlled text into the DB.
    """
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip().lower()[:20]
    if cleaned in VALID_PERSONAS:
        return cleaned
    return None


def _valid_email(email: str) -> bool:
    if not email or len(email) > _MAX_EMAIL_LEN:
        return False
    return bool(_EMAIL_RE.match(email))


@agent_bp.route("/waitlist", methods=["POST"])
@limiter.limit("5 per hour", key_func=lambda: request.remote_addr or "unknown")
def waitlist() -> Any:
    """POST /api/agent/waitlist

    Body (JSON):
        email    (str, required)  — RFC 5321 compliant address, <= 254 chars.
        persona  (str, optional)  — one of VALID_PERSONAS; unknown dropped.
        source   (str, optional)  — attribution (landing-teaser by default).
        referrer (str, optional)  — alias for source (frontend-compat).

    Responses:
        201 {"status": "queued",           "position": <int>}  — new enrolment
        200 {"status": "already-registered","position": <int>} — idempotent repeat
        400 — missing or malformed email
        429 — IP rate limit exceeded (5 per hour)
        500 — storage failure (structured JSON log emitted)

    Notes
    -----
    - Always 200/201 on success. ``status`` discriminates new vs repeat so
      the frontend can log the distinction without exposing row ids.
    - ``position`` is a 1-indexed ordinal among all existing rows (created_at
      ASC). It is advisory — admins control actual invitation order — and is
      recomputed on each request rather than stored.
    - The endpoint is intentionally independent of ``AGENT_ENABLED`` and the
      ops kill switch. Disabling the waitlist would defeat the Closed Beta
      funnel (task P0-2).
    - CSRF: the security middleware skips CSRF enforcement for requests
      without an authenticated session, which is the anonymous case we
      optimise for. Authenticated visitors hitting this endpoint (from the
      /companion page) still supply the double-submit token via ``apiFetch``.
    """
    # Structured log breadcrumb — every request gets a request_id so a
    # 500 traceback can be reconciled with the frontend's error surface.
    request_id = uuid.uuid4().hex[:12]

    payload = request.get_json(silent=True) or {}
    email_raw = payload.get("email")
    if not isinstance(email_raw, str):
        return jsonify({
            "error": "missing-email",
            "message": "Field 'email' is required (string).",
            "request_id": request_id,
        }), 400

    email = email_raw.strip()
    if not _valid_email(email):
        return jsonify({
            "error": "invalid-email",
            "message": "Provide a valid email address (RFC 5321).",
            "request_id": request_id,
        }), 400

    persona = _normalize_persona(payload.get("persona"))
    # ``referrer`` is an alias — the landing teaser currently sends ``source``,
    # but the task spec calls for ``referrer``; accept both to shield the
    # frontend from a breaking change.
    source = _normalize_source(payload.get("source") or payload.get("referrer"))

    # Opt-in semantics: submission of the form IS the consent. Raw email
    # stored so the admin invite flow can reach the user directly.
    user_id: Optional[int] = None
    if getattr(current_user, "is_authenticated", False):
        user_id = int(getattr(current_user, "id", 0)) or None

    try:
        from extensions import db
        from models.companion_waitlist import CompanionWaitlist

        # ``enroll()`` is now race-safe: it catches the IntegrityError raised
        # when two concurrent POSTs with the same email both miss the
        # pre-check. The second caller receives the first caller's row with
        # ``created=False``, identical to a normal idempotent re-submit. See
        # ``models/companion_waitlist.enroll`` for the full rationale.
        row, created = CompanionWaitlist.enroll(
            email=email,
            consent_direct_email=True,
            user_id=user_id,
            source=source,
            persona_interest=persona,
        )
        existed = not created

        # 1-indexed FIFO position. Cheap for Closed Beta volume (< 10k).
        # ``created_at ASC`` matches the admin invite cursor.
        position = (
            db.session.query(CompanionWaitlist.id)
            .filter(CompanionWaitlist.created_at <= row.created_at)
            .count()
        )

    except Exception as exc:  # noqa: BLE001
        # Structured JSON log — never emit the raw email (PII).
        logger.exception(
            json.dumps({
                "event": "agent.waitlist.store_failed",
                "request_id": request_id,
                "source": source,
                "persona": persona,
                "remote_addr": request.remote_addr,
                "error": str(exc)[:200],
            })
        )
        try:
            from extensions import db as _db
            _db.session.rollback()
        except Exception:
            pass
        return jsonify({
            "error": "waitlist-store-failed",
            "message": "Could not record waitlist entry. Try again shortly.",
            "request_id": request_id,
        }), 500

    logger.info(
        json.dumps({
            "event": "agent.waitlist.enrolled",
            "request_id": request_id,
            "already_registered": existed,
            "source": source,
            "persona": persona,
            "position": position,
        })
    )

    body = {
        "status": "already-registered" if existed else "queued",
        "position": int(position),
        "request_id": request_id,
    }
    return jsonify(body), (200 if existed else 201)


@agent_bp.route("/status", methods=["GET"])
def status() -> Any:
    """GET /api/agent/status — lightweight health + flag status.

    Public (no auth). Used by frontend to decide whether to render the
    Journal Companion entry point at all.
    """
    companion = _get_companion()
    return jsonify({
        "enabled": companion.is_enabled(),
        "phase": "closed-beta" if companion.is_enabled() else "off",
        "legal_status": "pending-counsel-review",
        "entitlement_plans": sorted(_ENTITLED_PLANS),
    })
