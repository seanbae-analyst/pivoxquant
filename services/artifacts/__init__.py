"""Artifact services — Weekly Memo, Brag Card, Earnings Pre-Brief, ...

Each artefact class lives in its own module and writes to the shared
`artifacts` table (see `models/artifact.py`). Public entry points are
re-exported here for convenience.
"""
from .weekly_memo_service import WeeklyMemoService  # noqa: F401
from .monthly_brag_service import MonthlyBragService  # noqa: F401

__all__ = ["WeeklyMemoService", "MonthlyBragService"]
