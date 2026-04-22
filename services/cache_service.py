"""Signal cache and discovery cache management."""
import json
import logging
import threading
import time
from datetime import datetime, timezone

from extensions import db
from models import SignalCache
from services.legal_filter import scrub_signal

logger = logging.getLogger(__name__)

# ── In-memory caches ──
discover_cache: dict = {}  # user_id -> {ts, data}
DISCOVER_TTL = 7200        # 2 hours — extended 2026-04-22 to absorb FMP 402 bursts

ca_cache: dict = {}        # cross-asset cache

# ── Earnings Tone cache (90-day TTL, lazy-loaded from routes/ai.py) ──
# Structure: {ticker: {"data": {...}, "ts": unix_timestamp}}
# Earnings calls are quarterly, so 90 days comfortably covers one cycle.
# Only written by /api/ai/earnings-tone endpoint (Pro/Premium users).
# engine.py reads this cache to surface results without ever triggering
# a Claude API call from the hot analyze() path.
earnings_tone_cache: dict = {}
EARNINGS_TONE_TTL = 90 * 24 * 3600  # 90 days
_earnings_tone_lock = threading.Lock()

# Daily call budget for earnings-tone to cap Claude API spend even if many
# Pro users hit it. Reset on the calendar day (UTC).
EARNINGS_TONE_DAILY_LIMIT = 50
_earnings_tone_usage: dict = {"day": None, "count": 0}


def earnings_tone_cache_get(ticker: str):
    """Thread-safe read of the earnings-tone cache. Returns data dict or None."""
    if not ticker:
        return None
    ticker = ticker.upper().strip()
    with _earnings_tone_lock:
        entry = earnings_tone_cache.get(ticker)
        if not entry:
            return None
        if time.time() - entry.get("ts", 0) >= EARNINGS_TONE_TTL:
            return None
        return entry.get("data")


def earnings_tone_cache_set(ticker: str, data: dict) -> None:
    """Thread-safe write to the earnings-tone cache."""
    if not ticker or data is None:
        return
    ticker = ticker.upper().strip()
    with _earnings_tone_lock:
        earnings_tone_cache[ticker] = {"data": data, "ts": time.time()}


def earnings_tone_budget_check_and_increment() -> bool:
    """Returns True if the daily budget still has room (and increments usage).
    Returns False if today's limit has been reached — caller should reject with 429.
    """
    today = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d")
    with _earnings_tone_lock:
        if _earnings_tone_usage["day"] != today:
            _earnings_tone_usage["day"] = today
            _earnings_tone_usage["count"] = 0
        if _earnings_tone_usage["count"] >= EARNINGS_TONE_DAILY_LIMIT:
            return False
        _earnings_tone_usage["count"] += 1
        return True


def earnings_tone_budget_remaining() -> int:
    """Return how many calls are left in today's budget."""
    today = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d")
    with _earnings_tone_lock:
        if _earnings_tone_usage["day"] != today:
            return EARNINGS_TONE_DAILY_LIMIT
        return max(0, EARNINGS_TONE_DAILY_LIMIT - _earnings_tone_usage["count"])


def get_signal(ticker: str):
    """Read signal cache for a ticker.

    Returns the SignalCache row if it exists and is not stale.
    Returns None if the record is missing or has exceeded TTL_SECONDS,
    so callers know to trigger a fresh analysis pass.
    """
    row = db.session.get(SignalCache, ticker)
    if row is None:
        return None
    if row.is_stale():
        logger.debug("SignalCache stale for %s (updated_at=%s)", ticker, row.updated_at)
        return None
    return row


def save_signal(ticker: str, data: dict):
    """Upsert signal cache for a ticker. Always refreshes updated_at.

    Legal filter: free-text fields (commentary, summary, risk notes, ...) are
    scrubbed via services.legal_filter.scrub_signal BEFORE serialization so
    "매수 권고" / "포지션 축소 고려" never land in the DB. Engine/models code
    stays untouched — scrubbing happens at the storage boundary.
    """
    data = scrub_signal(data)
    c = db.session.get(SignalCache, ticker)
    if c:
        c.data_json = json.dumps(data, ensure_ascii=False)
        c.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        db.session.add(SignalCache(
            ticker=ticker,
            data_json=json.dumps(data, ensure_ascii=False),
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ))
    db.session.commit()


def cache_ticker(ticker: str, capital: float, engine):
    """Analyze and cache a single ticker."""
    try:
        r = engine.analyze(ticker, capital)
        if r:
            save_signal(ticker, r)
    except Exception as e:
        logger.error(f"Cache update failed {ticker}: {e}")
