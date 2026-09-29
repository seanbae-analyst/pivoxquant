"""매수 ↔ 멈춤 명시 연결 (2026-09-29, CEO 승인).

사용자가 /pre-trade 에서 멈춤을 기록한 뒤 증권사 앱에서 실제로 사고, 나중에
그 매수를 PivoxQuant 에 기록한다. 지금까지 둘을 잇는 건 추정뿐이었다
(``friction_outcome`` 의 같은 종목 · 7일 창, ``imports.ledger.PreTradeIndex``).
여기서는 사용자가 매수를 기록하면서 **직접** "이 매수는 그 멈춤의 결과다"라고
잇게 한다 — ``TradeHistory.reflection_id``.

연결되면 그 멈춤의 rationale 이 곧 이 매수의 이유다. 7문항을 다시 적게 하지
않는다. rationale 은 reflection 행에 암호화된 채로 남고, 매수 행은 id 로만
가리킨다 (평문 복사본을 만들지 않는다).

규칙
----
* 연결은 **매수만** 한다. 매도 전 멈춤(EXIT — ``intended_side`` 가 매도 값)은
  매수에 잇지 않는다.
* 멈춤은 **본인 것**이고 **같은 종목**이어야 한다 (``005930`` ↔ ``005930.KS``
  처럼 거래소 접미사만 다른 건 같은 종목).
* 멈춤 하나는 매수 하나에만 잇는다 — 이미 다른 매수에 이어진 멈춤은 거부한다.
* 시세를 부르지 않는다. 사용자 자신의 행만 읽는다.

명시 거절 (``TradeHistory.reflection_declined``)
------------------------------------------------
후보가 보였는데 사용자가 체크를 끄고 기록했으면 그 매수는 "멈춤과 무관"이라고
사용자가 말한 것이다. 연결 없는 옛 행과 구분이 안 되면 friction_outcome 의
7일 창 추정이 그 매수를 다시 멈춤에 귀속시킨다. 그래서 거절을 저장한다.
요청 계약: 본문 ``reflection_declined: true`` (``reflection_id`` 는 없거나
null). 매수에만, 연결이 없을 때만 의미가 있다.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from extensions import db
from models import PreTradeReflection, TradeHistory
from services.pre_trade.friction_outcome import _is_buy_side, _norm, _utc_now

# 매수 기록 화면에 "최근 멈춤"으로 띄우는 창. 연결 자체는 창 밖 멈춤도 받는다
# (사용자가 고른 것) — 창은 후보를 보여 주는 범위일 뿐이다.
LINK_WINDOW_DAYS = 30

# 후보로 보여 줄 상태. pending(쿨다운 중)은 아직 기록이 끝나지 않았다.
# ready 는 7문항을 적고 진행/취소를 누르지 않은 기록 — 쿨다운이 0초라
# 증권사 앱으로 바로 넘어간 경우가 여기 남는다.
LINKABLE_STATUSES = ("proceeded", "cancelled", "ready")

MAX_CANDIDATES = 5


class ReflectionLinkError(Exception):
    """연결 요청이 유효하지 않다. 라우트가 ``api_error(..., status=400)`` 로 낸다."""

    def __init__(self, code: str, *, en: str, kr: str):
        super().__init__(code)
        self.code = code
        self.en = en
        self.kr = kr


# 한국 거래소 접미사만 뗀다. 미국 클래스주(BRK.A / BRK.B, BF.A / BF.B)의
# ".A" 는 거래소가 아니라 다른 종목이다 — 첫 "." 에서 자르면 둘이 같아진다.
_KR_SUFFIXES = (".KS", ".KQ", ".KRX")


def _base(ticker: Any) -> str:
    t = _norm(ticker)
    for suffix in _KR_SUFFIXES:
        if t.endswith(suffix):
            return t[: -len(suffix)]
    return t


def same_ticker(a: Any, b: Any) -> bool:
    """거래소 접미사(.KS/.KQ)만 다른 표기는 같은 종목으로 본다."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    return na == nb or _base(na) == _base(nb)


def _linked_ids(user_id: int) -> set[int]:
    rows = (
        db.session.query(TradeHistory.reflection_id)
        .filter(TradeHistory.user_id == int(user_id),
                TradeHistory.reflection_id.isnot(None))
        .all()
    )
    return {int(r[0]) for r in rows}


def linkable_reflections(
    user_id: int,
    ticker: str,
    *,
    now: datetime | None = None,
    days: int = LINK_WINDOW_DAYS,
    limit: int = MAX_CANDIDATES,
) -> list[dict]:
    """``ticker`` 에 대한 최근 매수 쪽 멈춤 중 아직 어느 매수에도 이어지지 않은 것.

    최신순 ``to_dict()`` 행. 본인 행만 (SQL 수준 ``user_id`` 필터).
    """
    if not _norm(ticker):
        return []
    now = now or _utc_now()
    since = now - timedelta(days=days)
    rows = (
        PreTradeReflection.query
        .filter(PreTradeReflection.user_id == int(user_id),
                PreTradeReflection.created_at >= since)
        .order_by(PreTradeReflection.created_at.desc(), PreTradeReflection.id.desc())
        .all()
    )
    used = _linked_ids(user_id)
    out: list[dict] = []
    for r in rows:
        if r.id in used or not _is_buy_side(r):
            continue
        if not same_ticker(r.intended_ticker, ticker):
            continue
        if r.status_label(now) not in LINKABLE_STATUSES:
            continue
        out.append(r.to_dict(now=now))
        if len(out) >= limit:
            break
    return out


