"""Alert routes.

Two groups of endpoints:

Legacy (kept for backwards compatibility — price_check et al.):
    GET  /api/alerts                 → {alerts: [...], unread: N}
    POST /api/alerts/read            → mark all read (legacy shape)
    POST /api/alerts/clear           → delete all
    GET  /api/alerts/price-check     → on-demand TP/SL scan

Bell-dropdown (added 2026-04-22, kind/title/body contract):
    GET    /api/alerts/unread-count  → {count: N}
    POST   /api/alerts/read-all      → mark all read (new shape {ok: true})
    POST   /api/alerts/<id>/read     → mark one read
    DELETE /api/alerts/<id>          → delete one

The bare `GET /api/alerts` response is enriched: each element now carries
`kind`, `title`, `body`, `link`, `read_at` alongside legacy fields so the
new NotificationDropdown and legacy /alerts page can share it.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from flask import Blueprint, jsonify, request
from flask_login import current_user

from extensions import db
from models import Position, Alert, SignalCache
from services.error_responses import api_error
from services.serializers import serialize_alert
from services.name_resolver import canonical_display_name
from .decorators import api_auth, legal_scrub_response
from security import general_rate_limit

logger = logging.getLogger(__name__)

alerts_bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


# ── Legacy list endpoint (enriched with bell fields) ───────────────────────

@alerts_bp.route("")
@api_auth
@legal_scrub_response
def get_alerts():
    """Return up to `limit` alerts (default 20, max 50).

    Response shape preserves the legacy `{alerts, unread}` envelope but
    each alert now carries the new bell-dropdown fields.
    """
    try:
        limit = int(request.args.get("limit", 20))
    except (TypeError, ValueError):
        limit = 20
    limit = max(1, min(limit, 50))

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=14)
    # TTL cleanup — best-effort. Must never break the GET if the delete fails
    # (e.g. row-lock contention); the read path below is what matters.
    try:
        Alert.query.filter(
            Alert.user_id == current_user.id, Alert.created_at < cutoff
        ).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("alerts.get_alerts TTL cleanup failed")

    alerts = (Alert.query.filter_by(user_id=current_user.id)
              .order_by(Alert.created_at.desc()).limit(limit).all())
    # 2026-05-09 fix: previously this counted unread off the limit-sliced
    # `alerts` list, which produced a desk-vs-bell mismatch — the bell
    # dropdown reads `unread` here, but the /alerts page recomputes total
    # from the same response's `alerts.length`. If 13 unread rows exist
    # but only the latest 20 fit the limit, the slice may also miss any
    # that were unread but pushed below the limit, AND a 14-day TTL
    # cleanup running in this same request can wipe rows mid-flight,
    # leaving the bell holding a stale "13" while the page reads 0.
    # Counting unread off a fresh query (independent of limit + ordering)
    # is the only honest source — and it matches /api/alerts/unread-count
    # exactly so both endpoints can never disagree.
    unread_count = Alert.query.filter_by(
        user_id=current_user.id, is_read=False,
    ).count()
    return jsonify({
        "alerts": [serialize_alert(a) for a in alerts],
        "unread": int(unread_count),
    })


# ── New bell-dropdown endpoints ────────────────────────────────────────────

@alerts_bp.route("/unread-count")
@api_auth
def unread_count():
    try:
        count = Alert.query.filter_by(
            user_id=current_user.id, is_read=False
        ).count()
    except Exception:
        logger.exception("alerts.unread_count failed")
        return api_error(
            en="Failed to load unread count",
            kr="안 읽은 알림 수를 불러오지 못했습니다.",
            code="ALERTS_UNREAD_COUNT_FAILED",
            status=500,
            count=0,
        )
    return jsonify({"count": int(count)})


@alerts_bp.route("/read-all", methods=["POST"])
@api_auth
@general_rate_limit
def read_all():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        Alert.query.filter_by(user_id=current_user.id, is_read=False).update(
            {"is_read": True, "read_at": now}
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("alerts.read_all commit failed")
        return api_error(
            en="Failed to update alerts",
            kr="알림 업데이트에 실패했습니다.",
            code="ALERTS_UPDATE_FAILED",
            status=500,
        )
    return jsonify({"ok": True})


@alerts_bp.route("/<int:alert_id>/read", methods=["POST"])
@api_auth
@general_rate_limit
def mark_one_read(alert_id: int):
    a = Alert.query.filter_by(id=alert_id, user_id=current_user.id).first()
    if a is None:
        return api_error(
            en="Alert not found", kr="알림을 찾을 수 없습니다.",
            code="ALERT_NOT_FOUND", status=404,
        )
    try:
        a.is_read = True
        a.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("alerts.mark_one_read commit failed id=%s", alert_id)
        return api_error(
            en="Failed to update alert",
            kr="알림 업데이트에 실패했습니다.",
            code="ALERT_UPDATE_FAILED",
            status=500,
        )
    return jsonify({"ok": True})


@alerts_bp.route("/<int:alert_id>", methods=["DELETE"])
@api_auth
@general_rate_limit
def delete_one(alert_id: int):
    a = Alert.query.filter_by(id=alert_id, user_id=current_user.id).first()
    if a is None:
        return api_error(
            en="Alert not found", kr="알림을 찾을 수 없습니다.",
            code="ALERT_NOT_FOUND", status=404,
        )
    try:
        db.session.delete(a)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("alerts.delete_one commit failed id=%s", alert_id)
        return api_error(
            en="Failed to delete alert",
            kr="알림 삭제에 실패했습니다.",
            code="ALERT_DELETE_FAILED",
            status=500,
        )
    return jsonify({"ok": True})


# ── Legacy mark-all-read and clear (kept for /alerts page) ─────────────────

@alerts_bp.route("/read", methods=["POST"])
@api_auth
@general_rate_limit
def mark_read():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        Alert.query.filter_by(user_id=current_user.id, is_read=False).update(
            {"is_read": True, "read_at": now}
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("alerts.mark_read commit failed")
        return api_error(
            en="Failed to update alerts",
            kr="알림 업데이트에 실패했습니다.",
            code="ALERTS_UPDATE_FAILED",
            status=500,
        )
    return jsonify({"ok": True})


@alerts_bp.route("/clear", methods=["POST"])
@api_auth
@general_rate_limit
def clear():
    try:
        Alert.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("alerts.clear commit failed")
        return api_error(
            en="Failed to clear alerts",
            kr="알림 전체 삭제에 실패했습니다.",
            code="ALERTS_CLEAR_FAILED",
            status=500,
        )
    return jsonify({"ok": True})


@alerts_bp.route("/price-check")
@api_auth
@legal_scrub_response
def price_check():
    positions = Position.query.filter_by(user_id=current_user.id).all()
    # Batch-load SignalCache for all user positions in a single query (avoid N+1).
    tickers = [p.ticker for p in positions]
    cache_map = {
        c.ticker: c
        for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
    } if tickers else {}
    alerts = []
    for p in positions:
        c = cache_map.get(p.ticker)
        if not c or not c.data_json:
            continue
        sd = json.loads(c.data_json)
        price = sd.get("price", 0)
        tp = sd.get("take_profit")
        sl = sd.get("stop_loss")
        name = canonical_display_name(sd.get("name"), p.ticker)
        cur = "₩" if sd.get("is_korean") else "$"
        if tp and price >= tp:
            alerts.append({"ticker": p.ticker, "name": name, "type": "TAKE_PROFIT",
                           "price": price, "target": tp, "shares": p.shares,
                           "proceeds": round(p.shares * price),
                           "message": f"{name} 사전 설정 TP 레벨 도달 — 정보 고지 ({cur}{round(price):,} ≥ {cur}{round(tp):,}, 보유 {p.shares}주)"})
        elif sl and price <= sl:
            alerts.append({"ticker": p.ticker, "name": name, "type": "STOP_LOSS",
                           "price": price, "target": sl, "shares": p.shares,
                           "proceeds": round(p.shares * price),
                           "message": f"{name} 사전 설정 SL 레벨 도달 — 정보 고지 ({cur}{round(price):,} ≤ {cur}{round(sl):,}, 보유 {p.shares}주)"})

    try:
        # Perf P1-1 (2026-05-10): batch the dedup lookup. Previous shape ran
        # one Alert.query per generated alert (N positions = N DB roundtrips).
        # For users with 20+ positions on a price-check pass this dominated
        # request latency. Single IN-query + Python postfilter for the
        # message-contains predicate keeps semantics identical.
        if alerts:
            tickers_in_alerts = {a["ticker"] for a in alerts}
            cutoff = (
                datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=4)
            )
            recent_rows = (
                Alert.query
                .filter_by(user_id=current_user.id)
                .filter(Alert.ticker.in_(tickers_in_alerts))
                .filter(Alert.created_at > cutoff)
                .all()
            )
            # Build a (ticker, type) presence set. Original predicate was
            # Alert.message.contains(a["type"]) where type ∈ {"TAKE_PROFIT",
            # "STOP_LOSS"} — those tokens are emitted into message via the
            # f-string above, so substring-in-message is equivalent to
            # checking whether the type token appears in row.message.
            recent_keys: set[tuple[str, str]] = set()
            for row in recent_rows:
                msg = row.message or ""
                for t in ("TAKE_PROFIT", "STOP_LOSS"):
                    if t in msg:
                        recent_keys.add((row.ticker, t))

            for a in alerts:
                if (a["ticker"], a["type"]) in recent_keys:
                    continue
                sig = "NEGATIVE" if a["type"] == "STOP_LOSS" else "POSITIVE"
                # Bug #1 fix (2026-05-09): kind was missing → frontend
                # rendered "INFO" instead of "PRICE". Set canonical kind so
                # the alerts page shows the right pill colour + label.
                kind = (
                    "price_stop_loss" if a["type"] == "STOP_LOSS"
                    else "price_take_profit"
                )
                db.session.add(Alert(
                    user_id=current_user.id, ticker=a["ticker"],
                    message=a["message"], signal=sig, score=0, kind=kind,
                ))
            db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("alerts.price_check persist failed")
        # Still return the alerts payload — persistence is a side-effect,
        # not the primary purpose of this endpoint.

    return jsonify({"alerts": alerts})


# ── Admin manual trigger (2026-04-22) ──────────────────────────────────────
# Used for smoke-testing the alert cron without waiting on Railway cron.
# 2026-05-18 Wave G-4 P1-B: gate moved from DEV_PREMIUM_EMAILS (tier override
# env, not an admin boundary) to ADMIN_EMAILS via services.admin_emails
# (PR #442 centralized parser). Aligns with admin_fmp / admin_preview /
# agent_admin / command_center.

def _is_admin_email(email: str | None) -> bool:
    if not email:
        return False
    from services.admin_emails import get_admin_emails
    return email.lower() in get_admin_emails()


@alerts_bp.route("/admin/check", methods=["POST"])
@api_auth
@general_rate_limit
def admin_check_alerts():
    """Manually trigger the alert-generation cron. Admin-only.

    Query params:
      mode=price (default) | daily | full
    """
    if not _is_admin_email(getattr(current_user, "email", None)):
        return api_error(
            en="admin only", kr="관리자 전용입니다.",
            code="ADMIN_ONLY", status=403,
        )

    mode = (request.args.get("mode") or "price").lower()
    from services.alert import check_52w_highs_lows, check_concentration_alerts

    result: dict = {"mode": mode}
    try:
        if mode in ("price", "full"):
            result["price"] = check_52w_highs_lows()
        if mode in ("daily", "full"):
            result["concentration"] = check_concentration_alerts()
    except Exception as exc:
        logger.exception("alerts.admin_check_alerts failed mode=%s", mode)
        # Hardening (2026-05-09 audit): clamp raw exception strings to 200
        # chars to match the convention in routes/auth.py:511 + agent.py:457
        # — prevents stack-trace fragments / SQL details / file paths from
        # leaking through unbounded exception messages.
        return api_error(
            en=str(exc)[:200],
            kr="알림 점검 중 오류가 발생했습니다.",
            code="ALERTS_ADMIN_CHECK_FAILED",
            status=500,
        )

    return jsonify({"ok": True, **result})
