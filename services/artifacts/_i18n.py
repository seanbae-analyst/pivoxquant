"""Shared i18n helper for the 17 PDF artifact templates + email bodies.

Wave F (2026-05-28). Centralises:

  * ``resolve_locale(user_id|user|data)`` — resolves a row's locale from
    multiple input shapes without raising. Falls back to "ko".
  * ``STRINGS`` — nested dict of {locale: {namespace: {key: str}}}.
  * ``localize_ctx(ctx, locale)`` — injects ``locale`` + ``t`` (namespaced
    accessor) + ``_t`` (flat accessor) into a Jinja render context.

Design principles
-----------------
1. **Never raise.** Render must stay resilient — every helper degrades to
   Korean (the pre-Wave F status quo) when anything goes wrong.
2. **Bilingual disclaimer is template-side** (services/artifacts/templates/
   _disclaimer.html already ships both languages — see Q-S4). The i18n
   layer does NOT touch the disclaimer block; it only branches headers,
   intro copy, table column labels, and CTA copy.
3. **§101 compliance.** English strings never use directive verbs
   (Buy/Sell/Long/Short/Recommend). Mirrors the Korean observation tone.
   Verified by ``tests/test_i18n_artifact_compliance.py`` (Wave F).
4. **Persona-agnostic.** Persona inflection (cautious/balanced/etc.)
   layers on TOP of locale via existing ``_with_persona`` paths.

Template usage
--------------
The render context exposes both shapes::

    {{ t('weekly_memo', 'title') }}         # callable, two-arg
    {{ _t.weekly_memo.title }}              # attribute-style (Jinja-friendly)

Unknown keys return the key itself (safe fallback, no crash); callers
should NOT special-case missing strings.
"""
from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)

# ── Supported locales ───────────────────────────────────────────────────────
SUPPORTED_LOCALES = ("ko", "en")
DEFAULT_LOCALE = "ko"


