"""실적 발표 뒤에 체결했나 — 개수만 센다 (순수 함수).

정의
----
실적 발표의 공식 공시일을 D 라 할 때, 체결의 같은 시장 날짜가 **D 다음 날부터
사흘 안**(D+1 … D+3)이면 "발표 뒤 사흘 안"이다. 시장 날짜는 미국 = 미 동부
(SEC 8-K 항목 2.02), 한국 = 한국 날짜(DART 잠정실적 접수일).

왜 이렇게 좁게 세나
-------------------
* 공시일만 믿는다. SEC 목록의 접수 시각은 몇 시간씩 어긋날 수 있어(sec.py)
  "24시간 안"은 셀 수 없다. 대신 공식 공시일은 정확하다. 실제 접수는 D 당일이나
  그 전이다(17:30 ET 뒤 접수분은 다음 영업일이 공시일 — Regulation S-T Rule 13)
  — 그래서 D+1 이후 체결은 확실히 발표 **뒤**다.
* 발표 당일(D) 체결은 세지 않는다. 장 마감 뒤(16:05 ET 등) 발표면 그날 장중
  체결은 발표 **전**이라, 당일을 넣으면 거꾸로 센다.
* 시각 없는 체결(날짜만 아는 행 — ``services.imports.is_date_only``, KST 날짜
  00:00)은 미국 종목이면 미 동부 날짜를 하루 단위로도 확정할 수 없어 따로 센다.
  한국 종목이면 그 날짜가 곧 시장 날짜라 그대로 센다.
* 확인 범위 앞쪽은 뺀다. SEC 목록이 덮는 첫날로부터 사흘이 지나기 전 체결은
  그 앞 사흘에 발표가 있었는지 모른다.

같은 공시일에 다른 회사 사정이 겹쳐도 이 함수는 원인을 말하지 않는다 — 날짜가
붙어 있다는 개수뿐이다.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Sequence
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
KST = ZoneInfo("Asia/Seoul")
WINDOW_DAYS = 3
MARKET_US = "us"
MARKET_KR = "kr"


@dataclass(frozen=True)
class FillPoint:
    """체결 하나. ``traded_at`` 은 저장 규약 그대로 — 시각이 있으면 naive UTC,
    없으면 KST 날짜 00:00 (``untimed``)."""

    traded_at: datetime
    side: str  # "buy" | "sell"
    untimed: bool = False


def us_date(traded_at_utc: datetime) -> date:
    """naive UTC 순간 → 미 동부 날짜 (서머타임 자동)."""
    return traded_at_utc.replace(tzinfo=timezone.utc).astimezone(ET).date()


def kr_date(traded_at_utc: datetime) -> date:
    return traded_at_utc.replace(tzinfo=timezone.utc).astimezone(KST).date()


def earnings_reaction(
    fills: Iterable[FillPoint],
    earnings_days: Sequence[date],
    *,
    coverage_from: date | None,
    window_days: int = WINDOW_DAYS,
    market: str = MARKET_US,
) -> dict:
    """→ ``{"window_days", "date_basis", "buys_after", "sells_after", "timed_fills", "untimed_fills"}``.

    ``timed_fills`` / ``untimed_fills`` 는 확인 범위 안에서 본 체결 수다
    (화면이 비율을 만들지 않도록 분모가 아니라 참고 값으로만 돌려준다).
    """
    days = sorted(set(earnings_days))
    first = (coverage_from + timedelta(days=window_days)) if coverage_from else None
    buys = sells = timed = untimed = 0
    for f in fills:
        if first is None:
            break
        if f.untimed and market != MARKET_KR:
            if f.traded_at.date() >= first:
                untimed += 1
            continue
        if f.untimed:
            d = f.traded_at.date()  # KST 날짜 그대로 = 한국 시장 날짜
        else:
            d = kr_date(f.traded_at) if market == MARKET_KR else us_date(f.traded_at)
        if d < first:
            continue
        timed += 1
        # D+1 ≤ d ≤ D+window ⇔ d-window ≤ D ≤ d-1 — 그 구간에 발표가 하나라도 있나.
        lo = bisect.bisect_left(days, d - timedelta(days=window_days))
        if lo < len(days) and days[lo] <= d - timedelta(days=1):
            if f.side == "buy":
                buys += 1
            elif f.side == "sell":
                sells += 1
    return {
        "window_days": window_days,
        "date_basis": market,
        "buys_after": buys,
        "sells_after": sells,
        "timed_fills": timed,
        "untimed_fills": untimed,
    }


__all__ = ["ET", "KST", "MARKET_KR", "MARKET_US", "WINDOW_DAYS", "FillPoint", "earnings_reaction", "kr_date", "us_date"]
