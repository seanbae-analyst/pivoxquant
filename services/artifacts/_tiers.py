"""Shared paid-tier sets for artifact cron fan-out.

Why this exists
---------------
Each artifact service used to define its own ``_PAID_TIERS`` frozenset and
filter ``User.subscription_tier.in_(_PAID_TIERS)`` when selecting recipients
for scheduled (cron) PDF generation. Those literals predated the
Companion-tier rollout (``premium_plus``) and the owner/founder tier
(``founding_lifetime``) — see ``routes/decorators.py:_TIER_RANK`` where
``premium_plus`` (rank 3) and ``founding_lifetime`` (rank 4) both outrank
``premium`` (rank 2).

The drift meant a ``founding_lifetime`` or ``premium_plus`` user — the
*highest*-paying / owner accounts — was silently excluded from every
scheduled artifact, because their stored ``subscription_tier`` value was
not in the per-service literal. This module centralises the membership
sets so the higher tiers can never be dropped again.

Two canonical sets
-------------------
``PAID_TIERS_PRO_AND_UP``
    Everything from ``pro`` upward. Use for artifacts whose original gate
    was ``{"pro", "premium", "elite"}``.

``PAID_TIERS_PREMIUM_AND_UP``
    Everything from ``premium`` upward (``pro`` excluded). Use for
    artifacts whose original gate was ``{"premium", "elite"}``.

Both sets always include ``premium_plus`` and ``founding_lifetime`` so the
top tiers are guaranteed coverage. ``elite`` is retained as a legacy alias
that some historical rows may still carry.
"""
from __future__ import annotations

from typing import Final

# Companion / owner tiers — always entitled. Kept in one place so adding a
# future tier (e.g. another founder cohort) only touches this line.
_TOP_TIERS: Final[frozenset[str]] = frozenset({"premium_plus", "founding_lifetime"})

#: pro < premium < elite < premium_plus < founding_lifetime
PAID_TIERS_PRO_AND_UP: Final[frozenset[str]] = (
    frozenset({"pro", "premium", "elite"}) | _TOP_TIERS
)

#: premium < elite < premium_plus < founding_lifetime  (pro excluded)
PAID_TIERS_PREMIUM_AND_UP: Final[frozenset[str]] = (
    frozenset({"premium", "elite"}) | _TOP_TIERS
)

__all__ = ["PAID_TIERS_PRO_AND_UP", "PAID_TIERS_PREMIUM_AND_UP"]
