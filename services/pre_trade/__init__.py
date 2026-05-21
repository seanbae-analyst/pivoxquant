"""Pre-trade friction package — Feature 6.

Public surface re-exported here so callers don't reach inside the
service module:

    from services.pre_trade import start_cooldown, check_status, proceed, cancel
"""
from .friction import (
    start_cooldown,
    check_status,
    list_reflections,
    proceed,
    cancel,
)

__all__ = [
    "start_cooldown",
    "check_status",
    "list_reflections",
    "proceed",
    "cancel",
]
