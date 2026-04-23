"""
services.agents — Personal Journal Companion (Closed Beta).

Layer 4 of the "Living CFO" architecture. Not shipped to production until
legal counsel signs off on §6 of reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md.

Public API:
  - JournalCompanion        main orchestrator class
  - GateResult / GateVerdict  legal gate outcomes (re-exported)
  - run_gate                  legal gate entry point (re-exported)

Feature flag (hard gate):
  settings.AGENT_ENABLED (default False). Even with code deployed, the
  route /api/agent/query returns 503 until this flag is True per Premium-
  Plus-and-only gate.

Privacy posture:
  - user data is pseudonymized before leaving the process (see data_bridge.py)
  - long-term memory is user-owned (client-side IndexedDB) by default; server
    storage is opt-in and always encrypted at rest
  - no cross-user pattern extraction
  - audit log retention 2 years then purge

Kill switch:
  AGENT_ENABLED = False in settings → all queries respond with T5 refusal
"""

from services.agents.legal_gate import (
    GateResult,
    GateVerdict,
    run_gate,
    T5_REFUSAL,
)

__all__ = [
    "GateResult",
    "GateVerdict",
    "run_gate",
    "T5_REFUSAL",
]
