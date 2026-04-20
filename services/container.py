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
    """Initialize AutoTrader after models are loaded."""
    global trader
    trader = AutoTrader(db=db, Position=Position, TradeHistory=TradeHistory, app=app)
    try:
        from kis_service import KISService
        kis = KISService()
        if kis.available:
            trader.set_kis(kis)
    except Exception:
        pass
    return trader
