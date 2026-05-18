"""Artifact-QA fixtures package.

Re-exports the 10 virtual-user profile registry and the factory that
turns each profile into persisted User + Position + TradeHistory rows
so the 170-case render matrix (17 artifacts x 10 profiles) can import
from a single namespace.
"""
from .virtual_users import USER_PROFILES, VirtualUserProfile  # noqa: F401
from .sample_data_factory import seed_virtual_user            # noqa: F401

__all__ = ["USER_PROFILES", "VirtualUserProfile", "seed_virtual_user"]
