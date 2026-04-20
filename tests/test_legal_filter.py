"""Tests for services.legal_filter — 자본시장법 §6 / §101 방어선 회귀 테스트.

42 replacement patterns + 6 prohibited patterns. Each group has at least one
sample that proves the pattern fires. These tests are the canary — if any
assert fails, production is one deploy away from a regulatory exposure.
"""
from __future__ import annotations

import pytest

from services.legal_filter import (
    detect_prohibited,
    ensure_disclaimer,
    safe_scrub,
    scrub_response,
    scrub_signal,
    scrub_text,
)


class TestReplacements:
    """Each sample hits one of the 42 regex patterns and confirms it rewrites."""

    # ── Group 1: 복합 구문 ────────────────────────────────────────────────
    def test_position_reduction(self):
        assert "약세 신호 감지" in scrub_text("포지션 축소 또는 청산 고려")

    def test_exposure_reduction(self):
        assert "노출 지표 상승 관찰" in scrub_text("노출 축소 권고")

    def test_new_entry_hold(self):
        assert "신규 진입 관찰 구간" == scrub_text("신규 매수 보류")

    def test_cash_ratio(self):
        assert "현금 비중 관찰 지표" == scrub_text("현금 비중 확대 권고")

    def test_tp_sl(self):
        assert "TP/SL 레벨 관찰" == scrub_text("부분 익절 / 손절 고려")

    # ── Group 2: 권고 / 추천 / 조언 ─────────────────────────────────────
    @pytest.mark.parametrize(
        "original",
        [
            "매수 추천", "매수 권고", "매수 권장",
            "매도 추천", "매도 권고", "매도 권장",
            "손절 권고", "익절 권고",
        ],
    )
    def test_single_verb_recommendation_removed(self, original):
        result = scrub_text(original)
        assert "추천" not in result
        assert "권고" not in result
        assert "권장" not in result

    def test_chumchun_drimnida(self):
        assert "추천" not in scrub_text("AAPL 추천 드립니다.")

    def test_gwanyu(self):
        assert "권유" not in scrub_text("투자 권유 드립니다.")

    # ── Group 3: 타이밍 / 목표가 ────────────────────────────────────────
    def test_buy_timing(self):
        assert "진입 레벨 관찰" == scrub_text("매수 타이밍")

    def test_sell_timing(self):
        assert "청산 레벨 관찰" == scrub_text("매도 타이밍")

    def test_target_price(self):
        assert "목표가" not in scrub_text("목표가 도달")
        assert "참고 지표" in scrub_text("목표가 도달")

    def test_fair_price(self):
        assert "적정가" not in scrub_text("적정가 분석")

    def test_expected_return_pct(self):
        # "예상 수익률 +12.5%" 전체 구가 "과거 기록 지표"로
        out = scrub_text("예상 수익률 +12.5%")
        assert "+12.5%" not in out
        assert "과거 기록 지표" in out

    # ── Group 4: 전망 / 예측 ────────────────────────────────────────────
    def test_outlook_future(self):
        assert "전망" not in scrub_text("향후 전망")

    def test_market_outlook(self):
        assert "시장 관찰 구간" == scrub_text("시장 전망")

    def test_will_rise(self):
        assert "상승 지표가 관찰됩니다" in scrub_text("오를 것으로 보입니다.")

    def test_will_fall(self):
        assert "하락 지표가 관찰됩니다" in scrub_text("내릴 것 같습니다.")

    # ── Group 5: 가치 판단 ──────────────────────────────────────────────
    def test_favorable(self):
        assert "지표가 높은" in scrub_text("유리한 종목")

    def test_unfavorable(self):
        assert "지표가 낮은" in scrub_text("불리한 종목")

    def test_promising(self):
        assert "관찰 대상인" in scrub_text("유망한 종목")

    def test_overvalued(self):
        assert "고평가" not in scrub_text("고평가 구간")

    def test_aggressive(self):
        assert "변동성 높은 투자" in scrub_text("공격적 투자 접근")

    def test_best_stock(self):
        assert "상위 지표 종목" == scrub_text("베스트 종목")

    # ── Group 6: English imperatives ────────────────────────────────────
    def test_buy_signal_en(self):
        assert "POSITIVE indicator" == scrub_text("BUY signal")

    def test_sell_signal_en(self):
        assert "NEGATIVE indicator" == scrub_text("SELL signal")

    def test_recommend(self):
        assert "recommend" not in scrub_text("We recommend AAPL").lower()

    def test_advise(self):
        assert "advise" not in scrub_text("We advise caution").lower()

    def test_suggest(self):
        assert "suggest" not in scrub_text("We suggest review").lower()

    def test_target_price_en(self):
        assert "reference price" in scrub_text("Target price $200")

    def test_fair_value_en(self):
        assert "reference value" in scrub_text("Fair value estimate")

    # ── Group 7: 시장 비교 / 전망 영문 ─────────────────────────────────
    def test_outperform(self):
        out = scrub_text("This stock will outperform").lower()
        assert "outperform" not in out

    def test_beat_market(self):
        assert "benchmark 대비 기록" in scrub_text("Beat the market")

    def test_beat_sp500(self):
        assert "S&P 500 benchmark 대비 기록" in scrub_text("Beat S&P 500")

    def test_bullish(self):
        assert "상승 관찰" == scrub_text("bullish")

    def test_bearish(self):
        assert "하락 관찰" == scrub_text("bearish")

    def test_predict(self):
        assert "predict" not in scrub_text("Models predict rally").lower()

    def test_forecast(self):
        assert "forecast" not in scrub_text("Forecast is positive").lower()

    def test_best_opportunity(self):
        assert "highest indicator" == scrub_text("best opportunity")

    def test_most_attractive(self):
        assert "highest indicator" == scrub_text("most attractive")


