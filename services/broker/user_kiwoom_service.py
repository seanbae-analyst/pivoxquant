"""
PivoxQuant — Per-user Kiwoom (키움증권) service — STUB.

Week 2 scope (not yet implemented). This module exists to reserve the name
and provide a fail-fast placeholder so callers depending on the broker
directory structure don't break.

Planned endpoints (per docs/launch/AUTO_SYNC_TECH_PLAN.md §1.2):
  - OAuth2 token:   POST https://api.kiwoom.com/oauth2/token
  - 잔고 조회:       POST https://api.kiwoom.com/api/dostk/acnt   api-id: kt00018
"""
from __future__ import annotations


class UserKiwoomServiceNotImplemented(NotImplementedError):
    """Raised when Kiwoom sync is requested before Week 2 ships."""


class UserKiwoomService:
    """Stub. Raises on any use."""

    BROKER = "kiwoom"

    def __init__(self, user_id: int):  # pragma: no cover
        raise UserKiwoomServiceNotImplemented(
            "Kiwoom 연동은 Week 2에 출시됩니다 (AUTO_SYNC_TECH_PLAN §1.2)."
        )
