"""
tests/test_wave_d_sub3_ops.py — Wave D Sub-wave 3 Operations 4건 단위 테스트
============================================================================

O-F: ticker_name_audit.py
O-G: email_compliance_check.py
O-H: section101_compliance_check.py
O-I: build_brief_kpi.py Stripe 매출 강화

각 스크립트의 핵심 로직을 import해 단위 검증한다.
외부 API(Stripe, Slack, Sentry, DB) 는 전부 mock — 0원 / 0 네트워크 호출.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"

# ── import helpers ────────────────────────────────────────────────────────────

def _import_module(rel_path: str, module_name: str):
    """Import a script as a module without executing __main__."""
    spec = importlib.util.spec_from_file_location(
        module_name, _REPO / rel_path
    )
    assert spec and spec.loader, f"Cannot load {rel_path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ─────────────────────────────────────────────────────────────────────────────
# O-F: ticker_name_audit
# ─────────────────────────────────────────────────────────────────────────────

class TestTickerNameAudit:
    """O-F: 종목명 매핑 누락 감지 로직 검증."""

    @pytest.fixture(scope="class")
    def mod(self):
        return _import_module(
            "scripts/nightly/ticker_name_audit.py",
            "ticker_name_audit",
        )

    def test_naked_ticker_null_name(self, mod):
        """name 이 None 이면 naked_ticker 판정."""
        assert mod._naked_ticker(None, "005930.KS") is True

    def test_naked_ticker_empty_string(self, mod):
        """name 이 빈 문자열이면 naked_ticker 판정."""
        assert mod._naked_ticker("", "005930.KS") is True
        assert mod._naked_ticker("   ", "005930.KS") is True

    def test_naked_ticker_same_as_ticker(self, mod):
        """name 이 ticker 자체이면 naked_ticker 판정."""
        assert mod._naked_ticker("005930.KS", "005930.KS") is True

    def test_naked_ticker_raw_pattern(self, mod):
        """숫자.KS 패턴 name 은 naked_ticker 판정."""
        assert mod._naked_ticker("123456.KS", "123456.KS") is True
        assert mod._naked_ticker("999999.KQ", "999999.KQ") is True

    def test_not_naked_ticker_valid_name(self, mod):
        """정상 회사명 → naked_ticker 아님."""
        assert mod._naked_ticker("삼성전자", "005930.KS") is False
        assert mod._naked_ticker("Apple Inc.", "AAPL") is False

    def test_main_no_db_returns_zero(self, mod):
        """DATABASE_URL 미설정 시 main() 은 0 반환 (graceful skip)."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DATABASE_URL", None)
            result = mod.main()
        assert result == 0

    def test_main_pass_when_no_missing(self, mod):
        """fetch_missing_names() 가 빈 리스트 반환 시 main() 은 0 반환."""
        with patch.object(mod, "fetch_missing_names", return_value=[]):
            result = mod.main()
        assert result == 0

    def test_main_fail_when_missing_exists(self, mod):
        """누락 종목이 있으면 main() 은 1 반환 + Slack/Sentry 호출."""
        fake_missing = [
            {"ticker": "005930.KS", "name": None, "source": "signal_cache"},
            {"ticker": "000660.KS", "name": "", "source": "signal_cache"},
        ]
        with (
            patch.object(mod, "fetch_missing_names", return_value=fake_missing),
            patch.object(mod, "_post_slack") as mock_slack,
            patch.object(mod, "_capture_sentry") as mock_sentry,
        ):
            result = mod.main()
        assert result == 1
        mock_slack.assert_called_once()
        mock_sentry.assert_called_once()
        # Slack 메시지에 ticker 포함
        slack_text = mock_slack.call_args[0][0]
        assert "005930.KS" in slack_text


# ─────────────────────────────────────────────────────────────────────────────
# O-G: email_compliance_check
# ─────────────────────────────────────────────────────────────────────────────

