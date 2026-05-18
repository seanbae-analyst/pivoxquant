"""
tests/test_billing_gate.py — Business registration payment gate
================================================================
P0 fix: 사업자등록 + 통신판매업 신고 전 Stripe 결제 차단 가드.

법적 근거:
  - 전자상거래법 §40 (1,000만원 이하 과태료 — 신원정보 미표시)
  - 통신판매법 §43 (3,000만원 이하 과태료 — 무신고 영업)

검증:
  - BUSINESS_REGISTRATION_NUMBER 또는 TELESELLER_REGISTRATION_NUMBER
    env 미설정 시 결제 endpoint들이 503 + BUSINESS_REGISTRATION_PENDING 반환
  - 둘 다 설정된 경우에만 정상 진행
  - /api/billing/availability 가 상태를 정확히 반영
"""
from unittest.mock import patch, MagicMock

import pytest


# conftest.py가 STRIPE_* env를 unset 처리하지만 BUSINESS_REGISTRATION_NUMBER /
# TELESELLER_REGISTRATION_NUMBER 는 명시적으로 보장하지 않을 수 있다.
# 가드 테스트는 두 값을 명시적으로 컨트롤한다.


@pytest.fixture
def gate_open(monkeypatch):
    """등록 완료 상태."""
    monkeypatch.setenv("BUSINESS_REGISTRATION_NUMBER", "123-45-67890")
    monkeypatch.setenv("TELESELLER_REGISTRATION_NUMBER", "2026-Seoul-1234")


@pytest.fixture
def gate_closed(monkeypatch):
    """등록 미완료 상태 (default in CI)."""
    monkeypatch.delenv("BUSINESS_REGISTRATION_NUMBER", raising=False)
    monkeypatch.delenv("TELESELLER_REGISTRATION_NUMBER", raising=False)


@pytest.fixture
def gate_partial(monkeypatch):
    """사업자등록만 완료, 통신판매업 신고 안 됨."""
    monkeypatch.setenv("BUSINESS_REGISTRATION_NUMBER", "123-45-67890")
    monkeypatch.delenv("TELESELLER_REGISTRATION_NUMBER", raising=False)


class TestCreateCheckoutGate:
    def test_gate_closed_returns_503(self, client, auth_user, gate_closed):
        r = client.post("/api/billing/create-checkout", json={"plan": "pro"})
        assert r.status_code == 503
        body = r.get_json()
        assert body["code"] == "BUSINESS_REGISTRATION_PENDING"
        assert "사업자등록" in body["error_ko"]

    def test_gate_partial_returns_503(self, client, auth_user, gate_partial):
        """사업자등록만 있고 통신판매업 신고 없으면 여전히 차단."""
        r = client.post("/api/billing/create-checkout", json={"plan": "pro"})
        assert r.status_code == 503
        assert r.get_json()["code"] == "BUSINESS_REGISTRATION_PENDING"

    def test_gate_open_allows_checkout(self, client, auth_user, gate_open):
        """등록 완료 + Stripe mock + consent → 정상 200."""
        with patch("routes.billing.PLAN_PRICES", {"pro": "price_123"}), \
             patch("routes.billing.stripe") as mock_stripe:
            mock_customer = MagicMock(id="cus_abc123")
            mock_stripe.Customer.create.return_value = mock_customer
            mock_session = MagicMock(url="https://checkout.stripe.com/pay/test")
            mock_stripe.checkout.Session.create.return_value = mock_session
            mock_stripe.StripeError = Exception
            # Wave G-1: consent block 이 routes/billing.py 에서 필수가 됐다.
            r = client.post(
                "/api/billing/create-checkout",
                json={
                    "plan": "pro",
                    "consent": {
                        "key_info": True,
                        "recurring": True,
                        "stripe_overseas": True,
                    },
                },
            )
        assert r.status_code == 200
        assert r.get_json()["url"].startswith("https://checkout.stripe.com/")


class TestPortalGate:
    def test_portal_gate_closed_returns_503(self, client, auth_user, gate_closed):
        r = client.post("/api/billing/portal")
        assert r.status_code == 503
        assert r.get_json()["code"] == "BUSINESS_REGISTRATION_PENDING"


class TestAvailabilityEndpoint:
    def test_availability_when_closed(self, client, gate_closed):
        r = client.get("/api/billing/availability")
        assert r.status_code == 200
        body = r.get_json()
        assert body["available"] is False
        assert body["code"] == "BUSINESS_REGISTRATION_PENDING"

    def test_availability_when_open(self, client, gate_open):
        r = client.get("/api/billing/availability")
        assert r.status_code == 200
        body = r.get_json()
        assert body["available"] is True
        assert body["code"] is None

    def test_availability_no_auth_required(self, raw_client, gate_closed):
        """공개 endpoint — 비로그인 상태에서도 200."""
        r = raw_client.get("/api/billing/availability")
        assert r.status_code == 200


class TestGateDoesNotBlockReadOnly:
    def test_subscription_read_not_blocked(self, client, auth_user, gate_closed):
        """GET /subscription 은 결제 시작이 아니라 상태 조회 — 차단하지 않음."""
        r = client.get("/api/billing/subscription")
        # 인증된 사용자면 200, 아니면 401 — 503은 절대 아님.
        assert r.status_code != 503
