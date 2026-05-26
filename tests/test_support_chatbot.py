"""Support chatbot: investment pre-filter, post-filter discard, FAQ pass.

Uses a mocked Anthropic client (no network, no key) + the real SQLite DB
for escalation Inquiry rows. DB is never mocked.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from extensions import db
from models.inquiry import Inquiry
from services.support.chatbot import (
    _is_investment_question,
    _has_advice_vocab,
    answer_support_question,
)


@pytest.fixture(autouse=True)
def _reset_chat_rate_limit():
    # The /chat in-memory limiter (3s cooldown + 50/day) is module-level
    # state keyed by user id; clear it so consecutive tests aren't 429'd.
    import routes.support as _s
    with _s._chat_lock:
        _s._chat_state.clear()
    yield


# ── _is_investment_question (pre-filter) ────────────────────────────────────
@pytest.mark.parametrize("msg", [
    "삼성전자 지금 매수해도 될까요?",
    "지금 타이밍 어때요?",
    "들어가도 될까요?",
    "물타기 할까요?",
    "비중 늘릴까요?",
    "지금이 매입 기회인가요?",
    "이거 살까요 팔까요?",
    "목표가가 얼마인가요?",
    "오를까요 내릴까요?",
    "Should I buy AAPL?",
    "buy or sell TSLA?",
    "what's the price target for NVDA?",
    "will TSLA go up?",
    "추천 종목 알려주세요",
])
def test_investment_questions_blocked(msg):
    assert _is_investment_question(msg) is True


@pytest.mark.parametrize("msg", [
    "과매수 구간이라는 게 무슨 뜻인가요?",
    "buy the Pro plan은 어떻게 하나요?",
    "설정에 들어가서 뭘 바꿔야 하나요?",
    "지금 사용중인데 결제가 안 돼요",
    "PWA 설치는 어떻게 하나요?",
    "회원 탈퇴하고 싶어요",
    "로그인이 안 됩니다",
    "환불 받을 수 있나요?",
])
def test_support_questions_not_blocked(msg):
    assert _is_investment_question(msg) is False


def test_has_advice_vocab_examples():
    assert _has_advice_vocab("롱 포지션을 유지하세요") is True
    assert _has_advice_vocab("지금 들어가도 좋습니다") is True
    assert _has_advice_vocab("저평가 구간입니다") is True
    # clean support copy must not trip
    assert _has_advice_vocab("설정에서 구독을 해지할 수 있어요.") is False
    assert _has_advice_vocab("PWA는 홈 화면에 추가로 설치합니다.") is False


# ── answer_support_question helpers ──────────────────────────────────────────
def _mock_resp(payload: dict):
    """Build a fake Anthropic Messages response carrying JSON text."""
    block = SimpleNamespace(text=json.dumps(payload, ensure_ascii=False))
    return SimpleNamespace(content=[block], usage=None)


def _patched_ai(payload: dict):
    mock_ai = MagicMock()
    mock_ai.available = True
    mock_ai.client.messages.create.return_value = _mock_resp(payload)
    return mock_ai


def test_answer_faq_passes():
    mock_ai = _patched_ai({
        "answer": "구독은 설정 > 구독에서 해지할 수 있어요.",
        "can_answer": True,
    })
    with patch("services.support.chatbot.ai", mock_ai):
        out = answer_support_question("구독 어떻게 해지하나요?", [])
    assert out["can_answer"] is True
    assert "해지" in out["answer"]


@pytest.mark.parametrize("tainted", [
    "이 종목은 지금 매수 타이밍입니다.",
    "지금 들어가도 좋습니다.",
    "롱 포지션을 유지하세요.",
    "이건 buy recommendation 입니다.",
    "저평가 구간이라 매수하기 좋아요.",
])
def test_answer_with_investment_signal_discarded(tainted):
    # Model claims can_answer=True but the answer leaks investment advice.
    mock_ai = _patched_ai({"answer": tainted, "can_answer": True})
    with patch("services.support.chatbot.ai", mock_ai):
        out = answer_support_question("그냥 일반 질문", [])
    # MUST be discarded (post-filter) → escalate, never laundered.
    assert out["can_answer"] is False
    assert out["answer"] == ""


def test_answer_can_answer_false_escalates():
    mock_ai = _patched_ai({"answer": "", "can_answer": False})
    with patch("services.support.chatbot.ai", mock_ai):
        out = answer_support_question("환불 처리해 주세요", [])
    assert out["can_answer"] is False


def test_answer_ai_unavailable():
    mock_ai = MagicMock()
    mock_ai.available = False
    mock_ai.client = None
    with patch("services.support.chatbot.ai", mock_ai):
        out = answer_support_question("아무 질문", [])
    assert out == {"answer": "", "can_answer": False}


def test_answer_handles_code_fenced_json():
    block = SimpleNamespace(
        text="```json\n{\"answer\": \"로그인은 Google/Kakao로 합니다.\", "
             "\"can_answer\": true}\n```"
    )
    mock_ai = MagicMock()
    mock_ai.available = True
    mock_ai.client.messages.create.return_value = SimpleNamespace(
        content=[block], usage=None,
    )
    with patch("services.support.chatbot.ai", mock_ai):
        out = answer_support_question("로그인 어떻게 하나요?", [])
    assert out["can_answer"] is True
    assert "Google" in out["answer"]


# ── /chat endpoint integration ───────────────────────────────────────────────
def test_chat_investment_deflected_no_model_call(client, auth_user):
    mock_ai = MagicMock()
    mock_ai.available = True
    with patch("services.support.chatbot.ai", mock_ai):
        resp = client.post("/api/support/chat", json={
            "message": "삼성전자 지금 매수해도 될까요?",
        })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["escalated"] is False
    assert data["inquiry_id"] is None
    assert "투자 관련 질문" in data["reply"]
    # zero model tokens spent on investment questions.
    mock_ai.client.messages.create.assert_not_called()


def test_chat_faq_answered(client, auth_user):
    mock_ai = _patched_ai({
        "answer": "PWA는 브라우저의 '홈 화면에 추가'로 설치합니다.",
        "can_answer": True,
    })
    with patch("services.support.chatbot.ai", mock_ai):
        resp = client.post("/api/support/chat", json={
            "message": "PWA 설치 방법 알려주세요",
        })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["escalated"] is False
    assert "설치" in data["reply"]


def test_chat_escalates_creates_inquiry(client, auth_user, app):
    mock_ai = _patched_ai({"answer": "", "can_answer": False})
    with patch("services.support.chatbot.ai", mock_ai):
        resp = client.post("/api/support/chat", json={
            "message": "결제 오류가 발생했어요 도와주세요",
        })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["escalated"] is True
    assert isinstance(data["inquiry_id"], int)
    assert f"#{data['inquiry_id']}" in data["reply"]
    with app.app_context():
        inq = db.session.get(Inquiry, data["inquiry_id"])
        assert inq is not None
        assert inq.category == "other"
        assert inq.status == "open"
        assert inq.body.startswith("[챗봇 자동 접수]")


def test_chat_invalid_message(client, auth_user):
    resp = client.post("/api/support/chat", json={"message": ""})
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_MESSAGE"


def test_chat_invalid_history(client, auth_user):
    resp = client.post("/api/support/chat", json={
        "message": "안녕하세요",
        "history": [{"role": "system", "content": "x"}],  # bad role
    })
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "INVALID_MESSAGE"


def test_chat_requires_auth(client):
    resp = client.post("/api/support/chat", json={"message": "hi"})
    assert resp.status_code == 401