class TestEmailComplianceCheck:
    """O-G: §50 List-Unsubscribe 검증 로직 검증."""

    @pytest.fixture(scope="class")
    def mod(self):
        return _import_module(
            "scripts/nightly/email_compliance_check.py",
            "email_compliance_check",
        )

    def test_skip_flag(self, mod):
        """PIVOX_EMAIL_COMPLIANCE_SKIP=1 이면 main() 은 0 반환."""
        with patch.dict(os.environ, {"PIVOX_EMAIL_COMPLIANCE_SKIP": "1"}):
            result = mod.main()
        assert result == 0

    def test_no_api_key_skip(self, mod):
        """SENDGRID_API_KEY 미설정 시 main() 은 0 반환 (graceful skip)."""
        env = {k: v for k, v in os.environ.items() if k != "SENDGRID_API_KEY"}
        env.pop("PIVOX_EMAIL_COMPLIANCE_SKIP", None)
        with patch.dict(os.environ, env, clear=True):
            result = mod.main()
        assert result == 0

    def test_pass_when_all_ok(self, mod):
        """발송 성공 + 헤더 OK + opt-out URL 200 → main() 0 반환."""
        with (
            patch.dict(os.environ, {"SENDGRID_API_KEY": "SG.test"}, clear=False),
            patch.dict(os.environ, {"PIVOX_EMAIL_COMPLIANCE_SKIP": ""}, clear=False),
            patch.object(
                mod,
                "_send_via_sendgrid",
                return_value=(
                    True,
                    "msg-id-123",
                    {"List-Unsubscribe": True, "List-Unsubscribe-Post": True},
                ),
            ),
            patch.object(mod, "_check_optout_url", return_value=(True, 200)),
        ):
            result = mod.main()
        assert result == 0

    def test_fail_when_header_missing(self, mod):
        """List-Unsubscribe 헤더 누락 시 main() 1 반환 + Slack 호출."""
        with (
            patch.dict(os.environ, {"SENDGRID_API_KEY": "SG.test"}, clear=False),
            patch.dict(os.environ, {"PIVOX_EMAIL_COMPLIANCE_SKIP": ""}, clear=False),
            patch.object(
                mod,
                "_send_via_sendgrid",
                return_value=(
                    True,
                    "msg-id-456",
                    {"List-Unsubscribe": False, "List-Unsubscribe-Post": True},
                ),
            ),
            patch.object(mod, "_check_optout_url", return_value=(True, 200)),
            patch.object(mod, "_post_slack") as mock_slack,
            patch.object(mod, "_capture_sentry"),
        ):
            result = mod.main()
        assert result == 1
        mock_slack.assert_called_once()

    def test_fail_when_optout_url_down(self, mod):
        """opt-out URL 비정상 시 main() 1 반환."""
        with (
            patch.dict(os.environ, {"SENDGRID_API_KEY": "SG.test"}, clear=False),
            patch.dict(os.environ, {"PIVOX_EMAIL_COMPLIANCE_SKIP": ""}, clear=False),
            patch.object(
                mod,
                "_send_via_sendgrid",
                return_value=(
                    True,
                    "msg-id-789",
                    {"List-Unsubscribe": True, "List-Unsubscribe-Post": True},
                ),
            ),
            patch.object(mod, "_check_optout_url", return_value=(False, 503)),
            patch.object(mod, "_post_slack"),
            patch.object(mod, "_capture_sentry"),
        ):
            result = mod.main()
        assert result == 1


# ─────────────────────────────────────────────────────────────────────────────
# O-H: section101_compliance_check
# ─────────────────────────────────────────────────────────────────────────────

class TestSection101ComplianceCheck:
    """O-H: §101 4요건 self-check 로직 검증."""

    @pytest.fixture(scope="class")
    def mod(self):
        return _import_module(
            "scripts/nightly/section101_compliance_check.py",
            "section101_compliance_check",
        )

    def test_pass_when_no_violations(self, mod):
        """4요건 모두 이상 없으면 main() 0 반환."""
        with (
            patch.object(mod, "_check_ad_keywords", return_value=[]),
            patch.object(mod, "_check_stripe_monthly", return_value=[]),
            patch.object(mod, "_check_artifact_solicitation", return_value=[]),
            patch.object(mod, "_check_generalization", return_value=[]),
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}, clear=False),
        ):
            result = mod.main()
        assert result == 0

    def test_fail_when_stripe_monthly_exists(self, mod):
        """Stripe 월 구독 plan 발견 시 main() 1 반환 + violations.log + Slack."""
        with (
            patch.object(mod, "_check_ad_keywords", return_value=[]),
            patch.object(
                mod,
                "_check_stripe_monthly",
                return_value=["price_id=price_xxx amount=9900 KRW"],
            ),
            patch.object(mod, "_check_artifact_solicitation", return_value=[]),
            patch.object(mod, "_check_generalization", return_value=[]),
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://fake"}, clear=False),
            patch.object(mod, "_post_slack") as mock_slack,
            patch.object(mod, "_capture_sentry") as mock_sentry,
            patch.object(mod, "_log_violation") as mock_log,
        ):
            result = mod.main()
        assert result == 1
        mock_slack.assert_called_once()
        mock_sentry.assert_called_once()
        mock_log.assert_called()

    def test_solicitation_pattern_regex(self, mod):
        """매수 권유 패턴 정규식 동작 확인."""
        pattern = mod._SOLICITATION_PATTERNS
        assert pattern.search("이 종목 매수 권유합니다")
        assert pattern.search("BUY NOW — immediate action")
        # false positive 예시 — 매수세 (거래량 분석) 는 패턴 불일치
        assert not pattern.search("매수세 강화되며 거래량 증가")

    def test_ad_keyword_pattern_regex(self, mod):
        """광고성 키워드 정규식 동작 확인."""
        pattern = mod._AD_PATTERNS
        assert pattern.search("이 서비스는 sponsored 콘텐츠입니다")
        assert pattern.search("할인 쿠폰을 받아보세요")
        # 일반 문구 — 불일치
        assert not pattern.search("PivoxQuant 데이터 분석 서비스")

    def test_no_db_skips_artifact_check(self, mod):
        """DATABASE_URL 미설정 시 (3) artifact check skip — main() 정상 종료."""
        env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(mod, "_check_ad_keywords", return_value=[]),
            patch.object(mod, "_check_stripe_monthly", return_value=[]),
            patch.object(mod, "_check_generalization", return_value=[]),
        ):
            result = mod.main()
        assert result == 0


