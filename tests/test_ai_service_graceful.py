"""tests/test_ai_service_graceful.py — B-08 graceful 503 regression suite.

Pins the contract for the four classified Anthropic failure modes:

    AI_API_KEY_INVALID    → 503 + Retry-After 3600
    AI_RATE_LIMITED       → 503 + Retry-After 60
    AI_QUOTA_EXHAUSTED    → 503 + Retry-After 3600
    AI_NETWORK_ERROR      → 503 + Retry-After 30

True server bugs (AI_UNKNOWN) keep the legacy 500 + ``detail`` contract;
that is covered in ``tests/test_ai_smoke.py``.

Coverage
--------
1. ``classify_anthropic_error`` unit tests — direct mapping for each
   exception class + heuristic string sniffing for the BadRequestError
   "credit balance" path (Anthropic's actual quota-exhausted shape).
2. Route-level integration: every classified failure on the ``/api/ai/coaching``
   endpoint returns 503 with the structured ``error_code`` body and
   ``Retry-After`` header.
3. Cross-endpoint consistency: ``/api/ai/swot``, ``/api/ai/commentary``,
   and ``/api/ai/sector-trend`` all use the same shape (route helper
   factored into ``_ai_failure_response``).
4. Happy path still returns 200 — the new failure path doesn't regress
   successful generations.

External cost: zero. All Anthropic SDK calls are mocked; no real API hits.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ═════════════════════════════════════════════════════════════════════════════
# 1. Unit tests — classify_anthropic_error
# ═════════════════════════════════════════════════════════════════════════════

class TestClassifyAnthropicError:
    """Direct unit tests for the classifier — no Flask, no SDK calls."""

    def test_authentication_error_maps_to_api_key_invalid(self):
        import anthropic
        from services.ai.errors import classify_anthropic_error, AI_API_KEY_INVALID

        response = MagicMock(); response.status_code = 401
        exc = anthropic.AuthenticationError(message="invalid api key", response=response, body=None)
        assert classify_anthropic_error(exc) == AI_API_KEY_INVALID

    def test_permission_denied_maps_to_api_key_invalid(self):
        import anthropic
        from services.ai.errors import classify_anthropic_error, AI_API_KEY_INVALID

        response = MagicMock(); response.status_code = 403
        exc = anthropic.PermissionDeniedError(message="forbidden", response=response, body=None)
        assert classify_anthropic_error(exc) == AI_API_KEY_INVALID

    def test_rate_limit_error_maps_to_rate_limited(self):
        import anthropic
        from services.ai.errors import classify_anthropic_error, AI_RATE_LIMITED

        response = MagicMock(); response.status_code = 429
        exc = anthropic.RateLimitError(message="rate limited", response=response, body=None)
        assert classify_anthropic_error(exc) == AI_RATE_LIMITED

    def test_api_timeout_maps_to_network_error(self):
        import anthropic
        from services.ai.errors import classify_anthropic_error, AI_NETWORK_ERROR

        # APITimeoutError takes a positional `request` arg per SDK contract.
        exc = anthropic.APITimeoutError(MagicMock())
        assert classify_anthropic_error(exc) == AI_NETWORK_ERROR

    def test_api_connection_error_maps_to_network_error(self):
        import anthropic
        from services.ai.errors import classify_anthropic_error, AI_NETWORK_ERROR

        exc = anthropic.APIConnectionError(request=MagicMock())
        assert classify_anthropic_error(exc) == AI_NETWORK_ERROR

    def test_internal_server_error_maps_to_network_error(self):
        import anthropic
        from services.ai.errors import classify_anthropic_error, AI_NETWORK_ERROR

        response = MagicMock(); response.status_code = 500
        exc = anthropic.InternalServerError(message="upstream 500", response=response, body=None)
        assert classify_anthropic_error(exc) == AI_NETWORK_ERROR

    def test_credit_balance_bad_request_maps_to_quota_exhausted(self):
        """Anthropic returns BadRequestError(400) with body 'Your credit balance
        is too low ...' when credits are depleted — sniff the literal string."""
        import anthropic
        from services.ai.errors import classify_anthropic_error, AI_QUOTA_EXHAUSTED

        response = MagicMock(); response.status_code = 400
        exc = anthropic.BadRequestError(
            message="Your credit balance is too low to access the Anthropic API.",
            response=response, body=None,
        )
        assert classify_anthropic_error(exc) == AI_QUOTA_EXHAUSTED

    def test_billing_keyword_in_message_also_quota(self):
        import anthropic
        from services.ai.errors import classify_anthropic_error, AI_QUOTA_EXHAUSTED

        response = MagicMock(); response.status_code = 400
        exc = anthropic.BadRequestError(
            message="billing issue: please contact support", response=response, body=None,
        )
        assert classify_anthropic_error(exc) == AI_QUOTA_EXHAUSTED

    def test_api_status_error_429_falls_back_to_rate_limited(self):
        """SDK builds that bypass RateLimitError — defensive isinstance check
        on APIStatusError + status_code."""
        import anthropic
        from services.ai.errors import classify_anthropic_error, AI_RATE_LIMITED

        response = MagicMock(); response.status_code = 429
        exc = anthropic.APIStatusError(message="too many", response=response, body=None)
        assert classify_anthropic_error(exc) == AI_RATE_LIMITED

    def test_string_sniff_fallback_for_credit_balance(self):
        """If the SDK isn't installed (or a wrapper masks the type), fall
        back to literal string sniffing — covers ``Exception('credit balance...')``."""
        from services.ai.errors import classify_anthropic_error, AI_QUOTA_EXHAUSTED

        exc = RuntimeError("Your credit balance is too low.")
        assert classify_anthropic_error(exc) == AI_QUOTA_EXHAUSTED

    def test_unknown_exception_maps_to_unknown(self):
        from services.ai.errors import classify_anthropic_error, AI_UNKNOWN

        exc = ValueError("some bug in our code")
        assert classify_anthropic_error(exc) == AI_UNKNOWN

    def test_none_input_returns_unknown(self):
        from services.ai.errors import classify_anthropic_error, AI_UNKNOWN

        assert classify_anthropic_error(None) == AI_UNKNOWN


