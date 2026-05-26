"""Zero-cost FAQ retrieval in the support chatbot.

The chatbot must answer common support questions WITHOUT any Anthropic model
call (so it stays useful when the API balance is empty). These tests prove the
FAQ path runs with zero model calls and never launders investment advice.
"""
import pytest

from services.support import chatbot
from services.support.chatbot import (
    _faq_match,
    _is_investment_question,
    answer_support_question,
)


class _BoomMessages:
    @staticmethod
    def create(*args, **kwargs):
        raise AssertionError("model must NOT be called on the FAQ path")


class _BoomClient:
    messages = _BoomMessages()


class _FakeBlock:
    def __init__(self, text):
        self.text = text


class _FakeResp:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]


class _GoodMessages:
    @staticmethod
    def create(*args, **kwargs):
        return _FakeResp('{"answer":"설정 페이지에서 변경하실 수 있어요.","can_answer":true}')


class _GoodClient:
    messages = _GoodMessages()


@pytest.fixture
def model_blows_up(monkeypatch):
    """Simulate a present-but-broken model (e.g. credit balance exhausted):
    any model call raises. FAQ answers must still work."""
    monkeypatch.setattr(chatbot.ai, "available", True, raising=False)
    monkeypatch.setattr(chatbot.ai, "client", _BoomClient(), raising=False)


@pytest.mark.parametrize(
    "q",
    [
        "Pro 요금제 얼마예요?",
        "구독 해지하려면 어떻게 해요?",
        "로그인이 안 돼요",
        "회원 탈퇴하고 싶어요",
        "데이터 출처가 어디예요?",
        "PWA 설치 어떻게 해요?",
        "시그널 라벨이 무슨 뜻이에요?",
        "고객센터 어디로 문의해요?",
    ],
)
def test_faq_match_returns_answer(q):
    ans = _faq_match(q)
    assert ans is not None and len(ans) > 0


def test_faq_answers_with_zero_model_calls(model_blows_up):
    # FAQ-matched question → can_answer=True and the model is never called
    # (the boom client would raise if the model path were taken).
    r = answer_support_question("Pro 요금제 얼마예요?", [])
    assert r["can_answer"] is True
    assert ("9,900" in r["answer"]) or ("9900" in r["answer"])


def test_unmatched_individual_topic_escalates(model_blows_up):
    # Refund processing is deliberately NOT an FAQ entry → no match → escalate.
    r = answer_support_question("제 결제 환불 처리 좀 해주세요", [])
    assert r["can_answer"] is False


def test_investment_question_never_faq_answered(model_blows_up):
    assert _is_investment_question("삼성전자 지금 사도 돼?") is True
    r = answer_support_question("삼성전자 지금 사도 돼?", [])
    assert r["can_answer"] is False


def test_refund_timing_does_not_false_match():
    # "환불" is not a keyword anywhere; a refund question must not mis-match the
    # pricing FAQ. None → escalation.
    assert _faq_match("환불 얼마나 걸려요?") is None


def test_llm_disabled_by_default_escalates_without_model(monkeypatch):
    # Default (no env): LLM fallback OFF. An FAQ-missed, non-investment
    # question must escalate WITHOUT any model call (boom client would raise).
    monkeypatch.delenv("SUPPORT_CHAT_LLM_ENABLED", raising=False)
    monkeypatch.setattr(chatbot.ai, "available", True, raising=False)
    monkeypatch.setattr(chatbot.ai, "client", _BoomClient(), raising=False)
    r = answer_support_question("리포트 발송 시간을 바꾸고 싶어요", [])
    assert r["can_answer"] is False


def test_llm_enabled_uses_model_fallback(monkeypatch):
    # With the flag on AND a working client, FAQ-missed questions use Claude.
    monkeypatch.setenv("SUPPORT_CHAT_LLM_ENABLED", "1")
    monkeypatch.setattr(chatbot.ai, "available", True, raising=False)
    monkeypatch.setattr(chatbot.ai, "client", _GoodClient(), raising=False)
    r = answer_support_question("리포트 발송 시간을 바꾸고 싶어요", [])
    assert r["can_answer"] is True
    assert "설정" in r["answer"]


def test_all_faq_answers_are_compliant():
    from services.legal.forbidden_terms import contains_forbidden_term
    from services.legal_filter import is_compliant

    for entry in chatbot._FAQ_ENTRIES:
        a = entry["answer"]
        assert is_compliant(a), a
        assert contains_forbidden_term(a) is None, a
        assert not chatbot._has_advice_vocab(a), a
