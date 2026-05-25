"""§101 회피 게이트 회귀 테스트 (2026-05-26 v52).

세 endpoint/context 에서 임의 ticker 분석을 차단하는 가드를 검증한다:

AI#1  GET /api/daytrade/analyze/<ticker>
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


# ── AI#1: /api/daytrade/analyze/<ticker> ─────────────────────────────────────

class TestDaytradeAnalyzeGate:
    def test_out_of_scope_ticker_returns_403(self, client, auth_user):
        # 보유/관심 없는 임의 종목 → §101 거부.
        r = client.get("/api/daytrade/analyze/TSLA")
        assert r.status_code == 403
        assert r.get_json()["error"] == "ticker_not_in_user_scope"

    def test_out_of_scope_kr_ticker_returns_403(self, client, auth_user):
        # bare 6-digit KR 코드 역시 정규화 후 거부.
        r = client.get("/api/daytrade/analyze/005930")
        assert r.status_code == 403
        assert r.get_json()["error"] == "ticker_not_in_user_scope"

    def test_owned_us_ticker_passes_gate_and_exposes_take_profit(
        self, client, auth_user, add_position,
    ):
        add_position(auth_user["id"], ticker="AAPL")
        # daytrade 서비스 boundary 를 mock — 게이트 통과 후 take_profit 포함 흐름 보존.
        with patch("routes.daytrade.daytrade") as mock_dt:
            mock_dt.available = True
            mock_dt.analyze_short_term.return_value = {
                "ticker": "AAPL", "name": "Apple", "signal": "NEUTRAL",
                "take_profit": 200, "stop_loss": 180,
            }
            r = client.get("/api/daytrade/analyze/AAPL")
        # 게이트 통과 (403 아님). take_profit 은 보유종목 한정으로만 노출.
        assert r.status_code == 200
        body = r.get_json()
        assert body["ticker"] == "AAPL"
        assert body["take_profit"] == 200

    def test_watched_ticker_passes_gate(self, app, client, auth_user):
        from extensions import db
        from models import Watchlist
        with app.app_context():
            db.session.add(Watchlist(user_id=auth_user["id"], ticker="MSFT"))
            db.session.commit()
        with patch("routes.daytrade.daytrade") as mock_dt:
            mock_dt.available = True
            mock_dt.analyze_short_term.return_value = {
                "ticker": "MSFT", "name": "Microsoft", "signal": "NEUTRAL",
            }
            r = client.get("/api/daytrade/analyze/MSFT")
        assert r.status_code != 403


# ── AI#2: /api/peers/<ticker> ────────────────────────────────────────────────

class TestPeerComparisonGate:
    def test_out_of_scope_ticker_returns_403(self, client, auth_user):
        r = client.get("/api/peers/TSLA")
        assert r.status_code == 403
        assert r.get_json()["error"] == "ticker_not_in_user_scope"

    def test_owned_ticker_passes_gate(self, client, auth_user, add_position):
        # 보유 ticker 는 게이트 통과 → SignalCache 없으면 404(분석먼저)지만 403 아님.
        add_position(auth_user["id"], ticker="AAPL")
        r = client.get("/api/peers/AAPL")
        assert r.status_code != 403

    def test_legal_scrub_decorator_attached(self):
        # 형제 endpoint 일치 — @legal_scrub_response 부착 확인.
        from routes import market as market_route
        assert hasattr(market_route.peer_comparison, "__wrapped__")


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
