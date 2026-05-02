"""
PivoxQuant — Backtester
Tests quant strategies on historical data with adaptive regime-aware parameters.
"Would this strategy have made money?"
"""

import numpy as np
from services.data.fetcher import DataFetcher
import logging
from quant_models import (MeanReversion, MomentumBreakout, VolatilityRegime,
                          RegimeSwitching, AdaptiveParams,
                          VarianceRatioFilter, TSMOM, FiftyTwoWeekHigh)

_data_fetcher = DataFetcher()

logger = logging.getLogger(__name__)


def _ema(data, period):
    """Exponential Moving Average — returns the final EMA value."""
    arr = np.array(data[-max(period * 3, len(data)):], dtype=float)
    if len(arr) < period:
        return arr[-1]  # fallback to last close
    alpha = 2.0 / (period + 1)
    ema = arr[0]
    for val in arr[1:]:
        ema = alpha * val + (1 - alpha) * ema
    return ema


class Backtester:

    # ── Realistic transaction costs ──────────────────────────────────────
    COMMISSION_PCT = 0.001      # 0.1% per trade (market impact proxy)
    SLIPPAGE_PCT = 0.001        # 0.1% slippage per trade
    KR_COMMISSION_PCT = 0.00015  # 0.015% Korean online brokerage fee (실제 증권사 수수료)
    KR_TAX_PCT = 0.0023         # 0.23% securities transaction tax (Korea, sell only)

    @staticmethod
    def _is_korean_ticker(ticker):
        """Detect Korean stock: ends with .KS/.KQ or is 6-digit numeric."""
        t = ticker.upper().strip()
        if t.endswith('.KS') or t.endswith('.KQ'):
            return True
        base = t.split('.')[0]
        return base.isdigit() and len(base) == 6

    @staticmethod
    def run(ticker, period="1y", initial_capital=10000,
            buy_threshold=None, sell_threshold=None):
        """
        Run backtest on a single ticker using PivoxQuant quant scoring
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

            h = _data_fetcher.get_price_history(ticker, period=period)
            if h is None or h.empty or len(h) < 20:
                return None

            closes = h["Close"].values
            highs = h["High"].values
            lows = h["Low"].values
            opens = h["Open"].values if "Open" in h.columns else None
            volumes = h["Volume"].values
            dates = [d.strftime("%Y-%m-%d") for d in h.index]

            capital = initial_capital
            shares = 0
            entry_price = 0
            peak_price = 0
            last_sell_day = -999
            entry_profile = None   # profile name at entry
            entry_params = None    # full adaptive params at entry
            _locked_tp_mode = "normal"  # locked at entry, never changes mid-trade
            total_costs = 0        # accumulated transaction costs
            portfolio_values = []
            trades = []
            daily_scores = []

            # Pre-compute cost rates for this ticker
            _kr = Backtester._is_korean_ticker(ticker)
            _buy_cost_pct = (Backtester.KR_COMMISSION_PCT if _kr
                             else Backtester.COMMISSION_PCT) + Backtester.SLIPPAGE_PCT
            _sell_cost_pct = _buy_cost_pct + (Backtester.KR_TAX_PCT if _kr else 0)

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
                open_w = opens[:i+1] if opens is not None else None
                vol_w = volumes[:i+1]

                # Calculate quant score
                score = Backtester._calc_score(window, high_w, low_w, vol_w, is_korean, open_w)
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
                    _tp_mode = entry_params.get("tp_mode", "normal")
                else:
                    _tp = ap["tp_pct"]
                    _sl = ap["sl_pct"]
                    _trail = ap["trail_pct"]
                    _tp_mode = ap.get("tp_mode", "normal")

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
                        effective_buy = price * (1 + _buy_cost_pct)
                        shares_to_buy = int(capital * alloc / effective_buy)
                        if shares_to_buy > 0:
                            cost_this_trade = shares_to_buy * price * _buy_cost_pct
                            total_costs += cost_this_trade
                            shares = shares_to_buy
                            entry_price = price
                            peak_price = price
                            entry_profile = profile_name
                            entry_params = ap  # lock exit params at entry
                            _locked_tp_mode = ap.get("tp_mode", "normal")  # v9: lock tp_mode at entry
                            capital -= shares * effective_buy
                            _entry_tp_mode = _locked_tp_mode
                            trades.append({
                                "date": dates[i], "action": "BUY",
                                "price": round(price, 2), "shares": shares,
                                "effective_price": round(effective_buy, 2),
                                "cost": round(cost_this_trade, 2),
                                "score": round(score, 1),
                                "profile": profile_name,
                                "tp_mode": _entry_tp_mode,
                                "params": f"TP{_tp:.0f}/SL{_sl:.0f}/TR{_trail:.0f}/{_entry_tp_mode}",
                            })

                elif shares > 0:
                    if price > peak_price:
                        peak_price = price

                    pnl_pct = (price - entry_price) / entry_price * 100

                    sold = False
                    reason = ""

                    # ── EXIT LOGIC (structured by priority) ──────────────────

                    # ═══ v10: Profile-based FIXED stop loss ═══════════════
                    # Overrides adaptive SL — fires first as hard floor.
                    PROFILE_FIXED_SL = {
                        "passive_index_hugger": 28.0,
                        "steady_accumulator": 18.0,
                        "swing_trader": 11.0,
                        "momentum_rider": 18.0,
                        "value_hunter": 22.0,
                        "risk_managed_growth": 9.0,
                        "aggressive_scalper": 6.0,
                        "macro_rotator": 18.0,
                    }
                    fixed_sl = PROFILE_FIXED_SL.get(entry_profile, None)
                    if fixed_sl and pnl_pct <= -fixed_sl:
                        reason = f"FixedSL {pnl_pct:.1f}% (profile={entry_profile}, limit={fixed_sl}%)"
                        sold = True

                    # ═══ v8: PRICE-FIRST REGIME + BULL HOLD (trail_only) ═══
                    # Key insight: RegimeSwitching oscillates, but PRICE > EMA200
                    # is the FINAL WORD on trend direction. If price is above
                    # EMA200, we HOLD regardless of what the model says.
                    #   PRICE > EMA200 + NOT CRISIS: HOLD (emergency stop only)
                    #   PRICE < EMA200 + MODEL BEAR:  Active defense (15% SL, 8% trail)
                    #   PRICE < EMA200 + NOT BEAR:    Wait 15d below EMA200*0.97
                    if not sold and _locked_tp_mode == "trail_only":

                        # --- Price-first trend detection: EMA200 is truth ---
                        _is_above_ema200 = False
                        _ema_200 = None
                        if i >= 200:
                            _ema_200 = _ema(closes[:i + 1], 200)
                            _is_above_ema200 = closes[i] > _ema_200
                        elif i >= 50:
                            # Fallback: use EMA50 if not enough data for EMA200
                            _ema_50 = _ema(closes[:i + 1], 50)
                            _is_above_ema200 = closes[i] > _ema_50

                        # --- Track consecutive days below EMA200 ---
                        if i >= 200 and _ema_200 is not None:
                            _below_ema_streak = 0
                            for _j in range(min(5, i)):
                                if closes[i - _j] < _ema_200:
                                    _below_ema_streak += 1
                                else:
                                    break
                            _is_confirmed_below = _below_ema_streak >= 3  # need 3 consecutive days
                        else:
                            _is_confirmed_below = False

                        # --- Model regime (secondary — only matters when price confirms) ---
                        _model_regime = "TRANSITION"
                        _vol_regime = "NORMAL"
                        try:
                            _rs_v8 = RegimeSwitching.analyze(closes[:i + 1])
                            _vr_v8 = VolatilityRegime.analyze(closes[:i + 1])
                            if _rs_v8:
                                _model_regime = _rs_v8.get("regime", "TRANSITION")
                            if _vr_v8:
                                _vol_regime = _vr_v8.get("regime", "NORMAL")
                        except Exception:
                            logger.debug("silent-fallback: run", exc_info=True)
                            pass

                        _is_crisis = _vol_regime == "CRISIS"
                        _is_model_bear = _model_regime in ("BEAR", "MILD_BEAR")

                        # ── BULL: price above EMA200 OR below for less than 3 days ──
                        # Match B&H: only emergency stop
                        if (_is_above_ema200 or not _is_confirmed_below) and not _is_crisis:
                            if pnl_pct <= -35.0:
                                reason = f"v8 EmergSL {pnl_pct:.1f}% (price>EMA200, regime={_model_regime})"
                                sold = True
                            if not sold:
                                continue  # HOLD — price above EMA200, not crisis

                        # ── PRICE BELOW EMA200 + MODEL BEAR → ACTIVE DEFENSE ─
                        if not _is_above_ema200 and _is_confirmed_below and _is_model_bear and not sold:
                            # Stop loss: 20% — bear pullbacks are violent, need room
                            if pnl_pct <= -20.0:
                                reason = f"v9 BearSL {pnl_pct:.1f}% (regime={_model_regime})"
                                sold = True

                            # Trail: 15% from peak when profitable > 5%
                            if not sold and pnl_pct > 5.0:  # only trail after 5% profit in bear
                                _peak_pnl_v8 = (peak_price - entry_price) / entry_price * 100
                                _dd_from_peak = (peak_price - price) / peak_price * 100
                                if _dd_from_peak >= 15.0:
                                    reason = f"v9 BearTrail {_dd_from_peak:.1f}% (w=15%, regime={_model_regime})"
                                    sold = True

                            # Score exit in bear
                            if not sold and score < sell_threshold:
                                reason = f"v8 BearScore {score:.0f} < {sell_threshold} (regime={_model_regime})"
                                sold = True

                            if not sold:
                                continue  # Hold in bear if nothing triggered

                        # ── PRICE BELOW EMA200 + NOT BEAR (transition/mild) → WAIT ─
                        if not _is_above_ema200 and _is_confirmed_below and not sold:
                            # Wait 15 consecutive days below EMA200*0.97 before selling
                            _below_count_v8 = 0
                            if i >= 200:
                                for j in range(min(15, i)):
                                    _ema_check = _ema(closes[:i - j + 1], 200)
                                    if closes[i - j] < _ema_check * 0.97:
                                        _below_count_v8 += 1
                                    else:
                                        break
                                if _below_count_v8 >= 15:
                                    reason = f"v8 TrendBreak ({_below_count_v8}d 3%+ below EMA200, regime={_model_regime})"
                                    sold = True

                            # Emergency stop always
                            if not sold and pnl_pct <= -30.0:
                                reason = f"v8 EmergSL {pnl_pct:.1f}% (below EMA200, regime={_model_regime})"
                                sold = True

                            if not sold:
                                continue  # Wait and see — not 15d below yet

                        # Default: hold (shouldn't reach here, but safety)
                        if not sold:
                            continue

                    # ═══ NORMAL EXIT LOGIC (scalper, defensive, survival) ════
                    elif not sold and _locked_tp_mode != "trail_only":

                        # 2. STOP LOSS — always active, all normal profiles
                        if pnl_pct <= -_sl:
                            reason = f"SL {pnl_pct:.1f}%"
                            sold = True

                        # 3. TRAILING STOP — normal profiles only
                        elif peak_price > entry_price:
                            _has_trend_override = entry_params and entry_params.get("trend_override")
                            trail_activation = _tp * (0.75 if _has_trend_override else 0.5)

                            if pnl_pct > trail_activation:
                                trail_width = _trail
                                drawdown_from_peak = (peak_price - price) / peak_price * 100
                                if drawdown_from_peak >= trail_width:
                                    reason = f"Trail {drawdown_from_peak:.1f}% (w={trail_width:.1f}%)"
                                    sold = True

                        # 4. TAKE PROFIT — only for normal tp_mode profiles
                        if not sold and pnl_pct >= _tp:
                            reason = f"TP +{pnl_pct:.1f}%"
                            sold = True

                        # 5. SCORE-BASED EXIT — only for defensive/survival
                        if not sold and score < sell_threshold:
                            _exit_profile = entry_profile or profile_name
                            if _exit_profile == "scalper" and pnl_pct > 0:
                                pass  # scalper with profit: rely on TP/trail
                            else:
                                reason = f"Score {score:.0f}"
                                sold = True

                    if sold:
                        effective_sell = price * (1 - _sell_cost_pct)
                        cost_this_trade = shares * price * _sell_cost_pct
                        total_costs += cost_this_trade
                        pnl = (effective_sell - entry_price * (1 + _buy_cost_pct)) * shares
                        pnl_pct = (effective_sell - entry_price * (1 + _buy_cost_pct)) / (entry_price * (1 + _buy_cost_pct)) * 100
                        capital += shares * effective_sell
                        prof = entry_profile or profile_name
                        trades.append({
                            "date": dates[i], "action": "SELL",
                            "price": round(price, 2), "shares": shares,
                            "effective_price": round(effective_sell, 2),
                            "cost": round(cost_this_trade, 2),
                            "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 1),
                            "reason": reason, "score": round(score, 1),
                            "profile": prof,
                            "tp_mode": _locked_tp_mode,
                        })
                        Backtester._update_regime_stats(regime_stats, prof, pnl_pct)
                        shares = 0
                        entry_price = 0
                        peak_price = 0
                        last_sell_day = i
                        entry_profile = None
                        entry_params = None
                        _locked_tp_mode = "normal"  # reset after sell

            # ── Results ───────────────────────────────────────────────────────
            # If still holding at end, account for sell costs on residual position
            if shares > 0:
                residual_sell = float(closes[-1]) * (1 - _sell_cost_pct)
                residual_cost = shares * float(closes[-1]) * _sell_cost_pct
                total_costs += residual_cost
                final_value = capital + shares * residual_sell
            else:
                final_value = capital

            total_return_gross = (capital + shares * float(closes[-1]) - initial_capital) / initial_capital * 100 if shares > 0 else (final_value + total_costs - initial_capital) / initial_capital * 100
            total_return_net = (final_value - initial_capital) / initial_capital * 100
            cost_drag_pct = (total_costs / initial_capital) * 100

            bh_start = max(0, warmup)
            bh_return = (float(closes[-1]) - float(closes[bh_start])) / float(closes[bh_start]) * 100

            # ── Sanity check: flag anomalous buy-and-hold returns ────────────
            data_warning = None
            for ci in range(1, len(closes)):
                pct_chg = abs(closes[ci] - closes[ci - 1]) / closes[ci - 1] if closes[ci - 1] != 0 else 0
                if pct_chg > 0.5:
                    logger.warning(f"{ticker}: suspicious {pct_chg*100:.0f}% daily move at index {ci} — possible split/data error")
            if abs(bh_return) > 500:
                data_warning = f"Buy-and-hold return of {bh_return:.1f}% is unusually high. Data may contain unadjusted splits."
                logger.warning(f"{ticker}: {data_warning}")

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
                avg_pnl_val = round(stats["total_pnl"] / total, 1) if total > 0 else 0
                regime_report[prof] = {
                    "trades": total,
                    "wins": stats["wins"],
                    "losses": stats["losses"],
                    "win_rate": round(stats["wins"] / total * 100, 1) if total > 0 else 0,
                    "avg_pnl": avg_pnl_val,
                    "avg_pnl_pct": avg_pnl_val,
                    "total_pnl_pct": round(stats["total_pnl"], 1),
                    "label": AdaptiveParams.PROFILES.get(prof, {}).get("label", prof),
                }

            # ── Risk-adjusted return metrics ────────────────────────────────
            sharpe = None
            sortino = None
            calmar = None
            if len(values) >= 2:
                pv_arr = np.array(values, dtype=np.float64)
                daily_rets = np.diff(pv_arr) / pv_arr[:-1]
                if len(daily_rets) > 1 and np.std(daily_rets, ddof=1) > 0:
                    mean_annual = np.mean(daily_rets) * 252
                    std_annual = np.std(daily_rets, ddof=1) * np.sqrt(252)
                    sharpe = round((mean_annual - 0.045) / std_annual, 2)

                    # Sortino: penalize downside volatility only
                    downside = daily_rets[daily_rets < 0]
                    if len(downside) > 1 and np.std(downside, ddof=1) > 0:
                        down_std_annual = np.std(downside, ddof=1) * np.sqrt(252)
                        sortino = round((mean_annual - 0.045) / down_std_annual, 2)

                    # Calmar: annualized return / |max drawdown|
                    if max_dd > 0:
                        annualized_return = total_return_net  # already in %
                        calmar = round(annualized_return / max_dd, 2)

            # Current regime snapshot
            current_params = AdaptiveParams.calculate(closes, highs, lows, volumes)

            return {
                "ticker": ticker,
                "period": period,
                "initial_capital": initial_capital,
                "final_value": round(final_value, 2),
                "total_return": round(total_return_net, 1),
                "total_return_gross": round(total_return_gross, 1),
                "buy_hold_return": round(bh_return, 1),
                "alpha": round(total_return_net - bh_return, 1),
                "alpha_gross": round(total_return_gross - bh_return, 1),
                "total_transaction_costs": round(total_costs, 2),
                "cost_drag_pct": round(cost_drag_pct, 2),
                "total_trades": total_trades,
                "win_rate": round(win_rate, 1),
                "wins": len(wins),
                "losses": len(losses),
                "max_drawdown": round(max_dd, 1),
                "sharpe": sharpe,
                "sortino": sortino,
                "calmar": calmar,
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
                **({"data_warning": data_warning} if data_warning else {}),
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
    def _calc_score(closes, highs, lows, volumes, is_korean=False, opens=None):
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
            if mb and mb["signal"] == "POSITIVE": score += 12
            elif mb and mb["signal"] == "NEGATIVE": score -= 12
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

        # Variance Ratio Filter
        try:
            vr_m = VarianceRatioFilter.calculate(list(closes))
            if vr_m.get("use_momentum"):
                score += 10
        except: pass

        # TSMOM — 12-month time-series momentum
        try:
            tsmom_m = TSMOM.calculate(list(closes))
            if tsmom_m.get("signal") == "POSITIVE":
                score += 12
            elif tsmom_m.get("signal") == "NEGATIVE":
                score -= 12
        except: pass

        # 52-Week High Momentum — boost applied to final score
        try:
            h52_m = FiftyTwoWeekHigh.calculate(list(closes))
            score *= h52_m.get("boost", 1.0)
        except: pass

        # Disposition Effect — Capital Gains Overhang (Frazzini 2006)
        # Requires 252+ bars of closes + volumes for meaningful CGO calculation
        try:
            from signal_models import DispositionEffect
            i = len(closes) - 1
            if i >= 252 and volumes is not None and len(volumes) > i:
                disp = DispositionEffect.calculate(
                    list(closes), list(volumes)
                )
                cgo = disp.get("cgo", 0) or 0
                if cgo > 0.15:
                    score += 8   # high CGO = selling pressure easing -> bullish
                elif cgo < -0.15:
                    score -= 5   # deep underwater holders = reluctance to sell, potential overhang
        except Exception:
            logger.debug("silent-fallback: Requires 252+ bars of closes + volumes for meaningful CGO ca | _calc_score", exc_info=True)
            pass

        # Order Flow Imbalance — Cont, Kukanov & Stoikov (2014)
        # Requires opens array; skipped if opens unavailable (backtester may only have closes)
        try:
            from signal_models import OrderFlowImbalance
            i = len(closes) - 1
            if opens is not None and i >= 20:
                ofi = OrderFlowImbalance.calculate(
                    list(opens), list(closes), list(volumes)
                )
                pressure = ofi.get("pressure_level", "neutral")
                if pressure == "strong_buying":
                    score += 6
                elif pressure == "strong_selling":
                    score -= 6
        except Exception:
            logger.debug("silent-fallback: Requires opens array; skipped if opens unavailable (backtest | _calc_score", exc_info=True)
            pass

        return max(0, min(100, score))
