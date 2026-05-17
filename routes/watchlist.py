"""Watchlist routes."""
from __future__ import annotations

import json
import logging

from flask import Blueprint, request, jsonify
from flask_login import current_user

from extensions import db
from models import Watchlist, SignalCache
from services import cache_service
from services.container import engine
from services.error_responses import api_error
from services.name_resolver import canonical_display_name
from services.price_overlay import overlay_prices, parse_price_display
from services.ticker_normalizer import normalize_ticker
from .decorators import api_auth
from security import general_rate_limit

logger = logging.getLogger(__name__)

watchlist_bp = Blueprint("watchlist", __name__, url_prefix="/api/watchlist")


def _serialize(w: Watchlist, overlay_entry: dict | None = None) -> dict:
    """Build the response payload for a watchlist row.

    Preferred price source: realtime/non-stale overlay (Alpaca/KIS/SignalCache).
    Falls back to the blob-only cache (even stale) for non-price metadata like
    name / signal / score. Price fields stay 0 when no fresh source exists —
    we never render a days-old number as "current".
    """
    c = db.session.get(SignalCache, w.ticker)
    sd = json.loads(c.data_json) if c and c.data_json else {}
    is_kr = w.ticker.upper().endswith(".KS") or w.ticker.upper().endswith(".KQ")

    o = overlay_entry or {}
    last_price = o.get("price")
    change_1d_pct = o.get("change_pct")
    observed_at = o.get("observed_at")
    price_source = o.get("source") or "stale"

    # Bug-hunter 2026-04-30: when the price overlay is empty/stale, fall
    # back to SignalCache.data_json["change_pct"] (populated by signal
    # cache builders + price_overlay.py:130). Without this fallback every
    # watchlist row showed +0.00% even though detail/signals pages had
    # the real change. Prefer stale-but-real over fake-zero.
    if change_1d_pct is None and "change_pct" in sd:
        try:
            change_1d_pct = float(sd.get("change_pct"))
        except (TypeError, ValueError):
            change_1d_pct = None

    # Bug C (2026-04-24): Watchlist used to render "$0.0000" whenever the
    # overlay came up empty, even though SignalCache stored a valid
    # `price_display` like "$402.91". Derive a last-resort numeric price
    # from the display string so UI never shows $0 when a legible value
    # exists. Mark source "stale" so the UX chip is honest.
    if not last_price:
        parsed = parse_price_display(sd.get("price_display"))
        if parsed:
            last_price = parsed
            if not price_source or price_source == "stale":
                price_source = "stale_display"

    # Bug #9 (2026-05-13): 52W range was rendered "—" on watchlist for every
    # row even though detail/market pages already publish honest values
    # (KIS-sourced for KR, FMP/Alpaca for US). The numbers live in the
    # SignalCache snapshot under week52_high/week52_low — surface them as a
    # `range_52w: [lo, hi]` envelope matching the convention already used by
    # /api/market/indices and /api/market/profile/<t>. Returns None (not 0/0)
    # when either bound is missing so the UI shows em-dash honestly instead
    # of fabricating "$0.00 - $0.00".
    range_52w: list[float] | None = None
    snap = sd.get("snapshot") or {}
    lo = snap.get("week52_low")
    hi = snap.get("week52_high")
    try:
        if lo is not None and hi is not None:
            lo_f = float(lo)
            hi_f = float(hi)
            if lo_f > 0 and hi_f > 0 and hi_f >= lo_f:
                # KRW = integer display, USD = 2 dp. Matches market.py:842.
                dp = 0 if (sd.get("currency") == "KRW" or is_kr) else 2
                range_52w = [round(lo_f, dp), round(hi_f, dp)]
    except (TypeError, ValueError):
        range_52w = None

    return {
        "id": w.id,
        "ticker": w.ticker,
        "name": canonical_display_name(sd.get("name"), w.ticker),
        "note": w.note or "",
        "added_at": w.added_at.isoformat() if w.added_at else None,
        "price": last_price or 0,
        "last_price": last_price or 0,
        "price_display": sd.get("price_display", "—"),
        "change_pct": change_1d_pct or 0,
        "change_1d_pct": change_1d_pct or 0,
        "observed_at": observed_at,
        "price_source": price_source,
        "signal": sd.get("signal", "—"),
        "score": sd.get("score", 0),
        "currency": sd.get("currency", "KRW" if is_kr else "USD"),
        "is_korean": sd.get("is_korean", is_kr),
        "range_52w": range_52w,
    }


