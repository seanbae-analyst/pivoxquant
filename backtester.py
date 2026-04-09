"""
StockPilot — Backtester
Tests quant strategies on historical data with adaptive regime-aware parameters.
"Would this strategy have made money?"
"""

import numpy as np
import pandas as pd
import fmp_service as fmp
import logging
from datetime import datetime
from quant_models import (MeanReversion, MomentumBreakout, VolatilityRegime,
                          RegimeSwitching, AdaptiveParams)

logger = logging.getLogger(__name__)


class Backtester:

    @staticmethod
    def run(ticker, period="1y", initial_capital=10000,
            buy_threshold=None, sell_threshold=None):
        """
        Run backtest on a single ticker using StockPilot quant scoring
        with 3-Layer adaptive exit parameters.
        """
        try:
            is_korean = ticker.upper().endswith('.KS') or ticker.upper().endswith('.KQ')
            is_etf = ticker.upper() in ('TSLL','ETHU','SPY','QQQ','TLT','GLD','USO')

            # Korean stocks are priced in KRW — scale capital accordingly
            if is_korean and initial_capital == 10000:
                initial_capital = 10_000_000  # ₩10M ≈ $7,500

            # Thresholds: use adaptive if not explicitly set, fallback to stock-type defaults
            use_adaptive_threshold = (buy_threshold is None and sell_threshold is None)
            if buy_threshold is None:
                if is_korean:
                    buy_threshold = 45
                elif is_etf:
                    buy_threshold = 58
                else:
                    buy_threshold = 62
            if sell_threshold is None:
                sell_threshold = 28 if is_korean else 30

            h = fmp.get_history(ticker, period=period)
            if h.empty or len(h) < 20:
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
            last_sell_day = -999
            entry_profile = None   # profile name at entry
            entry_params = None    # full adaptive params at entry
            portfolio_values = []
            trades = []
            daily_scores = []

            # ── Regime performance tracking (feedback loop) ───────────────────
            regime_stats = {}  # {profile_name: {wins, losses, total_pnl}}

            # Adaptive lookback: shorter periods use less warmup
            warmup = min(60, max(20, len(closes) // 3))

            # Cache adaptive params (regime changes slowly, recalc every 5 bars)
            _cached_params = None
            _cache_bar = -99

            for i in range(warmup, len(closes)):
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

                # ── Get adaptive params (cached, refreshed every 5 bars) ─────
                if i - _cache_bar >= 5 or _cached_params is None:
                    _cached_params = AdaptiveParams.calculate(window, high_w, low_w, vol_w)
                    _cache_bar = i

                ap = _cached_params

                # Update thresholds from adaptive params when available
                if use_adaptive_threshold and "buy_threshold" in ap:
                    buy_threshold = ap["buy_threshold"]
                    sell_threshold = ap["sell_threshold"]

                # Skip trade zone — don't open NEW positions, but hold existing
                if ap["skip_trade"] and shares == 0:
                    continue

                _cooldown = ap["cooldown"]
                _pos_mult = ap["position_mult"]
                profile_name = ap["profile"]

                # If holding a position, use ENTRY params (don't let regime shift
                # tighten our exits mid-trade — that causes premature selling)
                if shares > 0 and entry_params is not None:
                    _tp = entry_params["tp_pct"]
                    _sl = entry_params["sl_pct"]
                    _trail = entry_params["trail_pct"]
                else:
                    _tp = ap["tp_pct"]
                    _sl = ap["sl_pct"]
                    _trail = ap["trail_pct"]

                # ─�� Feedback loop: reduce position if this profile has been losing
                if profile_name in regime_stats:
                    stats = regime_stats[profile_name]
                    total_trades_in_regime = stats["wins"] + stats["losses"]
                    if total_trades_in_regime >= 5:
                        wr = stats["wins"] / total_trades_in_regime
                        if wr < 0.25:
                            _pos_mult *= 0.6  # reduce for consistently losing regime
                        elif wr > 0.75:
                            _pos_mult *= 1.15  # slight boost for strong regime

                # ── Trading logic ─────────────────────────────────────────────
                if shares == 0 and score >= buy_threshold:
                    days_since_sell = i - last_sell_day if last_sell_day > 0 else 999
                    if days_since_sell >= _cooldown:
                        alloc = min(0.9, 0.9 * _pos_mult)
                        shares_to_buy = int(capital * alloc / price)
                        if shares_to_buy > 0:
                            shares = shares_to_buy
                            entry_price = price
                            peak_price = price
                            entry_profile = profile_name
                            entry_params = ap  # lock exit params at entry
                            capital -= shares * price
                            trades.append({
                                "date": dates[i], "action": "BUY",
                                "price": round(price, 2), "shares": shares,
                                "score": round(score, 1),
                                "profile": profile_name,
                                "params": f"TP{_tp:.0f}/SL{_sl:.0f}/TR{_trail:.0f}",
                            })

                elif shares > 0:
                    if price > peak_price:
                        peak_price = price

                    pnl_pct = (price - entry_price) / entry_price * 100
                    trail_drop = (peak_price - price) / peak_price * 100

                    # Re-evaluate params with current data for exit decisions
                    # (regime may have changed since entry)
                    sold = False
                    reason = ""

                    # Take profit
                    if pnl_pct >= _tp:
                        reason = f"TP +{pnl_pct:.1f}%"
                        sold = True
                    # Stop loss
                    elif pnl_pct <= -_sl:
                        reason = f"SL {pnl_pct:.1f}%"
                        sold = True
                    # Trailing stop
                    elif trail_drop >= _trail and pnl_pct > 0:
                        reason = f"Trail {trail_drop:.1f}%"
                        sold = True
                    # Score-based exit (but not in trend_rider profile)
                    elif score < sell_threshold and profile_name not in ("trend_rider",):
                        reason = f"Score {score:.0f}"
                        sold = True

                    if sold:
                        pnl = (price - entry_price) * shares
                        capital += shares * price
                        prof = entry_profile or profile_name
                        trades.append({
                            "date": dates[i], "action": "SELL",
                            "price": round(price, 2), "shares": shares,
                            "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 1),
                            "reason": reason, "score": round(score, 1),
                            "profile": prof,
                        })
                        Backtester._update_regime_stats(regime_stats, prof, pnl_pct)
                        shares = 0
                        entry_price = 0
                        peak_price = 0
                        last_sell_day = i
                        entry_profile = None
                        entry_params = None

            # ── Results ───────────────────────────────────────────────────────
            final_value = capital + shares * float(closes[-1])
            total_return = (final_value - initial_capital) / initial_capital * 100

            bh_start = max(0, warmup)
            bh_return = (float(closes[-1]) - float(closes[bh_start])) / float(closes[bh_start]) * 100

            wins = [t for t in trades if t.get("action") == "SELL" and t.get("pnl", 0) > 0]
            losses = [t for t in trades if t.get("action") == "SELL" and t.get("pnl", 0) <= 0]
            total_trades = len([t for t in trades if t["action"] == "SELL"])
            win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0

            # Max drawdown
            values = [p["value"] for p in portfolio_values]
            peak_val = values[0] if values else initial_capital
            max_dd = 0
            for v in values:
                if v > peak_val:
                    peak_val = v
                dd = (peak_val - v) / peak_val * 100
                if dd > max_dd:
                    max_dd = dd

            # Format regime stats for output
            regime_report = {}
            for prof, stats in regime_stats.items():
                total = stats["wins"] + stats["losses"]
                regime_report[prof] = {
                    "trades": total,
                    "wins": stats["wins"],
                    "losses": stats["losses"],
                    "win_rate": round(stats["wins"] / total * 100, 1) if total > 0 else 0,
                    "avg_pnl": round(stats["total_pnl"] / total, 1) if total > 0 else 0,
                    "label": AdaptiveParams.PROFILES.get(prof, {}).get("label", prof),
                }

            # Current regime snapshot
            current_params = AdaptiveParams.calculate(closes, highs, lows, volumes)

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
                "scores": daily_scores[-30:],
                "regime_stats": regime_report,
                "current_regime": {
                    "profile": current_params["profile"],
                    "profile_label": current_params.get("profile_label", ""),
                    "profile_label_kr": current_params.get("profile_label_kr", ""),
                    "tp_pct": current_params["tp_pct"],
                    "sl_pct": current_params["sl_pct"],
                    "trail_pct": current_params["trail_pct"],
                    "layers_active": current_params["layers_active"],
                    "regime_info": current_params["regime_info"],
                },
            }

        except Exception as e:
            logger.error(f"Backtest error {ticker}: {e}")
            return None

    @staticmethod
    def _update_regime_stats(stats, profile, pnl_pct):
        """Track win/loss per regime profile for feedback loop."""
        if profile not in stats:
            stats[profile] = {"wins": 0, "losses": 0, "total_pnl": 0}
        if pnl_pct > 0:
            stats[profile]["wins"] += 1
        else:
            stats[profile]["losses"] += 1
        stats[profile]["total_pnl"] += pnl_pct

    @staticmethod
    def _calc_score(closes, highs, lows, volumes, is_korean=False):
        """Calculate simplified quant score for backtesting. Adaptive for KR/US."""
        score = 50.0
        regime_weight = 0.3 if is_korean else 1.0

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
            rsi_boost = 1.5 if is_korean else 1.0
            if rsi < 30: score += 18 * rsi_boost
            elif rsi < 45: score += 10 * rsi_boost
            elif rsi < 55 and is_korean: score += 6
            elif rsi > 70: score -= 15

        # Price trend (Korean stocks: trend following is key)
        if is_korean and len(closes) >= 20:
            ma20 = np.mean(closes[-20:])
            ma5 = np.mean(closes[-5:])
            if closes[-1] > ma20 and ma5 > ma20:
                score += 12
            elif closes[-1] > ma20:
                score += 6
            mom20 = (closes[-1] - closes[-20]) / closes[-20] * 100
            if mom20 > 5: score += 8
            elif mom20 > 2: score += 4

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
