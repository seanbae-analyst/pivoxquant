"""Service singletons — centralized instance management."""
from __future__ import annotations
from typing import Any

from services.quant.engine import QuantEngine
from services.data.fetcher import DataFetcher
from services.ai.service import AIService
from services.trading.daytrade import DayTradeService
from services.data.realtime import RealtimeService

# REMOVED 2026-04-27 per CEO + legal: top-level `from services.trading.autotrader import AutoTrader`
# eliminated alongside the autotrade feature removal (투자일임업 등록 회피).
# `services/trading/autotrader.py` is preserved on disk for rollback; importing it here at module
# load would still execute its module side-effects (AutoTrader class build,
# circuit-breaker constants, etc.), which is undesirable when the feature is
# disabled. Re-enable by restoring the import + the `init_trader()` body below.

engine = QuantEngine()
fetcher = DataFetcher()
ai = AIService()
daytrade = DayTradeService()
realtime = RealtimeService()

# AutoTrader removed 2026-04-27. `trader` kept as `None` for backward
# compatibility with any caller that still references `services.container.trader`
# (those callers should treat None as "feature disabled" and short-circuit).
trader: Any = None


def init_trader(db, Position, TradeHistory, app):
    """No-op since 2026-04-27 (per CEO + legal — autotrade feature removed).

    Kept as a callable so legacy invocations (e.g. app.py during a partial
    rollback) do not crash with AttributeError. Returns None.

    Restore path:
      1) Re-add `from services.trading.autotrader import AutoTrader` at module top.
      2) Replace this body with the prior implementation (AutoTrader instance
         + optional KISService market-data binding).
      3) Re-enable the `svc.init_trader(...)` call in app.py.
      4) Re-register routes/autotrade.py blueprint in routes/__init__.py.
    """
    return None
