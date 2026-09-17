"""월간 거울 리포트 — 데이터 조립(build)과 PDF 렌더(render).

무엇인가
--------
유저가 **직접 기록한 체결**만 읽어서, 지난 한 달(기본 30일)의 기록을 그대로
되비추는 한 장짜리 리포트다. 제품이 이미 가지고 있는 네 개의 거울 함수를
그대로 호출할 뿐, 새 통계를 여기서 만들지 않는다:

* :func:`services.behavior.turnover_mirror.compute_turnover_mirror` — 체결 수 ·
  통화별 거래대금 · 보유기간
* :func:`services.behavior.averaging_down_mirror.compute_averaging_down_mirror`
  — 이미 보유한 종목을 다시 취득한 기록
* :func:`services.behavior.profit_loss_mirror.compute_profit_loss_mirror` —
  기간 안에서 닫힌 거래의 실현 손익
* :func:`services.behavior.concentration_mirror.compute_concentration_mirror`
  — 생성 시점 보유분의 집중도(평균매입가 기준)

무엇이 아닌가
-------------
* **점수가 아니다.** ``services.behavior.scorer`` 를 import 하지 않는다.
  등급·점수·순위·별점 어느 것도 이 모듈의 출력에 없다. 제품의 공개 약속이
  "점수를 매기지 않습니다" 이고, 그 약속은 리포트에서도 지켜진다.
* **추천이 아니다.** 처방 문장이 없다. 리포트는 관측한 사실만 적고, 해석은  // legal-ok
  읽는 사람의 몫으로 남긴다 (자본시장법 §49).
* **시세를 쓰지 않는다.** 시세·평가액 서비스는 import조차 하지 않는다. 모든
  금액은 유저가 기록한 체결가 × 수량이다 (FMP 약관 §2.2.2).

기간을 자르는 방식
------------------
거울 함수들의 ``period_days`` 는 **입력에 들어 있는 마지막 체결**을 기준으로
창을 자른다. 코호트 스캔에는 맞지만 "지난 30일" 이라고 적어 보내는 월간
리포트에는 맞지 않는다 — 반 년 전에 거래를 멈춘 유저에게 "반 년 전 그 30일"
을 이번 달이라고 내밀게 된다. 그래서 여기서는 창을 ``as_of`` 기준으로 먼저
잘라 넣고 함수에는 ``period_days=None`` 을 준다. 잘라 넣는 것과 함수가
안에서 자르는 것은 계산상 같고, 기준점만 달라진다.

그 대가는 창 밖 원장을 못 본다는 것이다 — 기간 전에 취득한 종목을 기간 안에
다시 취득하면 '추가 취득' 이 아니라 새 취득으로 읽히고, 기간 전에 취득한
종목을 기간 안에 처분하면 닫힌 거래로 세지 않는다. 이 한계는 리포트의 "이
숫자가 말하지 않는 것" 절에 그대로 적어서 내보낸다. 숨기지 않는다.

최소 표본
---------
거울 함수들의 ``min_trades`` / ``min_follow_on`` / ``min_pairs`` 기본값(8·3·5)
은 코호트용 바닥이다. 개인 리포트는 n=1 이므로 1로 내린다 —
``services/toss/mirror_report.py`` 가 같은 이유로 같은 선택을 했다.

공개 API
--------
:func:`build_mirror_report` — 유저 기록만으로 리포트 데이터를 만든다. 순수
    조회 + 계산. 데이터가 부족하면 예외 대신 ``has_content=False``.
:func:`render_mirror_html` — 데이터를 인쇄용 HTML 로 렌더한다 (weasyprint 불필요).
:func:`render_mirror_pdf` — 그 HTML 을 PDF 바이트로 렌더한다.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from models import TradeHistory
from services.behavior.averaging_down_mirror import compute_averaging_down_mirror
from services.behavior.concentration_mirror import compute_concentration_mirror
from services.behavior.profit_loss_mirror import compute_profit_loss_mirror
from services.behavior.turnover_mirror import compute_turnover_mirror
from services.legal.disclaimers import (
    DISCLAIMER_ARTIFACT_KR,
    DISCLAIMER_MIRROR_RETROSPECTIVE_KR,
)

# ── 상수 ─────────────────────────────────────────────────────────────
_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_TEMPLATE_NAME = "mirror_report.html.j2"

# 개인 리포트의 최소 표본 — 코호트 바닥(8·3·5)이 아니라 1. 모듈 docstring 참조.
_PERSONAL_MIN: int = 1

_DEFAULT_PERIOD_DAYS: int = 30
_DEFAULT_LOCALE: str = "ko"
_EM_DASH: str = "—"


# ── 시각 정규화 ──────────────────────────────────────────────────────
def _as_naive_utc(as_of: Any) -> datetime:
    """``as_of`` 를 naive UTC ``datetime`` 으로 맞춘다.

    ``TradeHistory.traded_at`` 이 naive UTC 로 저장되므로 비교 전에 같은
    좌표계로 옮긴다. ``date`` 는 그 날의 끝(23:59:59.999999)으로 읽는다 —
    "9월 30일 기준" 이 9월 30일의 체결을 빠뜨리면 안 되기 때문이다.
    """
    if as_of is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if isinstance(as_of, datetime):
        if as_of.tzinfo is not None:
            return as_of.astimezone(timezone.utc).replace(tzinfo=None)
        return as_of
    if isinstance(as_of, date):
        return datetime.combine(as_of, time.max)
    raise TypeError(f"as_of must be datetime | date | None, got {type(as_of).__name__}")


# ── 데이터 조립 ──────────────────────────────────────────────────────
def build_mirror_report(user_id: int, *, period_days: int = _DEFAULT_PERIOD_DAYS, as_of=None) -> dict:
    """유저 본인 기록만으로 리포트 데이터를 만든다. 순수 조회 + 계산.

    Parameters
    ----------
    user_id : int
        리포트를 받을 유저.
    period_days : int
        ``as_of`` 에서 거슬러 올라가는 창의 길이(일). 기본 30일.
    as_of : datetime | date | None
        창의 끝. ``None`` 이면 지금(UTC).

    Returns
    -------
    dict
        JSON 으로 그대로 직렬화 가능한 값만 담는다. 키:
        ``has_content, user_id, period_days, period_start, period_end,
        generated_at, window_trade_count, turnover, averaging_down,
        profit_loss, concentration, disclaimers``.

        **점수 / 등급 / 순위 / 별점 필드는 어디에도 없다.**

        기간 안에 기록이 하나도 없으면 ``has_content`` 가 ``False`` 다.
        예외를 던지지 않는다 — 발송 쪽이 이 플래그로 스킵을 판단한다.
    """
    window_days = max(1, int(period_days or _DEFAULT_PERIOD_DAYS))
    period_end = _as_naive_utc(as_of)
    period_start = period_end - timedelta(days=window_days)

    rows = TradeHistory.query.filter_by(user_id=user_id).all()
    # 창 자르기는 as_of 기준으로 여기서 한다 (모듈 docstring "기간을 자르는 방식").
    windowed = [
        t for t in rows
        if t is not None and t.traded_at and period_start <= t.traded_at <= period_end
    ]

    turnover = compute_turnover_mirror(windowed, period_days=None, min_trades=_PERSONAL_MIN)
    averaging_down = compute_averaging_down_mirror(windowed, period_days=None, min_follow_on=_PERSONAL_MIN)
    profit_loss = compute_profit_loss_mirror(windowed, period_days=None, min_pairs=_PERSONAL_MIN)
    # 집중도는 '지금 보유분' 의 사실이라 창과 무관하다. 리포트에서도 그렇게 적는다.
    concentration = compute_concentration_mirror(user_id)

    # 기간 안에 기록이 하나도 없으면 리포트가 할 말이 없다. 보유분만 있는
    # 유저에게 "이번 달 체결 없음" 을 매달 보내지 않으려고, 집중도는
    # has_content 판정에 넣지 않는다.
    has_content = any(
        bool(mirror.get("sufficient_data"))
        for mirror in (turnover, averaging_down, profit_loss)
    )

    return {
        "has_content": has_content,
        "user_id": user_id,
        "period_days": window_days,
        "period_start": period_start.date().isoformat(),
        "period_end": period_end.date().isoformat(),
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "window_trade_count": len(windowed),
        "turnover": turnover,
        "averaging_down": averaging_down,
        "profit_loss": profit_loss,
        "concentration": concentration,
        # 문구는 SoT 에서만 온다. 여기서 새로 짓지 않는다.
        "disclaimers": {
            "mirror": DISCLAIMER_MIRROR_RETROSPECTIVE_KR,
            "artifact": DISCLAIMER_ARTIFACT_KR,
        },
    }


# ── 렌더 ─────────────────────────────────────────────────────────────
def _fmt(value: Any, digits: int = 0) -> str:
    """천단위 구분 숫자. ``None`` 은 em dash."""
    if value is None:
        return _EM_DASH
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return _EM_DASH


def _signed(value: Any, digits: int = 2) -> str:
    """부호를 붙인 숫자. 손실률의 음수 부호는 사실 그대로 남긴다."""
    if value is None:
        return _EM_DASH
    try:
        return f"{float(value):+,.{digits}f}"
    except (TypeError, ValueError):
        return _EM_DASH


def _money(value: Any, currency: str = "") -> str:
    """통화별 자릿수. 원화는 소수점 없이, 나머지는 두 자리."""
    digits = 0 if (currency or "").upper() == "KRW" else 2
    return _fmt(value, digits)


_ENV: Environment | None = None


def _env() -> Environment:
    """템플릿 환경 (프로세스당 한 번)."""
    global _ENV
    if _ENV is None:
        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=select_autoescape(default=True, default_for_string=True),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        env.filters["fmt"] = _fmt
        env.filters["signed"] = _signed
        env.filters["money"] = _money
        # 면책 문구는 데이터 dict 가 아니라 환경에서 주입한다 — 호출자가 dict 를
        # 어떻게 만들어 넘기든(직렬화 후 복원 포함) 문구가 빠질 수 없게.
        env.globals["disclaimer_mirror"] = DISCLAIMER_MIRROR_RETROSPECTIVE_KR
        env.globals["disclaimer_artifact"] = DISCLAIMER_ARTIFACT_KR
        _ENV = env
    return _ENV


# 화면에 나가는 라벨. 어휘 규칙: 지시로 읽힐 수 있는 낱말(매수/매도/추천/조언/  // legal-ok
# 익절/손절, buy/sell/hold/advice)은 쓰지 않는다. 대신 회계적 사실 명사인  // legal-ok
# 취득/처분(acquisition/disposal)을 쓴다 — services/legal/forbidden_terms.py
# 의 FORBIDDEN_DIRECTIVE_TERMS 를 통째로 통과하는 어휘다.
_LABELS: dict[str, dict[str, Any]] = {
    "ko": {
        "lang": "ko",
        "eyebrow": "PIVOXQUANT · 기록 거울",
        "title": "월간 거울 리포트",
        "subtitle": "지난 기간 동안 당신이 남긴 기록을, 그대로 되비춘다.",
        "period": "기간",
        "generated": "생성 시각",
        "unit_days": "일",
        "unit_count": "건",
        "unit_pct": "%",
        "empty_head": "이 기간에 기록된 체결이 없다",
        "empty_body": "적을 기록이 없어 숫자를 비워 둔다. 기록이 쌓이면 다음 리포트부터 채워진다.",
        "s_fills": "기록한 체결",
        "s_fills_lede": "이 기간에 직접 기록한 체결이다. 금액은 기록된 체결가 × 수량이며, 통화가 다르면 합치지 않는다.",
        "k_fills": "체결",
        "k_acquire": "취득",
        "k_dispose": "처분",
        "k_days_median": "취득에서 처분까지 · 중앙값",
        "k_days_mean": "취득에서 처분까지 · 평균",
        "th_currency": "통화",
        "th_gross": "거래대금 합계",
        "th_count": "건수",
        "none_fills": "이 기간에 기록된 체결이 없다.",
        "s_followon": "이미 보유한 종목을 다시 취득한 기록",
        "s_followon_lede": "그 시점의 평균매입가와 견주어 낮게 · 높게 · 같게로만 나눈다. 좋고 나쁨의 판정은 없다.",
        "k_followon": "추가 취득",
        "k_below": "평균매입가보다 낮게",
        "k_above": "평균매입가보다 높게",
        "k_flat": "평균매입가와 같게",
        "th_ticker": "종목",
        "none_followon": "이 기간에 이미 보유한 종목을 다시 취득한 기록이 없다.",
        "s_closed": "기간 안에서 닫힌 거래",
        "s_closed_lede": "취득과 처분이 선입선출로 맞물린 거래다. 수익률은 기록된 체결가로만 계산한다.",
        "k_gain_side": "이익을 실현한 처분",
        "k_loss_side": "손실을 실현한 처분",
        "k_count": "건수",
        "k_days_median_short": "보유일 중앙값",
        "k_return_median": "수익률 중앙값",
        "k_return_mean": "수익률 평균",
        "k_total_closed": "닫힌 거래 전체",
        "one_sided": "이 기간에는 한쪽 처분만 있었다. 반대쪽은 기록이 없었다는 사실만 적는다.",
        "none_closed": "이 기간에 취득과 처분이 맞물려 닫힌 거래가 없다.",
        "s_concentration": "생성 시점의 보유 집중",
        "s_concentration_lede": "리포트를 만든 시점의 보유분이다. 기간과 무관하고, 시장가가 아니라 평균매입가로 잰다.",
        "k_symbols": "보유 종목 수",
        "k_max_weight": "가장 큰 종목의 비중",
        "k_largest": "가장 큰 종목",
        "none_concentration": "평균매입가를 잴 수 있는 보유 종목이 없다.",
        "s_limits": "이 숫자가 말하지 않는 것",
        "limits": [
            "이 리포트는 직접 기록한 체결만 읽는다. 기록하지 않은 거래는 처음부터 없는 것으로 집계된다.",
            "금액은 기록된 체결가 × 수량이다. 외부 시세도, 오늘의 평가액도 쓰지 않는다.",
            "통화가 다른 금액은 합치지 않는다. 원화와 달러는 끝까지 따로 적는다.",
            "기간 밖의 기록은 이 숫자에 들어가지 않는다. 기간 전에 취득한 종목을 기간 안에 다시 취득했다면 "
            "'추가 취득' 으로 세지 않고, 기간 전에 취득한 종목을 기간 안에 처분했다면 닫힌 거래로 세지 않는다.",
            "집중도는 생성 시점 보유분을 평균매입가로 잰 것이다. 시장가도 아니고 기간과도 무관하다.",
            "여기에는 잘함과 못함의 판정이 없다. 점수도 등급도 순위도 매기지 않는다. 읽고 해석하는 일은 본인의 몫이다.",
        ],
        "s_notice": "면책 고지",
        "page": "쪽",
    },
    "en": {
        "lang": "en",
        "eyebrow": "PIVOXQUANT · RECORD MIRROR",
        "title": "Monthly Mirror Report",
        "subtitle": "The records you kept over the period, reflected back as they are.",
        "period": "Period",
        "generated": "Generated",
        "unit_days": "days",
        "unit_count": "",
        "unit_pct": "%",
        "empty_head": "No fills were recorded in this period",
        "empty_body": "There is nothing to report, so the figures stay blank. They fill in once records accumulate.",
        "s_fills": "Fills you recorded",
        "s_fills_lede": "Fills you entered yourself over this period. Values are recorded price x quantity, "
                        "and currencies are never added together.",
        "k_fills": "Fills",
        "k_acquire": "Acquisitions",
        "k_dispose": "Disposals",
        "k_days_median": "Days from acquisition to disposal · median",
        "k_days_mean": "Days from acquisition to disposal · mean",
        "th_currency": "Currency",
        "th_gross": "Gross traded value",
        "th_count": "Fills",
        "none_fills": "No fills were recorded in this period.",
        "s_followon": "Acquiring more of a position you already had",
        "s_followon_lede": "Each one is sorted only as below, above, or at the running average cost at that moment. "
                           "Nothing here is graded.",
        "k_followon": "Follow-on acquisitions",
        "k_below": "Below the average cost",
        "k_above": "Above the average cost",
        "k_flat": "At the average cost",
        "th_ticker": "Symbol",
        "none_followon": "No position you already had was acquired again in this period.",
        "s_closed": "Round trips closed inside the period",
        "s_closed_lede": "Acquisitions matched to disposals first-in-first-out. Returns come from recorded "
                         "fill prices only.",
        "k_gain_side": "Disposals that realised a gain",
        "k_loss_side": "Disposals that realised a loss",
        "k_count": "Count",
        "k_days_median_short": "Median days carried",
        "k_return_median": "Median return",
        "k_return_mean": "Mean return",
        "k_total_closed": "All closed round trips",
        "one_sided": "Only one side occurred in this period. The other side simply has no record.",
        "none_closed": "No acquisition was matched to a disposal inside this period.",
        "s_concentration": "Concentration at the time of writing",
        "s_concentration_lede": "Positions as of the moment this report was made — independent of the period, "
                                "measured at average cost rather than market price.",
        "k_symbols": "Symbols carried",
        "k_max_weight": "Largest symbol's share",
        "k_largest": "Largest symbol",
        "none_concentration": "No position has an average cost that can be measured.",
        "s_limits": "What these numbers do not say",
        "limits": [
            "This report reads only the fills you recorded yourself. A trade never entered never happened here.",
            "Values are recorded price x quantity. No external quote and no present-day valuation is used.",
            "Amounts in different currencies are never summed. Won and dollars stay on separate lines throughout.",
            "Records outside the period are not in these figures. A position acquired before the period and "
            "acquired again inside it is not counted as a follow-on, and one acquired before the period and "
            "disposed of inside it is not counted as a closed round trip.",
            "Concentration is measured on positions at the time of writing, at average cost. It is neither a "
            "market price nor tied to the period.",
            "Nothing here says well done or badly done. There is no score, no grade, no ranking. "
            "Reading it is yours to do.",
        ],
        "s_notice": "면책 고지",
        "page": "page",
    },
}


def render_mirror_html(data: dict, *, locale: str = _DEFAULT_LOCALE) -> str:
    """리포트 데이터를 인쇄용 HTML 로 렌더한다.

    weasyprint 없이도 돈다 — 문구 검사와 금지어 스캔이 네이티브 라이브러리에
    묶이지 않게 하려고 PDF 단계와 분리해 두었다.
    """
    labels = _LABELS.get((locale or _DEFAULT_LOCALE).lower(), _LABELS[_DEFAULT_LOCALE])
    return _env().get_template(_TEMPLATE_NAME).render(d=data or {}, L=labels)


def render_mirror_pdf(data: dict, *, locale: str = _DEFAULT_LOCALE) -> bytes:
    """:func:`build_mirror_report` 결과를 PDF 바이트로 렌더한다.

    weasyprint 는 네이티브 라이브러리(pango/gobject)에 의존해서 macOS 로컬에서
    import 가 깨질 수 있다 (HANDOVER.md). import 를 함수 안으로 미뤄서, PDF 를
    실제로 만들 때만 그 의존이 걸리게 한다 — 데이터 조립과 HTML 렌더는 영향
    받지 않는다.
    """
    html = render_mirror_html(data, locale=locale)
    from weasyprint import HTML  # noqa: PLC0415 — 지연 import (docstring 참조)

    return HTML(string=html, base_url=str(_TEMPLATE_DIR)).write_pdf()


__all__ = ["build_mirror_report", "render_mirror_html", "render_mirror_pdf"]
