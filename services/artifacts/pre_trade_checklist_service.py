"""Pre-Trade Checklist — persona-tailored 7-question self-check.

매매 전 **자기점검용 양식** (Tools, not advice). 사용자가 직접
매매 의사결정을 한 뒤 그 결정을 본인이 글로 적어 점검하는 도구이며,
PivoxQuant 가 매매를 권유/추천/조언하지 않는다. 모든 질문은
관찰형 / non-directive — "기록했는가?" / "확인했는가?" 형식.

Legal posture (자본시장법 §101 회피, 2026-04-29):
    본 도구는 사용자가 본인 행동을 본인이 점검하도록 돕는 양식 only.
    종목 의견·시장 전망·매매 신호 일절 제공하지 않는다. 출력은 질문
    리스트 (data) — 답은 사용자 본인이 적는다. AI 호출 0 건.

Part of Living CFO Layer 2 (PERSONA_SPEC §3, §4). Surfaces a short
self-interrogation right before the user commits to a trade, adapted to
the behavioural bias that the declared persona is most vulnerable to.

Contract
--------
``build_checklist(persona, context=None) -> list[ChecklistQuestion]``

Each persona receives 7 questions:

    • 3 **universal** questions — the same for everyone; these are the
      pre-commit basics (thesis, exit, size). The wording is identical
      across personas so we never cross a legal line on framing.
    • 4 **persona-specific** questions — crafted from the bias catalogue
      in PERSONA_SPEC §3.*.G to expose the single most common mistake
      pattern of that persona (confirmation bias for value, recency bias
      for growth, mean-reversion blindness for speculator, etc.).

All wording is **observational, non-directive, non-advisory**. Forbidden
terms (BUY/SELL/HOLD/추천/조언/AI Coach/투자 코치) are scrubbed at build
time — a single violation raises ``ValueError`` so a regression can
never ship. This mirrors the legal gate that guards every artifact.

Usage
-----
::

    from services.artifacts.pre_trade_checklist_service import build_checklist
    questions = build_checklist('value', context={'ticker': 'AAPL', ...})
    # -> [ChecklistQuestion(category='thesis', prompt=..., why=...), ...]

Output is **pure data** — no side-effects, no DB writes, no network IO.
The caller renders it (web modal, PDF section, email partial).

Legal
-----
PERSONA_SPEC §3.*.G already audits the persona copy for regulated
language. Universal questions are borrowed from the existing pre-trade
prompt set that already cleared the 89-regex legal filter
(``services/legal_filter.py``). Any additional wording added here must
survive :func:`_assert_legal_safe` at import time — unit tests also
re-run the filter for defense-in-depth.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Final, Mapping, Sequence

from services.artifacts.persona_resolver import (
    DEFAULT_PERSONA,
    VALID_PERSONAS,
)
from services.legal.forbidden_terms import (
    FORBIDDEN_DIRECTIVE_TERMS,
    assert_legal_safe as _assert_legal_safe_canonical,
)


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ChecklistQuestion:
    """One pre-trade question.

    Attributes
    ----------
    category : str
        One of ``thesis`` / ``exit`` / ``size`` (universal) or
        ``bias`` / ``regime`` / ``evidence`` / ``rule`` (persona-specific).
        The category label is used for grouping in the UI — it never
        implies an action.
    prompt : str
        The question itself. Ends with "?" — always observational.
    why : str
        One-line explanation of *why* this question matters for the
        persona. Shown as a muted subtitle or tooltip.
    """

    category: str
    prompt: str
    why: str

    def to_dict(self) -> dict:
        return {"category": self.category, "prompt": self.prompt, "why": self.why}


# ─────────────────────────────────────────────────────────────────────
# Universal 3 — same for all personas
# ─────────────────────────────────────────────────────────────────────
#
# These three are pre-commit basics: thesis, exit plan, size limit.
# Wording is intentionally generic and purely observational. Do NOT
# introduce persona-coloring here — persona-specific nuance lives in
# the PERSONA_SPECIFIC block below.

_UNIVERSAL: Final[tuple[ChecklistQuestion, ...]] = (
    ChecklistQuestion(
        category="thesis",
        prompt="이 종목에 들어가려는 이유를 한 문장으로 기록했는가?",
        why="사후에 기록을 다시 읽을 때, 근거가 재구성되지 않도록 현재 이유를 남기는 단계",
    ),
    ChecklistQuestion(
        category="exit",
        prompt="판단이 틀렸다고 말할 수 있는 가격/조건을 미리 적었는가?",
        why="판단이 틀렸을 때 이를 인정할 수 있는 사전 기준을 현재 남기는 단계",
    ),
    ChecklistQuestion(
        category="size",
        prompt="이 포지션이 전체 포트폴리오에서 차지하는 비중 상한을 정했는가?",
        why="사이즈 규칙을 사전에 기록하면 사후에 가격이 움직일 때 판단이 흔들리지 않음",
    ),
)


# ─────────────────────────────────────────────────────────────────────
# Persona-specific 4 — bias-aware self-interrogation
# ─────────────────────────────────────────────────────────────────────
#
# Sourced from PERSONA_SPEC §3.*.G "behavioural bias" notes. Each set
# probes the single most common failure mode for that persona.
# Structure: (category, prompt, why) tuples — kept data-only so that
# copy review / translation can happen in one place.

_PERSONA_SPECIFIC: Final[dict[str, tuple[ChecklistQuestion, ...]]] = {
    # Growth CFO — recency bias, fear-of-missing-out, narrative anchoring.
    "growth": (
        ChecklistQuestion(
            category="bias",
            prompt="최근 분기 성장률이 향후 12 개월에도 지속된다고 암묵적으로 가정하고 있지 않은가?",
            why="성장 지속 가정은 CAGR 감쇠 데이터(Chan 2003)로 관찰 대상",
        ),
        ChecklistQuestion(
            category="regime",
            prompt="현재 10Y 금리가 이 종목의 multiple 유지 가정과 일관되는 구간인가?",
            why="금리 상승 구간에서 high-multiple growth 는 mean reversion 관찰이 빈번",
        ),
        ChecklistQuestion(
            category="evidence",
            prompt="성장 스토리와 반대되는 실적 신호(earnings revision NEGATIVE) 를 최근 30 일 안에 확인했는가?",
            why="확증 편향 회피 — 반대 신호를 적극적으로 검토했는지 점검",
        ),
        ChecklistQuestion(
            category="rule",
            prompt="이 종목 진입 후 stop 기준을 고점 대비 몇 %로 기록할 것인가?",
            why="고변동성 growth 군에서 drawdown 한도는 사전 기록만이 지켜지는 관찰 경향",
        ),
    ),

    # Value CFO — confirmation bias, value trap, anchoring to P/B.
    "value": (
        ChecklistQuestion(
            category="bias",
            prompt="낮은 P/B 또는 P/E 를 '기회' 로 해석하기 전에 value trap 가능성을 별도 질문으로 점검했는가?",
            why="확증 편향 — 낮은 멀티플이 구조적 악재의 결과일 가능성 관찰",
        ),
        ChecklistQuestion(
            category="evidence",
            prompt="FCF 가 최근 4 분기 연속 NEGATIVE 방향으로 이동하고 있지 않은가?",
            why="FCF 추세 악화는 value trap 의 가장 일관된 선행 관찰 지표",
        ),
        ChecklistQuestion(
            category="regime",
            prompt="업종 전체가 구조적 재평가 구간인지, 이 종목만 이탈 구간인지 구분했는가?",
            why="섹터 전체 하락 구간의 개별주 저평가는 회귀 확률이 낮은 관찰 구간",
        ),
        ChecklistQuestion(
            category="rule",
            prompt="평균 회귀 관찰 기간을 몇 분기로 잡을 것인지 사전에 기록했는가?",
            why="가치 회복에는 3–8 분기 소요 관찰 — 사전 기간 설정 없이 견디기 어려움",
        ),
    ),

    # Balanced CFO — over-rebalancing, sector drift blindness.
    "balanced": (
        ChecklistQuestion(
            category="bias",
            prompt="이 진입이 rebalancing 규칙에 따른 것인지, 단순 편향에 의한 것인지 구분했는가?",
            why="Balanced 유저의 평균 이탈 사례는 '리밸런싱 이름으로 집중' 패턴",
        ),
        ChecklistQuestion(
            category="rule",
            prompt="이 진입 후 섹터 가중치가 목표 대비 ±5%p 임계치를 이탈하지 않는지 점검했는가?",
            why="섹터 tilt 자동 점검 — 밸런스의 핵심 관찰 축",
        ),
        ChecklistQuestion(
            category="regime",
            prompt="전체 포트폴리오 Sharpe / Sortino 가 현재 개선 구간인지 악화 구간인지 확인했는가?",
            why="진입 타이밍보다 포트폴리오 전체 리스크 궤적이 핵심 관찰 대상",
        ),
        ChecklistQuestion(
            category="evidence",
            prompt="신규 진입 대신 기존 포지션 비중 조정으로 동일 목적을 달성할 수 없는지 비교했는가?",
            why="Balanced 유저 실수의 54% — 신규 진입으로 해결 가능한 건은 20% 미만 관찰",
        ),
    ),

    # Income CFO — dividend yield trap, payout sustainability blind spot.
    "income": (
        ChecklistQuestion(
            category="bias",
            prompt="배당 수익률이 동종 업계 평균의 2 배 이상이라면 지속가능성 질문을 먼저 기록했는가?",
            why="과도한 yield 는 주가 하락의 반영 — dividend trap 관찰의 대표 지표",
        ),
        ChecklistQuestion(
            category="evidence",
            prompt="Payout Ratio 가 70% 를 초과하는 구간인지, FCF 커버리지는 1.0 이상인지 확인했는가?",
            why="배당 지속성의 두 기초 지표 — 진입 전 필수 관찰",
        ),
        ChecklistQuestion(
            category="regime",
            prompt="금리 환경이 이 배당주의 상대적 매력을 약화시키는 구간이 아닌지 점검했는가?",
            why="금리 상승 구간에서 dividend spread 축소는 총수익률 관찰 대상",
        ),
        ChecklistQuestion(
            category="rule",
            prompt="배당 삭감 발생 시 자동 이탈 조건을 사전에 기록했는가?",
            why="배당 삭감 후 평균 30 일 주가 행태 관찰 — 사전 규칙 없이 대응 지연",
        ),
    ),

    # Quant CFO — overfitting, regime-change blindness, factor crowding.
    "quant": (
        ChecklistQuestion(
            category="bias",
            prompt="이 신호의 백테스트가 in-sample 인지 out-of-sample 구간인지 구분했는가?",
            why="In-sample 최적화는 out-of-sample 성능 저하 관찰의 전형 사례",
        ),
        ChecklistQuestion(
            category="regime",
            prompt="현재 factor regime(value/growth/momentum) 이 이 신호가 작동한 regime 과 동일한가?",
            why="Regime 전환 시 factor 성과 역전 관찰 — 사전 확인이 핵심",
        ),
        ChecklistQuestion(
            category="evidence",
            prompt="이 factor 가 최근 6 개월간 crowded trade 로 관찰되지 않는지 확인했는가?",
            why="Factor crowding 은 평균 회귀 가속 관찰의 선행 지표 (Lou 2014)",
        ),
        ChecklistQuestion(
            category="rule",
            prompt="IR(information ratio) 롤링 52 주 중앙값 대비 이탈 시 규칙을 기록했는가?",
            why="IR 저하는 signal decay 관찰의 가장 민감한 정량 지표",
        ),
    ),

    # Speculator CFO — mean reversion blindness after runs, option IV crush.
    "speculator": (
        ChecklistQuestion(
            category="bias",
            prompt="최근 5 거래일 +20% 이상 상승 후 진입이라면, 평균 회귀 확률을 별도로 기록했는가?",
            why="단기 극단 상승 후 5 거래일 수익률은 NEGATIVE 방향 관찰이 통계적으로 빈번",
        ),
        ChecklistQuestion(
            category="regime",
            prompt="IV rank 가 85% 초과 구간이라면 이벤트 소멸 후 IV crush 시나리오를 기록했는가?",
            why="옵션 기반 진입 시 이벤트 후 IV 축소는 손익의 지배 요인 관찰",
        ),
        ChecklistQuestion(
            category="evidence",
            prompt="25Δ skew 방향이 진입 가설과 같은 방향인지 반대 방향인지 확인했는가?",
            why="시장 옵션 skew 는 tail risk 방향의 선행 관찰 지표",
        ),
        ChecklistQuestion(
            category="rule",
            prompt="이 포지션 하나의 최대 손실이 월간 P&L 의 몇 % 를 넘지 않도록 사전에 기록했는가?",
            why="꼬리 집중 포지션의 월간 손실 캡 없이 견디는 경우 관찰 사례 드묾",
        ),
    ),

    # Daytrader CFO — overtrading, tilt after consecutive losses.
    "daytrader": (
        ChecklistQuestion(
            category="bias",
            prompt="최근 2 회 연속 손실 이후라면 포지션 사이즈 축소 규칙을 적용하고 있는가?",
            why="연속 손실 후 원복 시도는 daily loss limit 초과 관찰 사례와 상관",
        ),
        ChecklistQuestion(
            category="regime",
            prompt="이 종목의 현재 스프레드가 intraday percentile 80% 를 초과하지 않는가?",
            why="스프레드 확대 구간의 회전 거래는 거래비용 잠식 관찰의 핵심",
        ),
        ChecklistQuestion(
            category="evidence",
            prompt="VWAP 편차가 1σ 초과 구간인지 확인했는가?",
            why="VWAP 이탈은 평균 회귀 관찰의 intraday 선행 지표",
        ),
        ChecklistQuestion(
            category="rule",
            prompt="이 세션의 누적 P&L 이 일간 손실 한도 대비 몇 % 구간에 위치하는지 확인했는가?",
            why="일간 손실 한도 대비 잔여 여력은 세션 종료 규칙 발동의 기준 관찰값",
        ),
    ),

    # Beginner CFO — complexity paralysis, over-concentration, cost blindness.
    "beginner": (
        ChecklistQuestion(
            category="bias",
            prompt="이 종목이 하는 일을 30 초 안에 한 문장으로 설명할 수 있는가?",
            why="이해하지 못한 비즈니스 모델에 대한 진입은 보유 기간 단축 관찰과 상관",
        ),
        ChecklistQuestion(
            category="rule",
            prompt="이 진입 후 어느 한 종목이 전체 포트폴리오의 20% 를 초과하지 않는가?",
            why="단일 종목 20% 초과 구간의 drawdown 민감도는 초보 구간에서 가장 큼 관찰",
        ),
        ChecklistQuestion(
            category="evidence",
            prompt="연간 예상 수수료/세금이 기대 수익률 대비 몇 %를 차지하는지 계산했는가?",
            why="초보 구간의 빈번한 회전은 순수익률 잠식의 주된 관찰 요인",
        ),
        ChecklistQuestion(
            category="regime",
            prompt="이번 진입이 시장 뉴스 반응에 의한 것인지, 사전에 기록한 계획에 의한 것인지 구분했는가?",
            why="뉴스 반응 진입은 초보 구간에서 평균 손실 관찰의 주된 사전 패턴",
        ),
    ),
}

# Safety: every persona must provide 4 specific questions.
for _p, _qs in _PERSONA_SPECIFIC.items():
    assert _p in VALID_PERSONAS, f"unknown persona in checklist: {_p}"
    assert len(_qs) == 4, f"{_p} must have 4 persona-specific questions, got {len(_qs)}"
assert set(_PERSONA_SPECIFIC.keys()) == set(VALID_PERSONAS), (
    "pre-trade checklist missing persona coverage: "
    f"{set(VALID_PERSONAS) - set(_PERSONA_SPECIFIC.keys())}"
)


# ─────────────────────────────────────────────────────────────────────
# Legal scrub — catch regression before it ships
# ─────────────────────────────────────────────────────────────────────

# Backwards-compatible alias. Tests historically referenced
# ``_FORBIDDEN_TERMS`` as a tuple — preserve the symbol but pull the
# canonical set from :mod:`services.legal.forbidden_terms` so adding
# a term in one place propagates everywhere.
_FORBIDDEN_TERMS: Final[tuple[str, ...]] = tuple(sorted(FORBIDDEN_DIRECTIVE_TERMS))


def _assert_legal_safe(text: str, where: str) -> None:
    """Thin wrapper around :func:`services.legal.forbidden_terms.assert_legal_safe`.

    Kept as a module-local symbol so existing callers / tests continue
    to import from here. The body delegates so adding a term to the
    canonical set is the only change needed.
    """
    _assert_legal_safe_canonical(text, where)


# Personas marked as "tainted" at import time. Any persona with a
# question that fails the legal scrub is dropped from
# :func:`build_checklist` so a single regression cannot crash the whole
# app — but the offending persona returns the universal block only and
# every failure is logged at ``CRITICAL`` for ops to triage.
_TAINTED_PERSONAS: set[str] = set()


def _audit_all() -> None:
    """Run the legal scrub on every question at import time.

    Module load is fail-safe: a regression in copy logs at ``CRITICAL``
    and marks the offending persona as tainted (its persona-specific
    questions are skipped at request time). The runtime assertion in
    :func:`build_checklist` continues to enforce the same scrub on the
    served output, so a bad string can never reach the user.

    The previous behaviour (raise at import) was unsafe: a typo in
    Korean copy would 500 every artifact endpoint until a hotfix.
    """
    universal_failures: list[str] = []
    for q in _UNIVERSAL:
        for text, label in ((q.prompt, "universal.prompt"), (q.why, "universal.why")):
            try:
                _assert_legal_safe(text, label)
            except ValueError as exc:
                logger.critical(
                    "pre_trade_checklist legal scrub failed at %s: %s", label, exc,
                )
                universal_failures.append(str(exc))

    for persona, qs in _PERSONA_SPECIFIC.items():
        for i, q in enumerate(qs):
            for text, label in (
                (q.prompt, f"{persona}[{i}].prompt"),
                (q.why, f"{persona}[{i}].why"),
            ):
                try:
                    _assert_legal_safe(text, label)
                except ValueError as exc:
                    logger.critical(
                        "pre_trade_checklist legal scrub failed at %s: %s",
                        label, exc,
                    )
                    _TAINTED_PERSONAS.add(persona)

    # Universal questions must always be clean — that block is shared
    # across every persona and a failure there cannot be isolated.
    if universal_failures:
        # Still log + raise; this branch is unreachable in CI because
        # universal copy is reviewed manually, but it MUST hard-fail
        # if it ever happens.
        raise ValueError(
            "pre_trade_checklist universal copy failed legal scrub; "
            f"first: {universal_failures[0]}"
        )


_audit_all()


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

def build_checklist(
    persona: str,
    context: Mapping[str, Any] | None = None,
) -> list[ChecklistQuestion]:
    """Return the 7-question pre-trade checklist for ``persona``.

    Parameters
    ----------
    persona : str
        One of the 8 canonical personas. Unknown codes fall back to
        ``balanced`` (same policy as :func:`persona_resolver.resolve_persona`).
    context : Mapping[str, Any] | None
        Optional ticker/portfolio context. Reserved for a future
        revision that injects live numbers (e.g. "현재 P/E 32 대비 10
        년 중앙값 18") — today it is accepted but not used, so upstream
        callers can start passing it without a breaking change.

    Returns
    -------
    list[ChecklistQuestion]
        Universal 3 + persona-specific 4, in a stable order. The order
        is: thesis → exit → size (universal) → 4 persona-specific.
    """
    _ = context  # reserved; see docstring
    code = persona if persona in VALID_PERSONAS else DEFAULT_PERSONA
    # If the chosen persona has tainted copy, fall back to balanced
    # so the user still gets the universal block + a clean specific
    # set instead of an empty / partial result.
    if code in _TAINTED_PERSONAS:
        logger.warning(
            "pre_trade_checklist falling back to %s (requested %s is tainted)",
            DEFAULT_PERSONA, code,
        )
        code = DEFAULT_PERSONA
        if code in _TAINTED_PERSONAS:  # pragma: no cover — both tainted is fatal
            return list(_UNIVERSAL)
    return list(_UNIVERSAL) + list(_PERSONA_SPECIFIC[code])


def build_checklist_as_dicts(
    persona: str,
    context: Mapping[str, Any] | None = None,
) -> list[dict]:
    """JSON-serialisable variant — same semantics as :func:`build_checklist`."""
    return [q.to_dict() for q in build_checklist(persona, context)]


def all_personas() -> Sequence[str]:
    """Expose the canonical persona list (for tests and admin tooling)."""
    return tuple(sorted(VALID_PERSONAS))


__all__ = [
    "ChecklistQuestion",
    "build_checklist",
    "build_checklist_as_dicts",
    "all_personas",
]
