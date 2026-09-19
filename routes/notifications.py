"""Notification routes — alias over ``routes.alerts``.

Rationale
---------
The frontend's bell-dropdown component lives under the brand name
"Notifications" (``NotificationDropdown``) but historically fetched from
``/api/alerts``. External callers (PWA service-workers, 3rd-party
integrations, QA harnesses, or any consumer searching for the intuitive
``/api/notifications`` path) have been landing on 404s.

This module exposes the same handlers one level over under the
``/api/notifications`` prefix. There is **no new business logic** and
**no new model** — every route delegates to the canonical implementations
in :mod:`routes.alerts`, which remain the single source of truth.

Mirrored endpoints
------------------
    GET    /api/notifications               → list (alias of GET /api/alerts)
    GET    /api/notifications/unread-count  → unread count
    POST   /api/notifications/read-all      → mark all read
    POST   /api/notifications/<id>/read     → mark one read
    DELETE /api/notifications/<id>          → delete one

Legacy ``/read``, ``/clear``, ``/price-check`` and ``/admin/check`` are
intentionally **not** re-exposed here — they are alert-semantic
(cron/price-check) rather than notification-semantic (user inbox).

Preferences endpoints (Settings v2 notification matrix)
-------------------------------------------------------
    GET /api/notifications/preferences  → all 7 events merged over defaults
    PUT /api/notifications/preferences  → validate + persist partial prefs

These persist the per-event × per-channel toggles that the settings v2
``notifications-matrix`` component previously only stored in localStorage
(GAP-E). The canonical event ids + channel defaults live on the
``models.user`` module (``NOTIFICATION_*`` constants), kept byte-for-byte
aligned with the frontend ``EVENTS`` array.
"""
import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user

from extensions import db
from models.user import (
    NOTIFICATION_CHANNELS,
    NOTIFICATION_EVENT_IDS,
    NOTIFICATION_PREF_DEFAULTS,
    visible_notification_event_ids,
)
from services.error_responses import api_error
from .alerts import (
    get_alerts,
    unread_count,
    read_all,
    mark_one_read,
    delete_one,
)
from .decorators import api_auth
from security import general_rate_limit

logger = logging.getLogger(__name__)

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


def _merged_prefs(stored) -> dict:
    """Merge a (possibly partial / NULL) stored dict over the canonical
    defaults so the response ALWAYS contains every CURRENTLY VISIBLE event
    with all three channels as real bools.

    Visible, not canonical: ``visible_notification_event_ids()`` drops an
    event whose producer is currently muted (``price_52w`` while
    ``MARKET_DATA_DISPLAY_ENABLED`` is off), so the Settings matrix never
    renders a toggle that cannot fire. Stored values for a hidden event are
    left untouched in the DB and reappear when its producer comes back.
    """
    merged: dict[str, dict[str, bool]] = {}
    stored = stored if isinstance(stored, dict) else {}
    for event_id in visible_notification_event_ids():
        defaults = NOTIFICATION_PREF_DEFAULTS[event_id]
        event_stored = stored.get(event_id)
        if not isinstance(event_stored, dict):
            event_stored = {}
        merged[event_id] = {
            ch: (event_stored[ch] if isinstance(event_stored.get(ch), bool)
                 else defaults[ch])
            for ch in NOTIFICATION_CHANNELS
        }
    return merged


@notifications_bp.route("/preferences", methods=["GET"])
@api_auth
def get_preferences():
    """Return the user's notification matrix, defaults merged in.

    Always 200 with all seven events even for a brand-new user whose
    ``notification_prefs`` column is still NULL.
    """
    try:
        merged = _merged_prefs(getattr(current_user, "notification_prefs", None))
    except Exception:
        logger.exception("notifications.get_preferences failed")
        return api_error(
            en="Failed to load notification preferences",
            kr="알림 설정을 불러오지 못했습니다.",
            code="NOTIF_PREFS_LOAD_FAILED",
            status=500,
        )
    return jsonify({"prefs": merged})