class TestStatusForCode:
    def test_transient_codes_are_503(self):
        from services.ai.errors import (
            status_for_code,
            AI_API_KEY_INVALID, AI_RATE_LIMITED,
            AI_QUOTA_EXHAUSTED, AI_NETWORK_ERROR,
        )
        for code in (AI_API_KEY_INVALID, AI_RATE_LIMITED,
                     AI_QUOTA_EXHAUSTED, AI_NETWORK_ERROR):
            assert status_for_code(code) == 503, code

    def test_unknown_is_500(self):
        from services.ai.errors import status_for_code, AI_UNKNOWN
        assert status_for_code(AI_UNKNOWN) == 500


class TestBuildErrorResponse:
    def test_quota_exhausted_response_shape(self):
        from services.ai.errors import build_error_response, AI_QUOTA_EXHAUSTED

        body, status, headers = build_error_response(AI_QUOTA_EXHAUSTED, op="coaching")
        assert status == 503
        assert body["error_code"] == "AI_QUOTA_EXHAUSTED"
        assert body["retry_after"] == 3600
        assert body["error"] == "AI service temporarily unavailable"
        assert "fallback" in body
        assert "fallback_kr" in body
        # 503 path NEVER includes detail (no SDK leakage).
        assert "detail" not in body
        # Retry-After header set for 503 with retry_after > 0.
        assert headers.get("Retry-After") == "3600"

    def test_rate_limited_short_retry(self):
        from services.ai.errors import build_error_response, AI_RATE_LIMITED

        body, status, headers = build_error_response(AI_RATE_LIMITED, op="swot")
        assert status == 503
        assert body["retry_after"] == 60
        assert headers.get("Retry-After") == "60"

    def test_unknown_includes_detail_when_provided(self):
        from services.ai.errors import build_error_response, AI_UNKNOWN

        body, status, headers = build_error_response(
            AI_UNKNOWN, op="swot", detail="swot: ValueError: bug",
        )
        assert status == 500
        assert body["detail"] == "swot: ValueError: bug"
        # No Retry-After for true server bugs.
        assert "Retry-After" not in headers


# ═════════════════════════════════════════════════════════════════════════════
# 2. Service-level — _record_error sets last_error_code
# ═════════════════════════════════════════════════════════════════════════════

