"""
PivoxQuant — Auto Trader (Alpaca Paper Trading)
Fully automated quant trading engine.
Scans → Analyzes → Executes → Manages Risk
"""

import os
import logging
import threading
import time
from datetime import datetime, timedelta

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

    # ── Circuit Breaker Config ───────────────────────────
    CB_POSITION_LOSS_PCT = 15.0     # auto-close if single position loses > 15% intraday
    CB_PORTFOLIO_HOURLY_DD = 3.0    # halt new orders 30 min if portfolio drops > 3% in 1 hour
    CB_PORTFOLIO_DAILY_DD = 5.0     # halt all trading for rest of day if > 5% daily drawdown
    CB_HOURLY_HALT_MINUTES = 30     # how long to halt after hourly drawdown breach
    CB_CONSECUTIVE_LOSS_LIMIT = 3   # pause after N consecutive losing trades
    CB_VELOCITY_PAUSE_MINUTES = 15  # pause duration for velocity breaker
    CB_EMERGENCY_HALT_HOURS = 1     # emergency halt lockout duration

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

        # ── Circuit Breaker State ────────────────────────
        self._circuit_breaker_state = {
            "position_stops": 0,        # count of position-level trips today
            "portfolio_halts": 0,       # count of portfolio-level trips today
            "velocity_pauses": 0,       # count of velocity pauses today
            "consecutive_losses": 0,    # current losing streak
            "halted_until": None,       # datetime when trading can resume
            "last_halt_reason": None,   # string description
        }
        self._equity_snapshots = []     # [(datetime, equity)] for hourly drawdown tracking

        # ── Confirmation Mode ────────────────────────────
        self._pending_trades: list[dict] = []
        self._confirmation_mode = True  # Default: require user confirmation before execution

        # Korean paper trading (simulated, no real API)
        self._kr_positions = {}     # {code: {entry_price, shares, peak_price, ...}}
        self._kr_capital = 10_000_000  # ₩10,000,000 starting capital
        self._kr_initial_capital = 10_000_000
        self._kr_daily_pnl = 0.0
        self._kis = None            # KIS service instance (set via set_kis)

        # ALPACA_ENABLED kill switch (config.py / Dockerfile). Default OFF —
        # Alpaca is disabled to remove the legal risk tied to its "My Data"
        # license. When disabled, AutoTrader will not initialize a US trading
        # client (KIS-based Korean paper trading still works via set_kis()).
        alpaca_enabled = os.environ.get("ALPACA_ENABLED", "0").strip() in (
            "1", "true", "True", "TRUE", "yes",
        )
        api_key = os.environ.get("ALPACA_API_KEY", "").strip()
        secret = os.environ.get("ALPACA_SECRET_KEY", "").strip()

        if not alpaca_enabled:
            logger.info(
                "AutoTrader: Alpaca disabled (ALPACA_ENABLED=0). "
                "US paper trading unavailable; KIS paper trading still supported."
            )
        elif api_key and secret:
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

        # Check emergency halt lockout
        halted_until = self._circuit_breaker_state.get("halted_until")
        if halted_until and datetime.now() < halted_until:
            remaining_min = int((halted_until - datetime.now()).total_seconds() / 60)
            reason = self._circuit_breaker_state.get("last_halt_reason", "circuit breaker active")
            return {"error": f"Trading halted: {reason}. Resumes in {remaining_min} min."}

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
            "circuit_breaker": {
                "position_stops": self._circuit_breaker_state["position_stops"],
                "portfolio_halts": self._circuit_breaker_state["portfolio_halts"],
                "velocity_pauses": self._circuit_breaker_state["velocity_pauses"],
                "consecutive_losses": self._circuit_breaker_state["consecutive_losses"],
                "halted": self._is_halted(),
                "halted_until": self._circuit_breaker_state["halted_until"].isoformat() if self._circuit_breaker_state.get("halted_until") else None,
                "last_halt_reason": self._circuit_breaker_state.get("last_halt_reason"),
            },
            "confirmation_mode": self._confirmation_mode,
            "pending_trades": len(self.get_pending_trades()),
            "logs": list(reversed(self._logs[-30:])),
        }

    # ── Main Loop ─────────────────────────────────────────

    def _run_loop(self):
        while self.running:
            try:
                # ── Circuit Breaker: daily reset + halt check ──
                self._reset_daily_circuit_breaker_state()

                if self._is_halted():
                    reason = self._circuit_breaker_state.get("last_halt_reason", "unknown")
                    halted_until = self._circuit_breaker_state.get("halted_until")
                    remaining = (halted_until - datetime.now()).total_seconds() if halted_until else 0
                    if remaining > 60:
                        self._log(f"Trading halted ({reason}). Resuming in {int(remaining)}s. Monitoring positions only.", "warn")
                    # While halted: still check position-level circuit breakers (emergency exits)
                    self._check_position_circuit_breaker()
                    self._check_position_circuit_breaker_kr()
                    time.sleep(self.SCAN_INTERVAL)
                    continue

                # ── Circuit Breaker: portfolio-level + velocity checks ──
                self._check_portfolio_circuit_breaker()
                self._check_velocity_circuit_breaker()

                if self._is_halted():
                    time.sleep(self.SCAN_INTERVAL)
                    continue

                # ── Position-level circuit breaker (runs even when not halted) ──
                self._check_position_circuit_breaker()
                self._check_position_circuit_breaker_kr()

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

    # ── Confirmation Mode ────────────────────────────────

    def _propose_trade(self, ticker: str, signal: dict, action: str, shares: int, price: float, reason: str):
        """Add trade to pending queue for user confirmation."""
        trade_id = f"{ticker}_{int(time.time())}"
        proposal = {
            "id": trade_id,
            "ticker": ticker,
            "action": action,       # "BUY" or "SELL"
            "shares": shares,
            "price": price,
            "score": signal.get("composite_score", signal.get("score", 0)),
            "signal": signal.get("signal", "NEUTRAL"),
            "reason": reason,
            "proposed_at": time.time(),
            "status": "PENDING",    # PENDING -> APPROVED / REJECTED / EXPIRED
            "expires_at": time.time() + 300,  # 5 minute expiry
        }

        # Attach AdaptiveParams info if available
        if "adaptive_params" in signal:
            ap = signal["adaptive_params"]
            proposal["tp_pct"] = ap.get("tp_pct")
            proposal["sl_pct"] = ap.get("sl_pct")
            proposal["regime"] = ap.get("profile")

        # Attach Korean-specific fields
        if signal.get("is_korean"):
            proposal["currency"] = "KRW"
            proposal["name"] = signal.get("name", ticker)
            proposal["is_korean"] = True
            if "_signal_data" in signal:
                proposal["_signal_data"] = signal["_signal_data"]

        with self._lock:
            self._pending_trades.append(proposal)
            # Clean expired proposals
            now = time.time()
            self._pending_trades = [
                t for t in self._pending_trades
                if t["expires_at"] > now or t["status"] != "PENDING"
            ]

        self._log(f"PROPOSED {action} {shares}x {ticker} @ {'₩' if signal.get('is_korean') else '$'}{price:,.2f} — awaiting confirmation (ID: {trade_id})")
        return trade_id

    def approve_trade(self, trade_id: str) -> dict:
        """User approves a pending trade -- execute it."""
        for trade in self._pending_trades:
            if trade["id"] == trade_id and trade["status"] == "PENDING":
                if trade["expires_at"] < time.time():
                    trade["status"] = "EXPIRED"
                    return {"ok": False, "error": "Trade proposal expired"}

                trade["status"] = "APPROVED"

                # Execute the actual trade
                if trade.get("is_korean"):
                    if trade["action"] == "BUY":
                        self._simulate_buy_kr(
                            trade["ticker"], trade["shares"], trade["price"],
                            trade.get("score", 0), trade.get("_signal_data"),
                        )
                    else:
                        self._simulate_sell_kr(
                            trade["ticker"], trade["shares"], trade["price"],
                            trade.get("reason", "USER APPROVED SELL"),
                        )
                else:
                    if trade["action"] == "BUY":
                        self._execute_buy(
                            trade["ticker"], trade["shares"], trade["price"],
                            trade.get("score", 0),
                        )
                    else:
                        self._execute_sell(
                            trade["ticker"], trade["shares"], trade["price"],
                            trade.get("reason", "USER APPROVED SELL"),
                        )

                self._log(f"APPROVED trade {trade_id}: {trade['action']} {trade['shares']}x {trade['ticker']}")
                return {"ok": True, "trade_id": trade_id}

        return {"ok": False, "error": "Trade not found or already processed"}

    def reject_trade(self, trade_id: str) -> dict:
        """User rejects a pending trade."""
        for trade in self._pending_trades:
            if trade["id"] == trade_id and trade["status"] == "PENDING":
                trade["status"] = "REJECTED"
                self._log(f"REJECTED trade {trade_id}: {trade['action']} {trade['shares']}x {trade['ticker']}")
                return {"ok": True, "trade_id": trade_id}
        return {"ok": False, "error": "Trade not found or already processed"}

    def get_pending_trades(self) -> list:
        """Get all pending trade proposals."""
        now = time.time()
        # Mark expired
        for t in self._pending_trades:
            if t["status"] == "PENDING" and t["expires_at"] < now:
                t["status"] = "EXPIRED"
        return [t for t in self._pending_trades if t["status"] == "PENDING"]

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

                    # Confirmation mode: propose instead of execute
                    if self._confirmation_mode:
                        signal_info = {
                            "composite_score": score,
                            "signal": "BUY",
                            "score": score,
                        }
                        # Attempt to attach adaptive params preview
                        try:
                            from quant_models import AdaptiveParams
                            from services.data import fmp as fmp
                            h = fmp.get_history(symbol, period="3mo")
                            if not h.empty and len(h) >= 20:
                                ap = AdaptiveParams.calculate(
                                    h["Close"].values, h["High"].values,
                                    h["Low"].values, h["Volume"].values,
                                )
                                signal_info["adaptive_params"] = ap
                        except Exception:
                            pass
                        self._propose_trade(
                            symbol, signal_info, "BUY", shares, price,
                            f"Score {score} >= {self.BUY_SCORE_MIN} (quant: {quant_score})",
                        )
                    else:
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
                from services.data import fmp as fmp
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

            # Sync to PivoxQuant portfolio DB
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
                reason = f"TAKE PROFIT (+{pnl_pct:.1f}%) [{pos.get('profile','?')}]"
                if self._confirmation_mode:
                    self._propose_trade(symbol, {"score": pos.get("score", 0), "signal": "SELL"}, "SELL", pos["shares"], current_price, reason)
                else:
                    self._execute_sell(symbol, pos["shares"], current_price, reason)
                continue

            # Check stop loss
            if pnl_pct <= -_sl:
                reason = f"STOP LOSS ({pnl_pct:.1f}%) [{pos.get('profile','?')}]"
                if self._confirmation_mode:
                    self._propose_trade(symbol, {"score": pos.get("score", 0), "signal": "SELL"}, "SELL", pos["shares"], current_price, reason)
                else:
                    self._execute_sell(symbol, pos["shares"], current_price, reason)
                continue

            # Check trailing stop
            drop_from_peak = (peak_price - current_price) / peak_price * 100
            if drop_from_peak >= _trail and pnl_pct > 0:
                reason = f"TRAILING STOP (peak ${peak_price:.2f} -> ${current_price:.2f}) [{pos.get('profile','?')}]"
                if self._confirmation_mode:
                    self._propose_trade(symbol, {"score": pos.get("score", 0), "signal": "SELL"}, "SELL", pos["shares"], current_price, reason)
                else:
                    self._execute_sell(symbol, pos["shares"], current_price, reason)
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

            # Track outcome for velocity circuit breaker
            self._track_trade_outcome(pnl)

            # Sync to PivoxQuant portfolio DB
            self._sync_sell_to_db(symbol, shares, price, pnl, reason)

        except Exception as e:
            self._log(f"SELL FAILED {symbol}: {e}", "error")

    # ── Circuit Breakers ─────────────────────────────────

    def _is_halted(self):
        """Check if trading is currently halted by a circuit breaker."""
        halted_until = self._circuit_breaker_state.get("halted_until")
        if halted_until is None:
            return False
        if datetime.now() >= halted_until:
            reason = self._circuit_breaker_state.get("last_halt_reason", "unknown")
            self._log(f"Circuit breaker cooldown expired (was: {reason}). Resuming trading.")
            self._circuit_breaker_state["halted_until"] = None
            self._circuit_breaker_state["last_halt_reason"] = None
            return False
        return True

    def _halt_trading(self, until, reason):
        """Set a trading halt until a specific datetime."""
        self._circuit_breaker_state["halted_until"] = until
        self._circuit_breaker_state["last_halt_reason"] = reason
        self._log(f"CIRCUIT BREAKER: {reason} — halted until {until.strftime('%H:%M:%S')}", "error")

    def _check_position_circuit_breaker(self):
        """Position-level: auto-close any position losing > CB_POSITION_LOSS_PCT intraday."""
        if not self._positions or not self.api:
            return

        from alpaca.data.requests import StockLatestBarRequest
        from alpaca.data.historical import StockHistoricalDataClient

        api_key = os.environ.get("ALPACA_API_KEY")
        secret = os.environ.get("ALPACA_SECRET_KEY")
        data_client = StockHistoricalDataClient(api_key, secret)

        symbols = list(self._positions.keys())
        try:
            req = StockLatestBarRequest(symbol_or_symbols=symbols)
            bars = data_client.get_stock_latest_bar(req)
        except Exception:
            return

        for symbol in list(self._positions.keys()):
            pos = self._positions.get(symbol)
            if not pos:
                continue
            bar = bars.get(symbol)
            if not bar:
                continue

            current_price = float(bar.close)
            entry_price = pos["entry_price"]
            pnl_pct = (current_price - entry_price) / entry_price * 100

            if pnl_pct <= -self.CB_POSITION_LOSS_PCT:
                self._log(
                    f"CIRCUIT BREAKER: Position {symbol} closed at {pnl_pct:.1f}% (threshold: -{self.CB_POSITION_LOSS_PCT}%)",
                    "error",
                )
                self._execute_sell(symbol, pos["shares"], current_price, f"CIRCUIT BREAKER ({pnl_pct:.1f}%)")
                self._circuit_breaker_state["position_stops"] += 1

    def _check_position_circuit_breaker_kr(self):
        """Position-level circuit breaker for Korean positions."""
        if not self._kr_positions or not self._kis:
            return

        for code in list(self._kr_positions.keys()):
            pos = self._kr_positions.get(code)
            if not pos:
                continue
            try:
                price_data = self._kis.get_current_price(code)
                if not price_data or not price_data.get("price"):
                    continue

                current_price = price_data["price"]
                entry_price = pos["entry_price"]
                pnl_pct = (current_price - entry_price) / entry_price * 100

                if pnl_pct <= -self.CB_POSITION_LOSS_PCT:
                    self._log(
                        f"CIRCUIT BREAKER: Position {pos.get('name', code)} closed at {pnl_pct:.1f}% (threshold: -{self.CB_POSITION_LOSS_PCT}%)",
                        "error",
                    )
                    self._simulate_sell_kr(code, pos["shares"], current_price, f"CIRCUIT BREAKER ({pnl_pct:.1f}%)")
                    self._circuit_breaker_state["position_stops"] += 1
            except Exception:
                pass

    def _check_portfolio_circuit_breaker(self):
        """Portfolio-level: halt on hourly or daily drawdown thresholds."""
        if self._is_halted():
            return  # Already halted

        now = datetime.now()
        current_equity = 0

        # Calculate current total equity (US + KR)
        if self.api:
            try:
                acc = self.api.get_account()
                current_equity = float(acc.equity)
            except Exception:
                return
        else:
            current_equity = self._initial_equity if self._initial_equity else 0

        # Add KR equity
        kr_deployed = sum(p["entry_price"] * p["shares"] for p in self._kr_positions.values())
        kr_total_equity = self._kr_capital + kr_deployed

        # Record equity snapshot for hourly tracking
        self._equity_snapshots.append((now, current_equity, kr_total_equity))
        # Keep only last 2 hours of snapshots
        cutoff = now - timedelta(hours=2)
        self._equity_snapshots = [(t, e, k) for t, e, k in self._equity_snapshots if t >= cutoff]

        # ── Daily drawdown check (US market, existing + formalized) ──
        if self._initial_equity > 0:
            daily_dd = (self._initial_equity - current_equity) / self._initial_equity * 100
            if daily_dd >= self.CB_PORTFOLIO_DAILY_DD:
                end_of_day = now.replace(hour=23, minute=59, second=59)
                self._halt_trading(end_of_day, f"Portfolio halt triggered at -{daily_dd:.1f}% drawdown (daily limit: -{self.CB_PORTFOLIO_DAILY_DD}%)")
                self._circuit_breaker_state["portfolio_halts"] += 1
                return

        # ── Hourly drawdown check ──
        one_hour_ago = now - timedelta(hours=1)
        hourly_snapshots = [(t, e, k) for t, e, k in self._equity_snapshots if t <= one_hour_ago]
        if hourly_snapshots:
            _, earliest_us, earliest_kr = hourly_snapshots[0]
            earliest_total = earliest_us + earliest_kr
            current_total = current_equity + kr_total_equity
            if earliest_total > 0:
                hourly_dd = (earliest_total - current_total) / earliest_total * 100
                if hourly_dd >= self.CB_PORTFOLIO_HOURLY_DD:
                    resume_at = now + timedelta(minutes=self.CB_HOURLY_HALT_MINUTES)
                    self._halt_trading(resume_at, f"Portfolio halt triggered at -{hourly_dd:.1f}% drawdown (hourly limit: -{self.CB_PORTFOLIO_HOURLY_DD}%)")
                    self._circuit_breaker_state["portfolio_halts"] += 1
                    return

    def _check_velocity_circuit_breaker(self):
        """Velocity: pause if N consecutive losing trades."""
        if self._is_halted():
            return
        consecutive = self._circuit_breaker_state["consecutive_losses"]
        if consecutive >= self.CB_CONSECUTIVE_LOSS_LIMIT:
            resume_at = datetime.now() + timedelta(minutes=self.CB_VELOCITY_PAUSE_MINUTES)
            self._halt_trading(
                resume_at,
                f"Velocity pause: {consecutive} consecutive losses (limit: {self.CB_CONSECUTIVE_LOSS_LIMIT})",
            )
            self._circuit_breaker_state["velocity_pauses"] += 1
            # Reset counter so we don't re-trigger immediately after cooldown
            self._circuit_breaker_state["consecutive_losses"] = 0

    def _track_trade_outcome(self, pnl):
        """Track consecutive wins/losses for velocity circuit breaker."""
        if pnl < 0:
            self._circuit_breaker_state["consecutive_losses"] += 1
        else:
            self._circuit_breaker_state["consecutive_losses"] = 0

    def _reset_daily_circuit_breaker_state(self):
        """Reset daily counters. Called at start of each trading day."""
        today = datetime.now().date().isoformat()
        if getattr(self, "_cb_reset_date", None) != today:
            self._circuit_breaker_state["position_stops"] = 0
            self._circuit_breaker_state["portfolio_halts"] = 0
            self._circuit_breaker_state["velocity_pauses"] = 0
            self._circuit_breaker_state["consecutive_losses"] = 0
            # Only clear halt if it was a daily halt (not an emergency halt)
            halted_until = self._circuit_breaker_state.get("halted_until")
            if halted_until and halted_until < datetime.now():
                self._circuit_breaker_state["halted_until"] = None
                self._circuit_breaker_state["last_halt_reason"] = None
            self._equity_snapshots = []
            self._cb_reset_date = today

    def emergency_halt(self):
        """Kill switch: stop scan loop, close all positions, lock out for CB_EMERGENCY_HALT_HOURS."""
        self._log("EMERGENCY HALT activated — closing all positions and locking trading", "error")

        # 1. Stop the scan loop
        self.running = False

        # 2. Close all US positions
        us_results = []
        if self.available:
            res = self.force_sell_all()
            us_results = res.get("results", [])

        # 3. Close all KR positions
        kr_results = self.force_sell_all_kr()

        # 4. Set halt lockout
        resume_at = datetime.now() + timedelta(hours=self.CB_EMERGENCY_HALT_HOURS)
        self._circuit_breaker_state["halted_until"] = resume_at
        self._circuit_breaker_state["last_halt_reason"] = (
            f"Emergency halt activated at {datetime.now().strftime('%H:%M:%S')}. "
            f"Locked for {self.CB_EMERGENCY_HALT_HOURS}h until {resume_at.strftime('%H:%M:%S')}."
        )

        all_results = us_results + kr_results
        self._log(
            f"EMERGENCY HALT complete — {len(all_results)} positions closed, "
            f"trading locked until {resume_at.strftime('%H:%M:%S')}",
            "error",
        )
        return {
            "ok": True,
            "halted_until": resume_at.isoformat(),
            "positions_closed": len(all_results),
            "results": all_results,
        }

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
        """Add position to PivoxQuant portfolio DB."""
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
        """Remove/reduce position from PivoxQuant portfolio DB."""
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

                if score >= self.BUY_SCORE_MIN and price > 0 and signal in ("ENTRY", "POSITIVE"):
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

                    # Confirmation mode: propose instead of execute
                    if self._confirmation_mode:
                        signal_info = {
                            "composite_score": score,
                            "signal": signal,
                            "score": score,
                            "is_korean": True,
                            "name": r.get("name", self.KR_NAMES.get(code, code)),
                            "_signal_data": r,  # Preserve for approve_trade execution
                        }
                        self._propose_trade(
                            code, signal_info, "BUY", shares, price,
                            f"Score {score} >= {self.BUY_SCORE_MIN} (signal: {signal})",
                        )
                    else:
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
                    reason = f"TAKE PROFIT (+{pnl_pct:.1f}%)"
                    if self._confirmation_mode:
                        self._propose_trade(code, {"score": pos.get("score", 0), "signal": "SELL", "is_korean": True, "name": pos.get("name", code)}, "SELL", pos["shares"], current_price, reason)
                    else:
                        self._simulate_sell_kr(code, pos["shares"], current_price, reason)
                elif pnl_pct <= -_sl:
                    reason = f"STOP LOSS ({pnl_pct:.1f}%)"
                    if self._confirmation_mode:
                        self._propose_trade(code, {"score": pos.get("score", 0), "signal": "SELL", "is_korean": True, "name": pos.get("name", code)}, "SELL", pos["shares"], current_price, reason)
                    else:
                        self._simulate_sell_kr(code, pos["shares"], current_price, reason)
                elif peak_price > entry_price:
                    drop = (peak_price - current_price) / peak_price * 100
                    if drop >= _trail and pnl_pct > 0:
                        reason = f"TRAILING STOP (peak {peak_price:,.0f} -> {current_price:,.0f})"
                        if self._confirmation_mode:
                            self._propose_trade(code, {"score": pos.get("score", 0), "signal": "SELL", "is_korean": True, "name": pos.get("name", code)}, "SELL", pos["shares"], current_price, reason)
                        else:
                            self._simulate_sell_kr(code, pos["shares"], current_price, reason)

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

        # Track outcome for velocity circuit breaker
        self._track_trade_outcome(pnl)

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
