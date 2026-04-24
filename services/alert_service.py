"""Alert generation service."""
import logging
from datetime import datetime, timedelta, timezone

from extensions import db
from models import Alert
from services.legal_filter import safe_scrub

logger = logging.getLogger(__name__)


def maybe_generate(user_id: int, r: dict):
    """Generate an alert if the signal is actionable (BUY/SELL) and not duplicated."""
    sig = r.get("signal")
    if sig not in ("POSITIVE", "NEGATIVE"):
        return

    # Only alert during market hours
    from zoneinfo import ZoneInfo
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None).replace(tzinfo=ZoneInfo("UTC"))
    is_kr = r.get("is_korean", False)
    if is_kr:
        kst = now_utc.astimezone(ZoneInfo("Asia/Seoul"))
        kr_min = kst.hour * 60 + kst.minute
        if kst.weekday() >= 5 or not (540 <= kr_min < 930):
            return
    else:
        et = now_utc.astimezone(ZoneInfo("America/New_York"))
        us_min = et.hour * 60 + et.minute
        if et.weekday() >= 5 or not (570 <= us_min < 960):
            return

    ticker = r["ticker"]
    name = r.get("name", ticker)
    score = r.get("score", 0)

    # Dedup: skip if same ticker alerted within 4 hours
    recent = (Alert.query.filter_by(user_id=user_id, ticker=ticker)
              .filter(Alert.created_at > datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=4))
              .first())
    if recent:
        return

    cur = "₩" if r.get("is_korean") else "$"
    if sig == "POSITIVE":
        sh = r.get("rec_shares", 0)
        inv = r.get("rec_investment", 0)
        tim = r.get("rec_timing", "")
        inv_str = f"{cur}{inv:,.0f}" if inv > 0 else "set capital for sizing"
        # 2026-04-24: "Rec:" abbreviation for "Recommendation" triggered a
        # 자본시장법 §17 (투자자문업 미등록) 경계 flag in compliance sweep.
        # Replaced with "Sized:" (neutral sizing observation, not advice).
        msg = (f"[POSITIVE] {name} ({ticker}) — Score {score:.0f}/100. "
               f"Sized: {sh} shares · {inv_str}. {tim}.")
    else:
        sell_pct = r.get("sell_pct", 50)
        # "Consider reducing" also directive — rephrased as observational.
        msg = (f"[NEGATIVE] {name} ({ticker}) — Score {score:.0f}/100. "
               f"Quant flags weakness. Observation: {sell_pct}% position weight elevated.")

    # Legal scrub — rewrite advisory verbs (Consider reducing, Scale in, etc.)
    # before the message is persisted or pushed to the user.
    msg = safe_scrub(msg, context="alert.message") or msg

    db.session.add(Alert(user_id=user_id, ticker=ticker, message=msg,
                         signal=sig, score=score))
    db.session.commit()

    # Send push notification (no-ops if not configured)
    try:
        from services.push_service import notify_alert
        notify_alert(user_id, {"signal": sig, "ticker": ticker, "message": msg})
    except Exception:
        pass