class TestRecordErrorClassifies:
    """``AIService._record_error`` must persist the classified code so the
    route can read it via ``ai.last_error_code``."""

    def _svc(self):
        from services.ai.service import AIService
        svc = AIService.__new__(AIService)
        svc.client = MagicMock()
        svc.available = True
        svc.last_error = None
        svc.last_error_code = None
        return svc

    def test_record_error_quota(self):
        from services.ai.errors import AI_QUOTA_EXHAUSTED

        svc = self._svc()
        svc._record_error("coaching", RuntimeError("Your credit balance is too low."))
        assert svc.last_error_code == AI_QUOTA_EXHAUSTED
        assert svc.last_error.startswith("coaching: RuntimeError:")

    def test_record_error_rate_limit(self):
        import anthropic
        from services.ai.errors import AI_RATE_LIMITED

        svc = self._svc()
        response = MagicMock(); response.status_code = 429
        exc = anthropic.RateLimitError(message="rate limited", response=response, body=None)
        svc._record_error("swot", exc)
        assert svc.last_error_code == AI_RATE_LIMITED

    def test_record_error_unknown_for_value_error(self):
        from services.ai.errors import AI_UNKNOWN

        svc = self._svc()
        svc._record_error("swot", ValueError("our bug"))
        assert svc.last_error_code == AI_UNKNOWN


class TestGenerateCoachingClassifiesQuota:
    """End-to-end on the AIService method: a quota-exhausted exception raised
    from the mocked Anthropic client must (a) leave the public contract intact
    (returns ``None``) and (b) populate ``last_error_code = AI_QUOTA_EXHAUSTED``."""

    def test_coaching_quota_path(self):
        import anthropic
        from services.ai.service import AIService
        from services.ai.errors import AI_QUOTA_EXHAUSTED

        svc = AIService.__new__(AIService)
        svc.client = MagicMock()
        svc.available = True
        svc.last_error = None
        svc.last_error_code = None

        response = MagicMock(); response.status_code = 400
        exc = anthropic.BadRequestError(
            message="Your credit balance is too low to access the Anthropic API.",
            response=response, body=None,
        )
        svc.client.messages.create.side_effect = exc

        result = svc.generate_coaching("any context")
        assert result is None
        assert svc.last_error_code == AI_QUOTA_EXHAUSTED


# ═════════════════════════════════════════════════════════════════════════════
# 3. Route integration — /api/ai/coaching B-08 root path
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def pro_client(client, make_user, app, add_position):
    """Pro-tier user logged in with a position (coaching needs ≥1 position)."""
    u = make_user(email="b08-pro@test.com", tier="pro")
    add_position(u["id"], ticker="AAPL", shares=10, avg_cost=150.0)
    client.post("/api/auth/login",
                json={"email": u["email"], "password": u["password"]})
    return client