# ── String tables ───────────────────────────────────────────────────────────
# Top-level keys = namespaces (one per artifact template + shared "common").
# Every namespace must define the same keys in both languages — see
# tests/test_i18n_artifact_compliance.py for the structural-symmetry assert.
STRINGS: dict[str, dict[str, dict[str, str]]] = {
    "ko": {
        "common": {
            "as_of": "기준일",
            "generated_by": "PivoxQuant이 생성한 리포트",
            "page": "쪽",
            "of": "/",
            "ai_label": "AI 생성 콘텐츠 (참고용)",
            "informational": "정보 제공 목적",
            "no_data": "데이터 부족",
            "observation": "관찰",
            "summary": "요약",
            "details": "상세",
            "ticker": "종목",
            "weight": "비중",
            "return": "수익률",
            "value": "평가액",
            "change": "변동",
        },
        "weekly_memo": {
            "title": "주간 투자 메모",
            "eyebrow": "주간 리뷰",
            "subtitle": "지난 주 포트폴리오 관찰",
            "section_performance": "성과 요약",
            "section_observations": "이번 주 관찰",
            "section_trajectory": "추세",
            "section_next_week": "다음 주 관찰 포인트",
            "section_memo_to_self": "자기 메모",
            "benchmark_vs": "S&P 500 대비",
            "portfolio_value": "포트폴리오 평가액",
            "weekly_return": "주간 수익률",
            "ytd_return": "연초 대비 수익률",
        },
        "brag_card": {
            "title": "월간 하이라이트",
            "eyebrow": "월간 카드",
            "month_return": "월간 수익률",
            "ytd_return": "연초 대비",
            "top_winner": "관찰 1위",
            "top_loser": "관찰 최하위",
            "share_caption": "PivoxQuant에서 생성한 포트폴리오 요약",
        },
        "earnings_prebrief": {
            "title": "실적 사전 브리핑",
            "eyebrow": "Earnings Pre-Brief",
            "subtitle": "다가오는 실적 발표 전 관찰 메모",
            "section_consensus": "컨센서스",
            "section_history": "과거 Beat/Miss",
            "section_iv": "옵션 IV / 예상 변동폭",
            "section_peers": "동종업계",
            "section_observations": "관찰 포인트",
            "next_earnings": "다음 실적 발표일",
        },
        "kpi_dashboard": {
            "title": "AI Suite KPI 대시보드",
            "eyebrow": "월간 KPI",
            "subtitle": "8개 AI 모델 성능 관찰",
            "section_models": "모델별 성능",
            "section_aggregate": "통합 지표",
            "win_rate": "일치율",
            "sharpe": "Sharpe",
            "max_dd": "최대 낙폭",
        },
        "risk_board": {
            "title": "리스크 보드",
            "eyebrow": "주간 리스크",
            "section_var": "Value at Risk",
            "section_dd": "낙폭 분석",
            "section_corr": "상관관계",
            "section_stress": "스트레스 시나리오",
            "section_layers": "7-Layer 점검",
        },
        "burn_rate": {
            "title": "현금 소진 분석",
            "eyebrow": "Burn Rate",
            "section_runway": "Runway",
            "section_ocf": "영업현금흐름",
            "section_history": "분기별 추세",
        },
        "credit_rating": {
            "title": "신용 등급 요약",
            "eyebrow": "Credit",
            "section_agencies": "신용평가사 등급",
            "section_altman": "Altman Z-Score",
            "section_ratios": "재무비율",
        },
        "capital_allocation": {
            "title": "자본 배분 시뮬레이션",
            "eyebrow": "Allocation",
            "section_current": "현재 배분",
            "section_scenarios": "What-if 시나리오",
            "section_observations": "관찰",
        },
        "dividend_income": {
            "title": "배당 수익 리포트",
            "eyebrow": "Dividend",
            "section_history": "수령 이력",
            "section_yield": "배당 수익률",
            "section_calendar": "배당 캘린더",
            "ex_date": "배당락일",
            "pay_date": "지급일",
        },
        "insider_mirror": {
            "title": "내부자 거래 미러",
            "eyebrow": "Form 4",
            "section_recent": "최근 신고",
            "section_pattern": "패턴 관찰",
        },
        "portfolio_segment": {
            "title": "포트폴리오 세그먼트",
            "eyebrow": "Segment",
            "section_sector": "섹터 분석",
            "section_geo": "지역 분포",
            "section_factor": "팩터 노출",
        },
        "monthly_finance": {
            "title": "월간 재무 리포트",
            "eyebrow": "월간 재무",
            "section_pnl": "월별 손익",
            "section_dividend": "배당 수령",
            "section_flows": "자본 흐름",
        },
        "self_audit": {
            "title": "거래 자기 감사",
            "eyebrow": "Self-Audit",
            "section_trades": "거래 기록",
            "section_winrate": "일치율 / 손익비",
            "section_observations": "관찰",
        },
        "year_end_letter": {
            "title": "연간 투자 리뷰",
            "eyebrow": "Year-End",
            "section_performance": "연간 성과",
            "section_monthly": "월별 추이",
            "section_reflection": "회고",
        },
        "dd_checklist": {
            "title": "Due Diligence 체크리스트",
            "eyebrow": "DD",
            "section_filings": "공시 검토",
            "section_ratios": "재무비율",
            "section_redflags": "Red Flag",
        },
        "quarterly_self_report": {
            "title": "분기 자기 리포트",
            "eyebrow": "Quarterly",
            "section_pnl": "분기 손익",
            "section_decisions": "의사결정 로그",
            "section_reflection": "회고",
        },
    },
    "en": {
        "common": {
            "as_of": "As of",
            "generated_by": "Generated by PivoxQuant",
            "page": "Page",
            "of": "of",
            "ai_label": "AI-generated content (informational)",
            "informational": "Informational use only",
            "no_data": "No data",
            "observation": "Observation",
            "summary": "Summary",
            "details": "Details",
            "ticker": "Ticker",
            "weight": "Weight",
            "return": "Return",
            "value": "Value",
            "change": "Change",
        },
        "weekly_memo": {
            "title": "Weekly Investor Memo",
            "eyebrow": "Weekly Review",
            "subtitle": "Observations from the past week",
            "section_performance": "Performance Summary",
            "section_observations": "This Week's Observations",
            "section_trajectory": "Trajectory",
            "section_next_week": "Next Week — Points to Watch",
            "section_memo_to_self": "Memo to Self",
            "benchmark_vs": "vs. S&P 500",
            "portfolio_value": "Portfolio Value",
            "weekly_return": "Weekly Return",
            "ytd_return": "Year-to-Date Return",
        },
        "brag_card": {
            "title": "Monthly Highlight",
            "eyebrow": "Monthly Card",
            "month_return": "Monthly Return",
            "ytd_return": "Year-to-Date",
            "top_winner": "Top Observed",
            "top_loser": "Bottom Observed",
            "share_caption": "Portfolio summary generated by PivoxQuant",
        },
        "earnings_prebrief": {
            "title": "Earnings Pre-Brief",
            "eyebrow": "Earnings Pre-Brief",
            "subtitle": "Observations ahead of the next earnings release",
            "section_consensus": "Consensus",
            "section_history": "Historical Beat / Miss",
            "section_iv": "Option IV / Implied Move",
            "section_peers": "Peers",
            "section_observations": "Points of Observation",
            "next_earnings": "Next Earnings Date",
        },
        "kpi_dashboard": {
            "title": "AI Suite KPI Dashboard",
            "eyebrow": "Monthly KPI",
            "subtitle": "Eight-model performance overview",
            "section_models": "Per-Model Performance",
            "section_aggregate": "Aggregate Metrics",
            "win_rate": "Consistency",
            "sharpe": "Sharpe",
            "max_dd": "Max Drawdown",
        },
        "risk_board": {
            "title": "Risk Board",
            "eyebrow": "Weekly Risk",
            "section_var": "Value at Risk",
            "section_dd": "Drawdown Analysis",
            "section_corr": "Correlation",
            "section_stress": "Stress Scenarios",
            "section_layers": "7-Layer Check",
        },
        "burn_rate": {
            "title": "Cash Burn Analysis",
            "eyebrow": "Burn Rate",
            "section_runway": "Runway",
            "section_ocf": "Operating Cash Flow",
            "section_history": "Quarterly Trend",
        },
        "credit_rating": {
            "title": "Credit Rating Summary",
            "eyebrow": "Credit",
            "section_agencies": "Agency Ratings",
            "section_altman": "Altman Z-Score",
            "section_ratios": "Financial Ratios",
        },
        "capital_allocation": {
            "title": "Capital Allocation Simulation",
            "eyebrow": "Allocation",
            "section_current": "Current Allocation",
            "section_scenarios": "What-If Scenarios",
            "section_observations": "Observations",
        },
        "dividend_income": {
            "title": "Dividend Income Report",
            "eyebrow": "Dividend",
            "section_history": "Receipt History",
            "section_yield": "Yield",
            "section_calendar": "Dividend Calendar",
            "ex_date": "Ex-Dividend Date",
            "pay_date": "Pay Date",
        },
        "insider_mirror": {
            "title": "Insider Trade Mirror",
            "eyebrow": "Form 4",
            "section_recent": "Recent Filings",
            "section_pattern": "Pattern Observations",
        },
        "portfolio_segment": {
            "title": "Portfolio Segments",
            "eyebrow": "Segment",
            "section_sector": "Sector Breakdown",
            "section_geo": "Geographic Mix",
            "section_factor": "Factor Exposure",
        },
        "monthly_finance": {
            "title": "Monthly Financial Report",
            "eyebrow": "Monthly Finance",
            "section_pnl": "Monthly P&L",
            "section_dividend": "Dividends Received",
            "section_flows": "Capital Flows",
        },
        "self_audit": {
            "title": "Trade Self-Audit",
            "eyebrow": "Self-Audit",
            "section_trades": "Trade Log",
            "section_winrate": "Consistency / Profit-Loss Ratio",
            "section_observations": "Observations",
        },
        "year_end_letter": {
            "title": "Year-End Investment Review",
            "eyebrow": "Year-End",
            "section_performance": "Annual Performance",
            "section_monthly": "Monthly Trend",
            "section_reflection": "Reflection",
        },
        "dd_checklist": {
            "title": "Due Diligence Checklist",
            "eyebrow": "DD",
            "section_filings": "Filings Review",
            "section_ratios": "Financial Ratios",
            "section_redflags": "Red Flags",
        },
        "quarterly_self_report": {
            "title": "Quarterly Self-Report",
            "eyebrow": "Quarterly",
            "section_pnl": "Quarterly P&L",
            "section_decisions": "Decision Log",
            "section_reflection": "Reflection",
        },
    },
}


