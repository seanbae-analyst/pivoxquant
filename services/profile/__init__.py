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

__all__ = ["compute_persona_response", "compute_rolling_response"]
