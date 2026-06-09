"""Real daily NAV snapshot recorder — the honest source for the equity curve.

We compute the user's CURRENT NAV from live positions × live prices and upsert
one row per (user, day). We record what we actually observe; we never
reconstruct the past from today's holdings (that was the fabrication CEO kept
flagging). Best-effort: a failure here must never break the request that
triggered it.
"""
from __future__ import annotations

import logging
from datetime import date as _date, datetime, timezone

from extensions import db
from models import Position, PortfolioNavSnapshot
from services import fx_service
from services.container import realtime

logger = logging.getLogger(__name__)


def _is_kr(ticker: str) -> bool:
    from services.ticker_normalizer import is_korean_ticker
    return is_korean_ticker(ticker)


def compute_current_nav(user_id: int) -> dict | None:
    """Live NAV from current positions × realtime prices.

    Returns ``{nav_total_usd, nav_us_usd, nav_kr_krw, fx_rate}`` or ``None``
    when the user has no positions / no usable prices — i.e. nothing honest to
    record. NAV is unified to USD (KR converted at the observed FX rate); the
    native subtotals are kept for a future split KPI.
    """
    positions = Position.query.filter_by(user_id=user_id).all()
    if not positions:
        return None

    try:
        prices = realtime.get_prices_batch([p.ticker for p in positions]) or {}
    except Exception:
        logger.debug("nav_snapshot: realtime price batch failed", exc_info=True)
        prices = {}

    try:
        fx = float(fx_service.get_rate() or 0) or fx_service.FALLBACK_USDKRW
    except Exception:
        fx = fx_service.FALLBACK_USDKRW

    nav_us_usd = 0.0
    nav_kr_krw = 0.0
    priced = 0
    for p in positions:
        px = None
        rt = prices.get(p.ticker)
        if rt and rt.get("price"):
            try:
                px = float(rt["price"])
            except (TypeError, ValueError):
                px = None
        if px is None:
            # No live price → fall back to avg_cost so a held position still
            # counts (avoids understating NAV). Skip only if even that is 0.
            try:
                px = float(p.avg_cost or 0)
            except (TypeError, ValueError):
                px = 0.0
        if px <= 0:
            continue
        priced += 1
        mv = px * float(p.shares or 0)
        if _is_kr(p.ticker):
            nav_kr_krw += mv
        else:
            nav_us_usd += mv

    if priced == 0:
        return None

    nav_total_usd = nav_us_usd + (nav_kr_krw / fx if fx else 0.0)
    return {
        "nav_total_usd": round(nav_total_usd, 2),
        "nav_us_usd": round(nav_us_usd, 2),
        "nav_kr_krw": round(nav_kr_krw, 2),
        "fx_rate": round(fx, 4),
    }


def record_today_snapshot(user_id: int, today: _date | None = None) -> bool:
    """Upsert today's NAV row for the user. Best-effort; never raises.

    Idempotent: re-recording the same day UPDATES the row (latest intraday
    reading wins). Returns True iff a row was written/updated.
    """
    try:
        nav = compute_current_nav(user_id)
        if nav is None:
            return False
        day = today or datetime.now(timezone.utc).replace(tzinfo=None).date()
        row = (
            PortfolioNavSnapshot.query
            .filter_by(user_id=user_id, as_of_date=day)
            .one_or_none()
        )
        if row is None:
            row = PortfolioNavSnapshot(user_id=user_id, as_of_date=day)
            db.session.add(row)
        row.nav_total_usd = nav["nav_total_usd"]
        row.nav_us_usd = nav["nav_us_usd"]
        row.nav_kr_krw = nav["nav_kr_krw"]
        row.fx_rate = nav["fx_rate"]
        db.session.commit()
        return True
    except Exception:
        logger.debug("nav_snapshot: record failed", exc_info=True)
        try:
            db.session.rollback()
        except Exception:
            pass
        return False
