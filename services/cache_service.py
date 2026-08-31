"""Signal cache and discovery cache management."""
import json
import logging
import threading
import time
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from extensions import db
from models import SignalCache
from services.legal_filter import scrub_signal

logger = logging.getLogger(__name__)

# ── In-memory caches ──
discover_cache: dict = {}  # user_id -> {ts, data}
_discover_cache_lock = threading.Lock()  # P1-1: thread-safe discover_cache writes
DISCOVER_TTL = 7200        # 2 hours — extended 2026-04-22 to absorb FMP 402 bursts

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
# B3 review (2026-06-11, business_model_audit §B3): this budget stays
# GLOBAL by design — tone results are cached per ticker for 90 days and
# shared across users, so the cap gates *new-ticker analyses per day*, not
# users (the audit's "51st user gets 429" only bites on the 51st UNCACHED
# ticker). Per-user split would multiply spend without serving anyone
# faster. Backed by DailyAiBudget for the env lever + the 80% warning.
from services.ai_budget import DailyAiBudget  # noqa: E402

EARNINGS_TONE_DAILY_LIMIT = 50  # base floor; env PIVOX_EARNINGS_TONE_DAILY_LIMIT
_earnings_tone_budget = DailyAiBudget(
    "earnings_tone",
    EARNINGS_TONE_DAILY_LIMIT,
    env_var="PIVOX_EARNINGS_TONE_DAILY_LIMIT",
)



# ── AI 분석 결과 캐시 (SWOT / commentary / competitor / sector-trend) ──
# 2026-06-12 토큰 최적화: 이 4개 인터랙티브 엔드포인트는 ticker(또는 sector)
# 단위의 비개인화 분석인데 캐시가 전혀 없어 — 같은 종목을 두 유저가(또는 한
# 유저가 두 번) 열 때마다 동일한 Claude 호출이 반복됐다. earnings_tone(90d)
# 패턴을 따르되 입력(quant score/price)이 더 자주 변하므로 TTL 6h.
# 비개인화 결과의 유저간 공유는 §101 면제 트랙(불특정 다수 대상 정보 제공)
# 관점에서도 개인화보다 방어적이다. 개인화 경로(coaching/morning_summary/
# chat)는 절대 여기 캐시하지 않는다.
# Structure: {(endpoint, key): {"data": {...}, "ts": unix}}
ai_result_cache: dict = {}
AI_RESULT_TTL = 6 * 3600          # 6 h — quant 입력 갱신 주기와 균형
AI_RESULT_MAX_ENTRIES = 2000      # (4 endpoint × ~500 ticker) LRU 상한
_ai_result_lock = threading.Lock()


def ai_result_cache_get(endpoint: str, key: str):
    """Thread-safe read of the AI-result cache. Returns data dict or None."""
    if not endpoint or not key:
        return None
    ck = (endpoint, key.upper().strip())
    with _ai_result_lock:
        entry = ai_result_cache.get(ck)
        if not entry:
            return None
        if time.time() - entry.get("ts", 0) >= AI_RESULT_TTL:
            return None
        return entry.get("data")


