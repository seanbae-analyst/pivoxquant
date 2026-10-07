"""A fill just arrived — ask for the reason while it is still fresh.

2026-10-07. The import webhook (routes/imports.py::webhook_import) receives a
fill notification the user's own phone automation forwarded (MacroDroid, iOS
Shortcuts — docs/product/IMPORT_INBOX_DESIGN.md §Phase 2). The fill waits in
the pending inbox until the user writes a reason and approves it. This module
closes the gap between "the fill happened" and "the user opened the app":

  * ``memo_path`` — where the reason box for these fills lives
    (/journal?pending=<id>, which focuses that row's reason field);
  * ``notify_fill_memo`` — one web push per webhook call (not per fill), only
    for rows that are actually waiting (duplicates and errors are skipped),
    gated by the user's ``fill_memo`` push setting.

Wording: a record prompt — what happened and "why" — never a judgement of
the trade, never a direction word in the push text.
"""
from __future__ import annotations

import logging
from typing import Iterable

log = logging.getLogger(__name__)

EVENT_ID = "fill_memo"


def _waiting(rows: Iterable[dict]) -> list[dict]:
    return [r for r in rows if isinstance(r, dict) and r.get("status") == "pending" and r.get("id")]


def memo_path(rows: Iterable[dict]) -> str | None:
    """The reason box for the first waiting fill, or None when nothing waits."""
    waiting = _waiting(rows)
    return f"/journal?pending={waiting[0]['id']}" if waiting else None


def memo_url(rows: Iterable[dict]) -> str | None:
    """``memo_path`` on the public site — what a phone automation opens."""
    path = memo_path(rows)
    if path is None:
        return None
    from services.email.urls import _frontend
    return f"{_frontend()}{path}"


def _label(r: dict) -> str:
    name = (r.get("name") or r.get("ticker") or "").strip()
    shares = r.get("shares")
    try:
        qty = f"{float(shares):g}주" if shares is not None else ""
    except (TypeError, ValueError):
        qty = ""
    return " ".join(x for x in (name, qty) if x) or "새 체결"


def notify_fill_memo(user_id: int, rows: Iterable[dict]) -> bool:
    """Push once for the waiting fills of one webhook call. Never raises."""
    waiting = _waiting(rows)
    if not waiting:
        return False
    try:
        from models import User
        from extensions import db
        u = db.session.get(User, user_id)
        if u is None or not u.notification_channel_enabled(EVENT_ID, "push"):
            return False
        if len(waiting) == 1:
            body = f"{_label(waiting[0])} 체결이 들어왔습니다. 잊기 전에 이유를 한 줄 남겨 두세요."
        else:
            body = f"체결 {len(waiting)}건이 들어왔습니다. 잊기 전에 이유를 한 줄씩 남겨 두세요."
        from services.push_service import send_push_to_user
        # transactional: the user set this up themselves (token + automation);
        # it is a record of their own fill, not marketing (정통망법 §50).
        send_push_to_user(
            user_id=user_id,
            title="PivoxQuant — 방금 체결",
            body=body[:200],
            url=memo_path(waiting) or "/journal",
            transactional=True,
        )
        return True
    except Exception:
        log.warning("fill_memo push failed user_id=%s", user_id, exc_info=True)
        return False