class TestProhibitedDetection:
    """Patterns that cannot be surgically fixed — must be caught upstream."""

    @pytest.mark.parametrize(
        "text",
        [
            "목표가 $200",
            "목표가 ₩50,000",
            "예상 수익률 +15%",
            "적정가 $180",
            "price target: $200",
            "expected return: +15%",
            "fair value: $180",
        ],
    )
    def test_prohibited_detected(self, text):
        assert detect_prohibited(text), f"Failed to detect: {text}"

    def test_clean_text_no_detection(self):
        assert detect_prohibited("POSITIVE indicator observed.") == []

    def test_empty_text(self):
        assert detect_prohibited("") == []
        assert detect_prohibited(None) == []


class TestSafeScrub:
    def test_none_passthrough(self):
        assert safe_scrub(None) is None

    def test_empty_passthrough(self):
        assert safe_scrub("") == ""

    def test_non_string_passthrough(self):
        assert safe_scrub(123) == 123  # type: ignore[arg-type]

    def test_logs_prohibited(self, caplog):
        import logging
        caplog.set_level(logging.WARNING)
        safe_scrub("목표가 $200", context="unit-test")
        assert any("prohibited" in r.message for r in caplog.records)


class TestScrubSignal:
    def test_nested_dict(self):
        data = {
            "ticker": "AAPL",
            "score": 72,
            "commentary_kr": "매수 추천",
            "summary": "BUY signal strong",
            "ai_commentary": {"thesis": "outperform the market"},
        }
        out = scrub_signal(data)
        assert "추천" not in out["commentary_kr"]
        assert "POSITIVE" in out["summary"]
        assert "outperform" not in out["ai_commentary"]["thesis"]
        # non-string fields intact
        assert out["ticker"] == "AAPL"
        assert out["score"] == 72

    def test_non_dict_noop(self):
        assert scrub_signal("not a dict") == "not a dict"
        assert scrub_signal(None) is None


class TestScrubResponse:
    def test_nested_list_and_dict(self):
        payload = {
            "items": [
                {"analysis": "매수 권고합니다"},
                {"analysis": "SELL signal"},
            ],
            "note": "bullish outlook",
        }
        out = scrub_response(payload)
        assert "권고" not in out["items"][0]["analysis"]
        assert "SELL" not in out["items"][1]["analysis"]
        assert "상승 관찰" in out["note"]


class TestEnsureDisclaimer:
    def test_append_kr(self):
        out = ensure_disclaimer("관찰 지표입니다.", "kr")
        assert "정보 제공 목적이며 투자 권유가 아닙니다" in out

    def test_append_en(self):
        out = ensure_disclaimer("Observed.", "en")
        assert "informational only" in out

    def test_idempotent(self):
        text = "Observed.\n\nThis is informational only and not investment advice."
        assert ensure_disclaimer(text, "en") == text

    def test_none_passthrough(self):
        assert ensure_disclaimer(None) is None
