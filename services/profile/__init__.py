"""Profile analytics services — Living CFO Layer 2.

Public surfaces:
    persona_analytics.compute_persona_response(user) → dict
    rolling_metrics.compute_rolling_response(user)   → dict

Both return JSON-ready dicts shaped exactly to the frontend
``frontend/src/lib/cfo/hooks.ts`` contract. Both degrade gracefully to
empty/zero payloads when the user has no trade history — never raise.
"""

from .persona_analytics import compute_persona_response  # noqa: F401
from .rolling_metrics import compute_rolling_response    # noqa: F401
from .persona_classifier_v2 import (                     # noqa: F401
    classify_persona_multi,
    get_persona_confidence,
    explain_persona_classification,
)
from .group_benchmark import (                            # noqa: F401
    compute_persona_stats,
    compute_all_personas,
    get_persona_stats,
    get_all_persona_stats,
)
from .persona_history import (                            # noqa: F401
    DRIFT_DISCLAIMER,
    take_snapshot,
    get_history,
    compute_drift,
    detect_significant_drift,
    iter_active_user_ids,
    run_weekly_snapshots,
)

__all__ = [
    "compute_persona_response",
    "compute_rolling_response",
    "classify_persona_multi",
    "get_persona_confidence",
    "explain_persona_classification",
    "compute_persona_stats",
    "compute_all_personas",
    "get_persona_stats",
    "get_all_persona_stats",
    "DRIFT_DISCLAIMER",
    "take_snapshot",
    "get_history",
    "compute_drift",
    "detect_significant_drift",
    "iter_active_user_ids",
    "run_weekly_snapshots",
]
