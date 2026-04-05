"""
StockPilot — Backtester
Tests quant strategies on historical data.
"Would this strategy have made money?"
"""

import numpy as np
import pandas as pd
import yfinance as yf
import logging
from datetime import datetime
from quant_models import MeanReversion, MomentumBreakout, VolatilityRegime, RegimeSwitching

logger = logging.getLogger(__name__)


class Backtester:

    @staticmethod
    def run(ticker, period="1y", initial_capital=10000,
            buy_threshold=None, sell_threshold=None,
            tp_pct=20, sl_pct=8):
        """
        Run backtest on a single ticker using StockPilot quant scoring.
        Adaptive thresholds based on stock type.
        """
        try:
            # Adaptive thresholds
            is_korean = ticker.upper().endswith('.KS') or ticker.upper().endswith('.KQ')
            is_etf = ticker.upper() in ('TSLL','ETHU','SPY','QQQ','TLT','GLD','USO')
            if buy_threshold is None:
                if is_korean:
                    buy_threshold = 45
                elif is_etf:
                    buy_threshold = 58
                else:
                    buy_threshold = 62
            if sell_threshold is None:
                sell_threshold = 28 if is_korean else 30

            h = yf.Ticker(ticker).history(period=period)
            if h.empty or len(h) < 60:
                return None

            closes = h["Close"].values
            highs = h["High"].values
            lows = h["Low"].values
            volumes = h["Volume"].values
            dates = [d.strftime("%Y-%m-%d") for d in h.index]

            capital = initial_capital
            shares = 0
            entry_price = 0
            peak_price = 0
            portfolio_values = []
            trades = []
            daily_scores = []

            for i in range(60, len(closes)):
                price = float(closes[i])
                window = closes[:i+1]
                high_w = highs[:i+1]
                low_w = lows[:i+1]
                vol_w = volumes[:i+1]

                # Calculate quant score
                score = Backtester._calc_score(window, high_w, low_w, vol_w, is_korean)
                daily_scores.append({"date": dates[i], "score": round(score, 1)})

                # Portfolio value
                pv = capital + shares * price
                portfolio_values.append({"date": dates[i], "value": round(pv, 2), "price": round(price, 2)})

                # Trading logic
                if shares == 0 and score >= buy_threshold:
                    # BUY
                    shares_to_buy = int(capital * 0.9 / price)  # 90% of capital
                    if shares_to_buy > 0:
                        shares = shares_to_buy
                        entry_price = price
                        peak_price = price
                        capital -= shares * price
                        trades.append({
                            "date": dates[i], "action": "BUY",
                            "price": round(price, 2), "shares": shares,
                            "score": round(score, 1),
                        })

                elif shares > 0:
                    # Update peak
                    if price > peak_price:
                        peak_price = price

                    pnl_pct = (price - entry_price) / entry_price * 100
                    trail_drop = (peak_price - price) / peak_price * 100

                    sold = False
                    reason = ""

                    # Take profit
                    if pnl_pct >= tp_pct:
                        reason = f"TP +{pnl_pct:.1f}%"
                        sold = True
                    # Stop loss
                    elif pnl_pct <= -sl_pct:
                        reason = f"SL {pnl_pct:.1f}%"
                        sold = True
                    # Trailing stop (5% from peak, only if profitable)
                    elif trail_drop >= 5 and pnl_pct > 0:
                        reason = f"Trail {trail_drop:.1f}%"
                        sold = True
                    # Score drops below sell threshold
                    elif score < sell_threshold:
                        reason = f"Score {score:.0f}"
                        sold = True

                    if sold:
                        pnl = (price - entry_price) * shares
                        capital += shares * price
                        trades.append({
                            "date": dates[i], "action": "SELL",
                            "price": round(price, 2), "shares": shares,
                            "pnl": round(pnl, 2),
                            "pnl_pct": round(pnl_pct, 1),
                            "reason": reason, "score": round(score, 1),
                        })
                        shares = 0
                        entry_price = 0
                        peak_price = 0

            # Final value
            final_value = capital + shares * float(closes[-1])
            total_return = (final_value - initial_capital) / initial_capital * 100

            # Buy & hold comparison
            bh_return = (float(closes[-1]) - float(closes[60])) / float(closes[60]) * 100

            # Stats
            wins = [t for t in trades if t.get("action") == "SELL" and t.get("pnl", 0) > 0]
            losses = [t for t in trades if t.get("action") == "SELL" and t.get("pnl", 0) <= 0]
            total_trades = len([t for t in trades if t["action"] == "SELL"])
            win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0

            # Max drawdown
            values = [p["value"] for p in portfolio_values]
            peak_val = values[0]
            max_dd = 0
            for v in values:
                if v > peak_val:
                    peak_val = v
                dd = (peak_val - v) / peak_val * 100
                if dd > max_dd:
                    max_dd = dd

            return {
                "ticker": ticker,
                "period": period,
                "initial_capital": initial_capital,
                "final_value": round(final_value, 2),
                "total_return": round(total_return, 1),
                "buy_hold_return": round(bh_return, 1),
                "alpha": round(total_return - bh_return, 1),
                "total_trades": total_trades,
                "win_rate": round(win_rate, 1),
                "wins": len(wins),
                "losses": len(losses),
                "max_drawdown": round(max_dd, 1),
                "portfolio_values": portfolio_values,
                "trades": trades,
                "scores": daily_scores[-30:],  # Last 30 days
            }

        except Exception as e:
            logger.error(f"Backtest error {ticker}: {e}")
            return None

    @staticmethod
    def _calc_score(closes, highs, lows, volumes, is_korean=False):
        """Calculate simplified quant score for backtesting. Adaptive for KR/US."""
        score = 50.0
        regime_weight = 0.5 if is_korean else 1.0  # Korean: less regime penalty

        # RSI
        if len(closes) >= 15:
            deltas = np.diff(closes[-15:])
            gains = np.where(deltas > 0, deltas, 0)
            losses_arr = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses_arr)
            if avg_loss > 0:
                rs = avg_gain / avg_loss
                rsi = 100 - 100 / (1 + rs)
            else:
                rsi = 100
            rsi_boost = 1.3 if is_korean else 1.0  # Korean: more RSI weight
            if rsi < 30: score += 15 * rsi_boost
            elif rsi < 45: score += 8 * rsi_boost
            elif rsi < 55 and is_korean: score += 5  # Korean: neutral RSI still positive
            elif rsi > 70: score -= 15

        # Mean Reversion
        try:
            mr = MeanReversion.analyze(closes)
            if mr:
                z = mr["z_score"]
                if z < -2: score += 15
                elif z < -1: score += 8
                elif z > 2: score -= 15
                elif z > 1: score -= 8
        except: pass

        # Momentum Breakout
        try:
            mb = MomentumBreakout.analyze(closes, highs, lows, volumes)
            if mb and mb["signal"] == "BUY": score += 12
            elif mb and mb["signal"] == "SELL": score -= 12
        except: pass

        # Volatility Regime
        try:
            vr = VolatilityRegime.analyze(closes)
            if vr:
                if vr["regime"] == "LOW_VOL": score += 5
                elif vr["regime"] == "HIGH_VOL": score -= 8 * regime_weight
                elif vr["regime"] == "CRISIS": score -= 15 * regime_weight
        except: pass

        # Regime Switching
        try:
            rs = RegimeSwitching.analyze(closes)
            if rs:
                if rs["regime"] == "BULL": score += 10 * regime_weight
                elif rs["regime"] == "BEAR": score -= 10 * regime_weight
        except: pass

        return max(0, min(100, score))
