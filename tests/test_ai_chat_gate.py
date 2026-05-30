"""§101③ isolation gate for the bidirectional AI chat channel.

DECISIONS.md ✅확정 2026-05-30: free-text 양방향 채팅(`POST /api/ai/chat`) =
자본시장법 §101③ 유사투자자문업 면제 트랙의 표적 채널. 출시 무료 Stage 0 에서는
``AI_CHAT_ENABLED`` 플래그(기본 OFF)로 닫는다. 엔드포인트 코드는 보존하고
플래그만 개폐한다(companion ``AGENT_ENABLED`` 패턴 복제).

These tests pin the gate so the bidirectional channel cannot silently reopen,
and prove the unidirectional analysis endpoints (`/swot`) stay live regardless
of the flag.
"""
from unittest.mock import patch

import pytest


def _login(client, user):
    resp = client.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"],
    })
    assert resp.status_code == 200, f"Login failed: {resp.data!r}"


class TestAiChatGate:
    def test_chat_disabled_returns_403_without_llm_call(
        self, app, client, make_user, monkeypatch,
    ):
        """Flag OFF (default): /api/ai/chat → 403 ai_chat_disabled, no LLM."""
        monkeypatch.delenv("AI_CHAT_ENABLED", raising=False)
        u = make_user(email="chat_gate_off@test.com", tier="pro")
        _login(client, u)

        # If the gate is bypassed and chat_stream is reached, this raises.
        with patch("routes.ai.ai") as mock_ai:
            mock_ai.available = True
            mock_ai.chat_stream.side_effect = AssertionError(
                "chat_stream must NOT be called when AI_CHAT_ENABLED is OFF"
            )
            r = client.post("/api/ai/chat", json={"message": "삼성전자 어때?"})

        assert r.status_code == 403, r.data
        assert r.get_json() == {"error": "ai_chat_disabled"}
        mock_ai.chat_stream.assert_not_called()

    @pytest.mark.parametrize("flag_value", ["1", "true", "TRUE"])
    def test_chat_enabled_passes_gate(
        self, app, client, make_user, monkeypatch, flag_value,
    ):
        """Flag ON: gate is open — request proceeds past the 403 (code preserved)."""
        monkeypatch.setenv("AI_CHAT_ENABLED", flag_value)
        u = make_user(email="chat_gate_on@test.com", tier="pro")
        _login(client, u)

        def fake_stream(message, history, context):
            yield "관찰 결과입니다."

        with patch("routes.ai.ai") as mock_ai, \
             patch("routes.ai.fetcher") as mock_fetcher:
            mock_ai.available = True
            mock_ai.build_portfolio_context.return_value = {}
            mock_ai.chat_stream.side_effect = fake_stream
            mock_fetcher.get_macro_data.return_value = {}
            r = client.post("/api/ai/chat", json={"message": "포트폴리오 관찰"})

        # Gate passed: NOT the 403 isolation response. SSE stream returns 200.
        assert r.status_code != 403, r.data
        assert r.get_json() != {"error": "ai_chat_disabled"}

    def test_swot_unaffected_by_chat_flag(
        self, app, client, make_user, add_position, monkeypatch,
    ):
        """Unidirectional /swot works while the chat channel is OFF."""
        from extensions import db
        from models import SignalCache

        monkeypatch.delenv("AI_CHAT_ENABLED", raising=False)  # chat OFF
        u = make_user(email="swot_unaffected@test.com", tier="pro")
        add_position(user_id=u["id"], ticker="AAPL", shares=1.0, avg_cost=100.0)
        with app.app_context():
            db.session.add(SignalCache(ticker="AAPL", data_json='{"price": 100.0}'))
            db.session.commit()
        _login(client, u)

        with patch("routes.ai.ai") as mock_ai:
            mock_ai.available = True
            mock_ai.generate_swot.return_value = {
                "strengths": ["s"], "weaknesses": ["w"],
                "opportunities": ["o"], "threats": ["t"],
            }
            r = client.post("/api/ai/swot", json={"ticker": "AAPL"})

        assert r.status_code == 200, r.data
        assert r.get_json() != {"error": "ai_chat_disabled"}
        mock_ai.generate_swot.assert_called_once()
