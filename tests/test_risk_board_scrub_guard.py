"""tests/test_risk_board_scrub_guard.py — Risk Board narrative scrub guard
==========================================================================
2026-05-22: the Risk Board narrative used a home-rolled IGNORECASE banned-word
loop with NO lookbehind, so it corrupted quant terms:
    "과매수 신호" → "과진입 관찰 신호"   (BUG)
    "과매도 영역" → "과청산 관찰 영역"   (BUG)
The loop was replaced with the authoritative `services.legal_filter.safe_scrub`
plus a lookbehind-guarded supplemental pass (`_board_supplemental_scrub`) for
Risk-Board-specific terms safe_scrub does not own (비중 축소 / 추천 / 조언 /
bare 매수·매도 / reduce). These tests assert quant terms survive while advisory
terms are still neutralized.
"""
from __future__ import annotations

import pytest

from services.artifacts.risk_board_service import _board_supplemental_scrub
from services.legal_filter import safe_scrub


def _board_scrub(text: str) -> str:
    """Mirror the production scrub path: safe_scrub → supplemental pass."""
    return _board_supplemental_scrub(safe_scrub(text, context="risk_board.ai") or "")


class TestRiskBoardScrubPreservesQuantTerms:
    @pytest.mark.parametrize(
        "text",
        [
            "과매수 신호 관찰",
            "과매도 영역 모니터링",
            "RSI 과매수",
            "과매수",
            "과매도",
        ],
    )
    def test_overbought_oversold_not_corrupted(self, text):
        out = _board_scrub(text)
        assert "과매수" in out or "과매도" in out, (
            f"quant term in {text!r} was corrupted → {out!r}"
        )
        for bad in ("과진입", "과청산", "과POSITIVE", "과NEGATIVE"):
            assert bad not in out, f"{text!r} corrupted → {out!r}"


class TestRiskBoardScrubNeutralizesAdvisory:
    @pytest.mark.parametrize(
        "text,banned",
        [
            ("비중 축소 권고", "비중 축소"),
            ("이 종목을 추천", "추천"),
            ("조언 드립니다", "조언"),
            ("reduce exposure now", "reduce"),
            ("손절 타이밍", "손절"),
            ("익절 시점", "익절"),
        ],
    )
    def test_advisory_terms_removed(self, text, banned):
        out = _board_scrub(text)
        assert banned.lower() not in out.lower(), (
            f"advisory term {banned!r} survived in {out!r}"
        )

    def test_helper_guards_bare_buy_sell(self):
        # supplemental pass alone: bare 매수/매도 scrubbed, 과매수/매수세 kept.
        assert "진입 관찰" in _board_supplemental_scrub("매수 압박")
        assert _board_supplemental_scrub("과매수") == "과매수"
        assert _board_supplemental_scrub("매수세 증가") == "매수세 증가"
