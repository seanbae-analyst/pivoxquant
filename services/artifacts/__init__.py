"""Artifact services — Weekly Memo, Brag Card, Earnings Pre-Brief, ...

Each artefact class lives in its own module and writes to the shared
`artifacts` table (see `models/artifact.py`). Public entry points are
re-exported here for convenience.
"""
from __future__ import annotations

import gc
import logging
import os
from typing import Callable, Iterable, Iterator, TypeVar

from .weekly_memo_service import WeeklyMemoService  # noqa: F401
from .monthly_brag_service import MonthlyBragService  # noqa: F401

__all__ = ["WeeklyMemoService", "MonthlyBragService", "iter_users_chunked"]

_logger = logging.getLogger(__name__)

# ── PDF chunked rendering helper (B18, 2026-05-02) ─────────────────────────
# Why this exists
#   Each PDF cron job iterates over all paid-tier users and calls
#   `render_pdf()` (WeasyPrint) per user. WeasyPrint holds large
#   intermediate cairo / pango buffers for the duration of a render — on
#   Railway hobby plan (512 MB RAM) a tight `for user in users:` loop
#   over even a handful of Premium users can push RSS toward the OOM
#   killer because Python's generational GC does not eagerly release the
#   freed C-extension memory between renders.
#
# What it does
#   Wraps any user iterable with a chunked iterator that yields one user
#   at a time but forces `gc.collect()` between chunks (default 3) and
#   emits a structured progress log line per chunk. Pure helper — no
#   behavioural change beyond memory release timing and logging.
#
# Tunable via env
#   ARTIFACT_PDF_CHUNK_SIZE — chunk size (default: 3). On a beefier box
#   you can set this to 10 or higher to reclaim throughput; on Railway
#   hobby leave at the default.

_DEFAULT_CHUNK_SIZE = 3
T = TypeVar("T")


def _resolve_chunk_size(override: int | None = None) -> int:
    if override is not None and override > 0:
        return override
    raw = os.environ.get("ARTIFACT_PDF_CHUNK_SIZE")
    if raw:
        try:
            v = int(raw)
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass
    return _DEFAULT_CHUNK_SIZE


def iter_users_chunked(
    users: Iterable[T],
    *,
    label: str,
    chunk_size: int | None = None,
    on_chunk_done: Callable[[int, int, int], None] | None = None,
) -> Iterator[T]:
    """Yield items from ``users`` while forcing a GC pass after every
    ``chunk_size`` items.

    Drop-in replacement for ``for user in users:`` — the caller's loop
    body is unchanged. Designed for PDF cron jobs that render one PDF
    per user and risk OOM on small dynos.

    Parameters
    ----------
    users : iterable of User
        Source iterable (typically a SQLAlchemy ``.all()`` result list,
        but any iterable works).
    label : str
        Human-readable name for log lines, e.g. ``"risk_board.monthly"``.
    chunk_size : int | None
        Override the default (3) and the ``ARTIFACT_PDF_CHUNK_SIZE`` env.
    on_chunk_done : callable(chunk_index, total_chunks, items_in_chunk) | None
        Optional progress callback fired right before the GC pass.

    Yields
    ------
    User
        Each user in order, exactly as the source iterable would have.
    """
    items = list(users)  # snapshot — we need a length to log totals
    total = len(items)
    if total == 0:
        _logger.info("pdf_chunk %s start — 0 users, nothing to do", label)
        return

    cs = _resolve_chunk_size(chunk_size)
    total_chunks = (total + cs - 1) // cs
    _logger.info(
        "pdf_chunk %s start — total=%d chunk_size=%d chunks=%d",
        label, total, cs, total_chunks,
    )

    for ci in range(total_chunks):
        start = ci * cs
        end = min(start + cs, total)
        chunk = items[start:end]
        for u in chunk:
            yield u
        # Hand back any C-extension memory (cairo, pango, pillow buffers)
        # that the per-user render allocated. gc.collect() is safe to call
        # synchronously here — we are inside a long-running cron, not a
        # request — and the Python overhead is negligible compared with
        # the WeasyPrint renders we just finished.
        gc.collect()
        if on_chunk_done is not None:
            try:
                on_chunk_done(ci + 1, total_chunks, len(chunk))
            except Exception as exc:  # noqa: BLE001 — never break cron over a callback
                _logger.debug("pdf_chunk %s on_chunk_done raised: %s", label, exc)
        _logger.info(
            "pdf_chunk %s progress — chunk=%d/%d processed=%d/%d",
            label, ci + 1, total_chunks, end, total,
        )
