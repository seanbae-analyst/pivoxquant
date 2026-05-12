"""Claude API wrapper — single invoke_agent() entry point for all agents."""
from __future__ import annotations

import logging
import re

from anthropic import Anthropic, APIError

from agent_worker.config import ANTHROPIC_API_KEY, CLAUDE_MODEL

log = logging.getLogger(__name__)

_CONFIDENCE_PATTERN = re.compile(r"\[CONFIDENCE:\s*(\d{1,3})\s*\]", re.IGNORECASE)
_DEFAULT_CONFIDENCE = 80

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        _client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _extract_confidence(text: str) -> tuple[int, bool]:
    """Returns (confidence, parse_error). Defaults to 80 if pattern missing."""
    match = _CONFIDENCE_PATTERN.search(text or "")
    if not match:
        return _DEFAULT_CONFIDENCE, True
    try:
        value = int(match.group(1))
    except ValueError:
        return _DEFAULT_CONFIDENCE, True
    return max(0, min(100, value)), False


def invoke_agent(
    system_prompt: str,
    user_message: str,
    model: str | None = None,
    max_tokens: int = 2048,
) -> dict:
    """
    Invoke Claude with a system prompt + user message.

    Returns:
        {
            "text": str,
            "input_tokens": int,
            "output_tokens": int,
            "confidence": int (0-100),
            "parse_error": bool,
        }
    """
    client = _get_client()
    resolved_model = model or CLAUDE_MODEL

    try:
        response = client.messages.create(
            model=resolved_model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
    except APIError as exc:
        log.exception("Claude API error: %s", exc)
        return {
            "text": "",
            "input_tokens": 0,
            "output_tokens": 0,
            "confidence": 0,
            "parse_error": True,
        }

    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    confidence, parse_error = _extract_confidence(text)

    return {
        "text": text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "confidence": confidence,
        "parse_error": parse_error,
    }
