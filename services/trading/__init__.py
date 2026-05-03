"""Trading services package.

- daytrade: active intraday scanner
- autotrader: DISABLED 2026-04-27 per CEO + legal (kept for rollback)
"""
from services.trading.daytrade import DayTradeService

__all__ = ["DayTradeService"]
# autotrader는 명시 export 안 함 (disabled). 직접 from services.trading.autotrader import 가능.
