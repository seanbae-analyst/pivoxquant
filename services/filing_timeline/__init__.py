"""종목 기록에 끼우는 미국 회사 공시 (SEC EDGAR) — 2026-10-25.

CEO "종목별 일어나고 있는 일" → 뉴스가 아니라 회사가 SEC 에 낸 공시 원문을
유저 기록 사이에 날짜로 끼운다 (/journal/stock/<ticker>). 유저가 더 적을 것은
없다.

규칙
----
* **사실만.** 무슨 양식이 언제 났는지와 원문 링크뿐이다. 제목 요약·해석·
  "호재/악재"·점수가 없다. 이름표는 양식에서 고정 목록으로 붙인다 (sec.py).
* **개수만.** "실적 발표 다음 날부터 사흘 안에 산 것 / 판 것"을 센다
  (reaction.py — 왜 24시간이 아니라 공시일 기준인지도 거기 있다). 비율 없음.
* **플래그 뒤.** ``FILINGS_ENABLED`` (기본 켜짐, 2026-10-25 대표 지시 — 끄면 SEC 를
  부르지 않는다).
* **미국 종목만.** 한국 종목(.KS/.KQ/.KRX)은 오픈다트 몫이라 여기서 다루지 않는다.
* **페이지를 막지 않는다.** SEC 가 응답하지 않으면 공시 없이 뜬다 (store.py).

출처 표기: "SEC EDGAR". sec.gov 정보는 허락 없이 복사·재배포할 수 있다
(sec.gov 웹사이트 정책, 2026-10-25 원문 확인). 공시 날짜는 미국 날짜다.
"""
from __future__ import annotations

import re
from datetime import date

from flask import current_app

from .reaction import WINDOW_DAYS, FillPoint, earnings_reaction
from .sec import is_earnings, label_for
from .store import stored_filings, sync_ticker

SOURCE_LABEL = "SEC EDGAR"
MAX_TIMELINE_FILINGS = 40

_KR_SUFFIXES = (".KS", ".KQ", ".KRX")
_US_SYMBOL = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def filings_enabled() -> bool:
    """Config 플래그. 요청·테스트가 ``current_app.config`` 로 덮어쓴다."""
    try:
        return bool(current_app.config.get("FILINGS_ENABLED", False))
    except RuntimeError:  # 앱 컨텍스트 밖
        return False


def is_us_ticker(normalized: str) -> bool:
    t = (normalized or "").strip().upper()
    if not t or t.endswith(_KR_SUFFIXES):
        return False
    return bool(_US_SYMBOL.match(t))


def filing_timeline(
    key: str,
    *,
    fills: list[FillPoint],
    since: date,
    now_ts: float | None = None,
) -> dict | None:
    """``key`` 종목의 공시 → ``{"events": [...], "reaction": {...} | None}``.

    ``since`` (유저의 첫 기록 무렵) 이후 공시만 타임라인에 넣는다 — 최신 먼저,
    최대 ``MAX_TIMELINE_FILINGS`` 건. 저장된 공시가 하나도 없으면 None.
    ``reaction`` 은 그 기간에 실적 발표가 있었을 때만 있다.
    """
    sync_ticker(key, now_ts=now_ts)
    rows = stored_filings(key)
    if not rows:
        return None

    events = []
    for r in rows:
        if r.filed_on < since:
            break  # 최신 먼저 정렬
        label = label_for(r.form, r.items)
        if label is None:
            continue
        events.append({
            "kind": "filing",
            # 날짜만 아는 값 — 날짜만 아는 체결과 같은 규약(그 날짜의 00:00).
            "at": f"{r.filed_on.isoformat()}T00:00:00",
            "filed_on": r.filed_on.isoformat(),
            "form": r.form,
            "label": label,
            "earnings": is_earnings(r.form, r.items),
            "url": r.url,
            "source": SOURCE_LABEL,
        })
        if len(events) >= MAX_TIMELINE_FILINGS:
            break

    earnings_days = [r.filed_on for r in rows if is_earnings(r.form, r.items)]
    earnings_in_view = sum(1 for d in earnings_days if d >= since)
    reaction = None
    if earnings_in_view:
        reaction = earnings_reaction(
            fills, earnings_days, coverage_from=min(r.filed_on for r in rows),
        )
        reaction["earnings"] = earnings_in_view
    return {"events": events, "reaction": reaction}


__all__ = [
    "MAX_TIMELINE_FILINGS",
    "SOURCE_LABEL",
    "WINDOW_DAYS",
    "FillPoint",
    "filing_timeline",
    "filings_enabled",
    "is_us_ticker",
]
