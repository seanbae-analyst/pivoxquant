"""Vendor market-quote DISPLAY gate — the single read point for
``MARKET_DATA_DISPLAY_ENABLED``.

Why this module exists
----------------------
2026-09-19: a terms sweep found no free, legal way to show vendor closing
prices to an end user. FMP ToS §2.2.2 bars displaying their data without a
Data Display Agreement (a free closed beta is not exempt) and §2.2 bars
derived works without prior written approval; the 금융위 공공데이터 4유형 and
KRX Open API feeds restrict redistribution, and every free US EOD source is
personal-use only.

CEO decision: turn the display OFF and run the product on cost basis
(``avg_cost x shares`` — the user's own data, no vendor licence). Turn it back
ON the day the FMP Data Display Agreement is executed. That is why this is a
flag and not a deletion.

Scope of the gate
-----------------
It gates **user display**, not the fetch layer. SignalCache warming, the
operator's own KIS read-only account and internal cron work all keep running:
what stops is emitting a vendor quote — or a number computed from one — in a
response a user reads.

Two flags, independently safe
-----------------------------
The frontend has its own ``NEXT_PUBLIC_MARKET_DATA_DISPLAY``. The two never
consult each other and neither may assume the other is set correctly: the
backend REFUSES (or nulls), the frontend HIDES. Either one alone is sufficient
to keep a vendor price off the screen.

Public API
----------
:func:`market_data_display_enabled` — the boolean. Read it here, never from
    ``os.environ``, so a request handler and a test can both override it via
    ``current_app.config["MARKET_DATA_DISPLAY_ENABLED"]``.
:func:`market_data_display_disabled_error` — the one canonical refusal for
    routes whose entire payload is a quote (there is no cost-basis version of
    "what is the KOSPI at").
:data:`MARKET_DATA_DISPLAY_FIELD` / :data:`PRICE_SOURCE_DISABLED` — the two
    response literals the frontend pattern-matches on.
"""
from __future__ import annotations

from typing import Tuple

from flask import current_app, has_app_context
from flask.wrappers import Response

import config as _config
from services.error_responses import api_error

#: Machine-readable ``code`` on every refusal from this gate.
DISABLED_CODE = "MARKET_DATA_DISPLAY_DISABLED"

#: Top-level boolean key added to every response that a quote would otherwise
#: have reached. Present in BOTH states (true / false) so the frontend has one
#: shape to branch on rather than "absent means on".
MARKET_DATA_DISPLAY_FIELD = "market_data_display"

#: ``price_source`` sentinel on a position row whose price was withheld. A
#: string (not null) because existing consumers switch on this value; the
#: neighbouring price fields are the ones that go null.
PRICE_SOURCE_DISABLED = "display_disabled"

_DISABLED_EN = (
    "Market price display is turned off. Cost-basis figures are unaffected."
)
_DISABLED_KR = (
    "시세 표시가 중단되어 있습니다. 취득가 기준 정보는 그대로 제공됩니다."
)


def market_data_display_enabled() -> bool:
    """Return True only when vendor quotes may be shown to a user.

    Prefers ``current_app.config`` (so ``monkeypatch.setitem(app.config, ...)``
    works and ``.env``'s ``override=True`` cannot surprise a test) and falls
    back to the module-level constant outside a request/app context — e.g. the
    APScheduler thread before it enters ``app.app_context()``.
    """
    if has_app_context():
        try:
            return bool(current_app.config["MARKET_DATA_DISPLAY_ENABLED"])
        except KeyError:
            # App built without config.Config (a bare test harness) — fall
            # through to the env-derived default rather than crashing.
            pass
    return bool(_config.MARKET_DATA_DISPLAY_ENABLED)


def market_data_display_disabled_error(status: int = 503) -> Tuple[Response, int]:
    """The canonical refusal for a route whose whole payload is a quote.

    503 (not 404): the surface is not gone, it is withheld until the Data
    Display Agreement lands. The body carries ``market_data_display: false``
    as well as the code so a client can branch on one field whether the reply
    was a 200 or an error.
    """
    return api_error(
        en=_DISABLED_EN,
        kr=_DISABLED_KR,
        code=DISABLED_CODE,
        status=status,
        **{MARKET_DATA_DISPLAY_FIELD: False},
    )


__all__ = [
    "DISABLED_CODE",
    "MARKET_DATA_DISPLAY_FIELD",
    "PRICE_SOURCE_DISABLED",
    "market_data_display_enabled",
    "market_data_display_disabled_error",
]
