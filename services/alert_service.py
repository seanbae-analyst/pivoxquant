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
    # 2026-05-09 (bug-hunter Bug #11): KR tickers (e.g. "124500.KQ") were
    # rendering as "124500.KQ (124500.KQ) — Score …" because
    # ``snapshot.get("name", ticker)`` upstream (services/quant/engine.py
    # L420) falls back to the ticker when FMP get_info doesn't carry the
    # name (typical for KRX). Re-resolve via the unified name resolver
    # (SignalCache → curated registry → KIS API → ticker) so the persisted
    # alert message always carries the human-readable company name.
    raw_name = r.get("name") or ""
    if not raw_name or raw_name == ticker:
        try:
            from services.name_resolver import resolve_stock_name_with_db
            resolved = resolve_stock_name_with_db(ticker)
        except Exception:
            logger.debug("silent-fallback: name_resolver in maybe_generate", exc_info=True)
            resolved = None
        name = resolved or ticker
    else:
        name = raw_name

    # Bug fix 2026-05-13 (feedback_ticker_display): when name resolution
    # fails the previous code rendered "124500.KQ (124500.KQ) — Score …",
    # duplicating the ticker. Build the subject so the parenthesised
    # ticker only appears when ``name`` is a real, distinct company name.
    # Caveats: ``name`` may be whitespace-padded or, in rare cases, a
    # display variant that equals the ticker after strip — collapse both
    # sides before comparing.
    subject = ticker if (name or "").strip() == ticker.strip() else f"{name} ({ticker})"
    score = r.get("score", 0)

    # Dedup: skip if same ticker alerted within 4 hours
    recent = (Alert.query.filter_by(user_id=user_id, ticker=ticker)
              .filter(Alert.created_at > datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=4))
              .first())
    if recent:
        return

    cur = "₩" if r.get("is_korean") else "$"
    # 2026-05-04: dropped raw "[POSITIVE]" / "[NEGATIVE]" bracket prefix
    # from the message body. The Alert row already persists the structured
    # ``signal`` field (line ~66 below), and the frontend renders it as a
    # separate badge — duplicating the enum into the user-visible string
    # both clutters the alert and risks reading like a directive. Bug-
    # hunter run 2026-05-04 surfaced "[POSITIVE] Taihan Fiber Optics ..."
    # bleeding through into the Alerts page list.
    if sig == "POSITIVE":
        sh = r.get("rec_shares", 0)
        inv = r.get("rec_investment", 0)
        tim = r.get("rec_timing", "")
        inv_str = f"{cur}{inv:,.0f}" if inv > 0 else "set capital for sizing"
        # 2026-04-24: "Rec:" abbreviation for "Recommendation" triggered a
        # 자본시장법 §17 (투자자문업 미등록) 경계 flag in compliance sweep.
        # Replaced with "Sized:" (neutral sizing observation, not advice).
        msg = (f"{subject} — Score {score:.0f}/100. "
               f"Sized: {sh} shares · {inv_str}. {tim}.")
    else:
        sell_pct = r.get("sell_pct", 50)
        # "Consider reducing" also directive — rephrased as observational.
        msg = (f"{subject} — Score {score:.0f}/100. "
               f"Quant flags weakness. Observation: {sell_pct}% position weight elevated.")

    # Legal scrub — rewrite advisory verbs (Consider reducing, Scale in, etc.)
    # before the message is persisted or pushed to the user.
    msg = safe_scrub(msg, context="alert.message") or msg

    # FIX 1 (2026-05-22) — per-event notification_prefs gate. A POSITIVE /
    # NEGATIVE signal alert maps to the canonical event_id "signal_state"
    # (one of the 7 NOTIFICATION_EVENT_IDS in models/user.py). Consult the
    # User accessor (notification_channel_enabled) for the in-app (bell) and
    # push channels so the Settings → Notifications matrix is actually
    # honoured. FAIL-OPEN: the accessor returns True for unknown events /
    # channels and on a missing pref, and any DB hiccup here must not
    # silently mute a real alert — so we resolve each gate defensively and
    # default to SEND on error.
    EVENT_ID = "signal_state"
    inapp_ok = True
    push_ok = True
    try:
        from models import User
        u = User.query.get(user_id)
        if u is not None:
            inapp_ok = bool(u.notification_channel_enabled(EVENT_ID, "inapp"))
            push_ok = bool(u.notification_channel_enabled(EVENT_ID, "push"))
    except Exception:
        # Never fail-closed: an unrelated lookup failure must not suppress
        # a legitimate signal alert.
        logger.debug("silent-fallback: notification_prefs gate in maybe_generate",
                     exc_info=True)
        inapp_ok = True
        push_ok = True

    # Bug #1 fix (2026-05-09 deep bug hunt): kind=None made every signal
    # alert render as "INFO" in the /alerts page (kindLabel(null) → "INFO").
    # Set the canonical kind so the frontend pill shows "SIGNAL" with proper
    # POSITIVE/NEGATIVE tone. Bypasses ALLOWED_KINDS (raw constructor) so no
    # whitelist edit is needed; the column accepts any string.
    if inapp_ok:
        db.session.add(Alert(
            user_id=user_id, ticker=ticker, message=msg,
            signal=sig, score=score,
            kind=("signal_negative" if sig == "NEGATIVE" else "signal_positive"),
        ))
        db.session.commit()

    # Send push notification (no-ops if not configured). Gated by the
    # "signal_state" push pref above — skip the fan-out entirely when off.
    if not push_ok:
        return
    try:
        from services.push_service import notify_alert
        # 2026-05-13 (Wave H): pass the already-resolved `name` so the
        # push surface does NOT re-run resolve_stock_name_with_db. Wave E
        # added a resolver call inside push_service._label_for_ticker;
        # before this payload key the resolver fired twice per alert
        # (once for the alert subject, once for the push title), which
        # broke test_resolver_skipped_when_snapshot_already_has_name in
        # tests/test_p1_backend_batch.py. Same label, half the I/O.
        notify_alert(user_id, {
            "signal":  sig,
            "ticker":  ticker,
            "message": msg,
            "name":    name,
        })
    except Exception:
        logger.debug("silent-fallback: Send push notification (no-ops if not configured) | maybe_generate", exc_info=True)
        pass
