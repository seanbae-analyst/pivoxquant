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
"""
from flask import Blueprint

from .alerts import (
    get_alerts,
    unread_count,
    read_all,
    mark_one_read,
    delete_one,
)

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


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
