"""Earnings Pre-Brief endpoints — surfacing the upcoming-earnings queue.

Endpoints
---------
  GET /api/brief/earnings/upcoming?days=7
      → { "next_event": {ticker, name, when, eps_est, rev_est, implied_move},
          "queue":      [{ticker, name, when}, ...] }

Data sources (official, licensed only — see `feedback_official_data_only`)
  • FMP `/earnings-calendar` (via services.data.fmp.get_earnings_calendar)
    - 24h TTL cache inside fmp_service; we additionally short-circuit
      below by hitting one FMP call per distinct ticker, not per row.
  • FMP `/quote` for `priceAvg30` (implied-move denominator) — best-effort.
  • Position table for portfolio-first prioritisation; falls back to
    Watchlist when the user holds nothing.

NOT used:
  • yfinance / pykrx / 네이버 finance / any unofficial scraping.

Legal posture
  • Read-only listing. No advice, no BUY/SELL, no targets.
  • All response strings pass through `legal_scrub_response`.

Caching
  • Process-local 6-hour TTL keyed on (user_id, days). The underlying FMP
    cache is 24h, so the wall clock for a stale row never exceeds ~6h+24h
    = 30h, well inside the "weekly horizon" the card promises.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from flask import Blueprint, jsonify, request
from flask_login import current_user

from models import Position, Watchlist
from services.name_resolver import canonical_display_name
from .decorators import api_auth, legal_scrub_response

logger = logging.getLogger(__name__)

brief_bp = Blueprint("brief", __name__, url_prefix="/api/brief")


# ── Cache (process-local, 6h TTL) ───────────────────────────────────────────

_CACHE_TTL_SECONDS = 6 * 3600
_cache: dict[tuple[int, int], tuple[float, dict]] = {}
_cache_lock = threading.Lock()


def _cache_get(user_id: int, days: int) -> Optional[dict]:
    with _cache_lock:
        item = _cache.get((user_id, days))
    if not item:
        return None
    ts, payload = item
    if (datetime.now(timezone.utc).timestamp() - ts) > _CACHE_TTL_SECONDS:
        return None
    return payload


def _cache_set(user_id: int, days: int, payload: dict) -> None:
    with _cache_lock:
        _cache[(user_id, days)] = (datetime.now(timezone.utc).timestamp(), payload)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _user_tickers() -> list[str]:
    """Holdings first, then watchlist. Deduped, preserving order."""
    tickers: list[str] = []
    seen: set[str] = set()

    try:
        positions = (
            Position.query
            .filter_by(user_id=current_user.id)
            .filter(Position.shares > 0)
            .all()
        )
        for p in positions:
            t = (p.ticker or "").upper()
            if t and t not in seen:
                seen.add(t)
                tickers.append(t)
    except Exception:
        logger.debug("silent-fallback: brief._user_tickers positions", exc_info=True)

    try:
        wl = Watchlist.query.filter_by(user_id=current_user.id).all()
        for w in wl:
            t = (w.ticker or "").upper()
            if t and t not in seen:
                seen.add(t)
                tickers.append(t)
    except Exception:
        logger.debug("silent-fallback: brief._user_tickers watchlist", exc_info=True)

    return tickers


def _parse_row_datetime(row: dict) -> Optional[datetime]:
    """FMP earnings rows carry either ``date`` (YYYY-MM-DD) plus optional
    ``time`` ("bmo"/"amc"/"HH:MM"), or already a full ISO timestamp.

    Returns a naive UTC datetime (consistent with services/artifacts/...).
    """
    d = row.get("date") or row.get("epochDate")
    if not d:
        return None
    try:
        # FMP date is YYYY-MM-DD
        s = str(d)[:10]
        base = datetime.strptime(s, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None

    t_raw = (row.get("time") or "").strip().lower()
    if t_raw in {"bmo", "before market open", "pre-market"}:
        base = base.replace(hour=12, minute=0)  # ~07:00 ET → 12:00 UTC
    elif t_raw in {"amc", "after market close", "post-market"}:
        base = base.replace(hour=21, minute=0)  # ~17:00 ET → 21:00 UTC
    elif ":" in t_raw:
        try:
            hh, mm = t_raw.split(":")[:2]
            base = base.replace(hour=int(hh), minute=int(mm))
        except ValueError:
            base = base.replace(hour=20, minute=0)
    else:
        base = base.replace(hour=20, minute=0)
    return base


def _safe_get_earnings_calendar(ticker: str, days_ahead: int) -> list[dict]:
    """FMP earnings calendar wrapper — never raises."""
    try:
        from services.data import fmp as fmp_mod
        rows = fmp_mod.get_earnings_calendar(ticker=ticker, days_ahead=days_ahead)
        return rows if isinstance(rows, list) else []
    except Exception:
        logger.debug("silent-fallback: brief earnings calendar %s", ticker,
                     exc_info=True)
        return []


def _safe_quote(ticker: str) -> Optional[dict]:
    try:
        from services.data import fmp as fmp_mod
        q = fmp_mod.get_quote(ticker)
        if isinstance(q, list):
            return q[0] if q else None
        return q if isinstance(q, dict) else None
    except Exception:
        logger.debug("silent-fallback: brief quote %s", ticker, exc_info=True)
        return None


def _format_revenue_millions(row: dict) -> Optional[float]:
    """FMP revenueEstimated in USD; surface as millions."""
    rev = row.get("revenueEstimated")
    try:
        rev_f = float(rev) if rev is not None else None
    except (TypeError, ValueError):
        return None
    if rev_f is None or rev_f <= 0:
        return None
    # Heuristic from artifacts service: >1e6 means raw USD.
    return round(rev_f / 1_000_000, 1) if rev_f > 1_000_000 else round(rev_f, 1)


def _implied_move_pct(quote: Optional[dict]) -> Optional[float]:
    """Best-effort implied-move proxy.

    True implied move requires straddle pricing — we don't ingest options
    chains. As a non-misleading placeholder we report the 30-day average
    daily move (changesPercentage relative to priceAvg30 surrogate) when
    available; otherwise ``None`` so the card shows an em-dash.
    """
    if not quote:
        return None
    try:
        price = quote.get("price")
        avg30 = quote.get("priceAvg30") or quote.get("priceAvg50")
        if not price or not avg30:
            return None
        pct = abs((float(price) - float(avg30)) / float(avg30)) * 100.0
        return round(pct, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _build_payload(rows: list[dict]) -> dict:
    """Translate the merged FMP rows into the response shape."""
    if not rows:
        return {"next_event": None, "queue": []}

    next_row = rows[0]
    next_event = {
        "ticker":       next_row["ticker"],
        "name":         next_row["name"],
        "when":         next_row["when"].isoformat() + "Z",
        "eps_est":      next_row.get("eps_est"),
        "rev_est":      next_row.get("rev_est"),
        "implied_move": next_row.get("implied_move"),
    }

    queue = [
        {
            "ticker": r["ticker"],
            "name":   r["name"],
            "when":   r["when"].isoformat() + "Z",
        }
        for r in rows[1:4]  # next 3 rows
    ]

    return {"next_event": next_event, "queue": queue}


# ── Route ───────────────────────────────────────────────────────────────────

@brief_bp.route("/earnings/upcoming", methods=["GET"])
@api_auth
@legal_scrub_response
def upcoming_earnings():
    """Return next earnings event + 7-day queue for the user.

    Query
      days (int, default 7, range 1..30)
    """
    try:
        days = int(request.args.get("days", 7))
    except (TypeError, ValueError):
        days = 7
    if days < 1:
        days = 1
    if days > 30:
        days = 30

    cached = _cache_get(current_user.id, days)
    if cached is not None:
        return jsonify(cached)

    tickers = _user_tickers()
    if not tickers:
        # Empty portfolio + empty watchlist → empty queue, NOT 404.
        payload: dict[str, Any] = {"next_event": None, "queue": []}
        _cache_set(current_user.id, days, payload)
        return jsonify(payload)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    horizon = now + timedelta(days=days)

    merged: list[dict[str, Any]] = []
    # Dedup by (ticker, calendar-date) — FMP occasionally returns multiple
    # rows per event (different fiscal-period rows, class-share alts, BMO/AMC
    # variants). The brief card only needs one row per (issuer, event-day).
    seen_keys: set[tuple[str, str]] = set()
    for ticker in tickers:
        # FMP earnings-calendar is per-ticker; days_ahead aligns with caller.
        cal = _safe_get_earnings_calendar(ticker, days_ahead=days + 1)
        for row in cal:
            dt = _parse_row_datetime(row)
            if dt is None or not (now <= dt <= horizon):
                continue
            key = (ticker, dt.date().isoformat())
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged.append({"ticker": ticker, "dt": dt, "row": row})

    if not merged:
        payload = {"next_event": None, "queue": []}
        _cache_set(current_user.id, days, payload)
        return jsonify(payload)

    # Earliest first; truncate to next 4 (1 headline + 3 queue rows).
    merged.sort(key=lambda r: r["dt"])
    merged = merged[:4]

    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(merged):
        ticker = item["ticker"]
        row = item["row"]
        dt = item["dt"]

        # Display name — KR Korean wins per `feedback_ticker_display`.
        name = canonical_display_name(None, ticker)

        eps_est: Optional[float] = None
        try:
            v = row.get("epsEstimated")
            eps_est = float(v) if v is not None else None
        except (TypeError, ValueError):
            eps_est = None

        rev_est = _format_revenue_millions(row)

        # Only fetch quote for the headline event — minimises FMP budget.
        implied = None
        if idx == 0:
            implied = _implied_move_pct(_safe_quote(ticker))

        rows.append({
            "ticker":       ticker,
            "name":         name,
            "when":         dt,
            "eps_est":      eps_est,
            "rev_est":      rev_est,
            "implied_move": implied,
        })

    payload = _build_payload(rows)
    _cache_set(current_user.id, days, payload)
    return jsonify(payload)
