"""Common micro-utilities shared across the profile service modules.

Removes 4-way duplication of three trivial helpers that previously
diverged by accident:

  * ``_utc_now`` — same one-liner copied into 4 modules.
  * Sector HHI — two slightly different implementations (one returned
    HHI, one returned 1-HHI) — see :func:`sector_hhi` and
    :func:`to_diversity_score` for the canonical split.
  * ``_finite`` — same arithmetic guard.

This module is **leaf** — it must not import from any other
``services.profile`` module. Anything that needs trade rows or DB
access lives in :mod:`fifo_util` or the service modules themselves.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Iterable, Mapping
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Time
# ─────────────────────────────────────────────────────────────────────

def utc_now() -> datetime:
    """Return current UTC time as a *naive* datetime.

    SQLAlchemy columns in this codebase are stored naive (no tzinfo),
    so we strip tzinfo to keep arithmetic comparisons against
    ``traded_at`` columns identity-safe.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─────────────────────────────────────────────────────────────────────
# HHI / diversification
# ─────────────────────────────────────────────────────────────────────

def sector_hhi(weights: Mapping[str, float]) -> float:
    """Herfindahl-Hirschman Index over a sector-weighted mapping.

    Parameters
    ----------
    weights : Mapping[str, float]
        ``sector → magnitude`` (volume, market value, count). Negative
        values are coerced to absolute. Sectors with magnitude ≤ 0 are
        ignored.

    Returns
    -------
    float
        HHI in ``[0.0, 1.0]``. ``0.0`` when every weight is zero or the
        mapping is empty (no signal). ``1.0`` when one sector holds all
        magnitude (max concentration). Square-of-share semantics:
        ``HHI = Σ (w_i / total) ^ 2``.
    """
    cleaned: list[float] = []
    total = 0.0
    for value in weights.values():
        try:
            v = abs(float(value))
        except (TypeError, ValueError):
            logger.debug("silent-fallback: sector_hhi", exc_info=True)
            continue
        if v <= 0:
            continue
        cleaned.append(v)
        total += v
    if total <= 0 or not cleaned:
        return 0.0
    hhi = sum((v / total) ** 2 for v in cleaned)
    return max(0.0, min(1.0, hhi))


def to_diversity_score(hhi: float) -> float:
    """Convert HHI to a diversity score (1 - HHI), clamped to [0, 1].

    Convenience wrapper so callers do not re-implement the inversion
    inline (it has been a source of "do I want HHI or 1-HHI?" bugs).
    """
    try:
        return max(0.0, min(1.0, 1.0 - float(hhi)))
    except (TypeError, ValueError):
        return 0.0


# ─────────────────────────────────────────────────────────────────────
# Numerical guards
# ─────────────────────────────────────────────────────────────────────

def is_finite(value: float) -> bool:
    """Return ``True`` iff ``value`` coerces to a finite float."""
    try:
        x = float(value)
    except (TypeError, ValueError):
        return False
    return not (math.isnan(x) or math.isinf(x))


def safe_mean(values: Iterable[float]) -> float:
    """Mean over the finite subset of ``values``; ``0.0`` when empty."""
    finite = [float(v) for v in values if is_finite(v)]
    if not finite:
        return 0.0
    return sum(finite) / len(finite)


__all__ = [
    "utc_now",
    "sector_hhi",
    "to_diversity_score",
    "is_finite",
    "safe_mean",
]
