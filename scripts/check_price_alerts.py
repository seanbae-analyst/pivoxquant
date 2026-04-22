#!/usr/bin/env python3
"""Alert generation cron.

Usage:
    python3 scripts/check_price_alerts.py            # 52W highs/lows sweep
    python3 scripts/check_price_alerts.py daily      # + concentration alerts
    python3 scripts/check_price_alerts.py full       # both drivers

Intended cadence (Railway cron / APScheduler):
    - every 15 min during market hours  → (no args)
    - once per day after close          → `daily`

Observation-neutral language only — alerts are emitted via the
`services.alert` module which enforces the approved vocabulary
(reached, at, exceeds). Never `BUY / SELL / recommend / advice`.
"""
from __future__ import annotations

import logging
import sys

from app import create_app
from services.alert import check_52w_highs_lows, check_concentration_alerts

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main() -> int:
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "price"

    app = create_app()
    with app.app_context():
        if mode in ("price", "full"):
            m = check_52w_highs_lows()
            logger.info("check_52w_highs_lows: %s", m)

        if mode in ("daily", "full"):
            m = check_concentration_alerts()
            logger.info("check_concentration_alerts: %s", m)

    print("alerts check complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
