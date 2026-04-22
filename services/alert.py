"""Alert creation service — NotificationDropdown bell backend.

Neutral, observation-only language only. BUY/SELL/recommend/advice/target
are banned in title and body. Use verbs like reached / noted / observed /
ready / complete.

Dedup: callers are expected to check cadence; this module is a thin
insert wrapper. Callers that fire frequently (e.g. 52w high sweeps)
should pass a dedup_window_hours to skip if an equivalent alert was
raised recently for the same (user_id, kind, ticker) triple.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from extensions import db
from models import Alert

logger = logging.getLogger(__name__)


# Allowed kinds. New kinds must stay observation-neutral.
ALLOWED_KINDS = {
    "price_52w_high",
    "price_52w_low",
    "concentration_alert",
    "macro_event",
    "artifact_ready",
    "account_sync",
    "watchlist_event",
}


def create_alert(
    user_id: int,
    kind: str,
    title: str,
    body: Optional[str] = None,
    ticker: Optional[str] = None,
    link: Optional[str] = None,
    dedup_window_hours: Optional[int] = None,
) -> Optional[Alert]:
    """Insert a new notification-bell alert.

    Returns the created Alert or None if skipped by dedup / invalid kind.
    Never raises on DB errors — logs and returns None.
    """
    if kind not in ALLOWED_KINDS:
        logger.warning("alert.create_alert rejected kind=%s", kind)
        return None

    if dedup_window_hours and dedup_window_hours > 0:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            hours=dedup_window_hours
        )
        q = Alert.query.filter(
            Alert.user_id == user_id,
            Alert.kind == kind,
            Alert.created_at > cutoff,
        )
        if ticker:
            q = q.filter(Alert.ticker == ticker)
        if q.first() is not None:
            return None

    try:
        a = Alert(
            user_id=user_id,
            kind=kind,
            title=title,
            body=body,
            ticker=ticker,
            link=link,
            message=title,  # legacy column mirror, for existing consumers
            is_read=False,
        )
        db.session.add(a)
        db.session.commit()
        return a
    except Exception:
        db.session.rollback()
        logger.exception("alert.create_alert failed user_id=%s kind=%s", user_id, kind)
        return None


# ── Convenience wrappers ────────────────────────────────────────────────────

def alert_52w_high(user_id: int, ticker: str, name: Optional[str] = None):
    label = name or ticker
    return create_alert(
        user_id,
        kind="price_52w_high",
        title=f"{label} reached 52-week high",
        body="Observation — price level noted against trailing 52-week range.",
        ticker=ticker,
        link=f"/detail/{ticker}",
        dedup_window_hours=24,
    )


def alert_52w_low(user_id: int, ticker: str, name: Optional[str] = None):
    label = name or ticker
    return create_alert(
        user_id,
        kind="price_52w_low",
        title=f"{label} at 52-week low",
        body="Observation — price level noted against trailing 52-week range.",
        ticker=ticker,
        link=f"/detail/{ticker}",
        dedup_window_hours=24,
    )


def alert_concentration(user_id: int, sector: str, pct: float):
    return create_alert(
        user_id,
        kind="concentration_alert",
        title=f"Portfolio concentration — {sector} {pct:.1f}%",
        body="Observation — single-sector weighting exceeds 30% of portfolio.",
        link="/risk",
        dedup_window_hours=12,
    )


def alert_macro_event(user_id: int, event: str, when: str):
    return create_alert(
        user_id,
        kind="macro_event",
        title=f"{event} {when}",
        body="Macro calendar event noted.",
        link="/market",
        dedup_window_hours=6,
    )


def alert_artifact_ready(user_id: int, artifact_label: str, artifact_id: Optional[int] = None):
    link = f"/reports/{artifact_id}" if artifact_id else "/reports"
    return create_alert(
        user_id,
        kind="artifact_ready",
        title=f"{artifact_label} ready",
        body="Artifact rendered and available for review.",
        link=link,
    )


def alert_account_sync(user_id: int, broker: str = "KIS"):
    return create_alert(
        user_id,
        kind="account_sync",
        title=f"{broker} account sync complete",
        body="Positions refreshed from broker.",
        link="/settings",
        dedup_window_hours=1,
    )


def alert_watchlist_event(user_id: int, ticker: str, name: Optional[str] = None):
    label = name or ticker
    return create_alert(
        user_id,
        kind="watchlist_event",
        title=f"{label} movement noted",
        body="Watchlist observation — significant intraday move recorded.",
        ticker=ticker,
        link=f"/detail/{ticker}",
        dedup_window_hours=4,
    )


# ── Cron drivers (2026-04-22) ───────────────────────────────────────────────
#
# Scheduled by scripts/check_price_alerts.py. Intended cadence:
#   - check_52w_highs_lows   — every 15 minutes during market hours
#   - check_concentration    — once per day (after close)
#
# Each driver iterates all users that own positions, fans out across their
# holdings, and dedups via the 24h/7d window on create_alert. Never raises
# — a single bad ticker must not kill the sweep.


def check_52w_highs_lows() -> dict:
    """Scan every user's holdings for 52-week high/low touches.

    Returns a small metrics dict so the cron driver can log a summary.
    """
    from models import Position, User
    from services.container import fetcher
    from services.name_resolver import resolve_stock_name

    # Distinct users that currently hold at least one position.
    user_ids = [row[0] for row in db.session.query(Position.user_id).distinct().all()]
    metrics = {"users_scanned": 0, "alerts_created": 0, "errors": 0}

    for uid in user_ids:
        user = User.query.get(uid)
        if user is None:
            continue
        metrics["users_scanned"] += 1
        positions = Position.query.filter_by(user_id=uid).all()
        tickers = sorted({p.ticker for p in positions if p.ticker})
        if not tickers:
            continue

        try:
            prices = fetcher.get_prices_batch(tickers) or {}
        except Exception:
            logger.exception("check_52w_highs_lows price batch failed uid=%s", uid)
            metrics["errors"] += 1
            continue

        # Pull 52W range from FMP quote (yearHigh / yearLow). Missing fields
        # skip silently — we'd rather miss an alert than emit a false one.
        for ticker in tickers:
            px = prices.get(ticker)
            if not px:
                continue
            current = px.get("price")
            if not current or not isinstance(current, (int, float)) or current <= 0:
                continue

            hi, lo = _lookup_52w_range(ticker)
            if not hi or not lo or hi <= 0 or lo <= 0 or hi <= lo:
                continue

            name = resolve_stock_name(ticker) or ticker
            # 0.1% epsilon — price sits right at the edge, not inside.
            if current >= hi * 0.999:
                a = alert_52w_high(uid, ticker, name=name)
                if a is not None:
                    metrics["alerts_created"] += 1
            elif current <= lo * 1.001:
                a = alert_52w_low(uid, ticker, name=name)
                if a is not None:
                    metrics["alerts_created"] += 1

    return metrics


def check_concentration_alerts(soft_limit_pct: float = 30.0) -> dict:
    """Detect per-user sector concentration exceeding ``soft_limit_pct``.

    Sector attribution is best-effort: we pull the cached sector from the
    SignalCache row, falling back to "Unknown". A user with no cached signals
    on any holding simply produces no concentration alert this cycle.
    """
    import json as _json
    from models import Position, SignalCache, User

    user_ids = [row[0] for row in db.session.query(Position.user_id).distinct().all()]
    metrics = {"users_scanned": 0, "alerts_created": 0, "errors": 0}

    for uid in user_ids:
        if User.query.get(uid) is None:
            continue
        metrics["users_scanned"] += 1
        positions = Position.query.filter_by(user_id=uid).all()
        if not positions:
            continue

        # Build sector totals from market value.
        totals: dict[str, float] = {}
        book_total = 0.0
        for p in positions:
            # Prefer live price from SignalCache; fall back to avg_cost so a
            # missing quote doesn't zero the exposure.
            sector = "Unknown"
            price = p.avg_cost or 0.0
            try:
                cache = SignalCache.query.get(p.ticker)
                if cache and cache.data_json:
                    payload = _json.loads(cache.data_json)
                    sector = payload.get("sector") or "Unknown"
                    px = payload.get("price")
                    if isinstance(px, (int, float)) and px > 0:
                        price = float(px)
            except Exception:
                metrics["errors"] += 1

            mv = max(0.0, float(p.shares or 0) * float(price or 0))
            if mv <= 0:
                continue
            book_total += mv
            totals[sector] = totals.get(sector, 0.0) + mv

        if book_total <= 0:
            continue

        for sector, mv in totals.items():
            pct = (mv / book_total) * 100.0
            if pct >= soft_limit_pct:
                a = alert_concentration(uid, sector, pct)
                if a is not None:
                    metrics["alerts_created"] += 1

    return metrics


def _lookup_52w_range(ticker: str) -> tuple[Optional[float], Optional[float]]:
    """Return ``(yearHigh, yearLow)`` from FMP quote, or ``(None, None)``.

    Never raises. US tickers only — KR tickers return a missing pair because
    FMP quote yearHigh/yearLow coverage is inconsistent for KRX.
    """
    try:
        import fmp_service
    except Exception:
        return None, None
    try:
        q = fmp_service.get_quote(ticker)
    except Exception:
        return None, None
    if not q:
        return None, None
    hi = q.get("yearHigh")
    lo = q.get("yearLow")
    try:
        hi = float(hi) if hi is not None else None
        lo = float(lo) if lo is not None else None
    except (TypeError, ValueError):
        return None, None
    return hi, lo
