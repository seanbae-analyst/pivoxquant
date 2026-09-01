"""§101 회피 게이트 회귀 테스트 (2026-05-26 v52).

세 endpoint/context 에서 임의 ticker 분석을 차단하는 가드를 검증한다:

        - 보유/관심 외 ticker → 403 access_denied
        - 보유 ticker → 게이트 통과(403 아님), take_profit 노출은 보유종목 한정
AI#2  GET /api/peers/<ticker>
        - 보유/관심 외 ticker → 403 access_denied
        - 보유 ticker → 게이트 통과(403 아님)
        - @legal_scrub_response 데코레이터 부착 확인
AI#3  AIService.build_analysis_context
        - 사용자공급 take_profit/stop_loss 가 LLM 컨텍스트에 미포함
"""
from __future__ import annotations

from unittest.mock import patch






# ── AI#3: build_analysis_context take_profit/stop_loss 미주입 ─────────────────

class TestBuildAnalysisContextNoTakeProfit:
    def test_take_profit_stop_loss_excluded_from_llm_context(self):
        from services.ai.service import AIService
        svc = AIService()
        ctx = svc.build_analysis_context({
            "ticker": "AAPL", "name": "Apple", "price": 190,
            "signal": "NEUTRAL", "score": 55,
            "signals": [{"type": "bullish", "msg": "Up trend"}],
            # 사용자공급 advisory 수치 — LLM 컨텍스트에 절대 들어가면 안 됨.
            "take_profit": 220, "stop_loss": 175,
        })
        assert "Take Profit" not in ctx
        assert "Stop Loss" not in ctx
        assert "220" not in ctx
        assert "175" not in ctx
        # 정상 필드는 보존.
        assert "AAPL" in ctx
        assert "Up trend" in ctx
