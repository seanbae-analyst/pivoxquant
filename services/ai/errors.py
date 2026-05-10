"""
PivoxQuant — AI error classification (B-08 graceful degradation)
================================================================

Single source of truth for translating Anthropic SDK exceptions into
stable, frontend-readable error codes + correct HTTP status codes.

Why a dedicated module
----------------------
Before this file, ``routes/ai.py`` returned a bare 500 with the literal
string "Failed to generate coaching" whenever the Anthropic call failed
— including when credits were exhausted (the actual root cause for
B-08, see memory v28). The user saw a server bug; the operator got
no diagnostic; the frontend had no machine-readable hook to render
a friendly retry banner.

This module classifies the failure into one of:

    AI_API_KEY_INVALID    — bad / revoked key (operator action: rotate)
    AI_RATE_LIMITED       — Anthropic 429 (transient: retry with backoff)
    AI_QUOTA_EXHAUSTED    — credits/balance depleted (operator action: top up)
    AI_NETWORK_ERROR      — connection / timeout (transient)
    AI_UNKNOWN            — anything else (true server bug → 500)

The first four map to **HTTP 503 Service Unavailable** — the semantically
correct status for transient external-service failure. Only AI_UNKNOWN
keeps the 500.

Frontend contract
-----------------
Every classified error response is shaped::

    {
      "error":      "AI service temporarily unavailable",
      "error_code": "AI_QUOTA_EXHAUSTED",
      "retry_after": 3600,            # seconds; advisory
      "fallback":   "Using cached signals; AI coaching ..."
    }

The route also sets the ``Retry-After`` HTTP header for HTTP-spec clients.

Compliance
----------
Quota / credit / API-key error messages from the SDK can embed account
identifiers, request IDs, or balance numbers. We **never** echo the raw
SDK message — only the classification code + a fixed user-facing string.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# ── Error codes ──────────────────────────────────────────────────────────────
# Stable, frontend-readable. Do NOT rename without coordinating with the
# frontend's AI error-banner component.
AI_API_KEY_INVALID = "AI_API_KEY_INVALID"
AI_RATE_LIMITED = "AI_RATE_LIMITED"
AI_QUOTA_EXHAUSTED = "AI_QUOTA_EXHAUSTED"
AI_NETWORK_ERROR = "AI_NETWORK_ERROR"
AI_UNKNOWN = "AI_UNKNOWN"

# Codes that map to HTTP 503 (transient / external). Anything not in this
# set is treated as a true server bug (HTTP 500).
TRANSIENT_CODES = frozenset({
    AI_API_KEY_INVALID,
    AI_RATE_LIMITED,
    AI_QUOTA_EXHAUSTED,
    AI_NETWORK_ERROR,
})

# User-facing fallback string per code. Bilingual (EN / KR) — matches the
# legal_filter convention used elsewhere in the AI surface.
USER_MESSAGES = {
    AI_API_KEY_INVALID: {
        "error": "AI service temporarily unavailable",
        "error_kr": "AI 서비스를 일시적으로 사용할 수 없습니다",
        "fallback": "Using cached signals; AI commentary will return when service resumes.",
        "fallback_kr": "캐시된 시그널을 사용 중입니다. AI 해설은 서비스 복구 후 제공됩니다.",
    },
    AI_RATE_LIMITED: {
        "error": "AI service temporarily unavailable",
        "error_kr": "AI 서비스를 일시적으로 사용할 수 없습니다",
        "fallback": "Too many requests; please retry in a moment.",
        "fallback_kr": "요청이 많아 일시적으로 제한됐습니다. 잠시 후 다시 시도해 주세요.",
    },
    AI_QUOTA_EXHAUSTED: {
        "error": "AI service temporarily unavailable",
        "error_kr": "AI 서비스를 일시적으로 사용할 수 없습니다",
        "fallback": "Using cached signals; AI coaching will return when service resumes.",
        "fallback_kr": "캐시된 시그널을 사용 중입니다. AI 코칭은 서비스 복구 후 제공됩니다.",
    },
    AI_NETWORK_ERROR: {
        "error": "AI service temporarily unavailable",
        "error_kr": "AI 서비스를 일시적으로 사용할 수 없습니다",
        "fallback": "Network issue reaching AI provider; please retry shortly.",
        "fallback_kr": "AI 서비스 연결에 문제가 있습니다. 잠시 후 다시 시도해 주세요.",
    },
    AI_UNKNOWN: {
        "error": "AI service error",
        "error_kr": "AI 서비스 오류",
        "fallback": "An unexpected error occurred. Please try again later.",
        "fallback_kr": "예기치 못한 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
    },
}

# Default Retry-After seconds per code. Advisory — frontend may override.
RETRY_AFTER_SECONDS = {
    AI_API_KEY_INVALID: 3600,    # operator must rotate; advise long backoff
    AI_RATE_LIMITED: 60,         # Anthropic rate windows are short
    AI_QUOTA_EXHAUSTED: 3600,    # credit top-up is operator action
    AI_NETWORK_ERROR: 30,        # short transient
    AI_UNKNOWN: 0,
}


def classify_anthropic_error(exc: BaseException) -> str:
    """Map an exception (typically from anthropic SDK) → error_code.

    Detection order matters — more specific subclasses first. We use
    ``isinstance`` against the SDK classes when available (graceful degrade
    if the SDK isn't installed at import time, e.g. in unit tests with a
    mocked client).

    Quota detection is heuristic: Anthropic returns ``BadRequestError``
    (400) with body containing "credit balance" / "billing" / "quota" when
    credits are depleted, NOT a dedicated exception class. We sniff the
    string representation defensively — never the exception's internal
    attributes (those vary across SDK versions).
    """
    if exc is None:
        return AI_UNKNOWN

    # Lazy SDK import — keeps this module testable without anthropic installed.
    try:
        import anthropic  # type: ignore
    except Exception:  # pragma: no cover
        anthropic = None  # type: ignore

    msg_lower = (str(exc) or "").lower()

    if anthropic is not None:
        # 1) Auth errors: bad / revoked / missing API key.
        if isinstance(exc, anthropic.AuthenticationError) or isinstance(
            exc, anthropic.PermissionDeniedError
        ):
            return AI_API_KEY_INVALID

        # 2) Rate limit (429).
        if isinstance(exc, anthropic.RateLimitError):
            return AI_RATE_LIMITED

        # 3) Network / transport.
        if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
            return AI_NETWORK_ERROR

        # 4) Quota exhaustion: comes through as BadRequestError(400) whose
        #    body mentions credit balance / billing / quota. The literal
        #    Anthropic message is "Your credit balance is too low to access
        #    the Anthropic API." — sniff that family.
        if isinstance(exc, anthropic.BadRequestError):
            if any(
                tok in msg_lower
                for tok in ("credit balance", "credit_balance", "billing", "quota")
            ):
                return AI_QUOTA_EXHAUSTED

        # 5) Generic 5xx from upstream → treat as transient network/provider.
        if isinstance(exc, anthropic.InternalServerError):
            return AI_NETWORK_ERROR

        # 6) Some SDK builds also surface APIStatusError(429) without using
        #    RateLimitError directly — sniff status_code defensively.
        if isinstance(exc, anthropic.APIStatusError):
            status = getattr(exc, "status_code", None)
            if status == 429:
                return AI_RATE_LIMITED
            if status in (401, 403):
                return AI_API_KEY_INVALID
            if status and 500 <= status < 600:
                return AI_NETWORK_ERROR
            # 400 with credit-balance text already handled above by
            # BadRequestError; status==400 here is "true bad request".

    # 7) Last-resort string sniffing — covers cases where the SDK is mocked
    #    in tests with a plain ``Exception("credit balance...")``, or where
    #    a custom wrapper masks the SDK type.
    if any(
        tok in msg_lower
        for tok in ("credit balance", "credit_balance", "quota exceeded")
    ):
        return AI_QUOTA_EXHAUSTED
    if "rate limit" in msg_lower or "rate_limit" in msg_lower:
        return AI_RATE_LIMITED
    if "authentication" in msg_lower or "invalid api key" in msg_lower or "unauthorized" in msg_lower:
        return AI_API_KEY_INVALID
    if "timeout" in msg_lower or "connection" in msg_lower:
        return AI_NETWORK_ERROR

    return AI_UNKNOWN


def status_for_code(code: str) -> int:
    """Return the HTTP status code for a given AI error code."""
    return 503 if code in TRANSIENT_CODES else 500


def build_error_response(
    code: str,
    *,
    op: str = "",
    detail: Optional[str] = None,
) -> Tuple[dict, int, dict]:
    """Build the (body, status, headers) tuple for a classified AI failure.

    Body shape (frontend contract — see module docstring)::

        {
          "error":       "<user-facing string>",
          "error_kr":    "<KR>",
          "error_code":  "<AI_*>",
          "retry_after": <int seconds>,
          "fallback":    "<user-facing fallback>",
          "fallback_kr": "<KR>",
        }

    ``detail`` is **optional** and only included for true 500s
    (AI_UNKNOWN) so end-users never see SDK internals on the 503 path.
    Even for 500s, the caller is expected to pass the already-truncated
    string from ``AIService.last_error`` (≤200 chars), not a raw exception.
    """
    msg = USER_MESSAGES.get(code, USER_MESSAGES[AI_UNKNOWN])
    retry = RETRY_AFTER_SECONDS.get(code, 0)
    body = {
        "error": msg["error"],
        "error_kr": msg["error_kr"],
        "error_code": code,
        "retry_after": retry,
        "fallback": msg["fallback"],
        "fallback_kr": msg["fallback_kr"],
    }
    # AI_UNKNOWN is the only code where we surface a (truncated, safe)
    # detail to the operator via the JSON body — matches existing Bug #14
    # behaviour. Transient 503 codes never expose detail.
    if code == AI_UNKNOWN and detail:
        body["detail"] = detail

    headers: dict = {}
    status = status_for_code(code)
    if status == 503 and retry > 0:
        headers["Retry-After"] = str(retry)

    # Operator log — no PII, no SDK secrets. ``op`` lets the operator see
    # which generator failed.
    log_method = logger.warning if status == 503 else logger.error
    log_method("AI %s classified as %s (status=%d)", op or "call", code, status)

    # Sentry breadcrumb — non-fatal, informational. Sentry's auto-init in
    # app.py will capture the full exception elsewhere; this breadcrumb
    # adds the classification dimension so dashboards can group by code.
    try:  # pragma: no cover — Sentry is optional in test env
        import sentry_sdk

        sentry_sdk.add_breadcrumb(
            category="ai",
            level="warning" if status == 503 else "error",
            message=f"ai.{op or 'call'} -> {code}",
            data={"error_code": code, "status": status, "retry_after": retry},
        )
    except Exception:
        pass

    return body, status, headers
