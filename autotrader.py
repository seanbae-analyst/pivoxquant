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
    SCAN_INTERVAL = 15          # seconds between scans
    MAX_POSITIONS = 5           # max simultaneous positions
    MAX_DAILY_TRADES = 10       # max trades per day
    MAX_DAILY_LOSS_PCT = 5.0    # stop if daily loss exceeds this %
    MAX_POSITION_PCT = 30       # max % of capital per position
    TP_PCT = 20.0               # fallback take profit %
    SL_PCT = 8.0                # fallback stop loss %
    TRAILING_STOP_PCT = 5.0     # fallback trailing stop from peak %
    BUY_SCORE_MIN = 65          # minimum score to buy
    SELL_SCORE_MAX = 30         # sell if score drops below
    STRONG_SELL_SCORE = 15      # full sell if below

    # Watchlist for auto-scanning
    WATCH_LIST = [
        "NVDA", "TSLA", "AAPL", "AMD", "META", "AMZN", "GOOGL", "MSFT",
        "PLTR", "COIN", "HOOD", "SOFI", "SMCI", "IONQ", "RKLB", "SPY",
    ]
    WATCH_LIST_KR = [
        "005930", "000660", "373220", "035420", "035720",  # 삼성, SK하이닉스, LG에너지, 네이버, 카카오
        "005380", "000270", "068270", "207940", "006400",  # 현대차, 기아, 셀트리온, 삼성바이오, 삼성SDI
    ]
    KR_NAMES = {
        "005930": "삼성전자", "000660": "SK하이닉스", "373220": "LG에너지솔루션",
        "035420": "NAVER", "035720": "카카오", "005380": "현대차",
        "000270": "기아", "068270": "셀트리온", "207940": "삼성바이오로직스",
        "006400": "삼성SDI",
    }

    def __init__(self, db=None, Position=None, TradeHistory=None, user_id=None, app=None):
        self.available = False
        self.running = False
        self.api = None
        self._thread = None
        self._app = app                # Flask app for context in threads
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

        # Korean paper trading (simulated, no real API)
        self._kr_positions = {}     # {code: {entry_price, shares, peak_price, ...}}
        self._kr_capital = 10_000_000  # ₩10,000,000 starting capital
        self._kr_initial_capital = 10_000_000
        self._kr_daily_pnl = 0.0
        self._kis = None            # KIS service instance (set via set_kis)

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

    def set_kis(self, kis_service):
        """Set KIS service for Korean stock data."""
        self._kis = kis_service
        if kis_service and kis_service.available:
            logger.info("AutoTrader: KIS connected (Korean paper trading enabled)")

    def _log(self, msg, level="info"):
        now = datetime.now()
        entry = {"time": now.isoformat(), "msg": msg, "level": level}
        # Daily reset: clear logs from previous days
        today = now.date().isoformat()
        if getattr(self, "_log_date", None) != today:
            self._logs = []
            self._log_date = today
        self._logs.append(entry)
        if len(self._logs) > 200:
            self._logs = self._logs[-200:]
        logger.info(f"[AutoTrader] {msg}")

    # ── Control ───────────────────────────────────────────

    def start(self):
        kr_available = self._kis and self._kis.available
        if not self.available and not kr_available:
            return {"error": "AutoTrader not available (Alpaca/KIS not configured)"}
        if self.running:
            return {"error": "Already running"}

        # Restore existing Alpaca positions so we don't double-buy
        if self.api and not self._positions:
            try:
                for p in self.api.get_all_positions():
                    self._positions[p.symbol] = {
                        "ticker": p.symbol,
                        "symbol": p.symbol,
                        "entry_price": float(p.avg_entry_price),
                        "shares": int(float(p.qty)),
                        "peak_price": float(p.current_price),
                        "entry_time": datetime.now().isoformat(),
                        "score": 0,
                    }
                if self._positions:
                    self._log(f"Restored {len(self._positions)} existing positions: {', '.join(self._positions.keys())}")
            except Exception as e:
                self._log(f"Position restore error: {e}", "error")

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

        # Korean paper trading stats
        kr_equity = self._kr_capital
        kr_deployed = 0
        kr_positions_list = []
        for code, pos in self._kr_positions.items():
            kr_deployed += pos["entry_price"] * pos["shares"]
            kr_positions_list.append(pos)
        kr_total = kr_equity + kr_deployed

        # Enrich US positions with live Alpaca data
        us_positions_list = []
        if self.api and self._positions:
            try:
                alpaca_positions = {p.symbol: p for p in self.api.get_all_positions()}
                for symbol, pos in self._positions.items():
                    ap = alpaca_positions.get(symbol)
                    enriched = {**pos}
                    if ap:
                        enriched["market_value"] = float(ap.market_value)
                        enriched["current_price"] = float(ap.current_price)
                        enriched["unrealized_pl"] = float(ap.unrealized_pl)
                        enriched["unrealized_plpc"] = float(ap.unrealized_plpc)
                        enriched["qty"] = int(ap.qty)
                    us_positions_list.append(enriched)
            except Exception:
                us_positions_list = list(self._positions.values())
        else:
            us_positions_list = list(self._positions.values())

        return {
            "available": self.available or (self._kis and self._kis.available),
            "running": self.running,
            "positions": len(self._positions) + len(self._kr_positions),
            "positions_us": len(self._positions),
            "positions_kr": len(self._kr_positions),
            "trades_today": len(self._trades_today),
            "max_positions": self.MAX_POSITIONS,
            "max_daily_trades": self.MAX_DAILY_TRADES,
            "account": account_info,
            "active_positions": us_positions_list + kr_positions_list,
            "kr_capital": self._kr_capital,
            "kr_equity": round(kr_total),
            "kr_daily_pnl": round(self._kr_daily_pnl),
            "logs": list(reversed(self._logs[-30:])),
        }

    # ── Main Loop ─────────────────────────────────────────

    def _run_loop(self):
        while self.running:
            try:
                us_active = False
                kr_active = False

                # ── US Market (Alpaca) ──
                if self.available:
                    try:
                        clock = self.api.get_clock()
                        # Paper trading: also active in pre/post market (extended hours)
                        us_active = True
                        if clock.is_open:
                            acc = self.api.get_account()
                            daily_pnl_pct = (float(acc.equity) - self._initial_equity) / self._initial_equity * 100
                            if daily_pnl_pct <= -self.MAX_DAILY_LOSS_PCT:
                                self._log(f"US DAILY LOSS LIMIT ({daily_pnl_pct:.1f}%) — Stopping US", "error")
                                us_active = False
                            elif len(self._trades_today) < self.MAX_DAILY_TRADES:
                                self._check_exits()
                                if len(self._positions) < self.MAX_POSITIONS:
                                    self._scan_for_entries()
                        else:
                            # Pre/post market: scan + check exits (extended hours trading)
                            if len(self._trades_today) < self.MAX_DAILY_TRADES:
                                if self._positions:
                                    try:
                                        self._check_exits()
                                    except Exception:
                                        pass
                                if len(self._positions) < self.MAX_POSITIONS:
                                    self._scan_for_entries()
                    except Exception as e:
                        self._log(f"US loop error: {e}", "error")

                # ── Korean Market (KIS Paper) ──
                if self._kis and self._kis.available:
                    try:
                        now = datetime.now()
                        hour, minute = now.hour, now.minute
                        kr_time = hour * 100 + minute
                        kr_market_open = 900 <= kr_time <= 1530 and now.weekday() < 5
                        # Paper trading: always active (use last prices when closed)
                        kr_active = True
                        if kr_market_open:
                            self._check_kr_exits()
                            if len(self._kr_positions) < self.MAX_POSITIONS:
                                self._scan_kr_entries()
                        elif not self._kr_positions:
                            # Market closed + no positions: scan once to populate
                            if not hasattr(self, '_kr_initial_scan_done'):
                                self._log("🇰🇷 KR market closed — running initial scan with last prices", "info")
                                self._scan_kr_entries()
                                self._kr_initial_scan_done = True
                        else:
                            # Market closed but holding positions: check exits with cached prices
                            self._check_kr_exits()
                    except Exception as e:
                        self._log(f"KR loop error: {e}", "error")

                if not us_active and not kr_active:
                    self._log("Both markets closed. Waiting...", "warn")
                    time.sleep(60)
                    continue

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

                    # Safety: cap total deployed capital at 90% of equity
                    deployed = sum(p.get("entry_price", 0) * p.get("shares", 0) for p in self._positions.values())
                    remaining = equity * 0.90 - deployed
                    if remaining <= 0:
                        self._log(f"Skip {symbol}: 90% capital cap reached", "info")
                        continue
                    max_invest = min(max_invest, remaining)

                    shares = int(max_invest / price)
                    if shares < 1 or shares * price > buying_power:
                        continue

                    # Execute buy
                    self._execute_buy(symbol, shares, price, score)

            except Exception as e:
                self._log(f"Scan error {symbol}: {e}", "error")

    def _execute_buy(self, symbol, shares, price, score):
        """Execute a buy order (limit order for extended hours compatibility)."""
        try:
            from alpaca.trading.requests import LimitOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

            # Use limit order at slightly above market price for reliable fills
            limit_price = round(price * 1.005, 2)  # 0.5% above current price

            order = self.api.submit_order(
                LimitOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY,
                    limit_price=limit_price,
                    extended_hours=True,
                )
            )

            # Calculate adaptive exit parameters
            try:
                from quant_models import AdaptiveParams
                import fmp_service as fmp
                h = fmp.get_history(symbol, period="3mo")
                if not h.empty and len(h) >= 20:
                    ap = AdaptiveParams.calculate(
                        h["Close"].values, h["High"].values,
                        h["Low"].values, h["Volume"].values
                    )
                    _tp = ap["tp_pct"]
                    _sl = ap["sl_pct"]
                    _trail = ap["trail_pct"]
                    _profile = ap["profile"]
                else:
                    _tp, _sl, _trail, _profile = self.TP_PCT, self.SL_PCT, self.TRAILING_STOP_PCT, "default"
            except Exception:
                _tp, _sl, _trail, _profile = self.TP_PCT, self.SL_PCT, self.TRAILING_STOP_PCT, "default"

            with self._lock:
                self._positions[symbol] = {
                    "symbol": symbol,
                    "shares": shares,
                    "entry_price": price,
                    "peak_price": price,
                    "entry_time": datetime.now().isoformat(),
                    "score": score,
                    "order_id": str(order.id),
                    "tp_pct": _tp,
                    "sl_pct": _sl,
                    "trail_pct": _trail,
                    "profile": _profile,
                    "tp_price": round(price * (1 + _tp / 100), 2),
                    "sl_price": round(price * (1 - _sl / 100), 2),
                }
                self._trades_today.append({
                    "symbol": symbol, "side": "BUY", "shares": shares,
                    "price": price, "time": datetime.now().isoformat(),
                })

            self._log(f"BUY {shares} x {symbol} @ ${price:.2f} (Score: {score}) — [{_profile}] TP: ${price*(1+_tp/100):.2f} ({_tp:.0f}%) / SL: ${price*(1-_sl/100):.2f} ({_sl:.0f}%) / Trail: {_trail:.0f}%")

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

            # Per-position adaptive params (with fallback to class defaults)
            _tp = pos.get("tp_pct", self.TP_PCT)
            _sl = pos.get("sl_pct", self.SL_PCT)
            _trail = pos.get("trail_pct", self.TRAILING_STOP_PCT)

            # Update peak price
            if current_price > peak_price:
                pos["peak_price"] = current_price
                peak_price = current_price

            # Check take profit
            if pnl_pct >= _tp:
                self._execute_sell(symbol, pos["shares"], current_price, f"TAKE PROFIT (+{pnl_pct:.1f}%) [{pos.get('profile','?')}]")
                continue

            # Check stop loss
            if pnl_pct <= -_sl:
                self._execute_sell(symbol, pos["shares"], current_price, f"STOP LOSS ({pnl_pct:.1f}%) [{pos.get('profile','?')}]")
                continue

            # Check trailing stop
            drop_from_peak = (peak_price - current_price) / peak_price * 100
            if drop_from_peak >= _trail and pnl_pct > 0:
                self._execute_sell(symbol, pos["shares"], current_price, f"TRAILING STOP (peak ${peak_price:.2f} → ${current_price:.2f}) [{pos.get('profile','?')}]")
                continue

    def _execute_sell(self, symbol, shares, price, reason):
        """Execute a sell order (limit order for extended hours compatibility)."""
        try:
            from alpaca.trading.requests import LimitOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

            # Use limit order at slightly below market price for reliable fills
            limit_price = round(price * 0.995, 2)  # 0.5% below current price

            order = self.api.submit_order(
                LimitOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                    limit_price=limit_price,
                    extended_hours=True,
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
            with self._app.app_context():
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
            with self._app.app_context():
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

    # ══════════════════════════════════════════════════════════
    #  KOREAN PAPER TRADING
    # ══════════════════════════════════════════════════════════

    def _kr_tick_size(self, price):
        """Korean stock tick size (호가 단위)."""
        if price < 2000: return 1
        if price < 5000: return 5
        if price < 20000: return 10
        if price < 50000: return 50
        if price < 200000: return 100
        if price < 500000: return 500
        return 1000

    def _kr_round_price(self, price):
        """Round to nearest Korean tick size."""
        tick = self._kr_tick_size(int(price))
        return int(round(price / tick) * tick)

    def _scan_kr_entries(self):
        """Scan Korean watchlist using KIS momentum scanner."""
        if not self._kis:
            return
        try:
            held_codes = set(self._kr_positions.keys())
            results = self._kis.scan_momentum(held_tickers=held_codes)
            if not results:
                return

            for r in results:
                code = r.get("ticker", "")
                if code in self._kr_positions:
                    continue
                if len(self._kr_positions) >= self.MAX_POSITIONS:
                    break

                score = r.get("score", 0)
                price = r.get("price", 0)
                signal = r.get("signal", "")

                if score >= self.BUY_SCORE_MIN and price > 0 and signal in ("ENTRY", "BUY"):
                    # Position sizing
                    alloc_pct = 0.30 if score >= 85 else 0.25 if score >= 75 else 0.15
                    max_invest = self._kr_capital * min(alloc_pct, self.MAX_POSITION_PCT / 100)

                    # Cap at 90% of total
                    deployed = sum(p["entry_price"] * p["shares"] for p in self._kr_positions.values())
                    remaining = self._kr_initial_capital * 0.90 - deployed
                    if remaining <= 0:
                        continue
                    max_invest = min(max_invest, remaining, self._kr_capital)

                    shares = int(max_invest / price)
                    if shares < 1:
                        continue

                    cost = shares * price
                    if cost > self._kr_capital:
                        continue

                    self._simulate_buy_kr(code, shares, price, score, r)

        except Exception as e:
            self._log(f"KR scan error: {e}", "error")

    def _simulate_buy_kr(self, code, shares, price, score, signal_data=None):
        """Simulate buying Korean stock (paper trading)."""
        name = self.KR_NAMES.get(code, signal_data.get("name", code) if signal_data else code)
        cost = shares * price

        with self._lock:
            self._kr_capital -= cost
            self._kr_positions[code] = {
                "symbol": f"{code}.KS",
                "code": code,
                "name": name,
                "shares": shares,
                "entry_price": price,
                "peak_price": price,
                "entry_time": datetime.now().isoformat(),
                "score": score,
                "currency": "KRW",
                "is_korean": True,
                "tp_pct": 8.0,    # Korean market: tighter targets
                "sl_pct": 5.0,
                "trail_pct": 3.0,
                "tp_price": self._kr_round_price(price * 1.08),
                "sl_price": self._kr_round_price(price * 0.95),
            }
            self._trades_today.append({
                "symbol": f"{name}({code})", "side": "BUY", "shares": shares,
                "price": price, "currency": "KRW",
                "time": datetime.now().isoformat(),
            })

        self._log(f"🇰🇷 BUY {shares}x {name} @ ₩{price:,.0f} (Score: {score}) — TP: ₩{price*1.08:,.0f} / SL: ₩{price*0.95:,.0f}")

        # Sync to DB
        ticker_db = f"{code}.KS"
        self._sync_buy_to_db_kr(ticker_db, name, shares, price)

    def _check_kr_exits(self):
        """Check Korean positions for TP/SL/trailing."""
        if not self._kr_positions or not self._kis:
            return

        for code in list(self._kr_positions.keys()):
            pos = self._kr_positions[code]
            try:
                price_data = self._kis.get_current_price(code)
                if not price_data or not price_data.get("price"):
                    continue

                current_price = price_data["price"]
                entry_price = pos["entry_price"]
                peak_price = pos.get("peak_price", entry_price)
                pnl_pct = (current_price - entry_price) / entry_price * 100
                _tp = pos.get("tp_pct", 8.0)
                _sl = pos.get("sl_pct", 5.0)
                _trail = pos.get("trail_pct", 3.0)

                if current_price > peak_price:
                    pos["peak_price"] = current_price
                    peak_price = current_price

                if pnl_pct >= _tp:
                    self._simulate_sell_kr(code, pos["shares"], current_price, f"TAKE PROFIT (+{pnl_pct:.1f}%)")
                elif pnl_pct <= -_sl:
                    self._simulate_sell_kr(code, pos["shares"], current_price, f"STOP LOSS ({pnl_pct:.1f}%)")
                elif peak_price > entry_price:
                    drop = (peak_price - current_price) / peak_price * 100
                    if drop >= _trail and pnl_pct > 0:
                        self._simulate_sell_kr(code, pos["shares"], current_price, f"TRAILING STOP (peak ₩{peak_price:,.0f} → ₩{current_price:,.0f})")

            except Exception as e:
                self._log(f"KR exit check {code}: {e}", "error")

    def _simulate_sell_kr(self, code, shares, price, reason):
        """Simulate selling Korean stock (paper trading)."""
        pos = self._kr_positions.get(code, {})
        name = pos.get("name", code)
        entry_price = pos.get("entry_price", price)
        pnl = (price - entry_price) * shares

        with self._lock:
            self._kr_capital += shares * price
            self._kr_daily_pnl += pnl
            if code in self._kr_positions:
                del self._kr_positions[code]
            self._trades_today.append({
                "symbol": f"{name}({code})", "side": "SELL", "shares": shares,
                "price": price, "pnl": round(pnl), "currency": "KRW",
                "reason": reason, "time": datetime.now().isoformat(),
            })

        self._log(f"🇰🇷 SELL {shares}x {name} @ ₩{price:,.0f} — {reason} — P&L: ₩{pnl:+,.0f}")

        # Sync to DB
        ticker_db = f"{code}.KS"
        self._sync_sell_to_db_kr(ticker_db, name, shares, price, pnl, reason)

    def _sync_buy_to_db_kr(self, ticker, name, shares, price):
        """Sync Korean paper buy to portfolio DB."""
        if not self._db or not self._Position or not self._user_id:
            return
        try:
            with self._app.app_context():
                existing = self._Position.query.filter_by(
                    user_id=self._user_id, ticker=ticker
                ).first()
                if existing:
                    total_shares = existing.shares + shares
                    existing.avg_cost = (existing.avg_cost * existing.shares + price * shares) / total_shares
                    existing.shares = total_shares
                else:
                    pos = self._Position(
                        user_id=self._user_id, ticker=ticker,
                        shares=shares, avg_cost=price
                    )
                    self._db.session.add(pos)

                if self._TradeHistory:
                    trade = self._TradeHistory(
                        user_id=self._user_id, ticker=ticker,
                        name=name, action="BUY",
                        shares=shares, price_per_share=price,
                        total_value=round(shares * price),
                        currency="KRW"
                    )
                    self._db.session.add(trade)
                self._db.session.commit()
                self._log(f"DB SYNC: 🇰🇷 BUY {shares}x {name} added")
        except Exception as e:
            self._log(f"DB SYNC FAILED (KR buy): {e}", "error")

    def _sync_sell_to_db_kr(self, ticker, name, shares, price, pnl, reason):
        """Sync Korean paper sell to portfolio DB."""
        if not self._db or not self._Position or not self._user_id:
            return
        try:
            with self._app.app_context():
                existing = self._Position.query.filter_by(
                    user_id=self._user_id, ticker=ticker
                ).first()
                if existing:
                    if shares >= existing.shares:
                        self._db.session.delete(existing)
                    else:
                        existing.shares -= shares

                if self._TradeHistory:
                    pnl_pct = (price - (existing.avg_cost if existing else price)) / max(existing.avg_cost if existing else price, 1) * 100
                    trade = self._TradeHistory(
                        user_id=self._user_id, ticker=ticker,
                        name=name, action="SELL",
                        shares=shares, price_per_share=price,
                        total_value=round(shares * price),
                        pnl=round(pnl), pnl_pct=round(pnl_pct, 2),
                        currency="KRW"
                    )
                    self._db.session.add(trade)
                self._db.session.commit()
                self._log(f"DB SYNC: 🇰🇷 SELL {shares}x {name} removed")
        except Exception as e:
            self._log(f"DB SYNC FAILED (KR sell): {e}", "error")

    def force_sell_all_kr(self):
        """Emergency: sell all Korean positions."""
        results = []
        for code in list(self._kr_positions.keys()):
            pos = self._kr_positions[code]
            try:
                price_data = self._kis.get_current_price(code) if self._kis else None
                price = price_data["price"] if price_data else pos["entry_price"]
                self._simulate_sell_kr(code, pos["shares"], price, "MANUAL SELL ALL")
                results.append({"symbol": pos.get("name", code), "status": "sold"})
            except Exception as e:
                results.append({"symbol": code, "status": f"error: {e}"})
        return results
