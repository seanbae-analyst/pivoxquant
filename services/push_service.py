"""Push notification service — wraps routes.push.send_push_to_user for use from services."""
import logging

logger = logging.getLogger(__name__)


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
    try:
        from routes.push import send_push_to_user
    except ImportError:
        logger.debug("silent-fallback: notify_alert", exc_info=True)
        return

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

    send_push_to_user(
        user_id=user_id,
        title=title,
        body=message[:200],
        url="/alerts",
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
    try:
        from routes.push import send_push_to_user
    except ImportError:
        logger.debug("silent-fallback: notify_bell_alert", exc_info=True)
        return

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
    try:
        from routes.push import send_push_to_user
    except ImportError:
        logger.debug("silent-fallback: notify_trade", exc_info=True)
        return

    # 2026-05-13: include readable name when available
    # (feedback_ticker_display rule applied consistently).
    label = _label_for_ticker(ticker)
    title = "PivoxQuant — Trade Executed"
    body = f"{action.upper()} {shares} shares of {label} @ ${price:,.2f}"

    send_push_to_user(user_id=user_id, title=title, body=body, url="/trades")


def notify_insight(user_id: int, title_text: str, body_text: str):
    """Send push for AI insights."""
    try:
        from routes.push import send_push_to_user
    except ImportError:
        logger.debug("silent-fallback: notify_insight", exc_info=True)
        return

    send_push_to_user(
        user_id=user_id,
        title=f"PivoxQuant — {title_text}",
        body=body_text[:200],
        url="/ai-alerts",
    )
