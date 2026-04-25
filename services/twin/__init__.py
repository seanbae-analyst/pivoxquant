"""Twin services — Feature 5 (paper-only AI Trader Twin).

Public surface
--------------
- ``initialize_twin(user_id)``
- ``run_twin_decisions(user_id, now=None)``
- ``generate_weekly_report(user_id, week_ending)``

LEGAL: every public function in this package is paper-only. No call
chain ever reaches Alpaca / KIS / any broker. Validated by
``the paper-isolation regression test``.
"""
from .twin_runner import (
    initialize_twin,
    run_twin_decisions,
    PERSONA_POSITION_SIZING,
    PERSONA_BUY_THRESHOLD,
    PERSONA_TP_PCT,
    PERSONA_SL_PCT,
    PERSONA_MAX_HOLDING_DAYS,
)
from .twin_reporter import generate_weekly_report

__all__ = [
    "initialize_twin",
    "run_twin_decisions",
    "generate_weekly_report",
    "PERSONA_POSITION_SIZING",
    "PERSONA_BUY_THRESHOLD",
    "PERSONA_TP_PCT",
    "PERSONA_SL_PCT",
    "PERSONA_MAX_HOLDING_DAYS",
]