class TestCoachingGracefulDegradation:
    """B-08 root cause: Anthropic credit exhaustion on /api/ai/coaching."""

    def test_quota_exhausted_returns_503_with_error_code(self, pro_client):
        from services.ai.errors import AI_QUOTA_EXHAUSTED

        with patch("routes.ai.ai") as mock_ai:
            mock_ai.available = True
            mock_ai.generate_coaching.return_value = None
            mock_ai.last_error = "coaching: BadRequestError: credit balance..."
            mock_ai.last_error_code = AI_QUOTA_EXHAUSTED
            mock_ai.build_portfolio_context.return_value = "ctx"

            r = pro_client.post("/api/ai/coaching", json={})

        assert r.status_code == 503, r.get_json()
        body = r.get_json()
        assert body["error_code"] == "AI_QUOTA_EXHAUSTED"
        assert body["retry_after"] == 3600
        assert body["error"] == "AI service temporarily unavailable"
        assert "fallback" in body
        # 503 path must NOT leak operator detail to end-users.
        assert "detail" not in body
        # HTTP-spec Retry-After header for compliant clients.
        assert r.headers.get("Retry-After") == "3600"

    def test_rate_limited_returns_503_with_short_retry(self, pro_client):
        from services.ai.errors import AI_RATE_LIMITED

        with patch("routes.ai.ai") as mock_ai:
            mock_ai.available = True
            mock_ai.generate_coaching.return_value = None
            mock_ai.last_error = "coaching: RateLimitError: 429"
            mock_ai.last_error_code = AI_RATE_LIMITED
            mock_ai.build_portfolio_context.return_value = "ctx"

            r = pro_client.post("/api/ai/coaching", json={})

        assert r.status_code == 503
        body = r.get_json()
        assert body["error_code"] == "AI_RATE_LIMITED"
        assert body["retry_after"] == 60
        assert r.headers.get("Retry-After") == "60"

    def test_api_key_invalid_returns_503(self, pro_client):
        from services.ai.errors import AI_API_KEY_INVALID

        with patch("routes.ai.ai") as mock_ai:
            mock_ai.available = True
            mock_ai.generate_coaching.return_value = None
            mock_ai.last_error = "coaching: AuthenticationError: invalid"
            mock_ai.last_error_code = AI_API_KEY_INVALID
            mock_ai.build_portfolio_context.return_value = "ctx"

            r = pro_client.post("/api/ai/coaching", json={})

        assert r.status_code == 503
        assert r.get_json()["error_code"] == "AI_API_KEY_INVALID"

    def test_network_error_returns_503(self, pro_client):
        from services.ai.errors import AI_NETWORK_ERROR

        with patch("routes.ai.ai") as mock_ai:
            mock_ai.available = True
            mock_ai.generate_coaching.return_value = None
            mock_ai.last_error = "coaching: APITimeoutError: 20s timeout"
            mock_ai.last_error_code = AI_NETWORK_ERROR
            mock_ai.build_portfolio_context.return_value = "ctx"

            r = pro_client.post("/api/ai/coaching", json={})

        assert r.status_code == 503
        body = r.get_json()
        assert body["error_code"] == "AI_NETWORK_ERROR"
        assert body["retry_after"] == 30
        assert r.headers.get("Retry-After") == "30"

    def test_unknown_keeps_legacy_500_with_detail(self, pro_client):
        """True server bugs (AI_UNKNOWN) preserve the Bug #14 500+detail contract."""
        from services.ai.errors import AI_UNKNOWN

        with patch("routes.ai.ai") as mock_ai:
            mock_ai.available = True
            mock_ai.generate_coaching.return_value = None
            mock_ai.last_error = "coaching: ValueError: bad prompt build"
            mock_ai.last_error_code = AI_UNKNOWN
            mock_ai.build_portfolio_context.return_value = "ctx"

            r = pro_client.post("/api/ai/coaching", json={})

        assert r.status_code == 500
        body = r.get_json()
        assert body["error"] == "Failed to generate coaching"
        assert body["detail"] == "coaching: ValueError: bad prompt build"
        # No Retry-After on a 500 (caller cannot meaningfully retry a bug).
        assert "Retry-After" not in r.headers

    def test_success_still_returns_200(self, pro_client):
        """The graceful-degradation path must not regress the happy path."""
        with patch("routes.ai.ai") as mock_ai:
            mock_ai.available = True
            mock_ai.generate_coaching.return_value = {
                "insight": "Diversification observed.",
                "insight_kr": "분산 투자가 관찰됩니다.",
            }
            mock_ai.build_portfolio_context.return_value = "ctx"

            r = pro_client.post("/api/ai/coaching", json={})

        assert r.status_code == 200
        body = r.get_json()
        assert "insight" in body


# ═════════════════════════════════════════════════════════════════════════════
# 4. Cross-endpoint consistency — same shape on swot / commentary / sector-trend
# ═════════════════════════════════════════════════════════════════════════════

