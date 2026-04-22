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
