"""
Personal Journal Companion — main orchestrator.

Legal-safe scope (see reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §6):
  Remember · Mirror · Question · Refuse. Nothing else.

Flow per request:
  1. Auth gate: user must be Premium Plus + AGENT_ENABLED flag True.
  2. Load pseudonymized context (journal_entries, trade_history_proxy, IPS).
  3. Compose prompt: [system.md] + [persona layer] + [user message] + [context].
  4. Invoke Claude (Haiku for cost; Sonnet optional for long recall).
  5. Run output through services.agents.legal_gate.run_gate().
  6. If gate DENIES → respond with T5_REFUSAL, log the violation.
  7. If gate PASSES → append to audit log, return to caller.

Every request is audited for 2 years (regulatory inquiry response + kill
switch retro analysis).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from services.agents.audit_logger import log_agent_request
from services.agents.legal_gate import GateResult, run_gate, T5_REFUSAL
from services.agents.persona_adapter import compose_system_prompt

logger = logging.getLogger(__name__)


# ── System prompt composition ───────────────────────────────────────────────
#
# The canonical universal prompt (companion_system.md) plus the per-request
# persona overlay are composed in services.agents.persona_adapter.
# Reading happens per request so ops can hot-patch prompts without a
# service restart — the files are ~10 KB so the read cost is trivial.


# ── Data types ──────────────────────────────────────────────────────────────

VALID_PERSONAS = frozenset({
    "growth", "value", "balanced", "income",
    "quant", "speculator", "daytrader", "beginner",
})


@dataclass(frozen=True)
class AgentContext:
    """Pseudonymized user context passed into the model.

    Contains only the minimum needed for REMEMBER / MIRROR / QUESTION.
    Never includes: real name, email, account id, raw trade amounts,
    external news/prices, or other users' data.
    """
    user_hash: str                    # sha256 of user_id (goes to LLM prompt)
    persona_code: str                 # one of VALID_PERSONAS
    journal_entries: list[dict[str, Any]]     # [{date, topic, text}, ...]
    trade_history_proxy: list[dict[str, Any]] # [{date, sector_bucket, amount_bin, hold_days, journaled}]
    ips_statements: list[dict[str, Any]]      # [{date, clause_text}, ...]
    # Real user_id is kept OUT of the LLM prompt (see to_prompt_context)
    # but needed server-side for audit row FK. Kept Optional so pre-existing
    # test fixtures that construct AgentContext without user_id still work.
    user_id: Optional[int] = None

    def to_prompt_context(self) -> str:
        """Serialize as a compact JSON payload appended to the system prompt."""
        payload = {
            "user_hash": self.user_hash,
            "persona_code": self.persona_code,
            "journal_entries": self.journal_entries,
            "trade_history_proxy": self.trade_history_proxy,
            "ips_statements": self.ips_statements,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)


@dataclass(frozen=True)
class AgentResponse:
    """Response returned to the route layer."""
    text: str                         # always safe (gate-filtered)
    gate_verdict: str                 # GateVerdict value
    gate_reason: str
    model: str                        # "claude-haiku-4-5-20251001" etc
    request_id: str                   # audit correlation id
    generated_at: datetime


# ── Companion ───────────────────────────────────────────────────────────────

class JournalCompanion:
    """Single instance is stateless — safe to share across requests.

    One companion per app. Per-user state lives in AgentContext + audit log.
    """

    def __init__(self, *, claude_client: Any = None,
                 model: str = "claude-haiku-4-5-20251001") -> None:
        # Lazy Anthropic client resolution — allows testing without API key
        self._client = claude_client
        self._model = model

    # ── Feature flag helpers ───────────────────────────────────────────────

    @staticmethod
    def is_enabled() -> bool:
        """Hard gate: set AGENT_ENABLED=1 in env to activate.

        When False, all queries short-circuit to T5 refusal — the code may
        be deployed long before legal counsel signs off.
        """
        return os.getenv("AGENT_ENABLED", "0") in ("1", "true", "TRUE")

    # ── Public entry point ─────────────────────────────────────────────────

    def query(self, *, user_message: str, ctx: AgentContext,
              request_id: str) -> AgentResponse:
        """Main entry. Always returns a safe response.

        The caller must already have authenticated the user and confirmed
        Premium Plus entitlement. This method does not perform auth.
        """
        now = datetime.now(timezone.utc)

        # Hard kill switch (legal + ops)
        if not self.is_enabled():
            return self._refusal(
                reason="agent-disabled-flag",
                request_id=request_id,
                now=now,
            )

        # Persona validation (defensive — route should have enforced this)
        if ctx.persona_code not in VALID_PERSONAS:
            logger.warning(
                "agent.query.invalid_persona persona=%s request_id=%s",
                ctx.persona_code, request_id,
            )
            return self._refusal(
                reason="invalid-persona",
                request_id=request_id,
                now=now,
            )

        # User-message sanity (cap the surface for prompt injection)
        if len(user_message) > 2000:
            return self._refusal(
                reason="user-message-too-long",
                request_id=request_id,
                now=now,
            )

        raw = self._invoke_llm(user_message=user_message, ctx=ctx,
                               request_id=request_id)
        gate = run_gate(raw)

        self._audit(request_id=request_id, ctx=ctx,
                    user_message=user_message, raw_output=raw, gate=gate,
                    now=now)

        return AgentResponse(
            text=gate.safe_output,
            gate_verdict=gate.verdict.value,
            gate_reason=gate.reason,
            model=self._model,
            request_id=request_id,
            generated_at=now,
        )

    # ── Internals ──────────────────────────────────────────────────────────

    def _invoke_llm(self, *, user_message: str, ctx: AgentContext,
                    request_id: str) -> str:
        """Compose the prompt and call Claude.

        Uses messages API. System prompt (universal + persona overlay) is
        loaded fresh from disk every request — see persona_adapter module
        docstring for the hot-patch rationale.
        """
        if self._client is None:
            # Lazy import + instantiation so unit tests can stub the client
            try:
                from anthropic import Anthropic  # type: ignore
                self._client = Anthropic()
            except Exception as exc:  # noqa: BLE001
                logger.error("agent.client.unavailable err=%s", exc)
                return ""  # gate will convert empty → T5

        system_prompt = compose_system_prompt(ctx.persona_code)
        context_payload = ctx.to_prompt_context()

        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=800,   # gate caps at 2400 chars; keep room under
                temperature=0.3,  # low — deterministic enough for templates
                system=system_prompt,
                messages=[
                    {"role": "user",
                     "content": (
                         f"[USER CONTEXT — pseudonymized]\n{context_payload}\n\n"
                         f"[USER MESSAGE]\n{user_message}"
                     )},
                ],
                metadata={"user_id": ctx.user_hash, "request_id": request_id},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("agent.llm.error err=%s request_id=%s", exc, request_id)
            return ""  # gate converts empty → T5 refusal

        # Claude returns a list of content blocks; we only expect text.
        blocks = getattr(resp, "content", None) or []
        return "\n".join(
            getattr(b, "text", "") for b in blocks
            if getattr(b, "type", "text") == "text"
        )

    def _refusal(self, *, reason: str, request_id: str,
                 now: datetime) -> AgentResponse:
        logger.info("agent.refusal reason=%s request_id=%s", reason, request_id)
        return AgentResponse(
            text=T5_REFUSAL,
            gate_verdict="refused",
            gate_reason=reason,
            model=self._model,
            request_id=request_id,
            generated_at=now,
        )

    def _audit(self, *, request_id: str, ctx: AgentContext,
               user_message: str, raw_output: str, gate: GateResult,
               now: datetime) -> None:
        """Persist every request for 2-year regulatory retention.

        Wave B delegates to :func:`services.agents.audit_logger.log_agent_request`
        which writes a ``UserAgentAudit`` row. Structured-log fallback below
        runs unconditionally so we still have forensic breadcrumbs even when
        the DB write silently fails (the logger swallows its exceptions by
        contract — never break the user's response).
        """
        logger.info(
            "agent.audit request_id=%s user_hash=%s persona=%s "
            "verdict=%s reason=%s user_msg_len=%d raw_len=%d ts=%s",
            request_id, ctx.user_hash, ctx.persona_code,
            gate.verdict.value, gate.reason,
            len(user_message), len(raw_output),
            now.isoformat(),
        )

        if ctx.user_id is None:
            # No FK → nothing to persist. Happens in unit tests that don't
            # wire up a DB or a real User. Structured log above is enough.
            return

        log_agent_request(
            request_id=request_id,
            user_id=ctx.user_id,
            persona_code=ctx.persona_code,
            user_message=user_message,
            raw_output=raw_output,
            gate_verdict=gate.verdict.value,
            gate_reason=gate.reason,
            model=self._model,
            generated_at=now,
        )
