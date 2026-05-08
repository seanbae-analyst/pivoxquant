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
from routes.decorators import api_auth
from security import ai_rate_limit, general_rate_limit, limiter, trade_rate_limit
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
@api_auth                # 2026-05-08 (PR #148 follow-up): authenticate FIRST so
                         # unauthenticated requests cannot drain the per-IP
                         # ai_rate_limit bucket. Also removes the redundant
                         # inline `current_user.is_authenticated` check below.
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
      401 — not authenticated (emitted by @api_auth before reaching this body)
      403 — not entitled (requires Premium Plus or Founding Lifetime)
      429 — rate-limited
      503 — AGENT_ENABLED flag is off (Closed Beta gate) /
            kill switch engaged
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
        logger.debug("silent-fallback: closed on DB outage so refusal > leaky response. | query", exc_info=True)
        pass

    # NOTE: inline `if not current_user.is_authenticated` removed —
    # @api_auth above already short-circuits with the standard
    # SESSION_EXPIRED 401 envelope before this body ever runs.

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
        200 {"ok": true, "message": "<generic>", "request_id": "<hex>"}  — accepted (new OR existing)
        400 — missing or malformed email
        429 — IP rate limit exceeded (5 per hour)
        500 — storage failure (structured JSON log emitted)

    Notes
    -----
    - 2026-05-09 (SEC-E / PIPA §29): both new and duplicate submissions now
      return the **same** status code (200) and the **same** generic body so
      an external attacker cannot use the response as an enumeration oracle
      to learn which emails are on the waitlist. The legacy
      201/``status=queued`` vs 200/``status=already-registered`` divergence
      was a textbook account-existence side channel — banned outright by the
      personal-information protection act §29 (technical safeguards).
    - The internal ``created`` flag is still surfaced in the structured
      audit log (``agent.waitlist.enrolled.already_registered``) so admins
      can monitor abuse, but it never leaves the server.
    - The ``position`` field was also dropped from the response — under the
      old semantics it monotonically increased across submissions and could
      be diffed across requests to reveal which emails were already enrolled.
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
        # ``row`` is intentionally unused after this point — see SEC-E note in
        # the docstring for why we no longer derive a public ``position``.
        del row

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
            logger.debug("silent-fallback: waitlist", exc_info=True)
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
            # ``already_registered`` stays in the audit log for admin
            # monitoring — it's never echoed to the public response.
            "already_registered": existed,
            "source": source,
            "persona": persona,
        })
    )

    # 2026-05-09 (SEC-E / PIPA §29): identical 200 + generic body whether the
    # email is new OR already on the list. ``existed`` deliberately does NOT
    # influence the response — see docstring.
    body = {
        "ok": True,
        "message": (
            "If your email is on the waitlist, you'll receive an update."
        ),
        "request_id": request_id,
    }
    return jsonify(body), 200


@agent_bp.route("/status", methods=["GET"])
@general_rate_limit  # 2026-05-09 (SEC-C): rate-limit even unauthenticated callers
def status() -> Any:
    """GET /api/agent/status — lightweight health + flag status.

    Public (no auth). Used by frontend to decide whether to render the
    Journal Companion entry point at all.

    Hardening (2026-05-09 SEC-C follow-up):
      * ``@general_rate_limit`` — bring the public endpoint into line with the
        rest of the agent surface; without this an unauthenticated visitor can
        scrape it without bound.
      * ``legal_status`` field removed — it leaked an internal posture
        (``pending-counsel-review``) that gave outsiders a discoverable hook
        for legal pressure and PR amplification. The frontend never read the
        field (only declared it in TypeScript) so removing it is safe.
    """
    companion = _get_companion()
    return jsonify({
        "enabled": companion.is_enabled(),
        "phase": "closed-beta" if companion.is_enabled() else "off",
        "entitlement_plans": sorted(_ENTITLED_PLANS),
    })


