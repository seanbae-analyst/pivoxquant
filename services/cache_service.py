"""Signal cache and risk-snapshot cache management."""
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

    This originally mirrored the sizing logic in services/quant/engine.py so
    read callers got the correct values for the requesting user's capital
    without those values ever entering the shared cache. That engine was
    deleted 2026-08-31, so this function is now the ONLY implementation of
    the sizing math — there is no upstream left to re-sync against.

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

        from services.price_overlay import parse_price_display

        # `price` is the numeric field every reader prefers; `price_display`
        # is the pre-formatted string. When the quote path returned only the
        # display string, recover the number from it rather than storing a
        # row whose numeric field is None (test_price_display_fallback_present
        # pins this invariant repo-wide).
        price = row.get("price")
        display = row.get("price_display")
        if price is None:
            price = parse_price_display(display)

        blob = {
            "ticker":        row.get("ticker", ticker),
            "name":          row.get("name"),
            "price":         price,
            "price_display": display,
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
# tolerance.
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