# ── Email subject / intro strings (used by send_email branches) ────────────
EMAIL_STRINGS: dict[str, dict[str, dict[str, str]]] = {
    "ko": {
        "weekly_memo": {
            "subject": "[PivoxQuant] {week} 주간 투자 메모",
            "intro": "지난 한 주 포트폴리오 관찰을 정리했습니다.",
        },
        "brag_card": {
            "subject": "[PivoxQuant] {month} 월간 하이라이트",
            "intro": "이번 달 포트폴리오를 한 장으로 요약했습니다.",
        },
        "earnings_prebrief": {
            "subject": "[PivoxQuant] {ticker} 실적 사전 브리핑",
            "intro": "다가오는 실적 발표 전 관찰 메모입니다.",
        },
        "kpi_dashboard": {
            "subject": "[PivoxQuant] {month} KPI 대시보드",
            "intro": "이번 달 AI Suite 8개 모델 성능 관찰입니다.",
        },
        "dd_checklist": {
            "subject": "[PivoxQuant] {ticker} DD 체크리스트",
            "intro": "선택하신 종목의 Due Diligence 체크리스트입니다.",
        },
        "default": {
            "subject": "[PivoxQuant] 신규 리포트",
            "intro": "PivoxQuant가 새 리포트를 생성했습니다.",
        },
    },
    "en": {
        "weekly_memo": {
            "subject": "[PivoxQuant] Weekly Memo — {week}",
            "intro": "A summary of last week's portfolio observations.",
        },
        "brag_card": {
            "subject": "[PivoxQuant] {month} Monthly Highlight",
            "intro": "Your month, captured on a single page.",
        },
        "earnings_prebrief": {
            "subject": "[PivoxQuant] {ticker} Earnings Pre-Brief",
            "intro": "Observations ahead of the upcoming earnings release.",
        },
        "kpi_dashboard": {
            "subject": "[PivoxQuant] {month} KPI Dashboard",
            "intro": "This month's AI Suite eight-model performance overview.",
        },
        "dd_checklist": {
            "subject": "[PivoxQuant] {ticker} DD Checklist",
            "intro": "Due-diligence checklist for the selected ticker.",
        },
        "default": {
            "subject": "[PivoxQuant] New Report",
            "intro": "PivoxQuant has generated a new report.",
        },
    },
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _normalize(locale: Optional[str]) -> str:
    if not locale:
        return DEFAULT_LOCALE
    val = str(locale).strip().lower()
    return val if val in SUPPORTED_LOCALES else DEFAULT_LOCALE


def resolve_locale(
    user: Any = None,
    user_id: Any = None,
    data: Optional[Mapping[str, Any]] = None,
) -> str:
    """Resolve the effective locale from any combination of inputs.

    Resolution order:
      1. ``data["locale"]`` if caller explicitly passed it
      2. ``user.locale`` attribute (ORM row)
      3. Look up ``User.locale`` via ``user_id``
      4. Default to "ko"

    Never raises. All exceptions degrade silently to the default.
    """
    if data and isinstance(data, Mapping):
        explicit = data.get("locale")
        if explicit:
            return _normalize(str(explicit))

    if user is not None:
        candidate = getattr(user, "locale", None)
        if candidate:
            return _normalize(str(candidate))

    if user_id is not None:
        try:
            from extensions import db
            from models import User
            row = db.session.get(User, user_id)
            if row and getattr(row, "locale", None):
                return _normalize(str(row.locale))
        except Exception as exc:
            logger.debug("locale lookup failed user_id=%s: %s", user_id, exc)

    return DEFAULT_LOCALE


class _AttrDict(dict):
    """Dict that also supports attribute access — for Jinja `{{ _t.ns.key }}`.

    Recursive: nested dicts are wrapped on read.
    """

    def __getattr__(self, item):
        try:
            val = self[item]
        except KeyError:
            return item  # safe fallback — return the key itself
        if isinstance(val, dict) and not isinstance(val, _AttrDict):
            val = _AttrDict(
                {k: (_AttrDict(v) if isinstance(v, dict) else v) for k, v in val.items()}
            )
            self[item] = val
        return val


def make_translator(locale: str):
    """Return a two-arg callable ``t(namespace, key) -> str``."""
    loc = _normalize(locale)
    table = STRINGS.get(loc) or STRINGS[DEFAULT_LOCALE]
    fallback = STRINGS[DEFAULT_LOCALE]

    def _t(namespace: str, key: str) -> str:
        ns = table.get(namespace) or fallback.get(namespace) or {}
        if key in ns:
            return ns[key]
        # Try Korean fallback for any string missing from English (safer for
        # legal-language defaults than returning the raw key).
        ko_ns = fallback.get(namespace) or {}
        return ko_ns.get(key, key)

    return _t


def make_attr_table(locale: str) -> _AttrDict:
    """Return an _AttrDict-wrapped string table for attribute-style access."""
    loc = _normalize(locale)
    table = STRINGS.get(loc) or STRINGS[DEFAULT_LOCALE]
    return _AttrDict({k: _AttrDict(v) for k, v in table.items()})


def localize_ctx(ctx: dict, locale: Optional[str] = None) -> dict:
    """Mutate ``ctx`` in place to add ``locale`` + ``t`` + ``_t``.

    Idempotent — safe to call multiple times (e.g. once in `_with_persona`
    and again at template render). Always returns ``ctx`` for chaining.
    """
    if "locale" not in ctx or not ctx["locale"]:
        ctx["locale"] = _normalize(locale or ctx.get("locale"))
    loc = _normalize(ctx["locale"])
    ctx["locale"] = loc
    ctx["t"] = make_translator(loc)
    ctx["_t"] = make_attr_table(loc)
    return ctx


def email_subject(artifact_kind: str, locale: str, **params: Any) -> str:
    """Return a localized email subject. ``params`` interpolates ``{week}``/``{ticker}`` etc."""
    loc = _normalize(locale)
    table = EMAIL_STRINGS.get(loc) or EMAIL_STRINGS[DEFAULT_LOCALE]
    bundle = table.get(artifact_kind) or table.get("default") or {}
    raw = bundle.get("subject") or "[PivoxQuant]"
    try:
        return raw.format(**params)
    except Exception:
        return raw


def email_intro(artifact_kind: str, locale: str) -> str:
    """Return a localized email intro paragraph."""
    loc = _normalize(locale)
    table = EMAIL_STRINGS.get(loc) or EMAIL_STRINGS[DEFAULT_LOCALE]
    bundle = table.get(artifact_kind) or table.get("default") or {}
    return bundle.get("intro", "")