@notifications_bp.route("/preferences", methods=["PUT"])
@api_auth
@general_rate_limit
def put_preferences():
    """Validate + persist a (partial) notification matrix.

    Body: ``{"prefs": {"<event_id>": {"email": bool, "push": bool,
    "inapp": bool}, ...}}``. Only the canonical seven event ids and the
    three known channels are accepted; any unknown key — or a non-bool
    value — is rejected with 400. On success the merged matrix (defaults
    under stored) is returned so the client never has to re-fetch.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("prefs"), dict):
        return api_error(
            en="Request body must be {\"prefs\": { ... }}",
            kr="요청 본문은 {\"prefs\": { ... }} 형태여야 합니다.",
            code="NOTIF_PREFS_BAD_BODY",
            status=400,
        )

    incoming = body["prefs"]
    clean: dict[str, dict[str, bool]] = {}
    for event_id, channels in incoming.items():
        if event_id not in NOTIFICATION_EVENT_IDS:
            return api_error(
                en=f"Unknown event id: {event_id}",
                kr=f"알 수 없는 이벤트 ID: {event_id}",
                code="NOTIF_PREFS_UNKNOWN_EVENT",
                status=400,
            )
        if not isinstance(channels, dict):
            return api_error(
                en=f"Event '{event_id}' must map to a channel object",
                kr=f"이벤트 '{event_id}' 는 채널 객체여야 합니다.",
                code="NOTIF_PREFS_BAD_EVENT_SHAPE",
                status=400,
            )
        for channel, value in channels.items():
            if channel not in NOTIFICATION_CHANNELS:
                return api_error(
                    en=f"Unknown channel: {channel}",
                    kr=f"알 수 없는 채널: {channel}",
                    code="NOTIF_PREFS_UNKNOWN_CHANNEL",
                    status=400,
                )
            if not isinstance(value, bool):
                return api_error(
                    en=f"Channel '{channel}' value must be a boolean",
                    kr=f"채널 '{channel}' 값은 boolean 이어야 합니다.",
                    code="NOTIF_PREFS_BAD_VALUE",
                    status=400,
                )
            clean.setdefault(event_id, {})[channel] = value

    # Partial PUT: merge incoming events/channels over the stored matrix so a
    # UI that only submits a subset of toggles cannot wipe the user's other
    # customizations. Merge at the channel level (per-event dict.update).
    stored = current_user.notification_prefs
    merged_store: dict[str, dict[str, bool]] = (
        {k: dict(v) for k, v in stored.items() if isinstance(v, dict)}
        if isinstance(stored, dict)
        else {}
    )
    for event_id, channels in clean.items():
        merged_store.setdefault(event_id, {}).update(channels)

    try:
        # JSON column mutation: reassign a brand-new dict so SQLAlchemy's
        # default (non-mutable) JSON tracking marks the attribute dirty.
        current_user.notification_prefs = merged_store
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("notifications.put_preferences commit failed")
        return api_error(
            en="Failed to save notification preferences",
            kr="알림 설정 저장에 실패했습니다.",
            code="NOTIF_PREFS_SAVE_FAILED",
            status=500,
        )

    return jsonify({"prefs": _merged_prefs(merged_store)})


# ── Alias routes ────────────────────────────────────────────────────────────
# Each view is registered directly; the original decorators on the alerts
# handlers (api_auth, legal_scrub_response) are preserved because we reuse
# the wrapped function object — not the underlying view.

notifications_bp.add_url_rule(
    "", endpoint="list", view_func=get_alerts, methods=["GET"]
)
notifications_bp.add_url_rule(
    "/unread-count", endpoint="unread_count",
    view_func=unread_count, methods=["GET"],
)
notifications_bp.add_url_rule(
    "/read-all", endpoint="read_all",
    view_func=read_all, methods=["POST"],
)
notifications_bp.add_url_rule(
    "/<int:alert_id>/read", endpoint="mark_one_read",
    view_func=mark_one_read, methods=["POST"],
)
notifications_bp.add_url_rule(
    "/<int:alert_id>", endpoint="delete_one",
    view_func=delete_one, methods=["DELETE"],
)
