"""공시 행 저장과 동기화 — 종목당 하루 한 번만 원천(SEC · DART)에 묻는다.

* 누가 그 종목의 기록 페이지를 열 때, 이 프로세스에서 마지막으로 받은 지
  ``REFRESH_SECONDS`` 가 지났으면 SEC 목록을 다시 받아 새 공시만 더한다.
  실패하면 ``RETRY_SECONDS`` 동안 다시 묻지 않는다 (SEC 장애가 페이지마다
  기다림이 되지 않게). 크론은 없다.
* 받은 기록은 프로세스 메모리에만 둔다. 재시작하면 한 번 더 받을 뿐이고,
  행은 DB 에 남아 있으니 SEC 가 죽어 있어도 이미 받은 공시는 보인다.
* 같은 공시를 두 요청이 동시에 넣으면 유니크 제약이 하나를 막는다 — 그때는
  되돌리고 지나간다.
"""
from __future__ import annotations

import logging
import threading
import time

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db
from models.company_filing import SOURCE_DART, SOURCE_SEC, CompanyFiling

from .sec import ParsedFiling, parse_recent

logger = logging.getLogger(__name__)

REFRESH_SECONDS = 24 * 3600
RETRY_SECONDS = 3600

_LOCK = threading.Lock()
# "source:ticker" → (마지막 시도 시각, 성공했나)
_SYNCED: dict[str, tuple[float, bool]] = {}


def _due(key: str, now_ts: float) -> bool:
    with _LOCK:
        last = _SYNCED.get(key)
        if last is not None:
            ts, ok = last
            if now_ts - ts < (REFRESH_SECONDS if ok else RETRY_SECONDS):
                return False
        # 시도 중으로 먼저 표시 — 같은 프로세스의 동시 요청이 또 받지 않게.
        # 성공하면 아래 _mark 가 ok=True 로 덮는다.
        _SYNCED[key] = (now_ts, False)
        return True


def _mark(key: str, now_ts: float, ok: bool) -> None:
    with _LOCK:
        _SYNCED[key] = (now_ts, ok)


def reset_sync_state() -> None:
    """테스트용 — 프로세스 동기화 기록을 비운다."""
    with _LOCK:
        _SYNCED.clear()


def _store(source: str, key: str, cik: str | None, rows: list[ParsedFiling]) -> int:
    if not rows:
        return 0
    have = {
        a for (a,) in db.session.query(CompanyFiling.accession).filter(
            CompanyFiling.source == source, CompanyFiling.ticker == key,
        )
    }
    new = []
    for r in rows:
        if r.accession in have:
            continue
        have.add(r.accession)
        new.append(CompanyFiling(
            source=source, ticker=key, cik=cik, accession=r.accession,
            form=r.form, items=r.items or None, filed_on=r.filed_on, url=r.url,
            title=r.title,
        ))
    if not new:
        return 0
    db.session.add_all(new)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()  # 동시에 들어온 다른 요청이 먼저 넣었다
        return 0
    return len(new)


def _fetch(source: str, key: str) -> tuple[str | None, list[ParsedFiling]] | None:
    if source == SOURCE_DART:
        from . import dart

        return dart.fetch(key)
    from services.data.edgar import EdgarService

    cik, payload = EdgarService.get_submissions(key)
    if not payload:
        return None
    return cik, parse_recent(payload, cik)


def sync_ticker(key: str, *, source: str = SOURCE_SEC, now_ts: float | None = None) -> bool:
    """때가 됐으면 원천 목록을 받아 새 공시를 저장한다. 받아서 저장까지 했으면 True."""
    now_ts = time.time() if now_ts is None else now_ts
    marker = f"{source}:{key}"
    if not key or not _due(marker, now_ts):
        return False
    try:
        got = _fetch(source, key)
    except Exception as exc:  # 네트워크·파싱 — 페이지는 공시 없이 뜬다
        logger.warning("filing sync: %s fetch failed for %s: %s", source, key, exc)
        return False
    if got is None:
        return False
    try:
        _store(source, key, got[0], got[1])
    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.warning("filing sync: store failed for %s %s: %s", source, key, exc)
        return False
    _mark(marker, now_ts, ok=True)
    return True


def stored_filings(key: str, source: str = SOURCE_SEC) -> list[CompanyFiling]:
    """저장된 공시, 공시일 최신 먼저."""
    return (
        CompanyFiling.query
        .filter(CompanyFiling.source == source, CompanyFiling.ticker == key)
        .order_by(CompanyFiling.filed_on.desc(), CompanyFiling.id.desc())
        .all()
    )


__all__ = ["REFRESH_SECONDS", "RETRY_SECONDS", "reset_sync_state", "stored_filings", "sync_ticker"]
