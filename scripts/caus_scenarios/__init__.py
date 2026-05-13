"""PivoxQuant CAUS Phase 3 — Playwright-based scenario modules.

Each scenario module exposes:
    run(page, context, *, agent_id: str, base_url: str) -> list[dict]

returning a list of finding dicts with the schema documented in `_base.py`.

Phase 3 replaces the Phase 2 `claude` CLI subprocess (which timed out at 600s
inside the cron child context — Claude in Chrome MCP isn't reachable from
detached subprocesses). Playwright Python is OSS ($0 incremental cost), runs
headless, and exercises the same prod surfaces as a real user.

Day rotation (Mon=0 ... Sun=6) mirrors `caus_daily_sweep.DAY_SCENARIOS`:
    day0_signup       — onboarding completion + first /home redirect
    day1_kr_search    — /signals KR ticker (삼성전자) + alert toggle
    day2_us_watchlist — /watchlist AAPL add + /ai chat round-trip
    day3_portfolio_risk — /portfolio entry + /risk 7-Layer + simulator
    day4_alert_simulation — /alerts dropdown + mark-all-read + toast
    day5_reports      — /reports artifact preview (graceful or rendered)
    day6_payment      — /pricing → Stripe test-mode checkout entry only

Cost: $0. stdlib + Playwright (already in requirements.txt).
"""
from __future__ import annotations

__all__ = [
    "day0_signup",
    "day1_kr_search",
    "day2_us_watchlist",
    "day3_portfolio_risk",
    "day4_alert_simulation",
    "day5_reports",
    "day6_payment",
]
