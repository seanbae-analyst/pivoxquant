"""보유 종목 공시 사실표 — 정기공시 재무제표만 쓰고 시세는 쓰지 않는다.

미국 = SEC EDGAR (companyfacts), 한국 = DART (금융감독원 전자공시 오픈API).
둘 다 공시 원천이라 벤더 시세 표시 플래그(``MARKET_DATA_DISPLAY_ENABLED``)와
무관하다 — FMP·KIS 를 한 번도 부르지 않는다.

"내 평단 기준" 숫자는 라우트가 유저의 ``Position.avg_cost`` 로 붙인다. 이 모듈의
캐시는 티커 단위 공개 데이터만 담는다 (유저 데이터 없음 — cache poisoning 무관).
"""
from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

TTL_SECONDS = 6 * 3600       # 공시는 분기 단위 — 6시간이면 충분히 신선하다
TTL_MISS_SECONDS = 30 * 60   # 실패·미지원은 짧게 (일시 장애를 6시간 굳히지 않는다)

_cache: dict[str, tuple[float, dict | None]] = {}
_lock = threading.Lock()


def market_of(ticker: str) -> str | None:
    t = (ticker or "").upper()
    if t.endswith((".KS", ".KQ")):
        return "KR"
    if t and "." not in t:
        return "US"
    return None


def source_configured(market: str | None) -> bool:
    """EDGAR 는 키가 없다. DART 는 DART_API_KEY 가 있어야 한다."""
    if market == "KR":
        from services.filings import dart_facts

        return bool(dart_facts.api_key())
    return market == "US"


def _compute(ticker: str) -> dict | None:
    market = market_of(ticker)
    if market == "US":
        from services.filings import edgar_facts

        raw = edgar_facts.fetch_companyfacts(ticker)
        return edgar_facts.compute(raw) if raw else None
    if market == "KR":
        from services.filings import dart_facts

        return dart_facts.facts_for(ticker)
    return None


def get_facts(ticker: str) -> dict | None:
    """티커 → 공통 사실표, 또는 None (미지원 시장 · 공시 없음 · 원천 장애)."""
    key = (ticker or "").upper()
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    try:
        facts = _compute(key)
    except Exception:
        logger.exception("filing facts failed for %s", key)
        facts = None
    with _lock:
        _cache[key] = (now + (TTL_SECONDS if facts else TTL_MISS_SECONDS), facts)
    return facts


def clear_cache() -> None:
    with _lock:
        _cache.clear()
