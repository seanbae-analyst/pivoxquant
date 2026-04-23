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
import logging
import time
import uuid
from datetime import date, timedelta
from typing import Any, Optional

from flask import Blueprint, jsonify, request
from flask_login import current_user

from models.investment_profile import InvestmentProfile
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
    plan = getattr(user, "plan", None) or getattr(user, "subscription_tier", None)
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
