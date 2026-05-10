"""
test_position_size_wording.py — 자본시장법 §101 ④ 회피 어휘 검증 (Q10).

services/ai/service.py:build_analysis_context() 가 AI 컨텍스트에 포함하는
포지션 크기 라인은 미등록 투자자문업 회피를 위해 다음 두 조건을 모두
충족해야 한다:

  1. 한국어 "참고" 어휘 사용 (예시 포지션 크기 / 투자권유·매매조언이 아닌
     참고용 정보입니다)
  2. 영문 "Suggested" / "recommendation" 단어 사용 금지

본 게이트가 깨지면 §101 ④ 면제 트랙(2026-05-04 CEO 확정) 이 위협받는다 —
출시 전 변호사 의견서(Q10) 결과와 함께 추가 보강 가능.
"""
from __future__ import annotations

import re

import pytest

from services.ai.service import AIService


@pytest.fixture
def analysis_context() -> str:
    svc = AIService()
    data = {
        "name": "Samsung Electronics",
        "ticker": "005930.KS",
        "price": 78000,
        "price_display": "₩78,000",
        "signal": "POSITIVE",
        "score": 72,
        "tech_score": 70,
        "fund_score": 75,
        "news_score": 71,
        "signals": [],
        "reason": "Earnings momentum and gross margin expansion.",
        "rec_shares": 12,
        "rec_investment": 936000,
    }
    return svc.build_analysis_context(data)


def test_position_size_uses_korean_reference_wording(analysis_context: str) -> None:
    """KR primary 어휘가 들어가야 한다."""
    assert "예시 포지션 크기 (참고)" in analysis_context, (
        "KR primary 참고용 어휘가 빠짐. §101 ④ 회피 어휘 회귀."
    )
    assert "투자권유·매매조언이 아닌 참고용 정보입니다" in analysis_context, (
        "면책 KR 어구가 빠짐. §101 ④ 회피 어휘 회귀."
    )


def test_position_size_does_not_use_suggested_or_recommendation(
    analysis_context: str,
) -> None:
    """영문 'Suggested' / 'recommendation' 어휘는 §101 위험."""
    # "Suggested position size" 라는 정확한 카피 금지
    assert not re.search(
        r"Suggested\s+position\s+size", analysis_context, re.IGNORECASE
    ), "'Suggested position size' 어휘가 §101 ④ 위반."

    # 포지션 크기 라인 자체에 "recommendation" 단어 금지
    pos_lines = [
        ln
        for ln in analysis_context.splitlines()
        if "참고" in ln or "position size" in ln.lower()
    ]
    joined = "\n".join(pos_lines)
    assert "recommendation" not in joined.lower(), (
        "포지션 크기 라인에 'recommendation' 어휘 — §101 ④ 위반."
    )


def test_position_size_includes_english_subline(analysis_context: str) -> None:
    """영문 병기는 유지 — 외국인 사용자 대응."""
    assert "Example position size for reference only" in analysis_context, (
        "영문 subline 누락 — 한국어 primary + 영문 병기 정책 위반."
    )