def ai_result_cache_set(endpoint: str, key: str, data: dict) -> None:
    """Thread-safe write. LRU-prunes oldest 25% past AI_RESULT_MAX_ENTRIES."""
    if not endpoint or not key or data is None:
        return
    ck = (endpoint, key.upper().strip())
    with _ai_result_lock:
        ai_result_cache[ck] = {"data": data, "ts": time.time()}
        if len(ai_result_cache) > AI_RESULT_MAX_ENTRIES:
            ordered = sorted(
                ai_result_cache.items(),
                key=lambda kv: kv[1].get("ts", 0),
            )
            for old_key, _ in ordered[: len(ordered) // 4]:
                ai_result_cache.pop(old_key, None)


def safe_cache_blob(cached) -> dict:
    """Parse a SignalCache row's data_json — `{}` on absence/corruption.

    Wave-3 P3 (2026-06-10): a dozen route loops did
    ``json.loads(c.data_json)`` unguarded, so ONE corrupted/truncated cache
    row 500'd the user's entire watchlist/signals/alerts/portfolio response.
    get_signals already guarded (routes/signals.py); this is that guard,
    centralised so the next loop can't forget it.
    """
    if not cached or not getattr(cached, "data_json", None):
        return {}
    try:
        v = json.loads(cached.data_json)
        return v if isinstance(v, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.warning("safe_cache_blob: corrupt data_json for %s",
                       getattr(cached, "ticker", "?"))
        return {}

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


EARNINGS_TONE_MAX_ENTRIES = 1000  # P1-2: LRU cap — ~800 major tickers + headroom


def earnings_tone_cache_set(ticker: str, data: dict) -> None:
    """Thread-safe write to the earnings-tone cache.

    P1-2: LRU prune at EARNINGS_TONE_MAX_ENTRIES so the in-process dict
    cannot grow unbounded when many tickers are analyzed over 90-day windows.
    Mirrors the risk_snapshot_cache_set eviction pattern.
    """
    if not ticker or data is None:
        return
    ticker = ticker.upper().strip()
    with _earnings_tone_lock:
        earnings_tone_cache[ticker] = {"data": data, "ts": time.time()}
        if len(earnings_tone_cache) > EARNINGS_TONE_MAX_ENTRIES:
            # Evict oldest 25% — identical strategy to risk_snapshot_cache_set.
            ordered = sorted(
                earnings_tone_cache.items(),
                key=lambda kv: kv[1].get("ts", 0),
            )
            for old_key, _ in ordered[: len(ordered) // 4]:
                earnings_tone_cache.pop(old_key, None)


def earnings_tone_budget_check_and_increment() -> bool:
    """Returns True if the daily budget still has room (and increments usage).
    Returns False if today's limit has been reached — caller should reject with 429.

    Atomic check-and-spend via DailyAiBudget.try_consume() (same UTC-day
    semantics the old inline counter had, plus the env override and the
    once-a-day 80% exhaustion warning).
    """
    return _earnings_tone_budget.try_consume()


def earnings_tone_budget_remaining() -> int:
    """Return how many calls are left in today's budget.

    Reads the live DailyAiBudget snapshot — the same source of truth that
    earnings_tone_budget_check_and_increment() spends against. (Previously
    referenced a since-deleted ``_earnings_tone_usage`` dict and a fixed
    EARNINGS_TONE_DAILY_LIMIT constant, so it ignored the env override /
    cohort scaling and would NameError if ever called.)
    """
    snap = _earnings_tone_budget.snapshot()
    return max(0, snap["limit"] - snap["count"])


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


# P0-2: Per-user sizing fields that are computed from the requesting user's
# capital. These MUST NOT be stored in the shared ticker-keyed SignalCache —
# doing so leaks user A's portfolio size to user B who reads the same cache.
# Strip at the write boundary; callers that need sizing call hydrate_sizing().
_PER_USER_FIELDS = frozenset(("rec_inv", "rec_sh", "capital_needed", "capital_gap"))


def hydrate_sizing(cached_data: dict, capital_usd: float, capital_krw: float, price: float) -> dict:
    """Re-compute per-user sizing fields from a cached (stripped) signal dict.

    This mirrors the sizing logic in services/quant/engine.py so read callers
    get the correct values for the requesting user's capital without those
    values ever entering the shared cache.

    Returns a new dict (does not mutate cached_data).
    """
    out = dict(cached_data)
    try:
        is_kr = bool(out.get("is_korean", False))
        cap = float(capital_krw if is_kr else capital_usd) or 0.0
        p = float(price or out.get("price") or 0)
        if cap > 0 and p > 0:
            # Allocate 5% of available capital (conservative default — mirrors engine.py)
            alloc = cap * 0.05
            out["rec_inv"] = round(alloc, 2)
            shares = alloc / p
            out["rec_sh"] = round(shares, 6 if is_kr else 4)
            out["capital_needed"] = round(p * out["rec_sh"], 2)
            out["capital_gap"] = round(max(0.0, out["capital_needed"] - cap), 2)
    except Exception:
        # Non-fatal: return data without sizing rather than raising.
        pass
    return out


def save_signal(ticker: str, data: dict):
    """Upsert signal cache for a ticker. Always refreshes updated_at.

    Legal filter: free-text fields (commentary, summary, risk notes, ...) are
    scrubbed via services.legal_filter.scrub_signal BEFORE serialization so
    "매수 권고" / "포지션 축소 고려" never land in the DB. Engine/models code
    stays untouched — scrubbing happens at the storage boundary.

    P0-2: per-user sizing fields (rec_inv / rec_sh / capital_needed /
    capital_gap) are stripped BEFORE persisting so the shared ticker-keyed
    SignalCache never exposes one user's portfolio sizing to another user.
    Callers that need per-user sizing must call hydrate_sizing() on the read
    side, passing the current user's capital.
    """
    # Strip per-user sizing before scrub+persist (cross-user leak defence).
    data = {k: v for k, v in data.items() if k not in _PER_USER_FIELDS}
    data = scrub_signal(data)
    # 2026-05-17 wave 11 P2: fail-fast at the write boundary if any upstream
    # numerical pipeline let NaN/Inf through. Python's default `allow_nan=True`
    # emits `NaN`/`Infinity` literals — valid JSON neither the browser
    # `JSON.parse` nor any strict downstream consumer can read. The frontend
    # would crash with `Unexpected token N` and the server would have no idea.
    # `allow_nan=False` raises `ValueError` here so the offending model
    # surfaces in logs immediately (paired with wave 11 P1 fixes in
    # services/quant/models.py to scrub the upstream zeros).
    # 2026-05-17 wave 12 P0: SignalCache upsert race. The previous
    # check-then-add let two concurrent background `_refresh` threads
    # (signals.py:199-210 spawns one per stale ticker per user) both
    # see `c=None` for the same ticker, both `db.session.add(...)`,
    # and the second `commit()` raised IntegrityError that poisoned
    # the worker's session for the next request.
    #
    # Fix: optimistic UPDATE-first; if no row exists, INSERT and
    # gracefully catch the IntegrityError that means a sibling thread
    # raced us — fall back to UPDATE for that case so the writer that
    # finishes last still gets its data in.
    c = db.session.get(SignalCache, ticker)
    json_payload = json.dumps(data, ensure_ascii=False, allow_nan=False)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if c:
        c.data_json = json_payload
        c.updated_at = now
        db.session.commit()
        return

    db.session.add(SignalCache(
        ticker=ticker,
        data_json=json_payload,
        updated_at=now,
    ))
    try:
        db.session.commit()
    except IntegrityError:
        # Sibling thread won the race; roll back and retry as UPDATE.
        db.session.rollback()
        c = db.session.get(SignalCache, ticker)
        if c is None:
            # Genuinely couldn't reconcile — re-raise so the caller sees it.
            raise
        c.data_json = json_payload
        c.updated_at = now
        db.session.commit()


def cache_ticker(ticker: str) -> None:
    """Warm the SignalCache row for one ticker.

    Until 2026-08-31 this ran ``QuantEngine.analyze()`` and stored a full
    4-pillar scoring blob. The engine is gone with the surfaces that read
    those scores; what still reads this cache — the Portfolio surface — only
    needs identity and price: name, price, price_display, currency,
    is_korean, sector. So the warm path is now a metadata lookup, not an
    analysis run, which also drops it from 10-30s to one quote call.

    Silent on failure by design: a cache miss makes the Portfolio read fall
    back to the stored avg_cost, exactly as before.
    """
    try:
        from services.container import fetcher

        row = fetcher.quick_lookup(ticker)
        if not row or not row.get("ok"):
            return

        blob = {
            "ticker":        row.get("ticker", ticker),
            "name":          row.get("name"),
            "price":         row.get("price"),
            "price_display": row.get("price_display"),
            "currency":      row.get("currency"),
            "is_korean":     row.get("is_korean"),
        }

        # Sector is only used for the allocation donut; a snapshot call is
        # more expensive than the quote, so a miss leaves the field absent
        # and the donut buckets the position under "Unknown" as it already
        # does for any uncached ticker.
        try:
            snap = fetcher.get_stock_snapshot(ticker)
            if snap and snap.get("sector"):
                blob["sector"] = snap["sector"]
        except Exception:
            logger.debug("cache_ticker: sector lookup failed for %s", ticker, exc_info=True)

        save_signal(ticker, blob)
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


# ── Discover section SWR cache (B-07, 2026-05-10) ─────────────────────────
#
# stale-while-revalidate layer for routes/discover.py 4 sections (us/kr
# movers, sectors, screeners). FMP upstream sometimes 402/5xx-bursts; the
# previous fail-fast 503 made entire Discover page unusable for an hour.
#
# Memory [feedback_bug_fix_patterns] "stale fallback" pattern:
#   fresh   (< DISCOVER_FRESH_TTL)         → 200 + stale=false
#   stale   (DISCOVER_FRESH_TTL ~ MAX_AGE) → 200 + stale=true + last_updated
#   no data OR > DISCOVER_MAX_AGE          → 503 + retry_after
#
# We DO NOT serve mock/sample data — only previously-real upstream payloads
# whose freshness we annotate. That respects "no fake market levels"
# (자본시장법 거짓 정보 제공) while restoring graceful degradation.
#
# Storage: in-process dict (CEO directive: 추가 비용 0원, no Redis). Lock
# protects concurrent /api/discover/* requests across gunicorn workers'
# threads. Per-process: each gunicorn worker has its own copy — that's fine,
# this is a soft cache, not a source-of-truth.

_discover_section_cache: dict = {}    # key -> {"ts": float, "data": ...}
_discover_section_lock = threading.Lock()

DISCOVER_FRESH_TTL = 3600             # 60 min — extended 2026-05-13 (Bug #4)
                                      # to absorb FMP daily-quota cool-offs.
                                      # Market microstructure on movers/sectors
                                      # is stable on hour scales; fresh ⇒ stale
                                      # transition still tagged in payload.
DISCOVER_MAX_AGE = 86400              # 24 h — over this we refuse to serve

# Override TTLs for ad-hoc test scenarios. Tests set these via
# discover_section_cache_set_ttls(); production leaves the defaults.
_discover_ttl_override: dict = {"fresh": None, "max": None}


def _discover_ttls():
    fresh = _discover_ttl_override["fresh"] or DISCOVER_FRESH_TTL
    max_age = _discover_ttl_override["max"] or DISCOVER_MAX_AGE
    return fresh, max_age


def discover_section_cache_set_ttls(fresh, max_age) -> None:
    """Test helper — override SWR thresholds. Pass None to reset."""
    _discover_ttl_override["fresh"] = fresh
    _discover_ttl_override["max"] = max_age


def discover_section_cache_clear() -> None:
    """Test/admin helper — drop all cached section payloads."""
    with _discover_section_lock:
        _discover_section_cache.clear()


def discover_section_get(key: str):
    """Fetch the raw entry for a section key. Returns {ts, data} or None.

    Routes call this directly so they can decide fresh vs stale; we don't
    bake the freshness check into the getter because the caller needs the
    timestamp for the response envelope (last_updated).
    """
    if not key:
        return None
    with _discover_section_lock:
        entry = _discover_section_cache.get(key)
        if not entry:
            return None
        # Drop entries past the absolute max-age — never serve a 30-day-old
        # snapshot as "stale data". Memory bounded.
        _, max_age = _discover_ttls()
        if time.time() - entry.get("ts", 0) >= max_age:
            _discover_section_cache.pop(key, None)
            return None
        # Return a copy so callers can't mutate the cache by accident.
        return {"ts": entry["ts"], "data": entry["data"]}


def discover_section_set(key: str, data) -> None:
    """Persist a fresh section payload. Stamps ts=now()."""
    if not key or data is None:
        return
    with _discover_section_lock:
        _discover_section_cache[key] = {"ts": time.time(), "data": data}


def discover_section_classify(entry) -> str:
    """Return 'fresh', 'stale', or 'miss' for a cache entry from get()."""
    if not entry:
        return "miss"
    fresh, max_age = _discover_ttls()
    age = time.time() - entry.get("ts", 0)
    if age < fresh:
        return "fresh"
    if age < max_age:
        return "stale"
    return "miss"