def resolve_reflection_link(
    user_id: int,
    raw_id: Any,
    *,
    ticker: str,
    action: str,
) -> int | None:
    """요청의 ``reflection_id`` 를 검증해 연결할 id 를 돌려준다.

    값이 없으면(None / "" ) None — 연결 없이 기록한다. 있는데 유효하지 않으면
    :class:`ReflectionLinkError`. 아무것도 쓰지 않는다 (호출자가 매수 행에 넣는다).
    """
    if raw_id is None or raw_id == "":
        return None
    try:
        rid = int(raw_id)
    except (TypeError, ValueError):
        rid = 0
    if rid <= 0 or isinstance(raw_id, bool):
        raise ReflectionLinkError(
            "REFLECTION_LINK_INVALID",
            en="reflection_id must be a positive integer.",
            kr="reflection_id 는 양의 정수여야 합니다.",
        )
    if str(action or "").lower() != "buy":
        raise ReflectionLinkError(
            "REFLECTION_LINK_BUY_ONLY",
            en="A pause record can only be linked to a recorded purchase.",
            kr="멈춤 기록은 매수 기록에만 연결할 수 있습니다.",
        )
    r = PreTradeReflection.query.filter_by(id=rid, user_id=int(user_id)).first()
    if r is None:
        raise ReflectionLinkError(
            "REFLECTION_LINK_NOT_FOUND",
            en="Pause record not found.",
            kr="멈춤 기록을 찾을 수 없습니다.",
        )
    if not _is_buy_side(r):
        raise ReflectionLinkError(
            "REFLECTION_LINK_SIDE_MISMATCH",
            en="This pause record was written before a sale, not a purchase.",
            kr="이 멈춤 기록은 매수가 아니라 매도 전에 적은 기록입니다.",
        )
    if not same_ticker(r.intended_ticker, ticker):
        raise ReflectionLinkError(
            "REFLECTION_LINK_TICKER_MISMATCH",
            en="This pause record is for a different ticker.",
            kr="이 멈춤 기록은 다른 종목의 기록입니다.",
        )
    if rid in _linked_ids(user_id):
        raise ReflectionLinkError(
            "REFLECTION_LINK_ALREADY_USED",
            en="This pause record is already linked to another purchase.",
            kr="이 멈춤 기록은 이미 다른 매수에 연결되어 있습니다.",
        )
    return rid


def import_reflection_link(user_id: int, data: dict, pending: Any) -> int | None:
    """가져오기 승인 시 연결할 멈춤.

    본문에 ``reflection_id`` 키가 있으면 사용자의 명시 선택이다 — 검증하고,
    유효하지 않으면 :class:`ReflectionLinkError` (null 이면 연결하지 않는다).
    키가 없으면 가져오기 때 추정해 둔 ``pending.pre_trade_reflection_id`` 를
    쓰되, 매수 쪽 · 같은 종목 · 미사용 조건을 못 맞추면 조용히 연결하지 않는다.
    """
    action = str(getattr(pending, "action", "") or "").lower()
    ticker = getattr(pending, "ticker", None) or ""
    if isinstance(data, dict) and "reflection_id" in data:
        return resolve_reflection_link(user_id, data.get("reflection_id"),
                                       ticker=ticker, action=action)
    inferred = getattr(pending, "pre_trade_reflection_id", None)
    if not inferred:
        return None
    try:
        return resolve_reflection_link(user_id, inferred, ticker=ticker, action=action)
    except ReflectionLinkError:
        return None


def link_declined(data: Any, reflection_id: int | None, *, action: str) -> bool:
    """본문이 보여진 후보를 명시로 거절했는가 (``reflection_declined: true``).

    매수에만, 연결이 없을 때만 True. 그 밖의 값(문자열 "true" 등)은 거절로
    보지 않는다 — 프론트는 불리언만 보낸다.
    """
    if reflection_id is not None or str(action or "").lower() != "buy":
        return False
    return isinstance(data, dict) and data.get("reflection_declined") is True


def import_link_declined(user_id: int, data: Any, pending: Any,
                         reflection_id: int | None) -> bool:
    """가져오기 승인의 명시 거절.

    ``reflection_declined: true`` 이거나, 가져올 때 매치된 멈춤이 아직 이을 수
    있었는데 본문이 ``reflection_id: null`` 로 끊었으면 거절이다.
    """
    action = str(getattr(pending, "action", "") or "").lower()
    if link_declined(data, reflection_id, action=action):
        return True
    if (reflection_id is not None or not isinstance(data, dict)
            or "reflection_id" not in data or data.get("reflection_id") is not None):
        return False
    inferred = getattr(pending, "pre_trade_reflection_id", None)
    if not inferred:
        return False
    try:
        resolve_reflection_link(user_id, inferred,
                                ticker=getattr(pending, "ticker", None) or "", action=action)
    except ReflectionLinkError:
        return False
    return True


def attach_reflection(trade_id: int | None, reflection_id: int | None,
                      *, declined: bool = False) -> None:
    """이미 만들어진 매수 행에 연결(또는 명시 거절)을 단다 (commit 은 호출자)."""
    if not trade_id or not (reflection_id or declined):
        return
    t = db.session.get(TradeHistory, int(trade_id))
    if t is None:
        return
    if reflection_id:
        t.reflection_id = int(reflection_id)
    else:
        t.reflection_declined = True


__all__ = [
    "LINK_WINDOW_DAYS",
    "ReflectionLinkError",
    "attach_reflection",
    "import_link_declined",
    "import_reflection_link",
    "link_declined",
    "linkable_reflections",
    "resolve_reflection_link",
    "same_ticker",
]
