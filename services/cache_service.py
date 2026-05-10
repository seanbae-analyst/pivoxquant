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
        logger.error("Cache update failed %s: %s", ticker, e)


# ── Risk portfolio-snapshot cache (Perf P0-2, 2026-05-10) ─────────────────
#
# Each /api/risk/* endpoint calls _portfolio_snapshot() which fans out to
# fetcher.get_price_history(ticker, "3mo") for every position (FMP/Alpaca
# round-trip), realtime.get_prices_batch, and a pandas DataFrame build.
# That's ~500ms-3s p99 per request; multiple risk endpoints on a single
# page render compound the cost.
#
# Cache key: (user_id, positions_signature). positions_signature is a
# stable hash of the user's (ticker, shares, avg_cost) tuples — so the
# cache invalidates the moment a position is added/edited/closed (no
# stale data after a trade).
#
# TTL: 5 minutes. The underlying inputs (price history, VIX) move on
# minute scales but the risk metrics (HHI, VaR, correlation matrix) are
# stable on 5-min windows. Well within project's existing observability
# tolerance — engine.py / discover_cache use 2h TTL.
#
# Memory: small dict, capped via simple LRU prune at 256 entries (one
# user typically has 1-2 active position-sets per 5-min window). Free,
# in-process, no Redis dependency (CEO directive: 추가 비용 0원).

_risk_snapshot_cache: dict = {}  # (user_id, sig) -> {ts, payload}
_risk_snapshot_lock = threading.Lock()
RISK_SNAPSHOT_TTL = 300            # 5 minutes
RISK_SNAPSHOT_MAX_ENTRIES = 256


def risk_snapshot_cache_get(user_id, signature: str):
    """Thread-safe read. Returns the cached payload or None."""
    if not user_id or not signature:
        return None
    key = (user_id, signature)
    with _risk_snapshot_lock:
        entry = _risk_snapshot_cache.get(key)
        if not entry:
            return None
        if time.time() - entry.get("ts", 0) >= RISK_SNAPSHOT_TTL:
            _risk_snapshot_cache.pop(key, None)
            return None
        return entry.get("payload")


def risk_snapshot_cache_set(user_id, signature: str, payload) -> None:
    """Thread-safe write. Best-effort LRU prune when over MAX_ENTRIES."""
    if not user_id or not signature or payload is None:
        return
    key = (user_id, signature)
    with _risk_snapshot_lock:
        _risk_snapshot_cache[key] = {"payload": payload, "ts": time.time()}
        if len(_risk_snapshot_cache) > RISK_SNAPSHOT_MAX_ENTRIES:
            ordered = sorted(
                _risk_snapshot_cache.items(),
                key=lambda kv: kv[1].get("ts", 0),
            )
            for old_key, _ in ordered[: len(ordered) // 4]:
                _risk_snapshot_cache.pop(old_key, None)


def risk_snapshot_cache_clear() -> None:
    """Test/admin helper — drop all cached snapshots."""
    with _risk_snapshot_lock:
        _risk_snapshot_cache.clear()
