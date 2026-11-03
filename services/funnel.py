"""First-time activation events on ``funnel_events``.

Each event is written once per user, after the request's own commit. A failure
here is logged and swallowed: a funnel row must never fail the action it
measures.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from extensions import db
from models import FunnelEvent
from models.funnel_event import ALLOWED_EVENTS

logger = logging.getLogger(__name__)


def record_once(user_id: int, event: str) -> None:
    """Write ``event`` for ``user_id`` unless it was already recorded."""
    if event not in ALLOWED_EVENTS:
        logger.warning("funnel event not allowed: %s", event)
        return
    try:
        if FunnelEvent.query.filter_by(user_id=int(user_id), event=event).first() is not None:
            return
        db.session.add(FunnelEvent(
            user_id=int(user_id),
            event=event,
            created_at=datetime.now(timezone.utc),
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.warning("funnel event failed (user_id=%s event=%s)", user_id, event, exc_info=True)
