"""Tiny body-rendering helpers shared across the artefact mailers.

These used to live as inline conditionals or duplicated one-liners
inside ``services/artifacts/*_service.py``. Pulling them here means
that any future tweak (e.g. adding 휴장-aware suffixes for ``.KQ``)
happens in exactly one place.

Nothing here imports SQLAlchemy or Flask — these are pure-Python
helpers safe to call from PDF rendering, email rendering, or unit
tests without an app context.
"""
from __future__ import annotations

from datetime import datetime, timezone


def utc_naive(dt: datetime | None) -> datetime:
    """Normalise to timezone-naive UTC, the form the DB columns store.

    onboarding_sequence and retention_sequence each carried a byte-identical
    copy of this until 2026-09-10. Two copies of one rule always drift — the
    lesson CLAUDE.md §10 records from the legal scrubber, and the one that had
    already played out in this package with ``_dashboard_url`` (three copies,
    two of which had diverged, all three pointing at a deleted route).

    ``None`` means now. An aware datetime is converted, not merely stripped:
    dropping the tzinfo off a KST timestamp would shift it nine hours, which
    is exactly the kind of silent error a shared helper should make
    impossible to write twice.
    """
    if dt is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


# ── Currency prefix ─────────────────────────────────────────────────────
# Korean tickers carry a ``.KS`` (KOSPI) or ``.KQ`` (KOSDAQ) suffix in
# our database. Anything else is treated as USD — that's true for the
# Alpaca + FMP universe we currently support. If we ever add JPY (.T)
# or EUR (.PA) we extend this single helper instead of grepping the
# 17 mailer files again.

def currency_prefix(ticker: str | None) -> str:
    """Return ``"₩"`` for KR tickers (.KS / .KQ suffix) else ``"$"``.

    Defaults to ``"$"`` for empty / ``None`` input — every existing
    call site assumed USD when ticker was absent, so preserving that
    keeps the behaviour 100 % identical post-refactor.

    Examples
    --------
    >>> currency_prefix("AAPL")
    '$'
    >>> currency_prefix("005930.KS")
    '₩'
    >>> currency_prefix("035720.kq")  # case-insensitive
    '₩'
    >>> currency_prefix(None)
    '$'
    """
    if not ticker:
        return "$"
    upper = ticker.upper()
    if upper.endswith(".KS") or upper.endswith(".KQ"):
        return "₩"
    return "$"


__all__ = ["currency_prefix"]
