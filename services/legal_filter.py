"""Runtime scrubber for legally risky phrases in AI output & cached signals.

Purpose
-------
자본시장법 §6 미등록 투자자문업 + §101 불공정 영업행위 리스크 방어선.
Engine / AI / 서비스 코드에서 "매수 권고", "매도 권고" 같은 advisory 동사가
유저에게 노출되기 전에 이 모듈이 safe alternative 로 치환한다.

Pattern taxonomy
----------------
`_REPLACEMENTS`      : 정규식 매치 → surgical 치환 (42 패턴).
`_PROHIBITED_PATTERNS`: 치환으로 복구 불가한 구조적 위반 — 로그 경고만.

Integration points
------------------
- services/cache_service.py :: cache_ticker() — SignalCache write path.
- ai_service.py :: generator 메서드 return 직전 safe_scrub() 호출.
- routes/ai.py :: 모든 엔드포인트 응답 return 직전 safe_scrub() 호출.

Non-goals
---------
- engine.py / quant_models.py 는 **수정 없이** 출력 경계면에서만 치환.
- 완벽한 NLP 필터 아님 — 알려진 pattern 에 한해 정규식 치환.
- _compliance_filter (ai_service.py) 와 달리 hard-drop 이 아닌 surgical replacement.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── Safe replacements (regex → safe alternative) ──────────────────────────
# 순서 중요: 긴 구문 먼저 매칭 → 짧은 구문이 부분 치환되지 않도록.
_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    # ── Group 1: 복합 구문 (우선 처리) ────────────────────────────────────
    (re.compile(r"포지션\s*축소\s*또는\s*청산\s*고려"), "약세 신호 감지 (정보 제공)"),
    (re.compile(r"노출\s*축소\s*(권고|권장)"), "노출 지표 상승 관찰"),
    (re.compile(r"신규\s*매수\s*보류"), "신규 진입 관찰 구간"),
    (re.compile(r"현금\s*비중\s*확대\s*(권고|권장)"), "현금 비중 관찰 지표"),
    (re.compile(r"위험자산\s*비중\s*축소"), "위험자산 비중 모니터링"),
    (re.compile(r"부분\s*익절\s*/\s*손절\s*고려"), "TP/SL 레벨 관찰"),

    # ── Group 2: 권고 / 권장 / 추천 (단일 동사) ─────────────────────────
    (re.compile(r"매수\s*(권고|권장|추천)"), "정보 고지 (사전 설정 레벨 도달)"),
    (re.compile(r"매도\s*(권고|권장|추천)"), "정보 고지 (사전 설정 레벨 도달)"),
    (re.compile(r"손절\s*(권고|권장|추천)"), "정보 고지 (SL 레벨 도달)"),
    (re.compile(r"익절\s*(권고|권장|추천)"), "정보 고지 (TP 레벨 도달)"),
    (re.compile(r"추천\s*드립니다"), "정보 제공 (참고)"),
    (re.compile(r"추천\s*합니다"), "정보 제공 (참고)"),
    (re.compile(r"권유\s*드립니다"), "정보 제공 (참고)"),
    (re.compile(r"권유\s*합니다"), "정보 제공 (참고)"),
    (re.compile(r"조언\s*드립니다"), "정보 제공 (참고)"),

    # ── Group 3: 타이밍 / 목표가 / 수익률 예측 ──────────────────────────
    (re.compile(r"매수\s*타이밍"), "진입 레벨 관찰"),
    (re.compile(r"매도\s*타이밍"), "청산 레벨 관찰"),
    (re.compile(r"목표\s*가격"), "참고 지표"),
    (re.compile(r"목표가"), "참고 지표"),
    (re.compile(r"적정\s*가격"), "참고 지표"),
    (re.compile(r"적정가"), "참고 지표"),
    (re.compile(r"예상\s*수익률\s*[+\-]?\d+(\.\d+)?%"), "과거 기록 지표"),

    # ── Group 4: 전망 / 예측 (미래 단정) ─────────────────────────────────
    (re.compile(r"향후\s*전망"), "향후 관찰 구간"),
    (re.compile(r"시장\s*전망"), "시장 관찰 구간"),
    (re.compile(r"전망입니다"), "관찰됩니다"),
    (re.compile(r"예측됩니다"), "관찰 지표입니다"),
    (re.compile(r"예측\s*됩니다"), "관찰 지표입니다"),
    (re.compile(r"예상됩니다"), "관찰됩니다"),
    (re.compile(r"오를\s*것\s*(으로\s*보입니다|입니다|같습니다)"), "상승 지표가 관찰됩니다"),
    (re.compile(r"내릴\s*것\s*(으로\s*보입니다|입니다|같습니다)"), "하락 지표가 관찰됩니다"),

    # ── Group 5: 가치 판단 부사/형용사 (권유 뉘앙스) ────────────────────
    (re.compile(r"유리한"), "지표가 높은"),
    (re.compile(r"불리한"), "지표가 낮은"),
    (re.compile(r"유망한"), "관찰 대상인"),
    (re.compile(r"최적의"), "관찰된"),
    (re.compile(r"고평가"), "지표 변동 구간"),
    (re.compile(r"저평가"), "지표 변동 구간"),
    (re.compile(r"공격적\s*(투자|포지션|접근)"), "변동성 높은 \\1"),
    (re.compile(r"보수적\s*(투자|포지션|접근)"), "변동성 낮은 \\1"),
    (re.compile(r"베스트\s*종목"), "상위 지표 종목"),
    (re.compile(r"이기"), "benchmark 대비 기록하"),  # "이기다", "이겼다", "이겼습니다"의 어간

    # ── Group 6: 영문 — 동사형 / 명령형 ──────────────────────────────────
    (re.compile(r"\bBUY\s+signal\b", re.IGNORECASE), "POSITIVE indicator"),
    (re.compile(r"\bSELL\s+signal\b", re.IGNORECASE), "NEGATIVE indicator"),
    (re.compile(r"\brecommend(ation|ed|ing|s)?\b", re.IGNORECASE), "note"),
    (re.compile(r"\badvise(d|s|ing)?\b", re.IGNORECASE), "provide information"),
    (re.compile(r"\badvice\b", re.IGNORECASE), "information"),
    (re.compile(r"\bsuggest(ed|ing|s)?\b", re.IGNORECASE), "observe"),
    (re.compile(r"\btarget\s*price\b", re.IGNORECASE), "reference price"),
    (re.compile(r"\bfair\s*value\b", re.IGNORECASE), "reference value"),
    (re.compile(r"\bprice\s*target\b", re.IGNORECASE), "reference price"),

    # ── Group 7: 영문 — 시장 비교 / 전망 ────────────────────────────────
    (re.compile(r"\boutperform(ed|ing|s)?\b", re.IGNORECASE), "benchmark 대비 높은 기록"),
    (re.compile(r"\bunderperform(ed|ing|s)?\b", re.IGNORECASE), "benchmark 대비 낮은 기록"),
    (re.compile(r"\bbeat\s+the\s+market\b", re.IGNORECASE), "benchmark 대비 기록"),
    (re.compile(r"\bbeat\s+S&?P(?:\s*500)?\b", re.IGNORECASE), "S&P 500 benchmark 대비 기록"),
    (re.compile(r"\bbullish\b", re.IGNORECASE), "상승 관찰"),
    (re.compile(r"\bbearish\b", re.IGNORECASE), "하락 관찰"),
    (re.compile(r"\bpredict(ed|ing|s|ion)?\b", re.IGNORECASE), "observe"),
    (re.compile(r"\bforecast(ed|ing|s)?\b", re.IGNORECASE), "observation"),
    (re.compile(r"\bbest\s+opportunity\b", re.IGNORECASE), "highest indicator"),
    (re.compile(r"\bmost\s+attractive\b", re.IGNORECASE), "highest indicator"),
]

# ── Prohibited patterns (log only, 설계 오류 조기 발견용) ─────────────────
# 이 패턴이 나타나면 scrub 으로도 해결 안 됨 — 코드 단에서 제거되어야 함.
_PROHIBITED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"목표가\s*[\$₩]?\s*[\d,\.]+"),
    re.compile(r"예상\s*수익률\s*[+\-]?\d+(\.\d+)?%"),
    re.compile(r"적정가\s*[\$₩]?\s*[\d,\.]+"),
    re.compile(r"price\s*target[:\s]*\$?[\d,\.]+", re.IGNORECASE),
    re.compile(r"expected\s*return[:\s]*\+?\d+(\.\d+)?%", re.IGNORECASE),
    re.compile(r"fair\s*value[:\s]*\$?[\d,\.]+", re.IGNORECASE),
]

# ── Required disclaimer (AI 산출물 말미에 자동 첨부 대상 검사용) ─────────
_DISCLAIMER_KR = "본 내용은 정보 제공 목적이며 투자 권유가 아닙니다"
_DISCLAIMER_EN = "This is informational only and not investment advice"

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
    "trend",
    "trend_kr",
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


def ensure_disclaimer(text: str | None, lang: str = "kr") -> str | None:
    """Append the required disclaimer sentence if missing.

    Used at AI response boundary where the SYSTEM_PROMPT asks the model to
    add it but we can't trust every generation path to comply.
    """
    if not text or not isinstance(text, str):
        return text
    disclaimer = _DISCLAIMER_KR if lang == "kr" else _DISCLAIMER_EN
    if disclaimer in text:
        return text
    sep = "\n\n" if not text.endswith("\n") else ""
    return f"{text}{sep}{disclaimer}."


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


def scrub_response(data: Any) -> Any:
    """Deep-scrub an arbitrary JSON-shaped response dict.

    Walks every string leaf recursively. Used by routes/ai.py to enforce
    the legal boundary on all AI endpoint responses regardless of shape.
    """
    if isinstance(data, dict):
        for k, v in list(data.items()):
            if isinstance(v, str):
                data[k] = safe_scrub(v, context=f"response.{k}")
            elif isinstance(v, (dict, list)):
                data[k] = scrub_response(v)
        return data
    if isinstance(data, list):
        return [scrub_response(x) for x in data]
    return data


__all__ = [
    "scrub_text",
    "safe_scrub",
    "scrub_signal",
    "scrub_response",
    "ensure_disclaimer",
    "detect_prohibited",
]