@watchlist_bp.route("")
@api_auth
def get_watchlist():
    items = (Watchlist.query
             .filter_by(user_id=current_user.id)
             .order_by(Watchlist.added_at.desc())
             .all())
    overlay = overlay_prices([w.ticker for w in items])
    out = [_serialize(w, overlay.get(w.ticker)) for w in items]
    return jsonify({"watchlist": out})


@watchlist_bp.route("", methods=["POST"])
@api_auth
@general_rate_limit
def add():
    d = request.get_json() or {}
    raw = (d.get("ticker") or "").strip()
    note = (d.get("note") or "").strip() or None
    if not raw:
        return api_error(
            en="Ticker required", kr="종목 코드가 필요합니다.",
            code="WATCHLIST_TICKER_REQUIRED", status=400,
        )
    if note and len(note) > 500:
        return api_error(
            en="Note too long (max 500 characters)",
            kr="메모는 최대 500자까지 가능합니다.",
            code="WATCHLIST_NOTE_TOO_LONG", status=400,
        )
    # Single-source normalization: bare 6-digit code → registry-guided
    # .KS/.KQ. Replaces the ad-hoc default-to-.KS rule that mis-routed
    # KOSDAQ tickers (e.g. 035760 CJ ENM).
    ticker = normalize_ticker(raw)
    if not ticker:
        return api_error(
            en="Ticker required", kr="종목 코드가 필요합니다.",
            code="WATCHLIST_TICKER_REQUIRED", status=400,
        )
    existing = Watchlist.query.filter_by(user_id=current_user.id, ticker=ticker).first()
    if existing:
        return api_error(
            en="Already in watchlist",
            kr="이미 관심 종목에 추가되어 있습니다.",
            code="WATCHLIST_DUPLICATE", status=409,
        )
    try:
        row = Watchlist(user_id=current_user.id, ticker=ticker, note=note)
        db.session.add(row)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("watchlist.add commit failed (ticker=%s)", ticker)
        return api_error(
            en="Failed to add to watchlist",
            kr="관심 종목 추가에 실패했습니다.",
            code="WATCHLIST_ADD_FAILED", status=500,
        )
    # Best-effort cache warm — never block the response on cache failures.
    try:
        cache_service.cache_ticker(ticker, current_user.available_capital, engine)
    except Exception:
        logger.exception("watchlist.add cache_ticker failed (ticker=%s)", ticker)
    overlay = overlay_prices([ticker])
    return jsonify({"ok": True, "ticker": ticker, "item": _serialize(row, overlay.get(ticker))})


@watchlist_bp.route("/<int:wid>", methods=["DELETE"])
@api_auth
@general_rate_limit
def remove(wid):
    w = db.session.get(Watchlist, wid)
    if not w or w.user_id != current_user.id:
        return api_error(
            en="Not found", kr="관심 종목을 찾을 수 없습니다.",
            code="WATCHLIST_NOT_FOUND", status=404,
        )
    try:
        db.session.delete(w)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("watchlist.remove commit failed (wid=%s)", wid)
        return api_error(
            en="Failed to remove from watchlist",
            kr="관심 종목 삭제에 실패했습니다.",
            code="WATCHLIST_REMOVE_FAILED", status=500,
        )
    return jsonify({"ok": True})


@watchlist_bp.route("/<int:wid>", methods=["PATCH"])
@api_auth
@general_rate_limit
def update(wid):
    """Patch the note on an existing watchlist row.

    Payload: {"note": "..."}   — empty string clears the note.
    Body is intentionally narrow: ticker changes are disallowed (delete +
    re-add instead), and we don't let the client rewrite added_at.
    """
    w = db.session.get(Watchlist, wid)
    if not w or w.user_id != current_user.id:
        return api_error(
            en="Not found", kr="관심 종목을 찾을 수 없습니다.",
            code="WATCHLIST_NOT_FOUND", status=404,
        )
    d = request.get_json() or {}
    if "note" in d:
        raw = d.get("note")
        if raw is None:
            w.note = None
        else:
            s = str(raw).strip()
            if len(s) > 500:
                return api_error(
            en="Note too long (max 500 characters)",
            kr="메모는 최대 500자까지 가능합니다.",
            code="WATCHLIST_NOTE_TOO_LONG", status=400,
        )
            w.note = s or None
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("watchlist.update commit failed (wid=%s)", wid)
        return api_error(
            en="Failed to update watchlist",
            kr="관심 종목 업데이트에 실패했습니다.",
            code="WATCHLIST_UPDATE_FAILED", status=500,
        )
    overlay = overlay_prices([w.ticker])
    return jsonify({"ok": True, "item": _serialize(w, overlay.get(w.ticker))})