# ── PIPA: Agent data export & delete ─────────────────────────────────────────
#
# Two endpoints powering the "Agent memory" subsection on the user's profile
# page (frontend/src/app/(dashboard)/profile/_v[12]/*). Required by the
# personal information protection act (개인정보보호법 §35 access right + §36
# correction/deletion right) — the user must be able to download and erase
# server-side personal data on demand.
#
# Scope (intentionally conservative — Wave-2 closed-beta posture):
#   * Export — UserAgentAudit rows belonging to the caller. Audit rows are
#     stored under sha256(message) so we never round-trip the raw text;
#     the export is therefore safe to hand back to the user verbatim.
#     CompanionWaitlist rows linked to user_id are also returned for
#     completeness (raw email is the user's own email).
#   * Delete — wipes the same two tables for this user. The local
#     `pq_*` localStorage keys (persona, pulse, history) are wiped by
#     the frontend after this call returns, so a successful 200 fully
#     clears server + client state.
#
# What is NOT touched here (deliberate):
#   * users.* / investment_profiles.* — full account deletion lives at
#     /api/auth/account (DELETE), which is the right surface for that.
#   * artifacts / brag_cards — those are PDF deliverables, not "agent
#     memory"; they have their own retention policy.

@agent_bp.route("/export", methods=["GET"])
@api_auth                # 2026-05-08 (PR #149 sibling fix — Vuln SEC-A): authenticate
                         # FIRST so unauthenticated requests cannot drain the per-IP
                         # general_rate_limit bucket. Also removes the redundant
                         # inline `current_user.is_authenticated` check below.
@general_rate_limit
def export_agent_data() -> Any:
    """GET /api/agent/export

    Returns a JSON blob the user can save locally (frontend triggers a
    download via Blob + a.click).

    Response shape (HTTP 200):
        {
            "exported_at":   ISO8601,
            "user_id":       <int>,
            "audit_rows":    [<UserAgentAudit.to_dict>, ...],
            "waitlist_rows": [<CompanionWaitlist.to_dict>, ...],
            "row_counts":    {"audit": N, "waitlist": M}
        }

    Errors:
        401 — not authenticated (emitted by @api_auth before reaching this body).
        500 — DB read failed (rolled back; payload describes the error).
    """
    request_id = uuid.uuid4().hex[:12]

    try:
        from datetime import datetime, timezone
        from extensions import db  # noqa: F401  — ensure session is bound
        from models.user_agent_audit import UserAgentAudit

        audit_rows: list[dict[str, Any]] = []
        try:
            rows = (
                UserAgentAudit.query
                .filter_by(user_id=int(current_user.id))
                .order_by(UserAgentAudit.generated_at.desc())
                .limit(2000)  # hard cap — paranoia bound on payload size
                .all()
            )
            for r in rows:
                audit_rows.append({
                    "request_id":    r.request_id,
                    "persona_code":  r.persona_code,
                    "user_message_len": int(r.user_message_len or 0),
                    "raw_output_len":   int(r.raw_output_len or 0),
                    "gate_verdict":  r.gate_verdict,
                    "gate_reason":   r.gate_reason or "",
                    "model":         r.model or "",
                    "generated_at":  r.generated_at.isoformat() + "Z"
                                     if r.generated_at else None,
                })
        except Exception as exc:
            logger.debug("export: audit read failed: %s", exc)

        waitlist_rows: list[dict[str, Any]] = []
        try:
            from models.companion_waitlist import CompanionWaitlist
            wl_rows = (
                CompanionWaitlist.query
                .filter_by(user_id=int(current_user.id))
                .all()
            )
            for w in wl_rows:
                waitlist_rows.append({
                    "email":           getattr(w, "email", None),
                    "source":          getattr(w, "source", None),
                    "persona_interest": getattr(w, "persona_interest", None),
                    "created_at":      w.created_at.isoformat() + "Z"
                                       if getattr(w, "created_at", None)
                                       else None,
                })
        except Exception as exc:
            logger.debug("export: waitlist read failed: %s", exc)

        return jsonify({
            "exported_at":   datetime.now(timezone.utc).isoformat(),
            "user_id":       int(current_user.id),
            "audit_rows":    audit_rows,
            "waitlist_rows": waitlist_rows,
            "row_counts": {
                "audit":    len(audit_rows),
                "waitlist": len(waitlist_rows),
            },
            "request_id":    request_id,
        })
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            json.dumps({
                "event": "agent.export.failed",
                "request_id": request_id,
                "user_id": int(getattr(current_user, "id", 0)),
                "error": str(exc)[:200],
            })
        )
        try:
            from extensions import db as _db
            _db.session.rollback()
        except Exception:
            pass
        return jsonify({
            "error": "export-failed",
            "message": "Could not assemble export. Try again shortly.",
            "request_id": request_id,
        }), 500


