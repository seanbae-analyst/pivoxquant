"""종목 기록에 끼우는 회사 공시 — 미국 SEC EDGAR · 한국 OpenDART (2026-10-25).

CEO "종목별 일어나고 있는 일" → 뉴스가 아니라 회사가 낸 공시 원문을 유저 기록
사이에 날짜로 끼운다 (/journal/stock/<ticker>). 유저가 더 적을 것은 없다.

규칙
----
* **사실만.** 무슨 공시가 언제 났는지와 원문 링크뿐이다. 요약·해석·"호재/악재"·
  점수가 없다. 미국은 양식에서 고정 이름표(sec.py), 한국은 금감원 공식
  보고서명(dart.py)을 그대로 쓴다.
* **개수만.** "실적 발표 다음 날부터 사흘 안에 산 것 / 판 것"을 센다
  (reaction.py — 왜 24시간이 아니라 공시일 기준인지도 거기 있다). 비율 없음.
* **플래그 뒤.** ``FILINGS_ENABLED`` (기본 켜짐, 2026-10-25 대표 지시 — 끄면 어느
  원천도 부르지 않는다). 한국은 ``DART_API_KEY`` 가 있어야 켜진다.
* **페이지를 막지 않는다.** 원천이 응답하지 않으면 공시 없이 뜬다 (store.py).

출처 표기: "SEC EDGAR"(날짜는 미국 날짜) · "DART"(금융감독원 전자공시).
"""
from __future__ import annotations

import re
from datetime import date

from flask import current_app

from models.company_filing import SOURCE_DART, SOURCE_SEC

from . import dart
from .reaction import MARKET_KR, MARKET_US, WINDOW_DAYS, FillPoint, earnings_reaction
from .sec import is_earnings, label_for
from .store import stored_filings, sync_ticker

SOURCE_LABELS = {SOURCE_SEC: "SEC EDGAR", SOURCE_DART: "DART"}
SOURCE_LABEL = SOURCE_LABELS[SOURCE_SEC]
MAX_TIMELINE_FILINGS = 40

_KR_SUFFIXES = (".KS", ".KQ", ".KRX")
_US_SYMBOL = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
_KR_CODE = re.compile(r"^[0-9][0-9A-Z]{5}$")


def filings_enabled() -> bool:
    """Config 플래그. 요청·테스트가 ``current_app.config`` 로 덮어쓴다."""
    try:
        return bool(current_app.config.get("FILINGS_ENABLED", False))
    except RuntimeError:  # 앱 컨텍스트 밖
        return False


def market_of(normalized: str) -> str | None:
    """정규화된 티커 → "us" | "kr" | None (어느 공시 원천에도 없음)."""
    t = (normalized or "").strip().upper()
    if not t:
        return None
    if t.endswith(_KR_SUFFIXES):
        return MARKET_KR if _KR_CODE.match(t.rsplit(".", 1)[0]) else None
    if _KR_CODE.match(t):
        return MARKET_KR
    return MARKET_US if _US_SYMBOL.match(t) else None


def is_us_ticker(normalized: str) -> bool:
    return market_of(normalized) == MARKET_US


def source_available(market: str | None) -> bool:
    if market == MARKET_US:
        return True
    if market == MARKET_KR:
        return bool(dart.api_key())
    return False


def _event(r) -> dict | None:
    if r.source == SOURCE_DART:
        label = (r.title or "").strip() or None
        earnings = dart.is_earnings(r.title)
        form = dart.TYPE_NAMES.get(r.form, r.form)
    else:
        label = label_for(r.form, r.items)
        earnings = is_earnings(r.form, r.items)
        form = r.form
    if label is None:
        return None
    return {
        "kind": "filing",
        # 날짜만 아는 값 — 날짜만 아는 체결과 같은 규약(그 날짜의 00:00).
        "at": f"{r.filed_on.isoformat()}T00:00:00",
        "filed_on": r.filed_on.isoformat(),
        "form": form,
        "label": label,
        "earnings": earnings,
        "url": r.url,
        "source": SOURCE_LABELS.get(r.source, r.source),
    }


def filing_timeline(
    key: str,
    *,
    fills: list[FillPoint],
    since: date,
    market: str = MARKET_US,
    now_ts: float | None = None,
) -> dict | None:
    """``key`` 종목의 공시 → ``{"events": [...], "reaction": {...} | None}``.

    ``since`` (유저의 첫 기록 무렵) 이후 공시만 타임라인에 넣는다 — 최신 먼저,
    최대 ``MAX_TIMELINE_FILINGS`` 건. 저장된 공시가 하나도 없으면 None.
    ``reaction`` 은 그 기간에 실적 발표가 있었을 때만 있다.
    """
    source = SOURCE_DART if market == MARKET_KR else SOURCE_SEC
    sync_ticker(key, source=source, now_ts=now_ts)
    rows = stored_filings(key, source)
    if not rows:
        return None

    events = []
    for r in rows:
        if r.filed_on < since:
            break  # 최신 먼저 정렬
        e = _event(r)
        if e is None:
            continue
        events.append(e)
        if len(events) >= MAX_TIMELINE_FILINGS:
            break

    earnings_days = [r.filed_on for r in rows if (_event(r) or {}).get("earnings")]
    earnings_in_view = sum(1 for d in earnings_days if d >= since)
    reaction = None
    if earnings_in_view:
        reaction = earnings_reaction(
            fills, earnings_days, coverage_from=min(r.filed_on for r in rows), market=market,
        )
        reaction["earnings"] = earnings_in_view
    return {"events": events, "reaction": reaction}


__all__ = [
    "MAX_TIMELINE_FILINGS",
    "SOURCE_LABEL",
    "SOURCE_LABELS",
    "WINDOW_DAYS",
    "FillPoint",
    "filing_timeline",
    "filings_enabled",
    "is_us_ticker",
    "market_of",
    "source_available",
]