class TestCrossEndpointConsistency:
    """Same classification and 503 contract on every AI generator endpoint.

    Coaching is covered by ``TestCoachingGracefulDegradation``. This class
    verifies the helper (``_ai_failure_response``) is wired uniformly so a
    quota-exhausted SWOT call doesn't accidentally still return 500.
    """

    def _setup_pro_with_aapl(self, client, make_user, app, add_position):
        u = make_user(email="b08-cross@test.com", tier="pro")
        add_position(u["id"], ticker="AAPL", shares=5, avg_cost=180.0)
        # SWOT also requires the ticker to be in the user's allow-list.
        from models import Watchlist
        from extensions import db
        with app.app_context():
            db.session.add(Watchlist(user_id=u["id"], ticker="AAPL"))
            db.session.commit()
        client.post("/api/auth/login",
                    json={"email": u["email"], "password": u["password"]})

    def test_swot_quota_exhausted_returns_503(self, client, make_user, app, add_position):
        from services.ai.errors import AI_QUOTA_EXHAUSTED

        self._setup_pro_with_aapl(client, make_user, app, add_position)

        with patch("routes.ai.ai") as mock_ai:
            mock_ai.available = True
            mock_ai.generate_swot.return_value = None
            mock_ai.last_error = "swot: BadRequestError: credit balance..."
            mock_ai.last_error_code = AI_QUOTA_EXHAUSTED

            r = client.post("/api/ai/swot", json={"ticker": "AAPL"})

        assert r.status_code == 503
        body = r.get_json()
        assert body["error_code"] == "AI_QUOTA_EXHAUSTED"

    def test_commentary_rate_limited_returns_503(self, client, make_user, app, add_position):
        from services.ai.errors import AI_RATE_LIMITED

        self._setup_pro_with_aapl(client, make_user, app, add_position)

        with patch("routes.ai.ai") as mock_ai:
            mock_ai.available = True
            mock_ai.generate_commentary.return_value = None
            mock_ai.last_error = "commentary: RateLimitError"
            mock_ai.last_error_code = AI_RATE_LIMITED

            r = client.post("/api/ai/commentary", json={"ticker": "AAPL"})

        assert r.status_code == 503
        assert r.get_json()["error_code"] == "AI_RATE_LIMITED"

    def test_sector_trend_network_error_returns_503(self, client, make_user, add_position):
        from services.ai.errors import AI_NETWORK_ERROR

        u = make_user(email="b08-st@test.com", tier="pro")
        add_position(u["id"], ticker="MSFT", shares=1, avg_cost=300.0)
        client.post("/api/auth/login",
                    json={"email": u["email"], "password": u["password"]})

        with patch("routes.ai.ai") as mock_ai:
            mock_ai.available = True
            mock_ai.generate_sector_trend.return_value = None
            mock_ai.last_error = "sector_trend: APITimeoutError"
            mock_ai.last_error_code = AI_NETWORK_ERROR

            # No ticker — sector-only call permitted, exercises the same helper.
            r = client.post("/api/ai/sector-trend", json={"sector": "Technology"})

        assert r.status_code == 503
        assert r.get_json()["error_code"] == "AI_NETWORK_ERROR"


# ═════════════════════════════════════════════════════════════════════════════
# 5. No-leak guarantees
# ═════════════════════════════════════════════════════════════════════════════

class TestNoSDKLeakOn503:
    """503 responses must NEVER echo SDK internals — no credit balance,
    no request_id, no exception chain."""

    def test_503_body_does_not_contain_credit_balance_phrase(self, client, make_user, add_position):
        from services.ai.errors import AI_QUOTA_EXHAUSTED

        u = make_user(email="b08-noleak@test.com", tier="pro")
        add_position(u["id"], ticker="AAPL", shares=10, avg_cost=150.0)
        client.post("/api/auth/login",
                    json={"email": u["email"], "password": u["password"]})

        with patch("routes.ai.ai") as mock_ai:
            mock_ai.available = True
            mock_ai.generate_coaching.return_value = None
            # Simulate the actual Anthropic message — must NOT bleed through.
            mock_ai.last_error = (
                "coaching: BadRequestError: Your credit balance is too low "
                "(account=acct_abc123, request_id=req_xyz789)"
            )
            mock_ai.last_error_code = AI_QUOTA_EXHAUSTED
            mock_ai.build_portfolio_context.return_value = "ctx"

            r = pro_client_post(client)

        assert r.status_code == 503
        body_str = r.get_data(as_text=True)
        assert "credit balance" not in body_str.lower()
        assert "acct_" not in body_str
        assert "req_" not in body_str


def pro_client_post(client):
    """Helper for the no-leak test — coaching needs an authenticated POST."""
    return client.post("/api/ai/coaching", json={})
