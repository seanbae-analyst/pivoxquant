"""PivoxQuant — Toss Securities Open API, **read-only, own-account only**.

Why this package exists
-----------------------
The only screen in PivoxQuant that needs prices is ``/portfolio`` (NAV,
unrealised P&L). Everything else — 멈춤 · 기록 · 거울 — never calls a price
service. Reading the valuation straight from the CEO's *own* brokerage account
therefore closes two open problems at once: the FMP §2.2.2 display licence and
R7 (KIS 시세 재배포). This package is the first concrete instance of that.

What it deliberately is **not**
-------------------------------
* Not a user-facing broker link. ``BROKER_LINKING_AVAILABLE`` stays ``false``
  in the frontend. Toss's Open API terms §5② forbid handing the app key to a
  third party, so asking *other* users to paste their keys is off the table
  until counsel answers whether a user-authorised service counts. This code
  reads credentials from the operator's own environment only.
* Not able to place, modify or cancel orders. Toss issues **one token with no
  scopes** — the same token that reads holdings can ``POST /api/v1/orders``.
  The process boundary is therefore the only defence, and
  :class:`services.toss.client.TossReadOnlyClient` enforces it with a GET-only
  path allowlist that raises :class:`TossReadOnlyViolation` before any request
  leaves the process. Mirrors the ``KIS_READ_ONLY`` guard in ``services/kis``.
"""
from services.toss.client import (  # noqa: F401
    TossApiError,
    TossReadOnlyClient,
    TossReadOnlyViolation,
    READ_ONLY_PATHS,
)
