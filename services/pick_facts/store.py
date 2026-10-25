"""연간 숫자 저장과 동기화 — 종목당 하루 한 번만 원천(SEC · DART)에 묻는다.

services/filing_timeline/store.py 와 같은 규율: 프로세스 메모리에 마지막 시도를
두고(성공 24시간 · 실패 1시간), 행은 DB 에 남긴다. 같은 회계연도는 처음 들어온
값을 지키고 덮어쓰지 않는다 — 가장 먼저 공시된 값이 그 해의 값이다.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date

from sqlalchemy.exc import IntegrityError

from extensions import db
from models.company_annual_fact import CompanyAnnualFact
from models.company_filing import SOURCE_DART

from .annual import AnnualRow, annual_rows_from_companyfacts, annual_rows_from_dart, earliest_per_year

logger = logging.getLogger(__name__)

REFRESH_SECONDS = 24 * 3600
RETRY_SECONDS = 3600
DART_YEARS = 3

_LOCK = threading.Lock()
_SYNCED: dict[str, tuple[float, bool]] = {}


def reset_sync_state() -> None:
    with _LOCK:
        _SYNCED.clear()


def _due(marker: str, now_ts: float) -> bool:
    with _LOCK:
        last = _SYNCED.get(marker)
        if last is not None and now_ts - last[0] < (REFRESH_SECONDS if last[1] else RETRY_SECONDS):
            return False
        _SYNCED[marker] = (now_ts, False)
        return True


def _fetch(source: str, key: str) -> list[AnnualRow] | None:
    if source == SOURCE_DART:
        from services.filing_timeline import dart

        if not dart.api_key():
            return None
        corp = dart.corp_code_for(key)
        if not corp:
            return None
        rows: list[AnnualRow] = []
        this_year = date.today().year
        for year in range(this_year - DART_YEARS, this_year):
            data = dart._get("fnlttSinglAcnt.json", {
                "corp_code": corp, "bsns_year": str(year), "reprt_code": "11011",
            }, timeout=dart.TIMEOUT).json()
            status = str(data.get("status") or "")
            if status == "013":
                continue
            if status != "000":
                logger.warning("pick_facts: DART %s for %s (%s)", status, key, data.get("message"))
                return None
            rows.extend(annual_rows_from_dart(data.get("list"), year))
        return earliest_per_year(rows)
    from services.data.edgar import EdgarService

    _cik, payload = EdgarService.get_companyfacts(key)
    if not payload:
        return None
    return annual_rows_from_companyfacts(payload)


def sync_facts(source: str, key: str, *, now_ts: float | None = None) -> bool:
    """때가 됐으면 원천에서 연간 숫자를 받아 새 회계연도만 저장. 받았으면 True."""
    now_ts = time.time() if now_ts is None else now_ts
    marker = f"{source}:{key}"
    if not key or not _due(marker, now_ts):
        return False
    try:
        rows = _fetch(source, key)
    except Exception as exc:  # 네트워크·파싱 — 카드는 "받는 중"으로 남는다
        logger.warning("pick_facts: %s fetch failed for %s: %s", source, key, exc)
        return False
    if rows is None:
        return False
    have = {
        d for (d,) in db.session.query(CompanyAnnualFact.fiscal_end).filter(
            CompanyAnnualFact.source == source, CompanyAnnualFact.ticker == key,
        )
    }
    new = [
        CompanyAnnualFact(
            source=source, ticker=key, fiscal_end=r.fiscal_end, filed_on=r.filed_on,
            revenue=r.revenue, net_income=r.net_income, liabilities=r.liabilities,
            equity=r.equity, currency=r.currency,
        )
        for r in rows if r.fiscal_end not in have
    ]
    if new:
        db.session.add_all(new)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
    with _LOCK:
        _SYNCED[marker] = (now_ts, True)
    return True


def facts_for(source: str, key: str) -> list[CompanyAnnualFact]:
    return (
        CompanyAnnualFact.query
        .filter(CompanyAnnualFact.source == source, CompanyAnnualFact.ticker == key)
        .order_by(CompanyAnnualFact.fiscal_end)
        .all()
    )


__all__ = ["facts_for", "reset_sync_state", "sync_facts"]
