"""Push notification service — wraps routes.push.send_push_to_user for use from services."""
import logging

logger = logging.getLogger(__name__)


def notify_alert(user_id: int, alert_data: dict):
    """Send a push notification for a new alert.

    Called after an Alert is persisted to DB.
    Gracefully no-ops if push is not configured.
    """
    try:
        from routes.push import send_push_to_user
    except ImportError:
        return

    sig = alert_data.get("signal", "")
    ticker = alert_data.get("ticker", "")
    message = alert_data.get("message", "")

    icon_map = {"POSITIVE": "Positive Signal", "NEGATIVE": "Negative Signal"}
    title = f"PivoxQuant — {icon_map.get(sig, 'Alert')}: {ticker}"

    send_push_to_user(
        user_id=user_id,
        title=title,
        body=message[:200],
        url="/alerts",
    )


def notify_trade(user_id: int, ticker: str, action: str, shares: int, price: float):
    """Send push for trade execution."""
    try:
        from routes.push import send_push_to_user
    except ImportError:
        return

    title = "PivoxQuant — Trade Executed"
    body = f"{action.upper()} {shares} shares of {ticker} @ ${price:,.2f}"

    send_push_to_user(user_id=user_id, title=title, body=body, url="/trades")


def notify_insight(user_id: int, title_text: str, body_text: str):
    """Send push for AI insights."""
    try:
        from routes.push import send_push_to_user
    except ImportError:
        return

    send_push_to_user(
        user_id=user_id,
        title=f"PivoxQuant — {title_text}",
        body=body_text[:200],
        url="/ai-alerts",
    )
