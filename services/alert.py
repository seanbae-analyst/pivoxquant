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
# 2026-09-01: macro_event / artifact_ready / account_sync / watchlist_event
# went with their emitters — every one had lost its caller. What remains is
# what the scheduled sweeps in app.py actually produce.
ALLOWED_KINDS = {
    "price_52w_high",
    "price_52w_low",
    "concentration_alert",
}


# Bell-alert kind → notification_prefs event_id map.
#
# models/user.py defines the NOTIFICATION_EVENT_IDS the Settings matrix
# exposes: price_52w · concentration.
#
# The per-event × per-channel matrix (User.notification_prefs, served by
# /api/notifications/preferences, toggled in Settings) governs those.
# When a bell-alert ``kind`` maps to one of them we gate the in-app (and the
# email channel, if/when an alert ever sends email) by the user's stored
# pref. When it does NOT map (the common case below) we DELIVER AS BEFORE —
# there is no pref to consult, and FAIL-OPEN (sending an un-gated alert) is
# strictly safer than wrongly suppressing a real one.
#
# Call-site → event_id mapping for the kinds this module emits:
#   price_52w_high      → "price_52w"
#   price_52w_low       → "price_52w"     (one toggle covers both ends)
#   concentration_alert → "concentration"
#
# A kind absent from the map ships unconditionally: there is no pref to
# consult, and FAIL-OPEN is strictly safer than wrongly suppressing a real
# alert. ALLOWED_KINDS above means that case cannot arise today.
# 2026-09-01: every kind used to map to None, so the Settings → Notifications
# matrix had no effect on the only two alerts this product actually sends. The
# 52-week sweep and the concentration sweep now carry the event ids the matrix
# exposes, which is what makes those toggles real. The four kinds that used to
# sit here (macro_event / artifact_ready / account_sync / watchlist_event) went
# with their emitters — none had a caller left.
_BELL_KIND_TO_EVENT_ID: dict[str, Optional[str]] = {
    "price_52w_high":      "price_52w",
    "price_52w_low":       "price_52w",
    "concentration_alert": "concentration",
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

    # F3-05 (2026-05-17): defense-in-depth scrub. All current callers pass
    # hardcoded observation-neutral text, but any future caller piping
    # advisory/recommendation language (e.g. an LLM-rendered macro blurb)
    # would write it straight into the Alert row AND fan it out as the
    # push payload. Run the same legal_filter that ai_service / routes/ai
    # already use. safe_scrub returns None on internal failure; we keep
    # the original text in that case so a scrubber bug never empties
    # legitimate alerts.
    try:
        from services.legal_filter import safe_scrub
        title = safe_scrub(title, context="alert.title") or title
        if body:
            body = safe_scrub(body, context="alert.body") or body
    except Exception:
        logger.debug("safe_scrub import/call failed in create_alert", exc_info=True)

    # FIX 1 (2026-05-22) — in-app (bell) notification_prefs gate. Only gate
    # when this kind maps to one of the 7 NOTIFICATION_EVENT_IDS; an unmapped
    # kind (every current one — see _BELL_KIND_TO_EVENT_ID) ships as before.
    # FAIL-OPEN: any lookup failure leaves the alert un-suppressed, because
    # wrongly muting a real alert is worse than an over-send.
    event_id = _BELL_KIND_TO_EVENT_ID.get(kind)
    if event_id is not None:
        try:
            from models import User
            u = User.query.get(user_id)
            if u is not None and not u.notification_channel_enabled(event_id, "inapp"):
                logger.info(
                    "alert.create_alert suppressed by inapp pref user_id=%s "
                    "kind=%s event_id=%s", user_id, kind, event_id,
                )
                return None
        except Exception:
            # Never fail-closed on a pref lookup hiccup.
            logger.debug("inapp pref gate lookup failed in create_alert",
                         exc_info=True)

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
    except Exception:
        db.session.rollback()
        logger.exception("alert.create_alert failed user_id=%s kind=%s", user_id, kind)
        return None

    # Fan out to PWA Web Push. Silent fallback — push delivery must never
    # cause the bell-alert insert to fail. Routed through push_service so
    # the opt-out gate (정통망법 §50) is honoured uniformly.
    try:
        from services.push_service import notify_bell_alert
        notify_bell_alert(
            user_id=user_id,
            kind=kind,
            title=title,
            body=body or "",
            link=link or "/mirror",
        )
    except Exception:
        logger.warning("push delivery failed for alert id=%s kind=%s",
                       getattr(a, "id", None), kind, exc_info=True)

    return a


# ── Convenience wrappers ────────────────────────────────────────────────────

def _ticker_label(ticker: str, name: Optional[str]) -> str:
    """Render "name (ticker)" when a non-degenerate name is available.

    2026-05-13: aligns wrappers with feedback_ticker_display (CEO directive,
    3+ times). When the caller didn't pass a name, fall back to the central
    resolver via services.push_service._label_for_ticker. On total miss
    returns the ticker alone — never produces "X (X)".
    """
    nm = (name or "").strip()
    if nm and nm != (ticker or "").strip():
        return f"{nm} ({ticker})"
    # Caller didn't resolve — try the shared resolver.
    try:
        from services.push_service import _label_for_ticker
        return _label_for_ticker(ticker)
    except Exception:
        return ticker or ""


def alert_52w_high(user_id: int, ticker: str, name: Optional[str] = None):
    label = _ticker_label(ticker, name)
    return create_alert(
        user_id,
        kind="price_52w_high",
        title=f"{label} reached 52-week high",
        body="Observation — price level noted against trailing 52-week range.",
        ticker=ticker,
        link="/portfolio",
        dedup_window_hours=24,
    )


def alert_52w_low(user_id: int, ticker: str, name: Optional[str] = None):
    label = _ticker_label(ticker, name)
    return create_alert(
        user_id,
        kind="price_52w_low",
        title=f"{label} at 52-week low",
        body="Observation — price level noted against trailing 52-week range.",
        ticker=ticker,
        link="/portfolio",
        dedup_window_hours=24,
    )


def alert_concentration(user_id: int, sector: str, pct: float):
    return create_alert(
        user_id,
        kind="concentration_alert",
        title=f"Portfolio concentration — {sector} {pct:.1f}%",
        body="Observation — single-sector weighting exceeds 30% of portfolio.",
        link="/mirror",
        dedup_window_hours=12,
    )


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
        # Skip soft-deleted users (30-day grace) — generating alerts/push for
        # an account pending deletion violates PIPA §21. Mirrors app.load_user.
        if user is None or user.deletion_requested_at is not None:
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
            # FIX 2 (2026-05-22) used to skip KR tickers entirely because the
            # range lookup was FMP-only and FMP's KRX coverage is unreliable.
            # 2026-06-11: ``_lookup_52w_range`` now routes KR → KIS
            # ``w52_hgpr``/``w52_lwpr`` (official feed), so KR positions get
            # real 52w-range alerts; when KIS is unavailable the lookup
            # returns a missing pair and the hi/lo validation below skips —
            # identical safety to the old guard, never a fabricated range.
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
        user = User.query.get(uid)
        # Skip soft-deleted users (PIPA §21) — see check_52w_highs_lows.
        if user is None or user.deletion_requested_at is not None:
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
    """Return ``(52w high, 52w low)``, or ``(None, None)``. Never raises.

    Source routing (2026-06-11 — closes the FIX 2 deferred KR gap):
      * KR (.KS/.KQ)  → KIS ``inquire-price`` ``w52_hgpr``/``w52_lwpr``
        (exchange-licensed feed; FMP's KRX yearHigh/yearLow is unreliable).
        KIS unavailable/missing → missing pair, i.e. the old silent skip —
        never a fabricated range, never a false alert.
      * US            → FMP quote yearHigh/yearLow (unchanged).
    """
    tk = (ticker or "").upper()
    if tk.endswith(".KS") or tk.endswith(".KQ"):
        try:
            from services.data import kis_market_adapter
            rng = kis_market_adapter.get_52w_range(tk)
        except Exception:
            return None, None
        return rng if rng else (None, None)

    try:
        from services.data import fmp as fmp_service
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
