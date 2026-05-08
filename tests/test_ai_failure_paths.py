"""tests/test_ai_failure_paths.py — Wave 10 P2 supplementary coverage.

Existing ``test_ai_smoke.py`` covers the happy / unauthenticated /
unavailable paths. This file pins the **failure-mode contracts** of
``services/ai/service.py`` — the public guarantee that a transient
Anthropic SDK error never surfaces a 500, never leaks the SDK error
message to end-users, and degrades gracefully to ``None``.

Covers:
  - APITimeoutError → ``generate_commentary`` returns None.
  - InternalServerError (5xx) → ``generate_morning_summary`` returns None.
  - RateLimitError-equivalent → ``generate_swot`` returns None.
  - Generator path: a streaming exception yields a Korean fallback line
    rather than raising up to the route handler.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch


def _build_service_with_mock_client():
    """Build an AIService whose ``self.client`` is a MagicMock and whose
    ``self.available`` is True so the early ``if not self.available``
    guard does not short-circuit the failure path under test.
    """
    from services.ai.service import AIService

    svc = AIService.__new__(AIService)
    svc.client = MagicMock()
    svc.available = True
    # Bug #14: routes/ai.py reads ``ai.last_error`` to surface a non-opaque
    # 500. AIService.__init__ sets it to None; mirror that here so tests
    # that bypass __init__ don't AttributeError on the attribute access.
    svc.last_error = None
    return svc


def test_generate_commentary_returns_none_on_timeout():
    """``APITimeoutError`` from messages.create → graceful None return."""
    import anthropic

    svc = _build_service_with_mock_client()
    # APITimeoutError requires a positional `request` argument in the SDK.
    # Construct a minimal httpx.Request stand-in via MagicMock — the SDK
    # only stores it for str/repr.
    err = anthropic.APITimeoutError(MagicMock())
    svc.client.messages.create.side_effect = err

    result = svc.generate_commentary({
        "name": "Apple", "ticker": "AAPL", "score": 70,
        "signal": "POSITIVE", "tech_score": 60, "fund_score": 70,
        "news_score": 50, "signals": [], "reason": "n/a",
    })
    assert result is None


def test_generate_morning_summary_returns_none_on_5xx():
    """``InternalServerError`` from the SDK → graceful None return."""
    import anthropic

    svc = _build_service_with_mock_client()

    # InternalServerError is an APIStatusError subclass; instantiate
    # via the public class with a MagicMock'd response object.
    response = MagicMock()
    response.status_code = 500
    err = anthropic.InternalServerError(
        message="upstream 500", response=response, body=None,
    )
    svc.client.messages.create.side_effect = err

    result = svc.generate_morning_summary({
        "stories": [{"title": "x", "sentiment": "neutral"}],
        "market_mood": "Mixed",
        "gs_view": {"bias": "Neutral", "risk_level": "Moderate"},
    })
    assert result is None


def test_generate_swot_returns_none_on_rate_limit():
    """A simulated rate-limit-style ``APIStatusError`` → None.

    We construct a generic ``APIStatusError`` rather than the
    rate-limit subclass to keep the test resilient across SDK version
    bumps that may rename the rate-limit error.
    """
    import anthropic

    svc = _build_service_with_mock_client()
    response = MagicMock()
    response.status_code = 429
    err = anthropic.APIStatusError(
        message="rate limited", response=response, body=None,
    )
    svc.client.messages.create.side_effect = err

    result = svc.generate_swot({
        "name": "Apple", "ticker": "AAPL", "score": 70,
        "signal": "POSITIVE", "tech_score": 60, "fund_score": 70,
        "news_score": 50, "signals": [], "reason": "n/a",
    })
    assert result is None


def test_generate_swot_records_last_error_for_route_diagnostics():
    """Bug #14: when ``generate_swot`` returns None due to a transient SDK
    error, ``self.last_error`` is set to a short ``op: ExceptionType: msg``
    string. ``routes/ai.py`` reads this to surface a non-opaque 500.
    """
    import anthropic

    svc = _build_service_with_mock_client()
    # ``__new__`` skips ``__init__``, so initialise the field the same way
    # AIService.__init__ would (the field defaults to None when ``ai_service``
    # is built normally; routes/ai.py reads it via ``getattr(..., None)``).
    svc.last_error = None
    response = MagicMock()
    response.status_code = 429
    err = anthropic.APIStatusError(
        message="rate limited", response=response, body=None,
    )
    svc.client.messages.create.side_effect = err

    assert svc.last_error is None
    result = svc.generate_swot({
        "name": "Apple", "ticker": "AAPL", "score": 70,
        "signal": "POSITIVE", "tech_score": 60, "fund_score": 70,
        "news_score": 50, "signals": [], "reason": "n/a",
    })
    assert result is None
    assert svc.last_error is not None
    assert svc.last_error.startswith("swot: APIStatusError: ")
    # Length-bounded so we never leak large stack traces / SDK secrets.
    assert len(svc.last_error) <= 256


def test_record_error_truncates_long_messages():
    """`_record_error` must clip very long exception messages to 160 chars
    to avoid leaking large SDK payloads / stack-trace fragments to the
    end-user via the route's `detail` field."""
    from services.ai.service import AIService

    svc = AIService.__new__(AIService)
    svc.last_error = None
    svc._record_error("op", RuntimeError("x" * 500))
    assert svc.last_error.startswith("op: RuntimeError: ")
    # 160 chars + ellipsis, so total tail is ≤ ~200 chars.
    assert "..." in svc.last_error
    assert len(svc.last_error) <= 200


def test_chat_stream_exception_yields_fallback_message():
    """If the streaming context raises, ``chat_stream`` must still produce
    output for the SSE consumer — it must not raise, and it must not
    leak the raw SDK error text."""
    svc = _build_service_with_mock_client()

    # Make `messages.stream(...)` raise on enter so the body never starts.
    cm = MagicMock()
    cm.__enter__ = MagicMock(
        side_effect=RuntimeError("internal sdk failure with credit balance leaked")
    )
    cm.__exit__ = MagicMock(return_value=False)
    svc.client.messages.stream.return_value = cm

    chunks = list(svc.chat_stream("hi", history=[], context="ctx"))
    full = "".join(chunks)

    # Must produce SOMETHING (the SSE consumer requires a final chunk).
    assert chunks, "chat_stream must yield at least one chunk on error"
    # Must NOT leak the SDK error text into the user-facing chunk.
    assert "credit balance" not in full
    assert "RuntimeError" not in full
    # Must yield a Korean-ish friendly fallback.
    assert "AI" in full or "다시" in full
