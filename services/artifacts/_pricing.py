"""Shared price helper for artifact builders.

Extracted from FIVE byte-identical private ``_safe_price`` copies
(year_end_letter, risk_board, quarterly_self_report, monthly_finance,
kpi_dashboard). Centralising the "fetch latest close, guard non-finite → None"
logic is exactly what the 2026-06-07 ``$nan``-in-paid-PDF fix needed but had to
apply in 7 separate places — a single missed ``math.isfinite`` guard shipped an
invalid money figure. One copy now, so a fix lands once.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)


def safe_last_price(ticker: str) -> Optional[float]:
    """Latest close via the shared fetcher, or ``None``. Never raises.

    Returns ``None`` on missing/empty history or a non-finite close, so a
    caller's ``safe_last_price(...) or avg_cost`` fallback works — a returned
    ``NaN`` would be truthy and defeat that fallback (the original bug).
    """
    try:
        from services.container import fetcher

        hist = fetcher.get_price_history(ticker, period="5d")
        if hist is None or "Close" not in hist or len(hist["Close"]) == 0:
            return None
        v = float(hist["Close"].iloc[-1])
        return v if math.isfinite(v) else None
    except Exception as exc:  # noqa: BLE001 — never raise into a report builder
        logger.debug("safe_last_price failed for %s: %s", ticker, exc)
        return None
