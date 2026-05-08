"""Regression tests for services.ai.service._compliance_filter.

Background — 2026-05-09 regression
----------------------------------
The required closing disclaimer mandated by SYSTEM_PROMPT
(services/ai/service.py:84-85) is:

    EN: "This content is informational only and not investment advice.
         PivoxQuant does not provide individualized recommendations."
    KR: "본 내용은 정보 제공 목적이며 투자 권유가 아닙니다.
         PivoxQuant는 개별 투자 자문을 제공하지 않습니다."

Both versions contain words on the forbidden-vocab regex used by
``services.legal_filter.is_compliant`` ("advice", "recommendations",
"권유", "자문"). Without the disclaimer-strip pre-step, every
well-formed AI response would be silently replaced by the fallback
one-liner, blanking the analysis body.

The fix in services/ai/service.py introduces ``_strip_disclaimers``
which excises known disclaimer fragments before the vocab check, so
the body alone is evaluated. The full original text (disclaimer
preserved verbatim) is returned when the body is compliant.

These tests are the canary for that contract.
"""
from __future__ import annotations

import pytest

from services.ai.service import (
    _DISCLAIMER_EN,
    _DISCLAIMER_KR,
    _compliance_filter,
    _strip_disclaimers,
)


class TestStripDisclaimers:
    def test_en_full_disclaimer_removed(self):
        text = (
            "AAPL is up. " + _DISCLAIMER_EN
        )
        body = _strip_disclaimers(text)
        assert "AAPL is up." in body
        assert "advice" not in body.lower()
        assert "recommendations" not in body.lower()

    def test_kr_full_disclaimer_removed(self):
        text = "삼성전자 지표 상승 관찰. " + _DISCLAIMER_KR
        body = _strip_disclaimers(text)
        assert "지표 상승 관찰" in body
        assert "권유" not in body
        assert "자문" not in body

    def test_short_en_variant_removed(self):
        # The legal_filter._DISCLAIMER_EN short variant.
        text = "Body text. This is informational only and not investment advice."
        body = _strip_disclaimers(text)
        assert "Body text." in body
        assert "advice" not in body.lower()

    def test_short_kr_variant_removed(self):
        text = "본문입니다. 본 내용은 정보 제공 목적이며 투자 권유가 아닙니다."
        body = _strip_disclaimers(text)
        assert "본문입니다." in body
        assert "권유" not in body

    def test_empty_passthrough(self):
        assert _strip_disclaimers("") == ""
        assert _strip_disclaimers(None) is None


class TestComplianceFilter:
    """End-to-end: full SYSTEM_PROMPT-compliant response should pass through."""

    def test_normal_response_with_required_disclaimer_en(self):
        # This is the regression that broke /api/ai/{swot,coaching,...} —
        # before the fix, this entire string was replaced with the fallback.
        text = (
            "AAPL shows positive momentum on the day, with the quant score "
            "recording a +5 indicator move. " + _DISCLAIMER_EN
        )
        out = _compliance_filter(text, "en")
        assert out == text, "compliant body + disclaimer must pass through verbatim"

    def test_normal_response_with_required_disclaimer_kr(self):
        text = (
            "삼성전자 모멘텀 지표가 양호한 흐름을 기록했습니다. " + _DISCLAIMER_KR
        )
        out = _compliance_filter(text, "kr")
        assert out == text

    def test_advisory_text_still_blocked_en(self):
        # Body itself contains forbidden imperative — must fall back.
        text = "I recommend you buy AAPL right now. " + _DISCLAIMER_EN
        out = _compliance_filter(text, "en")
        assert out == _DISCLAIMER_EN
        assert "buy AAPL" not in out

    def test_advisory_text_still_blocked_kr(self):
        text = "삼성전자 매수 추천드립니다. " + _DISCLAIMER_KR
        out = _compliance_filter(text, "kr")
        assert out == _DISCLAIMER_KR
        assert "추천" not in out
        assert "매수" not in out

    def test_disclaimer_only_passthrough(self):
        # Vacuous case — body is empty after strip, but is_compliant("")
        # returns True, so original is returned.
        out = _compliance_filter(_DISCLAIMER_EN, "en")
        assert out == _DISCLAIMER_EN

    def test_clean_body_no_disclaimer_passthrough(self):
        # Compliant body without disclaimer suffix still passes (legacy
        # callers may not append the suffix; safe-side behavior).
        text = "AAPL recorded a +2.1 percent move on the day."
        out = _compliance_filter(text, "en")
        assert out == text

    def test_none_passthrough(self):
        assert _compliance_filter(None, "en") is None
        assert _compliance_filter(None, "kr") is None

    @pytest.mark.parametrize("lang", ["en", "kr"])
    def test_advisory_no_disclaimer_blocked(self, lang):
        text = "Buy this stock immediately."
        out = _compliance_filter(text, lang)
        expected = _DISCLAIMER_KR if lang == "kr" else _DISCLAIMER_EN
        assert out == expected
