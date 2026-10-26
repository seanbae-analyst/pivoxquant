"""가설 다시 보기 — 리서치를 쓴 뒤 그 종목에 새 정기보고서·실적 발표가 나면 벨 알림.

2026-10-25 (CEO "다음꺼 진행해" — 공시 레이어 4단계). 리서치(services/
research_notes)는 "틀렸다고 볼 신호"와 다시 볼 날을 적어 둔다. 회사가 새 정기
보고서나 실적 발표를 내면 그 날짜가 오기 전이라도 다시 볼 거리가 생긴 것이다.
매일 08:20–23:20 KST 매시(``ops_research_filing_check`` — 서버가 08:20 에 자고
있어도 깨어 있는 다음 정각에 돈다) 채점 전 리서치가 있는
종목의 공시를 받고(services/filing_timeline/store — 종목당 하루 1번), 리서치를 쓴
날 **다음 날 이후** 나온 가장 최근 것 하나로 벨 알림을 남긴다.

규칙
----
* **사실만.** "새 공시 · Apple 분기보고서 (7/31)" + "N월 N일에 쓴 리서치가
  있어요." 공시를 해석하지 않고, 무엇을 하라고 하지 않는다.
* **유저 문장을 알림에 옮기지 않는다.** 리서치 본문·틀린 신호는 DB 에 암호화돼
  있는데 ``alerts.body`` 는 평문이다 — 링크(종목 기록)에서 본인이 본다.
* **벨 + 푸시.** 알림 설정의 "가설 다시 보기" 줄(``research_filing`` —
  models/user.py, 2026-10-25 CEO "푸시도 켜")로 앱 안·푸시를 따로 끈다.
* **한 공시에 한 번.** 제목에 공시 날짜가 들어가고 400일 안 같은 제목은 다시
  만들지 않는다. 같은 종목에 리서치가 여럿이어도 알림은 하나.
* 원천은 종목 기록과 같다: ``FILINGS_ENABLED``, 한국은 ``DART_API_KEY`` 도.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any

from models.company_filing import SOURCE_DART, SOURCE_SEC

logger = logging.getLogger(__name__)

KIND = "research_filing"
TICKER_BUDGET = 40
DEDUP_HOURS = 24 * 400
_KST = timedelta(hours=9)
_PERIODIC_SEC = frozenset({"10-K", "10-Q", "20-F", "40-F"})


def _relevant(row) -> bool:
    """정기보고서 원본 또는 실적 발표 원본."""
    from . import dart
    from .sec import is_earnings

    if row.source == SOURCE_DART:
        title = (row.title or "").strip()
        return (row.form == "A" and not title.startswith("[")) or dart.is_earnings(title)
    return row.form in _PERIODIC_SEC or is_earnings(row.form, row.items)


def _label(row) -> str:
    from .sec import label_for

    if row.source == SOURCE_DART:
        return (row.title or "").strip()
    return label_for(row.form, row.items) or row.form


def _display(normalized: str) -> str:
    try:
        from services.name_resolver import resolve_stock_name

        name = resolve_stock_name(normalized)
    except Exception:  # 이름은 꾸밈일 뿐
        name = None
    return (name or "").strip() or normalized.split(".")[0]


def run_once(*, now: datetime | None = None, ticker_budget: int = TICKER_BUDGET) -> dict[str, int]:
    from models import ResearchNote
    from services.alert import create_alert
    from services.pre_trade.friction_outcome import ticker_key
    from services.ticker_normalizer import normalize_ticker

    from . import filings_enabled, market_of, source_available
    from .reaction import MARKET_KR
    from .store import stored_filings, sync_ticker

    summary = {"notes": 0, "tickers": 0, "synced": 0, "alerts": 0}
    if not filings_enabled():
        return summary
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    today = (now + _KST).date()

    # (user, 종목) → 채점 전 리서치 중 가장 이른 작성일 (KST)
    earliest: dict[tuple[int, str], tuple[date, str, str]] = {}
    for n in ResearchNote.query.filter(ResearchNote.reviewed_at.is_(None)).all():
        normalized = normalize_ticker(n.ticker or "")
        market = market_of(normalized)
        if not normalized or not source_available(market) or n.created_at is None:
            continue
        summary["notes"] += 1
        key = ticker_key(normalized)
        written = (n.created_at + _KST).date()
        k = (int(n.user_id), key)
        if k not in earliest or written < earliest[k][0]:
            earliest[k] = (written, normalized, SOURCE_DART if market == MARKET_KR else SOURCE_SEC)

    tickers = sorted({(key, src) for (_u, key), (_w, _n, src) in earliest.items()})
    summary["tickers"] = len(tickers)
    for key, src in tickers[:ticker_budget]:
        try:
            if sync_ticker(key, source=src):
                summary["synced"] += 1
        except Exception as exc:  # 한 종목 실패가 나머지를 막지 않게
            logger.warning("research_filing_check: sync failed for %s %s: %s", src, key, exc)

    for (user_id, key), (written, normalized, src) in sorted(earliest.items()):
        fresh = [
            r for r in stored_filings(key, src)
            if written < r.filed_on <= today and _relevant(r)
        ]
        if not fresh:
            continue
        r = max(fresh, key=lambda x: (x.filed_on, x.id or 0))
        title = f"새 공시 · {_display(normalized)} {_label(r)} ({r.filed_on.month}/{r.filed_on.day})"
        body = f"{written.month}월 {written.day}일에 쓴 리서치가 있어요. 종목 기록에서 공시와 함께 볼 수 있어요."
        made = create_alert(
            user_id, KIND, title, body=body, ticker=normalized,
            link=f"/journal/stock/{normalized}",
            dedup_window_hours=DEDUP_HOURS, dedup_title_prefix=title,
        )
        if made is not None:
            summary["alerts"] += 1
    return summary


def main() -> int:
    """``services/scheduler/cron_jobs.py`` 의 ``_wrap_python_main`` 진입점 (0 = 성공)."""
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        from app import create_app
        from extensions import db
    except Exception as exc:
        logger.error("create_app import failed: %s", exc)
        return 1
    try:
        app = create_app(start_scheduler=False, populate_cache=False)
    except Exception as exc:
        logger.error("create_app() failed: %s", exc)
        return 1
    summary: dict[str, Any] = {}
    try:
        with app.app_context():
            try:
                summary = run_once()
            except Exception as exc:
                logger.exception("research filing check crashed: %s", exc)
                return 1
    finally:
        try:
            with app.app_context():
                db.engine.dispose()
        except Exception:
            logger.debug("engine dispose failed (non-fatal)", exc_info=True)
    print(f"research_filing_check summary: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
