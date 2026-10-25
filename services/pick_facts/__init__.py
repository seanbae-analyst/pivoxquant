"""내가 고른 회사들 — 산 날 직전에 공시된 연간 숫자로 센다 (2026-10-25).

CEO "퀀트로 구상 가능한 것" → 시세 없는 팩터 지문. 유저가 최근 1년에 처음 산
종목마다, **산 날보다 먼저 공시된 가장 최근 연간 보고**의 숫자를 대고 세 가지를
센다:

* 순손실이었나 (순이익 < 0)
* 매출이 그 전 해보다 줄었나 (두 해 모두 산 날 전에 공시된 값)
* 부채가 자본보다 많았나 (자본이 0 이하면 그렇다고 본다)

규칙
----
* **산 뒤에 나온 숫자는 쓰지 않는다** (``filed_on`` ≤ 산 날). 과거 결정을 지금
  아는 것으로 비추지 않는다 — 퀀트의 기본(룩어헤드 금지).
* **개수만.** 점수·등급·"좋은 회사/나쁜 회사"·비율 없음. 회사 가치에 대한 말이
  아니라 유저가 고른 곳들에 공시된 사실을 센 것이다.
* **시세 없음.** 주가·시총·PER 을 쓰지 않는다 (MARKET_DATA_DISPLAY 와 무관).
* 원천: 미국 SEC ``companyfacts`` (``FILINGS_ENABLED``), 한국 OpenDART 주요계정
  (``DART_API_KEY`` 도 필요). 한 번 요청에 원천을 부르는 종목은 ``SYNC_BUDGET``
  개까지 — 나머지는 "받는 중"으로 세고 다음에 채운다.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from extensions import db
from models import TradeHistory
from models.company_filing import SOURCE_DART, SOURCE_SEC
from services.filing_timeline import filings_enabled, market_of, source_available
from services.filing_timeline.reaction import MARKET_KR
from services.pre_trade.friction_outcome import ticker_key
from services.profile.fifo_util import is_registration_row
from services.ticker_normalizer import normalize_ticker

from .store import facts_for, sync_facts

logger = logging.getLogger(__name__)

WINDOW_DAYS = 365
SYNC_BUDGET = 3
_KST = timedelta(hours=9)
_SOURCE_LABELS = {SOURCE_SEC: "SEC EDGAR", SOURCE_DART: "DART"}


def _kst_day(at: datetime) -> date:
    # 날짜만 아는 체결은 KST 날짜 00:00 으로 저장돼 있다 — 그대로 그 날짜.
    if (at.hour, at.minute, at.second, at.microsecond) == (0, 0, 0, 0):
        return at.date()
    return (at + _KST).date()


def as_of(rows: list, day: date) -> tuple[Any, Any] | None:
    """``day`` 전에 공시된 가장 최근 연간 값과 그 전 해 값 (둘 다 ``day`` 전 공시)."""
    known = [r for r in rows if r.filed_on < day and r.fiscal_end < day]
    if not known:
        return None
    latest = max(known, key=lambda r: r.fiscal_end)
    prev = next(
        (r for r in sorted(known, key=lambda r: r.fiscal_end, reverse=True)
         if 330 <= (latest.fiscal_end - r.fiscal_end).days <= 400),
        None,
    )
    return latest, prev


def pick_facts(user_id: int, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    since = now - timedelta(days=WINDOW_DAYS)
    rows = [
        t for t in TradeHistory.query.filter(
            TradeHistory.user_id == int(user_id), TradeHistory.traded_at >= since,
        ).all()
        if t.ticker and t.traded_at and (t.action or "").upper() == "BUY"  # // legal-ok — action value, compared only
        and not is_registration_row(t)
    ]
    rows.sort(key=lambda t: t.traded_at)
    first: dict[str, tuple[str, date, str | None]] = {}
    for t in rows:
        normalized = normalize_ticker(t.ticker)
        key = ticker_key(normalized)
        if key not in first:
            first[key] = (normalized, _kst_day(t.traded_at), (t.name or "").strip() or None)

    on = filings_enabled()
    budget = SYNC_BUDGET
    picks: list[dict[str, Any]] = []
    counts = {"net_loss": 0, "revenue_down": 0, "liabilities_over_equity": 0}
    pending = no_source = 0
    sources: set[str] = set()
    for key, (normalized, day, name) in first.items():
        market = market_of(normalized)
        if not on or not source_available(market):
            no_source += 1
            continue
        source = SOURCE_DART if market == MARKET_KR else SOURCE_SEC
        stored = facts_for(source, key)
        if budget > 0:
            try:
                if sync_facts(source, key):
                    budget -= 1
                    stored = facts_for(source, key)
            except Exception as exc:  # 한 종목 실패가 카드를 막지 않게
                db.session.rollback()
                logger.warning("pick_facts: sync failed for %s %s: %s", source, key, exc)
        hit = as_of(stored, day)
        if hit is None:
            pending += 1 if not stored else 0
            no_source += 1 if stored else 0
            continue
        latest, prev = hit
        loss = latest.net_income is not None and latest.net_income < 0
        down = (
            latest.revenue is not None and prev is not None and prev.revenue
            and latest.revenue < prev.revenue
        )
        lev = latest.equity is not None and (
            latest.equity <= 0 or (latest.liabilities is not None and latest.liabilities > latest.equity)
        )
        counts["net_loss"] += bool(loss)
        counts["revenue_down"] += bool(down)
        counts["liabilities_over_equity"] += bool(lev)
        sources.add(_SOURCE_LABELS[source])
        picks.append({
            "ticker": normalized,
            "name": name,
            "bought_on": day.isoformat(),
            "fiscal_end": latest.fiscal_end.isoformat(),
            "filed_on": latest.filed_on.isoformat(),
            "net_loss": bool(loss),
            "revenue_down": bool(down),
            "liabilities_over_equity": bool(lev),
            "source": _SOURCE_LABELS[source],
        })
    return {
        "window_days": WINDOW_DAYS,
        "picked": len(first),
        "with_facts": len(picks),
        "pending": pending,
        "no_facts": no_source,
        "counts": counts,
        "sources": sorted(sources),
        "picks": picks,
    }


__all__ = ["SYNC_BUDGET", "WINDOW_DAYS", "as_of", "pick_facts"]
