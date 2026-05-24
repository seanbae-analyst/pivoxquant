"""Push notification service — Web Push delivery + helpers.

2026-05-17 wave 13 structure P1 (PR #437): ``send_push_to_user`` lives
here now, not in ``routes/push.py``. Previously it sat on the route
layer and every service caller did
``from routes.push import send_push_to_user`` — a `services → routes`
reverse import that only worked through lazy imports. If
``routes/push.py`` ever needed to import anything from ``services``,
the cycle would deadlock at module load. The function migrated here
where it belongs; ``routes/push.py`` keeps a thin re-export so
external callers (or any code still on the old import path) still
work.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def send_push_to_user(
    user_id: int,
    title: str,
    body: str,
    url: str = "/alerts",
    actions: Optional[list] = None,
    transactional: bool = False,
):
    """Send push notification to all subscriptions for a user.

    Call this from services (e.g. alert_service) after creating an alert.

    ``transactional=True`` bypasses the marketing opt-out gate
    (``User.email_opt_out`` — 정통망법 §50). Use it only for
    service-info pushes the user explicitly subscribed to (price
    alerts, portfolio events, account sync, artifact-ready). Marketing
    pushes must leave it ``False`` so opted-out users are silenced.
    """
    # Lazy import of the runtime deps so unit tests that don't touch the
    # push path don't have to install pywebpush, and the function still
    # behaves as a no-op when the package is missing.
    try:
        from pywebpush import webpush, WebPushException  # noqa: F401
    except ImportError:
        logger.warning(
            "pywebpush not installed — skipping push notification"
        )
        return

    # Model imports are also lazy to keep this module importable from
    # test contexts that haven't initialised SQLAlchemy yet.
    from extensions import db
    from models import PushSubscription, User

    # Continuous User Simulation Phase 1 — sim users must NEVER reach
    # a real device subscription. ``User.is_simulated`` (migration 032)
    # is the single SoT; this check runs before the opt-out gate AND
    # before the transactional bypass, because the transactional
    # channel is also forbidden for sim users (no real recipient,
    # VAPID quota waste).
    try:
        sim_user = User.query.get(user_id)
        if sim_user is not None and bool(
            getattr(sim_user, "is_simulated", False)
        ):
            logger.info(
                "skipping push for simulated user id=%s", user_id
            )
            return
    except Exception:
        # Never fail-closed for an unrelated DB hiccup — same posture
        # as the opt-out gate below.
        logger.debug("is_simulated gate lookup failed", exc_info=True)

    # 정통망법 §50 marketing opt-out gate. Mirrors the email path —
    # ``User.email_opt_out`` is the global kill-switch that disables
    # every marketing channel. Until a dedicated ``push_opt_out``
    # column exists we honour the email flag for non-transactional
    # pushes.
    if not transactional:
        try:
            user = User.query.get(user_id)
            if user is not None and bool(
                getattr(user, "email_opt_out", False)
            ):
                logger.info(
                    "push opt-out: user_id=%s skipped "
                    "(email_opt_out=True)", user_id,
                )
                return
        except Exception:
            # Never fail-closed on push delivery for an unrelated DB
            # hiccup.
            logger.debug("opt-out gate lookup failed", exc_info=True)

    vapid_private = os.environ.get("VAPID_PRIVATE_KEY", "")
    vapid_email = os.environ.get(
        "VAPID_EMAIL", "mailto:admin@pivoxquant.com"
    )

    if not vapid_private:
        logger.warning(
            "VAPID_PRIVATE_KEY not set — skipping push notification"
        )
        return

    subs = PushSubscription.query.filter_by(user_id=user_id).all()
    if not subs:
        return

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url,
        "actions": actions or [],
    })

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=vapid_private,
                vapid_claims={"sub": vapid_email},
            )
        except Exception as e:
            err_msg = str(e)
            # Remove expired/invalid subscriptions.
            if "410" in err_msg or "404" in err_msg:
                logger.info(
                    "Removing expired push subscription %s", sub.id
                )
                try:
                    db.session.delete(sub)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    logger.exception(
                        "push send cleanup failed for sub %s", sub.id
                    )
            else:
                logger.error(
                    "Push send failed for sub %s: %s", sub.id, e
                )


# Bell-alert kinds that are TRANSACTIONAL (service info). The 정통망법 §50
# opt-out switch (`User.email_opt_out`) does not apply — these are price /
# portfolio / system events the user explicitly subscribed to. The
# `send_push_to_user` opt-out gate is bypassed for these via
# `transactional=True`.
TRANSACTIONAL_BELL_KINDS = frozenset({
    "price_52w_high",
    "price_52w_low",
    "concentration_alert",
    "macro_event",
    "artifact_ready",
    "account_sync",
    "watchlist_event",
})


def _label_for_ticker(ticker: str) -> str:
    """Return "name (ticker)" when the resolver hits, else ticker alone.

    Centralised so notify_alert / notify_trade / any future push helper
    follow the feedback_ticker_display rule consistently with the in-app
    surfaces (services/alert_service.py:53-61). Resolver miss falls back
    to ticker so the push is never empty. Failures are swallowed: a push
    is a side channel and must never block the caller.
    """
    if not ticker:
        return ""
    try:
        from services.name_resolver import resolve_stock_name_with_db
        name = resolve_stock_name_with_db(ticker)
    except Exception:
        logger.debug("silent-fallback: _label_for_ticker resolver", exc_info=True)
        name = None
    if name and name.strip() and name.strip() != ticker.strip():
        return f"{name} ({ticker})"
    return ticker


def notify_alert(user_id: int, alert_data: dict):
    """Send a push notification for a new alert.

    Called after an Alert is persisted to DB.
    Gracefully no-ops if push is not configured.

    2026-05-13: title now prefers "name (ticker)" via _label_for_ticker,
    aligning with services/alert_service.py and the CEO directive
    (feedback_ticker_display, repeated 3+ times).
    """
    # send_push_to_user lives in this module now (PR #437) — no
    # cross-layer import needed.
    sig = alert_data.get("signal", "")
    ticker = alert_data.get("ticker", "")
    message = alert_data.get("message", "")
    # 2026-05-13 (Wave H): callers that already resolved the name
    # (e.g. services/alert_service.maybe_generate) hand it in here so we
    # skip the resolver. Falls back to _label_for_ticker when missing or
    # degenerate, preserving the standalone push surface contract.
    preresolved_name = (alert_data.get("name") or "").strip()
    if (
        preresolved_name
        and preresolved_name != ticker.strip()
    ):
        label = f"{preresolved_name} ({ticker})"
    else:
        label = _label_for_ticker(ticker)

    icon_map = {"POSITIVE": "Positive Signal", "NEGATIVE": "Negative Signal"}
    title = f"PivoxQuant — {icon_map.get(sig, 'Alert')}: {label}"

    # F3-01 (2026-05-17): signal pushes are transactional — the user
    # explicitly subscribed to alerts for tickers they care about. Without
    # ``transactional=True`` the marketing opt-out gate (정통망법 §50,
    # ``User.email_opt_out``) silenced every signal push for opted-out
    # users, even though the bell-alert path (notify_bell_alert) already
    # treats the same kinds as transactional. Aligns the two surfaces.
    send_push_to_user(
        user_id=user_id,
        title=title,
        body=message[:200],
        url="/alerts",
        transactional=True,
    )


def notify_bell_alert(user_id: int, kind: str, title: str,
                      body: str = "", link: str = "/alerts"):
    """Send a PWA push for a NotificationDropdown bell alert.

    Called from ``services.alert.create_alert`` after a row is persisted.
    Silent fallback: if pywebpush / VAPID isn't configured the underlying
    sender no-ops, and any unexpected error here is logged but never raised.

    The ``kind`` flows through to ``send_push_to_user`` so the opt-out gate
    can distinguish transactional events (price / portfolio / system) from
    marketing pushes. Bell-alert kinds are all transactional today —
    advertising kinds must be added to ``TRANSACTIONAL_BELL_KINDS`` only
    when they qualify.
    """
    # send_push_to_user lives in this module now (PR #437).
    #
    # FIX 1 (2026-05-22) — per-event push pref gate. When this bell ``kind``
    # maps to one of the 7 NOTIFICATION_EVENT_IDS, consult the user's stored
    # push pref before delivering (the Settings → Notifications matrix must
    # actually silence pushes for events the user toggled off). The
    # kind→event_id map is owned by services.alert._BELL_KIND_TO_EVENT_ID; an
    # unmapped kind (every current one) is delivered as before. FAIL-OPEN:
    # any lookup failure leaves the push un-gated.
    try:
        from services.alert import _BELL_KIND_TO_EVENT_ID
        event_id = _BELL_KIND_TO_EVENT_ID.get(kind)
    except Exception:
        event_id = None
    if event_id is not None:
        try:
            from models import User
            u = User.query.get(user_id)
            if u is not None and not u.notification_channel_enabled(event_id, "push"):
                logger.info(
                    "notify_bell_alert suppressed by push pref user_id=%s "
                    "kind=%s event_id=%s", user_id, kind, event_id,
                )
                return
        except Exception:
            logger.debug("push pref gate lookup failed in notify_bell_alert",
                         exc_info=True)

    transactional = kind in TRANSACTIONAL_BELL_KINDS
    full_title = f"PivoxQuant — {title}" if title else "PivoxQuant"

    try:
        send_push_to_user(
            user_id=user_id,
            title=full_title[:120],
            body=(body or "")[:200],
            url=link or "/alerts",
            transactional=transactional,
        )
    except Exception:
        logger.warning("notify_bell_alert delivery failed user_id=%s kind=%s",
                       user_id, kind, exc_info=True)


def notify_trade(user_id: int, ticker: str, action: str, shares: int, price: float):
    """Send push for trade execution."""
    # send_push_to_user lives in this module now (PR #437).
    # 2026-05-13: include readable name when available
    # (feedback_ticker_display rule applied consistently).
    label = _label_for_ticker(ticker)
    title = "PivoxQuant — Trade Executed"
    body = f"{action.upper()} {shares} shares of {label} @ ${price:,.2f}"

    # Trade confirmation is a transactional/portfolio event — must reach
    # opted-out users too (bypasses the 정통망법 §50 marketing gate).
    send_push_to_user(user_id=user_id, title=title, body=body, url="/trades", transactional=True)


def notify_insight(user_id: int, title_text: str, body_text: str):
    """Send push for AI insights."""
    # send_push_to_user lives in this module now (PR #437).
    send_push_to_user(
        user_id=user_id,
        title=f"PivoxQuant — {title_text}",
        body=body_text[:200],
        url="/ai-alerts",
    )
