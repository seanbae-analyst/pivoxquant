"""Service singletons — centralized instance management."""
from __future__ import annotations
from engine import QuantEngine
from data_fetcher import DataFetcher
from ai_service import AIService
from daytrade_service import DayTradeService
from realtime_service import RealtimeService
from autotrader import AutoTrader

engine = QuantEngine()
fetcher = DataFetcher()
ai = AIService()
daytrade = DayTradeService()
realtime = RealtimeService()

# AutoTrader requires db + models, initialized via init_trader()
trader: AutoTrader | None = None


def init_trader(db, Position, TradeHistory, app):
    """Initialize AutoTrader after models are loaded.

    Security note (H2, 2026-04-24):
        The global `KISService()` here is intentionally app-owner-scoped —
        it is used ONLY for *public market data* queries (get_current_price,
        scan_momentum, intraday bars), never for per-user balance or order
        APIs. KIS's "1 App Key = 1 계좌" covenant applies to account-bound
        operations; market-data endpoints do not touch any user's account.

        All per-user operations (balance sync, credential storage,
        optional order execution) flow through `UserKISService(user_id)`
        with encrypted per-user credentials. See
        `services/broker/user_kis_service.py`.

        DO NOT call `kis.get_balance()` / `kis.buy_order()` / `kis.sell_order()`
        on this global instance — those are either disabled (H5) or would
        return the app-owner's account data and leak across users.
    """
    global trader
    trader = AutoTrader(db=db, Position=Position, TradeHistory=TradeHistory, app=app)
    try:
        from kis_service import KISService
        kis = KISService()
        if kis.available:
            # Market-data-only binding. AutoTrader uses this for KR price
            # scanning in paper mode; per-user trading goes through
            # UserKISService (never this singleton).
            trader.set_kis(kis)
    except Exception:
        pass
    return trader