# ─────────────────────────────────────────────────────────────────────────────
# O-I: build_brief_kpi — Stripe 매출 강화
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildBriefKpiStripeRevenue:
    """O-I: Stripe 매출 강화 섹션 검증."""

    @pytest.fixture(scope="class")
    def mod(self):
        return _import_module(
            "scripts/morning_brief/build_brief_kpi.py",
            "build_brief_kpi",
        )

    def test_stripe_kpi_no_api_key(self, mod):
        """STRIPE_SECRET_KEY 미설정 시 N/A 반환 (graceful skip)."""
        env = {k: v for k, v in os.environ.items() if k != "STRIPE_SECRET_KEY"}
        with patch.dict(os.environ, env, clear=True):
            result = mod.fetch_stripe_kpi()
        assert result["charges_success"] == "N/A"
        assert result.get("caveat") == "STRIPE_SECRET_KEY 미설정"

    def test_stripe_kpi_new_fields_present(self, mod):
        """O-I 신규 필드 6개가 결과에 존재하는지 확인."""
        fake_pi = [
            {"status": "succeeded", "amount_received": 9900, "currency": "usd", "customer": "cus_A"},
        ]
        fake_bt = [{"net": 9900}]
        fake_refunds: list = []
        fake_subs: list = []

        with (
            patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_fake"}, clear=False),
            patch.object(mod, "_stripe_get", side_effect=lambda key, path: {
                "data": fake_pi
            } if "payment_intents" in path else {"data": []}),
            patch.object(mod, "_stripe_balance_transactions", return_value=fake_bt),
            patch.object(mod, "_stripe_refunds", return_value=fake_refunds),
            patch.object(mod, "_stripe_subscriptions", return_value=fake_subs),
            patch.object(mod, "_stripe_top_customers", return_value=[
                {"customer": "cus_A", "revenue_usd": "$99.00"}
            ]),
        ):
            result = mod.fetch_stripe_kpi()

        required_fields = [
            "revenue_yesterday_usd",
            "revenue_this_month_usd",
            "revenue_prev_month_usd",
            "mom_change_pct",
            "refund_count",
            "refund_amount_usd",
            "mrr_estimate_usd",
            "top_customers",
        ]
        for field in required_fields:
            assert field in result, f"신규 필드 누락: {field}"

    def test_mom_calculation_positive(self, mod):
        """전월 대비 이번달 매출 증가 시 MoM + 표기 확인."""
        with (
            patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_fake"}, clear=False),
            patch.object(mod, "_stripe_get", return_value={"data": []}),
            patch.object(mod, "_stripe_balance_transactions", side_effect=[
                # today
                [{"net": 5000}],
                # this_month
                [{"net": 12000}],
                # prev_month
                [{"net": 10000}],
            ]),
            patch.object(mod, "_stripe_refunds", return_value=[]),
            patch.object(mod, "_stripe_subscriptions", return_value=[]),
            patch.object(mod, "_stripe_top_customers", return_value=[]),
        ):
            result = mod.fetch_stripe_kpi()
        # MoM = (12000 - 10000) / 10000 * 100 = +20.0%
        assert result["mom_change_pct"] == "+20.0%"

    def test_render_includes_new_fields(self, mod):
        """render_kpi_brief 출력에 O-I 신규 필드 포함 확인."""
        stripe = {
            "charges_success": 3,
            "charges_fail": 0,
            "revenue_today_usd": "$9.90",
            "revenue_yesterday_usd": "$19.80",
            "revenue_this_month_usd": "$59.40",
            "revenue_prev_month_usd": "$39.60",
            "mom_change_pct": "+50.0%",
            "refund_count": 0,
            "refund_amount_usd": "$0.00",
            "mrr_estimate_usd": "$99.00",
            "top_customers": [{"customer": "cus_A", "revenue_usd": "$59.40"}],
        }
        db = {"dau": 5, "wau": 20, "new_users_24h": 2, "total_users": 50}
        sentry = {"total_issues_24h": 0, "unresolved_critical": 0}

        rendered = mod.render_kpi_brief(db, stripe, sentry)

        assert "MRR 추정 USD" in rendered
        assert "$99.00" in rendered
        assert "MoM 변화율" in rendered
        assert "+50.0%" in rendered
        assert "전일 매출 USD" in rendered
        assert "Top 5 Customer" in rendered
        assert "cus_A" in rendered
