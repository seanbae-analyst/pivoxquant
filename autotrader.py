"""
StockPilot — Auto Trader (Alpaca Paper Trading)
Fully automated quant trading engine.
Scans → Analyzes → Executes → Manages Risk
"""

import os
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class AutoTrader:
    """Automated trading engine using Alpaca Paper Trading."""

    # ── Config ────────────────────────────────────────────
    SCAN_INTERVAL = 30          # seconds between scans
    MAX_POSITIONS = 5           # max simultaneous positions
    MAX_DAILY_TRADES = 10       # max trades per day
    MAX_DAILY_LOSS_PCT = 5.0    # stop if daily loss exceeds this %
    MAX_POSITION_PCT = 30       # max % of capital per position
    TP_PCT = 20.0               # take profit %
    SL_PCT = 8.0                # stop loss %
    TRAILING_STOP_PCT = 5.0     # trailing stop from peak %
    BUY_SCORE_MIN = 65          # minimum score to buy
    SELL_SCORE_MAX = 30         # sell if score drops below
    STRONG_SELL_SCORE = 15      # full sell if below

    # Watchlist for auto-scanning
    WATCH_LIST = [
        "NVDA", "TSLA", "AAPL", "AMD", "META", "AMZN", "GOOGL", "MSFT",
        "PLTR", "COIN", "HOOD", "SOFI", "SMCI", "IONQ", "RKLB", "SPY",
    ]

    def __init__(self, db=None, Position=None, TradeHistory=None, user_id=None):
        self.available = False
        self.running = False
        self.api = None
        self._thread = None
        self._db = db                  # Flask-SQLAlchemy db instance
        self._Position = Position      # Position model
        self._TradeHistory = TradeHistory  # TradeHistory model
        self._user_id = user_id        # User ID for DB sync
        self._positions = {}        # {symbol: {entry_price, shares, peak_price, entry_time, score}}
        self._trades_today = []     # list of trades today
        self._daily_pnl = 0.0
        self._initial_equity = 0
        self._logs = []             # recent activity logs
        self._lock = threading.Lock()

        api_key = os.environ.get("ALPACA_API_KEY", "").strip()
        secret = os.environ.get("ALPACA_SECRET_KEY", "").strip()

        if api_key and secret:
            try:
                from alpaca.trading.client import TradingClient
                self.api = TradingClient(api_key, secret, paper=True)
                account = self.api.get_account()
                self._initial_equity = float(account.equity)
                self.available = True
                logger.info(f"AutoTrader initialized (Paper Trading) — Equity: ${self._initial_equity:,.2f}")
            except Exception as e:
                logger.warning(f"AutoTrader init failed: {e}")

    def _log(self, msg, level="info"):
        entry = {"time": datetime.now().isoformat(), "msg": msg, "level": level}
        self._logs.append(entry)
        if len(self._logs) > 100:
            self._logs = self._logs[-100:]
        logger.info(f"[AutoTrader] {msg}")

    # ── Control ───────────────────────────────────────────

    def start(self):
        if not self.available:
            return {"error": "AutoTrader not available (Alpaca not configured)"}
        if self.running:
            return {"error": "Already running"}

        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._log("AutoTrader STARTED")
        return {"ok": True, "status": "running"}

    def stop(self):
        self.running = False
        self._log("AutoTrader STOPPED")
        return {"ok": True, "status": "stopped"}

    def get_status(self):
        account_info = {}
        if self.available:
            try:
                acc = self.api.get_account()
                account_info = {
                    "equity": float(acc.equity),
                    "cash": float(acc.cash),
                    "buying_power": float(acc.buying_power),
                    "initial_equity": self._initial_equity,
                    "daily_pnl": round(float(acc.equity) - self._initial_equity, 2),
                    "daily_pnl_pct": round((float(acc.equity) - self._initial_equity) / self._initial_equity * 100, 2) if self._initial_equity > 0 else 0,
                }
            except Exception:
                pass

        return {
            "available": self.available,
            "running": self.running,
            "positions": len(self._positions),
            "trades_today": len(self._trades_today),
            "max_positions": self.MAX_POSITIONS,
            "max_daily_trades": self.MAX_DAILY_TRADES,
            "account": account_info,
            "active_positions": list(self._positions.values()),
            "logs": self._logs[-20:],
        }

    # ── Main Loop ─────────────────────────────────────────

    def _run_loop(self):
        while self.running:
            try:
                # Check if market is open
                clock = self.api.get_clock()
                if not clock.is_open:
                    self._log("Market closed. Waiting...", "warn")
                    time.sleep(60)
                    continue

                # Check daily loss limit
                acc = self.api.get_account()
                daily_pnl_pct = (float(acc.equity) - self._initial_equity) / self._initial_equity * 100
                if daily_pnl_pct <= -self.MAX_DAILY_LOSS_PCT:
                    self._log(f"DAILY LOSS LIMIT ({daily_pnl_pct:.1f}%) — Stopping", "error")
                    self.running = False
                    break

                # Check daily trade limit
                if len(self._trades_today) >= self.MAX_DAILY_TRADES:
                    self._log("Daily trade limit reached. Waiting...")
                    time.sleep(60)
                    continue

                # 1. Monitor existing positions (TP/SL/Trailing)
                self._check_exits()

                # 2. Scan for new entries
                if len(self._positions) < self.MAX_POSITIONS:
                    self._scan_for_entries()

            except Exception as e:
                self._log(f"Loop error: {e}", "error")

            time.sleep(self.SCAN_INTERVAL)

    # ── Entry Logic ───────────────────────────────────────

    def _scan_for_entries(self):
        """Scan watchlist using full quant engine (Tech + Fund + News + Quant Models)."""
        from engine import QuantEngine
        qe = QuantEngine()

        for symbol in self.WATCH_LIST:
            if symbol in self._positions:
                continue  # Already holding
            if len(self._positions) >= self.MAX_POSITIONS:
                break

            try:
                analysis = qe.analyze(symbol, 100000)  # Paper trading capital
                if not analysis:
                    continue

                score = analysis.get("score", 0)
                price = analysis.get("price", 0)
                rsi = None  # RSI is embedded in tech_score now

                # Buy conditions — full quant score (Tech 30% + Fund 20% + News 10% + Quant 40%)
                if score >= self.BUY_SCORE_MIN and price > 0:
                    # Skip if quant models flag bearish regime
                    quant_score = analysis.get("quant_score", 50)
                    if quant_score < 30:
                        continue  # Quant models strongly bearish

                    # Calculate position size
                    acc = self.api.get_account()
                    buying_power = float(acc.buying_power)
                    equity = float(acc.equity)

                    if score >= 85:
                        alloc_pct = 0.30
                    elif score >= 75:
                        alloc_pct = 0.25
                    else:
                        alloc_pct = 0.15

                    max_invest = equity * min(alloc_pct, self.MAX_POSITION_PCT / 100)
                    shares = int(max_invest / price)

                    if shares < 1 or shares * price > buying_power:
                        continue

                    # Execute buy
                    self._execute_buy(symbol, shares, price, score)

            except Exception as e:
                self._log(f"Scan error {symbol}: {e}", "error")

    def _execute_buy(self, symbol, shares, price, score):
        """Execute a market buy order."""
        try:
            from alpaca.trading.requests import MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

            order = self.api.submit_order(
                MarketOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY,
                )
            )

            with self._lock:
                self._positions[symbol] = {
                    "symbol": symbol,
                    "shares": shares,
                    "entry_price": price,
                    "peak_price": price,
                    "entry_time": datetime.now().isoformat(),
                    "score": score,
                    "order_id": str(order.id),
                    "tp_price": round(price * (1 + self.TP_PCT / 100), 2),
                    "sl_price": round(price * (1 - self.SL_PCT / 100), 2),
                }
                self._trades_today.append({
                    "symbol": symbol, "side": "BUY", "shares": shares,
                    "price": price, "time": datetime.now().isoformat(),
                })

            self._log(f"BUY {shares} x {symbol} @ ${price:.2f} (Score: {score}) — TP: ${price*(1+self.TP_PCT/100):.2f} / SL: ${price*(1-self.SL_PCT/100):.2f}")

            # Sync to StockPilot portfolio DB
            self._sync_buy_to_db(symbol, shares, price)

        except Exception as e:
            self._log(f"BUY FAILED {symbol}: {e}", "error")

    # ── Exit Logic ────────────────────────────────────────

    def _check_exits(self):
        """Check all positions for TP/SL/trailing stop."""
        if not self._positions:
            return

        # Get latest prices
        from alpaca.data.requests import StockLatestBarRequest
        from alpaca.data.historical import StockHistoricalDataClient

        api_key = os.environ.get("ALPACA_API_KEY")
        secret = os.environ.get("ALPACA_SECRET_KEY")
        data_client = StockHistoricalDataClient(api_key, secret)

        symbols = list(self._positions.keys())
        try:
            req = StockLatestBarRequest(symbol_or_symbols=symbols)
            bars = data_client.get_stock_latest_bar(req)
        except Exception as e:
            self._log(f"Price fetch error: {e}", "error")
            return

        for symbol in list(self._positions.keys()):
            pos = self._positions[symbol]
            bar = bars.get(symbol)
            if not bar:
                continue

            current_price = float(bar.close)
            entry_price = pos["entry_price"]
            peak_price = pos.get("peak_price", entry_price)
            pnl_pct = (current_price - entry_price) / entry_price * 100

            # Update peak price
            if current_price > peak_price:
                pos["peak_price"] = current_price
                peak_price = current_price

            # Check take profit
            if pnl_pct >= self.TP_PCT:
                self._execute_sell(symbol, pos["shares"], current_price, f"TAKE PROFIT (+{pnl_pct:.1f}%)")
                continue

            # Check stop loss
            if pnl_pct <= -self.SL_PCT:
                self._execute_sell(symbol, pos["shares"], current_price, f"STOP LOSS ({pnl_pct:.1f}%)")
                continue

            # Check trailing stop
            drop_from_peak = (peak_price - current_price) / peak_price * 100
            if drop_from_peak >= self.TRAILING_STOP_PCT and pnl_pct > 0:
                self._execute_sell(symbol, pos["shares"], current_price, f"TRAILING STOP (peak ${peak_price:.2f} → ${current_price:.2f})")
                continue

    def _execute_sell(self, symbol, shares, price, reason):
        """Execute a market sell order."""
        try:
            from alpaca.trading.requests import MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

            order = self.api.submit_order(
                MarketOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                )
            )

            pos = self._positions.get(symbol, {})
            entry_price = pos.get("entry_price", price)
            pnl = (price - entry_price) * shares

            with self._lock:
                if symbol in self._positions:
                    del self._positions[symbol]
                self._trades_today.append({
                    "symbol": symbol, "side": "SELL", "shares": shares,
                    "price": price, "pnl": round(pnl, 2),
                    "reason": reason, "time": datetime.now().isoformat(),
                })

            self._log(f"SELL {shares} x {symbol} @ ${price:.2f} — {reason} — P&L: ${pnl:+.2f}")

            # Sync to StockPilot portfolio DB
            self._sync_sell_to_db(symbol, shares, price, pnl, reason)

        except Exception as e:
            self._log(f"SELL FAILED {symbol}: {e}", "error")

    # ── Manual Actions ────────────────────────────────────

    def force_sell_all(self):
        """Emergency: sell all positions."""
        if not self.available:
            return {"error": "Not available"}
        results = []
        for symbol in list(self._positions.keys()):
            pos = self._positions[symbol]
            try:
                from alpaca.data.requests import StockLatestBarRequest
                from alpaca.data.historical import StockHistoricalDataClient
                data_client = StockHistoricalDataClient(
                    os.environ.get("ALPACA_API_KEY"),
                    os.environ.get("ALPACA_SECRET_KEY")
                )
                bars = data_client.get_stock_latest_bar(
                    StockLatestBarRequest(symbol_or_symbols=[symbol])
                )
                price = float(bars[symbol].close) if bars.get(symbol) else pos["entry_price"]
                self._execute_sell(symbol, pos["shares"], price, "MANUAL SELL ALL")
                results.append({"symbol": symbol, "status": "sold"})
            except Exception as e:
                results.append({"symbol": symbol, "status": f"error: {e}"})
        return {"results": results}

    # ── DB Sync ───────────────────────────────────────────

    def _sync_buy_to_db(self, symbol, shares, price):
        """Add position to StockPilot portfolio DB."""
        if not self._db or not self._Position or not self._user_id:
            return
        try:
            from flask import current_app
            with current_app.app_context():
                # Check if position already exists
                existing = self._Position.query.filter_by(
                    user_id=self._user_id, ticker=symbol
                ).first()
                if existing:
                    # Update: weighted average cost
                    total_shares = existing.shares + shares
                    existing.avg_cost = (existing.avg_cost * existing.shares + price * shares) / total_shares
                    existing.shares = total_shares
                else:
                    # New position
                    pos = self._Position(
                        user_id=self._user_id, ticker=symbol,
                        shares=shares, avg_cost=price
                    )
                    self._db.session.add(pos)

                # Add trade history
                if self._TradeHistory:
                    trade = self._TradeHistory(
                        user_id=self._user_id, ticker=symbol,
                        name=symbol, action="BUY",
                        shares=shares, price_per_share=price,
                        total_value=round(shares * price, 2),
                        currency="USD"
                    )
                    self._db.session.add(trade)

                self._db.session.commit()
                self._log(f"DB SYNC: BUY {shares}x {symbol} added to portfolio")
        except Exception as e:
            self._log(f"DB SYNC FAILED (buy): {e}", "error")

    def _sync_sell_to_db(self, symbol, shares, price, pnl, reason):
        """Remove/reduce position from StockPilot portfolio DB."""
        if not self._db or not self._Position or not self._user_id:
            return
        try:
            from flask import current_app
            with current_app.app_context():
                existing = self._Position.query.filter_by(
                    user_id=self._user_id, ticker=symbol
                ).first()
                if existing:
                    if shares >= existing.shares:
                        # Full sell
                        self._db.session.delete(existing)
                    else:
                        # Partial sell
                        existing.shares -= shares

                # Add trade history
                if self._TradeHistory:
                    pnl_pct = (price - (existing.avg_cost if existing else price)) / max(existing.avg_cost if existing else price, 0.01) * 100
                    trade = self._TradeHistory(
                        user_id=self._user_id, ticker=symbol,
                        name=symbol, action="SELL",
                        shares=shares, price_per_share=price,
                        total_value=round(shares * price, 2),
                        pnl=round(pnl, 2), pnl_pct=round(pnl_pct, 2),
                        currency="USD"
                    )
                    self._db.session.add(trade)

                self._db.session.commit()
                self._log(f"DB SYNC: SELL {shares}x {symbol} removed from portfolio")
        except Exception as e:
            self._log(f"DB SYNC FAILED (sell): {e}", "error")
