#!/usr/bin/env python3
"""Group-Benchmark recompute cron.

Usage:
    python3 scripts/compute_group_stats.py               # all windows
    python3 scripts/compute_group_stats.py 30            # only 30d
    python3 scripts/compute_group_stats.py 30 90 365     # explicit list

Intended cadence (Railway cron / APScheduler):
    - once per week, Sunday 02:00 KST (late-night, low traffic)

What it does
------------
For each window (30 / 90 / 365 days) computes one aggregate row per
persona via ``services.profile.compute_all_personas``. Below the legal
group-size floor (N < 20) the row is stored with ``suppressed=True``
and a ``null`` metrics payload so downstream reads cannot leak the raw
numbers even by accident.

Observation-neutral: produces statistics, not recommendations. Never
emits BUY/SELL language.
"""
from __future__ import annotations

import logging
import sys

from app import create_app
from models import VALID_WINDOWS
from services.profile import compute_all_personas


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def _parse_windows(argv: list[str]) -> list[int]:
    if not argv:
        return list(VALID_WINDOWS)
    parsed: list[int] = []
    for a in argv:
        try:
            val = int(a)
        except ValueError:
            logger.error("invalid window %r — must be int", a)
            continue
        if val not in VALID_WINDOWS:
            logger.error("window %d not in VALID_WINDOWS %s — skipping", val, VALID_WINDOWS)
            continue
        parsed.append(val)
    return parsed or list(VALID_WINDOWS)


def main() -> int:
    windows = _parse_windows(sys.argv[1:])
    app = create_app()
    with app.app_context():
        for w in windows:
            try:
                rows = compute_all_personas(w)
            except Exception:
                logger.exception("compute_all_personas(%d) failed", w)
                continue
            total = len(rows)
            suppressed = sum(1 for r in rows if r.suppressed)
            published = total - suppressed
            logger.info(
                "group_stats window=%dd → %d personas with data "
                "(%d published, %d suppressed < MIN_GROUP_SIZE)",
                w, total, published, suppressed,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
