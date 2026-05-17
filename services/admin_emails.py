"""Centralized ADMIN_EMAILS env-var parser.

Why this module exists
----------------------
Wave 13 structure audit found 5 identical ``_admin_emails()``
implementations duplicated across:
  - routes/admin_fmp.py
  - routes/admin_preview.py
  - routes/command_center.py
  - routes/agent_admin.py
  - agent_worker/admin_routes.py

Each one parsed ``os.getenv("ADMIN_EMAILS", "")`` into a lowercased
set the same way. A typo / format drift in any single copy would
silently let through (or block) the wrong set of admin emails — and
nothing pinned the parsing contract.

This module is the single source of truth. Callers route through
``get_admin_emails()``; the parsing rule (comma split, strip, lower,
drop empties) lives here.

Tests pin the contract in ``tests/test_admin_emails_module.py``.

2026-05-17 wave 13 P2 (PR #442).
"""
from __future__ import annotations

import os


def get_admin_emails() -> set[str]:
    """Return the set of lowercased admin email addresses.

    Parses ``ADMIN_EMAILS`` (comma-separated). Whitespace is stripped
    around each entry; empty entries are dropped. Missing env var →
    empty set (fail-closed behaviour: every admin check returns
    False).
    """
    raw = os.environ.get("ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_admin_email(email: str | None) -> bool:
    """Convenience predicate. Lowercase-normalises the input so callers
    don't have to remember the convention.
    """
    if not email:
        return False
    return email.strip().lower() in get_admin_emails()
