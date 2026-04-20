"""Runtime scrubber for legally risky phrases in AI output & cached signals.

Purpose
-------
자본시장법 §6 미등록 투자자문업 리스크 방어선. Engine/AI/서비스 코드에서
"매수 권고", "매도 권고" 같은 advisory 동사가 유저에게 노출되기 전에
이 모듈이 safe alternative 로 치환한다.

Integration points
------------------
- services/cache_service.py :: cache_ticker() — engine.analyze() 결과를
  SignalCache 저장 **직전** scrub_signal() 호출
- ai_service.py :: generator 메서드 return 직전 safe_scrub() 호출 (옵션)

Non-goals
---------
- engine.py 수정 없이 출력 경계면에서만 치환 (런타임 방어선)
- 완벽한 NLP 기반 필터 아님 — 알려진 pattern 에 한해 정규식 치환
- _compliance_filter (ai_service.py) 와 달리 hard-drop 이 아니라 surgical replacement
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── Safe replacements (regex → safe alternative) ──────────────────────────
# 순서 중요: 긴 구문 먼저 매칭 → 짧은 구문이 부분 치환되지 않도록.
_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    # 복합 구문 (우선 처리)
    (re.compile(r"포지션\s*축소\s*또는\s*청산\s*고려"), "약세 신호 감지 (정보 제공)"),
    (re.compile(r"노출\s*축소\s*(권고|권장)"), "노출 지표 상승 관찰"),
    (re.compile(r"신규\s*매수\s*보류"), "신규 진입 관찰 구간"),
    (re.compile(r"현금\s*비중\s*확대\s*(권고|권장)"), "현금 비중 관찰 지표"),
    (re.compile(r"위험자산\s*비중\s*축소"), "위험자산 비중 모니터링"),
    (re.compile(r"부분\s*익절\s*/\s*손절\s*고려"), "TP/SL 레벨 관찰"),
    # 단일 동사 + 권고/권장
    (re.compile(r"매수\s*(권고|권장|추천)"), "정보 고지 (사전 설정 레벨 도달)"),
    (re.compile(r"매도\s*(권고|권장|추천)"), "정보 고지 (사전 설정 레벨 도달)"),
    (re.compile(r"손절\s*(권고|권장|추천)"), "정보 고지 (SL 레벨 도달)"),
    (re.compile(r"익절\s*(권고|권장|추천)"), "정보 고지 (TP 레벨 도달)"),
    (re.compile(r"매수\s*타이밍"), "진입 레벨 관찰"),
    (re.compile(r"매도\s*타이밍"), "청산 레벨 관찰"),
    # 영문
    (re.compile(r"\bBUY\s+signal\b", re.IGNORECASE), "POSITIVE signal"),
    (re.compile(r"\bSELL\s+signal\b", re.IGNORECASE), "NEGATIVE signal"),
    (re.compile(r"\brecommend(ation|ed)?\b", re.IGNORECASE), "information"),
    (re.compile(r"\badvice\b", re.IGNORECASE), "information"),
]

# ── Prohibited patterns (log only, 설계 오류 조기 발견용) ─────────────────
# 이 패턴이 나타나면 scrub 으로도 해결 안 됨 — 코드 단에서 제거되어야 함.
_PROHIBITED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"목표가\s*[\$₩]?\s*[\d,\.]+"),
    re.compile(r"예상\s*수익률\s*[+\-]?\d+(\.\d+)?%"),
    re.compile(r"적정가\s*[\$₩]?\s*[\d,\.]+"),
    re.compile(r"price\s*target\s*\$?[\d,\.]+", re.IGNORECASE),
]

# SignalCache JSON 필드 중 scrub 대상 (자유 텍스트 필드만)
_SCRUB_FIELDS: tuple[str, ...] = (
    "commentary",
    "commentary_kr",
    "summary",
    "summary_kr",
    "swot",
    "swot_kr",
    "insight",
    "insight_kr",
    "analysis",
    "analysis_kr",
    "message",
    "rationale",
    "thesis",
    "risk_note",
    "risk_notes",
)


def scrub_text(text: str | None) -> str | None:
    """Replace legally risky phrases with safe alternatives.

    None/empty-string passthrough. Returns the original text unchanged if
    no patterns match — cheap happy-path.
    """
    if not text or not isinstance(text, str):
        return text
    result = text
    for pattern, replacement in _REPLACEMENTS:
        result = pattern.sub(replacement, result)
    return result


def detect_prohibited(text: str | None) -> list[str]:
    """Return list of prohibited pattern names found. Empty list if clean."""
    if not text or not isinstance(text, str):
        return []
    hits = []
    for pattern in _PROHIBITED_PATTERNS:
        if pattern.search(text):
            hits.append(pattern.pattern)
    return hits


def safe_scrub(text: str | None, context: str = "") -> str | None:
    """Scrub + log warning if prohibited patterns were detected.

    Use this at every boundary where AI-generated or engine-generated text
    reaches the user (SignalCache write, API response, push notification body).
    """
    prohibited = detect_prohibited(text)
    if prohibited:
        logger.warning(
            "Legal filter: prohibited patterns %s detected (context=%s)",
            prohibited,
            context or "unknown",
        )
    return scrub_text(text)


def scrub_signal(data: Any) -> Any:
    """Deep-scrub a signal dict before caching.

    Walks known free-text fields in a SignalCache payload and scrubs each.
    Unknown fields pass through untouched (score/price/ticker stay as-is).
    Safe for arbitrary dict shape — no-op on non-dict inputs.
    """
    if not isinstance(data, dict):
        return data
    for field in _SCRUB_FIELDS:
        if field in data and isinstance(data[field], str):
            original = data[field]
            scrubbed = safe_scrub(original, context=f"signal.{field}")
            if scrubbed != original:
                data[field] = scrubbed
    # Nested: some engines put free-text inside a sub-dict
    for key in ("commentary_block", "ai", "ai_commentary"):
        nested = data.get(key)
        if isinstance(nested, dict):
            scrub_signal(nested)
    return data


__all__ = [
    "scrub_text",
    "safe_scrub",
    "scrub_signal",
    "detect_prohibited",
]
