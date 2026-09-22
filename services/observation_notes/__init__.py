"""Observation notes package — 거래 없이 적어 두는 관찰 기록.

Public surface re-exported here so callers don't reach inside the service
module:

    from services.observation_notes import create_note, list_notes
"""
from .service import (
    create_note,
    delete_note,
    get_note,
    list_notes,
    notes_for_ticker,
)

__all__ = [
    "create_note",
    "delete_note",
    "get_note",
    "list_notes",
    "notes_for_ticker",
]
