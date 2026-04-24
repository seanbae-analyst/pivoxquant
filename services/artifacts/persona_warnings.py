"""Persona-aware warning copy for artifact reports.

Upgrades generic "risk exists" language to observational, persona-specific
language that references group statistics. Example:

    Before: "이 신호는 손실 가능성이 있습니다."
    After:  "해당 패턴 진입 이후 30 일 수익률은 Speculator 그룹 내에서
             중앙값 -5.2% 로 관찰되는 구간입니다."

Contract
--------
``generate_warning(persona, signal_type, stats=None) -> str``

Legal framing
-------------
Every string is observational. Forbidden terms (BUY/SELL/HOLD/추천/조언)
are scrubbed at import time. Stat injection uses neutral numerical
phrasing ("중앙값", "사분위 범위", "관찰 구간") — never directive.

Stat source
-----------
Group statistics are pulled from
:mod:`services.profile.persona_analytics` where available, or fall back
to hand-tuned catalogue defaults derived from the backtester (see
``backtester.py``). A missing stats mapping does *not* fail — the
template falls back to the qualitative version of the same warning.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Final, Mapping

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
# Signal taxonomy
# ─────────────────────────────────────────────────────────────────────
#
# The signal_type enum is intentionally small. Expanding it is a
# deliberate product decision — do not add ad-hoc types at call sites.

SIGNAL_TYPES: Final[frozenset[str]] = frozenset({
    "momentum_entry",      # recent N-day strong move, potential mean reversion
    "low_multiple",        # low P/E or P/B — potential value trap
    "high_dividend",       # yield > 2× peer median — potential dividend trap
    "earnings_surprise",   # post-earnings drift window
    "factor_crowding",     # factor exposure in crowded regime
    "consecutive_losses",  # loss streak — tilt risk
    "concentration",       # single-position weight above threshold
    "regime_transition",   # volatility regime flip
})


@dataclass(frozen=True)
class _WarningTemplate:
    """Persona + signal → warning rendering hints.

    ``qualitative`` is the pure text fallback used when no stats are
    supplied. ``with_stats`` is a str.format() template whose named
    placeholders are filled from the stats dict — all placeholders are
    numeric and receive observational phrasing at format time.
    """

    qualitative: str
    with_stats: str | None = None


# ─────────────────────────────────────────────────────────────────────
# Templates — indexed by (persona, signal_type)
# ─────────────────────────────────────────────────────────────────────
#
# Design notes:
#   • Every template ends with "관찰 구간" / "관찰 사례" / similar
#     observational coda. No "권유" / "판단하십시오".
#   • Stat templates carry 1–3 numeric placeholders:
#        {median_return_30d} / {p25} / {p75} / {win_rate}
#   • Unused combinations fall back to a persona-neutral generic — see
#     :func:`_GENERIC` below.

_TEMPLATES: Final[dict[tuple[str, str], _WarningTemplate]] = {
    # ── momentum_entry ────────────────────────────────────────────
    ("growth", "momentum_entry"): _WarningTemplate(
        qualitative=(
            "최근 강한 상승 구간 진입은 Growth 그룹 내에서 이후 30 일 "
            "평균 회귀 관찰 사례와 상관이 보고되는 구간입니다."
        ),
        with_stats=(
            "이 신호 패턴 진입 이후 30 일 수익률은 Growth 그룹 내에서 "
            "중앙값 {median_return_30d:+.1f}% 로 관찰되며, 25–75 분위 범위는 "
            "{p25:+.1f}% ~ {p75:+.1f}% 로 기록됩니다."
        ),
    ),
    ("speculator", "momentum_entry"): _WarningTemplate(
        qualitative=(
            "단기 급등 직후 진입은 Speculator 그룹 내에서 이후 5 거래일 "
            "NEGATIVE 방향 편향 관찰 구간으로 기록됩니다."
        ),
        with_stats=(
            "최근 5 거래일 +20% 이상 상승 후 진입 패턴의 이후 30 일 "
            "수익률은 Speculator 그룹 내 중앙값 {median_return_30d:+.1f}% 로 "
            "관찰되며, 승률(수익률 0% 초과 비율)은 {win_rate:.0%} 로 기록됩니다."
        ),
    ),
    ("daytrader", "momentum_entry"): _WarningTemplate(
        qualitative=(
            "intraday 고변동 구간 진입은 Daytrader 그룹 내에서 거래비용 "
            "잠식 관찰 사례와 상관이 보고됩니다."
        ),
        with_stats=(
            "VWAP 편차 1σ 초과 구간 진입 후 세션 종료 시점 수익률은 "
            "Daytrader 그룹 내 중앙값 {median_return_30d:+.2f}% 로 "
            "관찰됩니다 (거래비용 차감 후)."
        ),
    ),

    # ── low_multiple (value trap) ──────────────────────────────────
    ("value", "low_multiple"): _WarningTemplate(
        qualitative=(
            "낮은 멀티플 진입은 Value 그룹 내에서 value trap 관찰 사례와 "
            "구분이 필요한 구간으로 기록됩니다."
        ),
        with_stats=(
            "P/B 하위 10% 이탈 구간 진입 후 12 개월 수익률은 Value 그룹 내 "
            "중앙값 {median_return_30d:+.1f}% 이며, 해당 중 FCF 악화 동반 "
            "case 는 하위 사분위 {p25:+.1f}% 로 관찰됩니다."
        ),
    ),

    # ── high_dividend (dividend trap) ─────────────────────────────
    ("income", "high_dividend"): _WarningTemplate(
        qualitative=(
            "동종 대비 2 배 이상의 배당 수익률 구간은 Income 그룹 내에서 "
            "dividend trap 관찰 사례와 중첩되는 구간으로 기록됩니다."
        ),
        with_stats=(
            "Peer 배당 수익률 2× 초과 구간 진입 후 12 개월 총수익률은 "
            "Income 그룹 내 중앙값 {median_return_30d:+.1f}% 로 관찰되며, "
            "배당 삭감 발생 비율은 {win_rate:.0%} 로 기록됩니다."
        ),
    ),

    # ── factor_crowding (quant) ───────────────────────────────────
    ("quant", "factor_crowding"): _WarningTemplate(
        qualitative=(
            "crowded factor regime 에서의 진입은 Quant 그룹 내에서 "
            "평균 회귀 가속 관찰 사례와 상관이 보고됩니다."
        ),
        with_stats=(
            "Crowding percentile 상위 10% 구간에서 factor 진입 후 90 일 IR "
            "은 Quant 그룹 내 중앙값 {median_return_30d:+.2f} 로 관찰됩니다."
        ),
    ),

    # ── consecutive_losses (daytrader) ────────────────────────────
    ("daytrader", "consecutive_losses"): _WarningTemplate(
        qualitative=(
            "2 회 이상 연속 손실 구간에서 원복 시도는 Daytrader 그룹 내 "
            "일간 손실 한도 초과 관찰 사례와 상관이 보고됩니다."
        ),
        with_stats=(
            "3 회 연속 손실 이후 세션 내 누적 손실은 Daytrader 그룹 내 "
            "중앙값 {median_return_30d:+.1f}% (사이즈 축소 미적용 case) 로 "
            "관찰됩니다."
        ),
    ),

    # ── concentration (beginner / balanced) ───────────────────────
    ("beginner", "concentration"): _WarningTemplate(
        qualitative=(
            "단일 종목 20% 초과 구간은 Beginner 그룹 내에서 drawdown 민감도 "
            "관찰이 두드러지는 구간으로 기록됩니다."
        ),
        with_stats=(
            "단일 종목 20% 초과 구간의 월간 최대 낙폭은 Beginner 그룹 내 "
            "중앙값 {median_return_30d:+.1f}% 로 관찰됩니다."
        ),
    ),
    ("balanced", "concentration"): _WarningTemplate(
        qualitative=(
            "섹터 tilt 가 목표 ±5%p 임계치를 이탈하는 구간은 Balanced 그룹 "
            "내에서 Sharpe 저하 관찰 사례와 상관이 보고됩니다."
        ),
        with_stats=(
            "섹터 tilt ±5%p 초과 구간의 90 일 Sharpe 변화는 Balanced 그룹 "
            "내 중앙값 {median_return_30d:+.2f} 로 관찰됩니다."
        ),
    ),

    # ── regime_transition ────────────────────────────────────────
    ("quant", "regime_transition"): _WarningTemplate(
        qualitative=(
            "volatility regime 전환 구간은 Quant 그룹 내에서 factor 성과 "
            "역전 관찰 사례와 상관이 보고됩니다."
        ),
        with_stats=(
            "Regime 전환 후 30 일 factor 성과는 Quant 그룹 내 "
            "중앙값 {median_return_30d:+.1f}% (이전 regime 대비 변화) 로 "
            "관찰됩니다."
        ),
    ),
    ("speculator", "regime_transition"): _WarningTemplate(
        qualitative=(
            "VIX regime Elevated 진입 구간은 Speculator 그룹 내에서 "
            "IV crush 관찰 사례의 선행 구간으로 기록됩니다."
        ),
    ),
}


_GENERIC: Final[_WarningTemplate] = _WarningTemplate(
    qualitative=(
        "해당 신호는 포트폴리오 관찰 대상이며, 사전 설정된 규칙과의 "
        "정합성 점검이 권장되는 구간으로 기록됩니다."
    ),
)


# ─────────────────────────────────────────────────────────────────────
# Legal scrub (defense-in-depth — primary filter is legal_filter.py)
# ─────────────────────────────────────────────────────────────────────

# Backwards-compat alias. Tests reference ``_FORBIDDEN_TERMS`` as a
# module attribute; we keep the symbol but pull from the canonical set
# in :mod:`services.legal.forbidden_terms` so the lists cannot diverge
# again. Sorted so the tuple order is deterministic for any caller
# that snapshots it.
_FORBIDDEN_TERMS: Final[tuple[str, ...]] = tuple(sorted(FORBIDDEN_DIRECTIVE_TERMS))


def _assert_legal_safe(text: str, where: str) -> None:
    """Delegate to the canonical scrub; preserved for in-module callers."""
    _assert_legal_safe_canonical(text, where)


# Templates flagged at import time. Failed templates are removed from
# :data:`_TEMPLATES_SAFE` and :func:`generate_warning` falls back to
# the persona-neutral generic copy. The runtime ``_assert_legal_safe``
# call on rendered output (for the with-stats path) is unchanged so
# stat injection cannot smuggle a forbidden term back in.
_TEMPLATES_SAFE: dict[tuple[str, str], _WarningTemplate] = {}


def _audit_all() -> None:
    """Scrub every template at import time. Fail-safe (does not raise).

    Each violation is logged at ``CRITICAL`` and the offending template
    is dropped from :data:`_TEMPLATES_SAFE` — :func:`generate_warning`
    will then fall back to the generic copy for that ``(persona,
    signal)`` combination. The previous behaviour (raise at import)
    blocked the entire artifact pipeline on a single bad string; the
    fail-safe path keeps the rest of the catalogue available while ops
    fixes the regression.
    """
    for key, tpl in _TEMPLATES.items():
        persona, sig = key
        bad = False
        try:
            _assert_legal_safe(tpl.qualitative, f"{persona}/{sig}.qualitative")
        except ValueError as exc:
            logger.critical(
                "persona_warnings template tainted at %s/%s.qualitative: %s",
                persona, sig, exc,
            )
            bad = True
        if tpl.with_stats is not None:
            try:
                _assert_legal_safe(tpl.with_stats, f"{persona}/{sig}.with_stats")
            except ValueError as exc:
                logger.critical(
                    "persona_warnings template tainted at %s/%s.with_stats: %s",
                    persona, sig, exc,
                )
                bad = True
        if not bad:
            _TEMPLATES_SAFE[key] = tpl
    try:
        _assert_legal_safe(_GENERIC.qualitative, "GENERIC.qualitative")
    except ValueError as exc:  # pragma: no cover — generic must always be clean
        # Generic is the universal fallback; if it's tainted there is
        # nowhere left to fall back to. Hard fail.
        raise ValueError(
            f"persona_warnings generic copy tainted: {exc}"
        ) from exc


_audit_all()


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

def generate_warning(
    persona: str,
    signal_type: str,
    stats: Mapping[str, Any] | None = None,
) -> str:
    """Return the persona-tailored warning string.

    Parameters
    ----------
    persona : str
        One of the 8 canonical persona codes. Unknown → ``balanced``
        (then falls back to the generic template if no Balanced entry
        matches).
    signal_type : str
        Must be in :data:`SIGNAL_TYPES`. Unknown types return the
        generic template (safe).
    stats : Mapping[str, Any] | None
        Numerical stat payload, e.g.::

            {"median_return_30d": -5.2, "p25": -12.0, "p75": 1.3,
             "win_rate": 0.38}

        If ``None`` or missing any required placeholder, the qualitative
        template is used instead.

    Returns
    -------
    str
        Ready-to-embed sentence. Never empty.
    """
    code = persona if persona in VALID_PERSONAS else DEFAULT_PERSONA
    if signal_type not in SIGNAL_TYPES:
        return _GENERIC.qualitative

    # Pull from the audited subset; tainted templates are absent and
    # collapse to the persona-neutral generic copy.
    tpl = _TEMPLATES_SAFE.get((code, signal_type))
    if tpl is None:
        return _GENERIC.qualitative

    if stats and tpl.with_stats:
        try:
            rendered = tpl.with_stats.format(**stats)
            # Paranoia: re-scrub the *rendered* string. A bad stat key
            # cannot introduce a forbidden word, but a bad stat value
            # (string sneaking past the type hint) could — so we check.
            _assert_legal_safe(rendered, f"rendered/{code}/{signal_type}")
            return rendered
        except (KeyError, IndexError, ValueError):
            # Missing placeholder or invalid value → graceful fallback.
            return tpl.qualitative

    return tpl.qualitative


def available_signal_types() -> frozenset[str]:
    """Return the enum of supported signal types."""
    return SIGNAL_TYPES


__all__ = [
    "SIGNAL_TYPES",
    "generate_warning",
    "available_signal_types",
]