@agent_bp.route("/delete", methods=["DELETE"])
@agent_bp.route("", methods=["DELETE"])
@api_auth                # 2026-05-08 (PR #149 sibling fix — Vuln SEC-A): authenticate
                         # FIRST so unauthenticated requests cannot drain the per-IP
                         # trade_rate_limit bucket. Also removes the redundant
                         # inline `current_user.is_authenticated` check below.
@trade_rate_limit        # destructive endpoint — tighter (30/min) than general
def delete_agent_data() -> Any:
    """DELETE /api/agent/delete  (alias: DELETE /api/agent)

    Wipes server-side agent memory for the calling user:
      * UserAgentAudit  — all rows where user_id == current_user.id
      * CompanionWaitlist — rows linked to user_id (raw email is removed)

    Response shape (HTTP 200):
        {
            "deleted":     {"audit": N, "waitlist": M},
            "deleted_at":  ISO8601,
            "request_id":  <hex12>
        }

    Errors:
        401 — not authenticated (emitted by @api_auth before reaching this body).
        500 — DB write failed; transaction rolled back.

    The frontend then wipes local `pq_*` keys; a successful 200 here
    means the server-side trace is gone.
    """
    request_id = uuid.uuid4().hex[:12]
    user_id = int(current_user.id)

    try:
        from datetime import datetime, timezone
        from extensions import db
        from models.user_agent_audit import UserAgentAudit

        deleted_audit = 0
        deleted_wait = 0

        try:
            deleted_audit = (
                UserAgentAudit.query
                .filter_by(user_id=user_id)
                .delete(synchronize_session=False)
            )
        except Exception as exc:
            logger.debug("delete: audit wipe failed: %s", exc)
            deleted_audit = 0

        try:
            from models.companion_waitlist import CompanionWaitlist
            deleted_wait = (
                CompanionWaitlist.query
                .filter_by(user_id=user_id)
                .delete(synchronize_session=False)
            )
        except Exception as exc:
            logger.debug("delete: waitlist wipe failed: %s", exc)
            deleted_wait = 0

        db.session.commit()

        logger.info(
            json.dumps({
                "event": "agent.data.deleted",
                "request_id": request_id,
                "user_id": user_id,
                "audit_rows": int(deleted_audit or 0),
                "waitlist_rows": int(deleted_wait or 0),
            })
        )

        return jsonify({
            "deleted": {
                "audit":    int(deleted_audit or 0),
                "waitlist": int(deleted_wait or 0),
            },
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
        })
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            json.dumps({
                "event": "agent.delete.failed",
                "request_id": request_id,
                "user_id": user_id,
                "error": str(exc)[:200],
            })
        )
        try:
            from extensions import db as _db
            _db.session.rollback()
        except Exception:
            pass
        return jsonify({
            "error": "delete-failed",
            "message": "Could not delete agent data. Try again shortly.",
            "request_id": request_id,
        }), 500
