"""Year recap route — 올해의 기록 (``GET /api/mirror-home/year?year=2026``).

거울 홈(routes/mirror_home.py)의 하위 읽기라 같은 접두사를 쓴다. 이 파일은 행을
읽어 넘기기만 하고, 계산은 전부 순수 함수 ``services/year_recap`` 에 있다.

Response (``ok`` · ``disclaimer`` 봉투 + 아래)::

    year, years[]            — 요청한 해 / 기록이 있는 해(최신순)
    range                    — {start, end, partial}  KST 날짜
    fills                    — {total, buys, sells, tickers, months_active, by_month[]}
    pauses                   — {started, proceeded, cancelled, open,
                                cancelled_buy, bought_later_anyway, never_bought}
    records                  — {reasoned_fills, research_written, research_reviewed,
                                verdicts{right,wrong,unknown}, observation_notes}
    holding                  — {sells, median_days}
    rules                    — null | {confirmed_on, frequency, holding}
    quotes[]                 — {kind, source, text, date, ticker, name, verdict?}
    doorway                  — null | 그해 문 앞의 한 줄 개수 (services/doorway.year_section)
    empty                    — 그해 기록이 하나도 없음
    share_disclaimer         — 공유 카드에 찍는 한 줄 (SoT services/legal/disclaimers.py)

Legal posture
-------------
``@legal_scrub_response`` 를 거친다. 인용 문장(``text``)만 ``skip_keys`` 로 원문을
둔다 — 유저가 쓴 문장을 서버가 고쳐 돌려주면 그건 기록이 아니다
(routes/research_notes.py 와 같은 방식, 스크럽 구현은 services/legal_filter 하나).
우리가 붙이는 것은 개수·중앙값과 면책 문구뿐이고, 점수·등급·지시를 만들지 않는다.
시세를 부르지 않는다.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request
from flask_login import current_user

from extensions import db
from models import (
    DoorwayCheck, InvestmentProfile, ObservationNote, PreTradeReflection, ResearchNote, TradeHistory,
)
from models.import_batch import STATUS_APPROVED, PendingTrade
from security import general_rate_limit
from services.error_responses import api_error
from services.legal.disclaimers import DISCLAIMER_BRAG_BILINGUAL, DISCLAIMER_MIRROR_RETROSPECTIVE_KR
from services.profile.my_rules import is_recorded_fill
from services.year_recap import available_years, compute_year_recap, kst_year

from .decorators import api_auth, legal_scrub_response

logger = logging.getLogger(__name__)

year_recap_bp = Blueprint("year_recap", __name__, url_prefix="/api/mirror-home")

_BAD_YEAR = "YEAR_RECAP_BAD_YEAR"
# 서비스 시작 전 해는 기록이 있을 수 없다 — 요청 위생용 하한.
_MIN_YEAR = 2020
# The user's own words — kept verbatim through the scrub (see Legal posture).
_scrub = legal_scrub_response(skip_keys=("text",))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_year(raw: str | None, now: datetime) -> int | None:
    """``?year=`` → int, 없으면 올해(KST). 범위 밖·숫자 아님이면 None."""
    this_year = kst_year(now)
    if raw is None or raw == "":
        return this_year
    if not (raw.isascii() and raw.isdigit()) or len(raw) != 4:  # "²⁰²⁶".isdigit() is True
        return None
    year = int(raw)
    return year if _MIN_YEAR <= year <= this_year else None


def _offline_name(ticker: str | None) -> str | None:
    """종목명 — 오프라인 레지스트리만 (research_note / observation_note to_dict 와 같은 이유)."""
    if not ticker:
        return None
    try:
        if ticker.endswith((".KS", ".KQ")):
            from services import kr_stock_registry

            return kr_stock_registry.get_name(ticker) or ticker
        from services import us_stock_registry

        return us_stock_registry.get_name(ticker) or ticker
    except Exception:
        return ticker


def _load_rows(uid: int) -> dict:
    """한 유저의 행 전부 — 소유 필터는 여기 한 곳."""
    profile = InvestmentProfile.query.filter_by(user_id=uid).first()
    return {
        "trades": TradeHistory.query.filter_by(user_id=uid).all(),
        "reflections": PreTradeReflection.query.filter_by(user_id=uid).all(),
        "approved_pending": PendingTrade.query.filter_by(user_id=uid, status=STATUS_APPROVED).all(),
        "research_notes": ResearchNote.query.filter_by(user_id=uid).all(),
        # 관찰 노트는 개수만 센다 — 본문(암호문)을 읽지 않는다.
        "observation_times": [
            ts for (ts,) in db.session.query(ObservationNote.created_at)
            .filter(ObservationNote.user_id == uid).all()
        ],
        "rules_answers": profile.onboarding_answers() if profile else None,
        "rules_confirmed_at": profile.rules_confirmed_at if profile else None,
        **_doorway_rows(uid),
    }


def _doorway_rows(uid: int) -> dict:
    """문 앞의 한 줄 — 열림 전부 + 첫 열림 이후의 체결(대기 중 포함). 한 줄
    (note)은 셀 때 쓰지 않는다."""
    from services.doorway.service import FOLLOW_MINUTES, load_fills

    checks = DoorwayCheck.query.filter_by(user_id=uid).all()
    first = min((c.created_at for c in checks if c.created_at), default=None)
    fills = load_fills(uid, first - timedelta(minutes=FOLLOW_MINUTES)) if first else []
    return {"doorway_checks": checks, "doorway_fills": fills, "doorway_first_at": first}


def _row_times(rows: dict) -> list:
    return (
        [t.traded_at for t in rows["trades"] if is_recorded_fill(t)]
        + [r.created_at for r in rows["reflections"]]
        + [p.approved_at for p in rows["approved_pending"]]
        + [n.created_at for n in rows["research_notes"]]
        + [n.reviewed_at for n in rows["research_notes"]]
        + rows["observation_times"]
        + [c.created_at for c in rows["doorway_checks"]]
    )


@year_recap_bp.route("/year", methods=["GET"])
@api_auth
@_scrub
@general_rate_limit
def year_recap():
    now = _utc_now()
    year = _parse_year(request.args.get("year"), now)
    if year is None:
        return api_error(
            en=f"year must be a 4-digit year between {_MIN_YEAR} and this year.",
            kr="연도가 올바르지 않습니다.", code=_BAD_YEAR, status=400,
        )
    rows = _load_rows(int(current_user.id))
    recap = compute_year_recap(year, now=now, **rows)
    for q in recap["quotes"]:
        q["name"] = _offline_name(q.get("ticker"))
    body = {
        "ok": True,
        "disclaimer": DISCLAIMER_MIRROR_RETROSPECTIVE_KR,
        "share_disclaimer": DISCLAIMER_BRAG_BILINGUAL,
        "years": available_years(_row_times(rows), now),
        **recap,
    }
    return jsonify(body), 200
