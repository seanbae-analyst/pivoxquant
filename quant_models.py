"""
StockPilot — Advanced Quant Models
1. OU Statistical Arbitrage (Pairs Trading)
2. Mean Reversion
3. Momentum Breakout
4. Volatility Regime Detection
"""

import numpy as np
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class StatArb:
    """
    Ornstein-Uhlenbeck Statistical Arbitrage
    Trades the spread between two correlated assets (e.g. SPY vs QQQ)
    When spread deviates from mean → enter, when returns to mean → exit
    """

    # Default pairs to monitor
    PAIRS = [
        ("SPY", "QQQ"),      # S&P 500 vs NASDAQ
        ("AAPL", "MSFT"),    # Tech giants
        ("GOOGL", "META"),   # Ad tech
        ("AMD", "NVDA"),     # Semiconductors
        ("JPM", "GS"),       # Banks
    ]

    @staticmethod
    def calculate_spread(prices_a, prices_b):
        """Calculate log spread between two assets."""
        if len(prices_a) != len(prices_b) or len(prices_a) < 20:
            return None
        log_a = np.log(np.array(prices_a, dtype=float))
        log_b = np.log(np.array(prices_b, dtype=float))
        spread = log_a - log_b
        return spread

    @staticmethod
    def estimate_ou_params(spread):
        """
        Estimate OU process parameters:
        θ (theta) = mean reversion speed
        μ (mu) = long-term mean
        σ (sigma) = volatility
        """
        if spread is None or len(spread) < 20:
            return None

        n = len(spread)
        mu = np.mean(spread)
        sigma = np.std(spread)

        # Estimate theta using AR(1) regression
        # spread[t] = a + b * spread[t-1] + noise
        y = spread[1:]
        x = spread[:-1]
        b = np.corrcoef(x, y)[0, 1] * np.std(y) / np.std(x)
        theta = -np.log(max(abs(b), 0.001))  # Mean reversion speed

        return {
            "theta": round(float(theta), 4),
            "mu": round(float(mu), 6),
            "sigma": round(float(sigma), 6),
            "half_life": round(float(np.log(2) / max(theta, 0.001)), 1),  # Days to revert halfway
        }

    @staticmethod
    def generate_signal(spread, params):
        """
        Generate trading signal based on z-score of spread.
        z > 2.0  → Short spread (sell A, buy B)
        z < -2.0 → Long spread (buy A, sell B)
        |z| < 0.5 → Close position (mean reverted)
        """
        if params is None or spread is None:
            return None

        mu = params["mu"]
        sigma = params["sigma"]
        current = spread[-1]

        if sigma == 0:
            return None

        z_score = (current - mu) / sigma

        if z_score > 2.0:
            signal = "SHORT_SPREAD"
            action = "Spread is too wide — sell A, buy B"
            action_kr = "스프레드 과대 — A 매도, B 매수"
            confidence = min(abs(z_score) / 3.0 * 100, 100)
        elif z_score < -2.0:
            signal = "LONG_SPREAD"
            action = "Spread is too narrow — buy A, sell B"
            action_kr = "스프레드 과소 — A 매수, B 매도"
            confidence = min(abs(z_score) / 3.0 * 100, 100)
        elif abs(z_score) < 0.5:
            signal = "CLOSE"
            action = "Spread reverted to mean — close position"
            action_kr = "스프레드 평균 회귀 — 포지션 청산"
            confidence = 80
        else:
            signal = "HOLD"
            action = "Spread within normal range"
            action_kr = "스프레드 정상 범위"
            confidence = 0

        return {
            "signal": signal,
            "z_score": round(float(z_score), 2),
            "current_spread": round(float(current), 6),
            "mean": round(float(mu), 6),
            "action": action,
            "action_kr": action_kr,
            "confidence": round(confidence, 1),
        }

    @classmethod
    def analyze_pair(cls, prices_a, prices_b, name_a="A", name_b="B"):
        """Full pair analysis."""
        spread = cls.calculate_spread(prices_a, prices_b)
        if spread is None:
            return None

        params = cls.estimate_ou_params(spread)
        if params is None:
            return None

        signal = cls.generate_signal(spread, params)
        if signal is None:
            return None

        # Correlation
        corr = float(np.corrcoef(prices_a[-60:], prices_b[-60:])[0, 1]) if len(prices_a) >= 60 else 0

        return {
            "pair": f"{name_a}/{name_b}",
            "name_a": name_a,
            "name_b": name_b,
            "correlation": round(corr, 3),
            "params": params,
            "signal": signal,
            "spread_history": [round(float(s), 6) for s in spread[-50:]],
            "price_a": round(float(prices_a[-1]), 2),
            "price_b": round(float(prices_b[-1]), 2),
        }


class MeanReversion:
    """
    Mean Reversion Model
    Buy when price is significantly below its moving average
    Sell when price returns to or exceeds moving average
    Uses Bollinger Bands + RSI for confirmation
    """

    @staticmethod
    def analyze(closes, period=20, std_mult=2.0):
        """Analyze mean reversion opportunity."""
        if len(closes) < period + 5:
            return None

        closes = np.array(closes, dtype=float)
        ma = np.mean(closes[-period:])
        std = np.std(closes[-period:])
        current = closes[-1]

        upper = ma + std_mult * std
        lower = ma - std_mult * std
        pct_b = (current - lower) / (upper - lower) if upper != lower else 0.5

        # Z-score from mean
        z = (current - ma) / std if std > 0 else 0

        # Signal
        score = 50
        signals = []

        if z < -2:
            score += 25
            signals.append({"type": "bullish", "msg": f"Price {abs(z):.1f}σ below mean — strong reversion expected",
                           "msg_kr": f"가격이 평균보다 {abs(z):.1f}σ 아래 — 강한 평균회귀 예상"})
        elif z < -1:
            score += 15
            signals.append({"type": "bullish", "msg": f"Price {abs(z):.1f}σ below mean — reversion likely",
                           "msg_kr": f"가격이 평균보다 {abs(z):.1f}σ 아래 — 회귀 가능성"})
        elif z > 2:
            score -= 25
            signals.append({"type": "bearish", "msg": f"Price {z:.1f}σ above mean — pullback expected",
                           "msg_kr": f"가격이 평균보다 {z:.1f}σ 위 — 하락 조정 예상"})
        elif z > 1:
            score -= 15
            signals.append({"type": "bearish", "msg": f"Price {z:.1f}σ above mean — extended",
                           "msg_kr": f"가격이 평균보다 {z:.1f}σ 위 — 과확장"})

        signal = "BUY" if score >= 65 else "SELL" if score < 35 else "HOLD"

        return {
            "model": "Mean Reversion",
            "signal": signal,
            "score": round(score, 1),
            "z_score": round(float(z), 2),
            "current": round(float(current), 2),
            "mean": round(float(ma), 2),
            "upper_band": round(float(upper), 2),
            "lower_band": round(float(lower), 2),
            "pct_b": round(float(pct_b), 3),
            "signals": signals,
        }


class MomentumBreakout:
    """
    Momentum Breakout Model
    Detects price breakouts from consolidation ranges
    Uses volume confirmation + ATR for breakout threshold
    """

    @staticmethod
    def analyze(closes, highs, lows, volumes, period=20):
        """Detect momentum breakout."""
        if len(closes) < period + 5:
            return None

        closes = np.array(closes, dtype=float)
        highs = np.array(highs, dtype=float)
        lows = np.array(lows, dtype=float)
        volumes = np.array(volumes, dtype=float)

        # ATR
        trs = []
        for i in range(1, len(closes)):
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            trs.append(tr)
        atr = np.mean(trs[-period:]) if trs else 0

        # Consolidation range (last N periods)
        range_high = np.max(highs[-period:])
        range_low = np.min(lows[-period:])
        range_width = (range_high - range_low) / closes[-1] * 100  # as % of price

        # Volume analysis
        avg_vol = np.mean(volumes[-period:])
        cur_vol = volumes[-1]
        vol_ratio = cur_vol / avg_vol if avg_vol > 0 else 1

        current = closes[-1]
        score = 50
        signals = []

        # Breakout detection
        if current > range_high and vol_ratio > 1.5:
            score += 30
            signals.append({"type": "bullish",
                           "msg": f"Breakout above ${range_high:.2f} with {vol_ratio:.1f}x volume",
                           "msg_kr": f"${range_high:.2f} 돌파 + 거래량 {vol_ratio:.1f}배"})
        elif current < range_low and vol_ratio > 1.5:
            score -= 30
            signals.append({"type": "bearish",
                           "msg": f"Breakdown below ${range_low:.2f} with {vol_ratio:.1f}x volume",
                           "msg_kr": f"${range_low:.2f} 이탈 + 거래량 {vol_ratio:.1f}배"})
        elif range_width < 5:
            signals.append({"type": "neutral",
                           "msg": f"Tight consolidation ({range_width:.1f}%) — breakout imminent",
                           "msg_kr": f"좁은 횡보 ({range_width:.1f}%) — 돌파 임박"})

        # Volume surge without breakout
        if vol_ratio > 2 and abs(current - np.mean(closes[-5:])) / current < 0.01:
            signals.append({"type": "neutral",
                           "msg": f"Volume surge ({vol_ratio:.1f}x) without price movement — watch closely",
                           "msg_kr": f"거래량 급증 ({vol_ratio:.1f}x) 가격 변동 없음 — 주시 필요"})

        signal = "BUY" if score >= 65 else "SELL" if score < 35 else "HOLD"

        return {
            "model": "Momentum Breakout",
            "signal": signal,
            "score": round(score, 1),
            "range_high": round(float(range_high), 2),
            "range_low": round(float(range_low), 2),
            "range_width_pct": round(float(range_width), 1),
            "atr": round(float(atr), 2),
            "vol_ratio": round(float(vol_ratio), 1),
            "signals": signals,
        }


class VolatilityRegime:
    """
    Volatility Regime Detection
    Classifies market into: Low Vol, Normal, High Vol, Crisis
    Adjusts position sizing and strategy accordingly
    """

    @staticmethod
    def analyze(closes, period=20):
        """Detect current volatility regime."""
        if len(closes) < period * 3:
            return None

        closes = np.array(closes, dtype=float)
        returns = np.diff(np.log(closes))

        # Current vol (annualized)
        current_vol = np.std(returns[-period:]) * np.sqrt(252) * 100

        # Historical vol for percentile
        rolling_vols = []
        for i in range(period, len(returns)):
            rv = np.std(returns[i-period:i]) * np.sqrt(252) * 100
            rolling_vols.append(rv)

        if not rolling_vols:
            return None

        vol_percentile = np.percentile(rolling_vols, [25, 50, 75])

        # Regime classification
        if current_vol < vol_percentile[0]:
            regime = "LOW_VOL"
            label = "Low Volatility"
            label_kr = "저변동성"
            recommendation = "Larger positions OK. Consider selling premium."
            rec_kr = "큰 포지션 가능. 프리미엄 매도 전략 고려."
            position_mult = 1.3
        elif current_vol < vol_percentile[2]:
            regime = "NORMAL"
            label = "Normal"
            label_kr = "보통"
            recommendation = "Standard position sizing. Follow quant signals."
            rec_kr = "표준 포지션 사이즈. 퀀트 시그널 따르기."
            position_mult = 1.0
        elif current_vol < vol_percentile[2] * 1.5:
            regime = "HIGH_VOL"
            label = "High Volatility"
            label_kr = "고변동성"
            recommendation = "Reduce position sizes by 50%. Tighten stops."
            rec_kr = "포지션 50% 축소. 손절선 타이트하게."
            position_mult = 0.5
        else:
            regime = "CRISIS"
            label = "Crisis"
            label_kr = "위기"
            recommendation = "Minimal exposure. Cash is king. Wait for stability."
            rec_kr = "최소 노출. 현금 보유. 안정 대기."
            position_mult = 0.2

        # Vol trend
        vol_5d = np.std(returns[-5:]) * np.sqrt(252) * 100
        vol_trend = "rising" if vol_5d > current_vol else "falling"

        return {
            "model": "Volatility Regime",
            "regime": regime,
            "label": label,
            "label_kr": label_kr,
            "current_vol": round(float(current_vol), 1),
            "vol_percentile_25": round(float(vol_percentile[0]), 1),
            "vol_percentile_75": round(float(vol_percentile[2]), 1),
            "vol_trend": vol_trend,
            "position_multiplier": position_mult,
            "recommendation": recommendation,
            "recommendation_kr": rec_kr,
        }


class RegimeSwitching:
    """
    Hidden Markov Model (HMM) Regime Switching
    Classifies market into Bull/Bear/Transition regimes
    using return patterns and volatility clustering.
    Simplified version without hmmlearn dependency.
    """

    @staticmethod
    def analyze(closes, period=60):
        """Detect bull/bear regime using rolling stats."""
        if len(closes) < period + 20:
            return None

        closes = np.array(closes, dtype=float)
        returns = np.diff(np.log(closes))

        # Short-term stats (20 days)
        ret_20 = np.mean(returns[-20:]) * 252  # annualized
        vol_20 = np.std(returns[-20:]) * np.sqrt(252)

        # Medium-term stats (60 days)
        ret_60 = np.mean(returns[-60:]) * 252
        vol_60 = np.std(returns[-60:]) * np.sqrt(252)

        # Trend strength: ratio of return to volatility
        sharpe_20 = ret_20 / vol_20 if vol_20 > 0 else 0
        sharpe_60 = ret_60 / vol_60 if vol_60 > 0 else 0

        # Regime classification
        if sharpe_20 > 1.0 and ret_20 > 0:
            regime = "BULL"
            label = "Strong Bull"
            label_kr = "강한 강세장"
            confidence = min(sharpe_20 / 2 * 100, 100)
        elif sharpe_20 > 0.3 and ret_20 > 0:
            regime = "MILD_BULL"
            label = "Mild Bull"
            label_kr = "약한 강세장"
            confidence = 60
        elif sharpe_20 < -1.0 and ret_20 < 0:
            regime = "BEAR"
            label = "Strong Bear"
            label_kr = "강한 약세장"
            confidence = min(abs(sharpe_20) / 2 * 100, 100)
        elif sharpe_20 < -0.3 and ret_20 < 0:
            regime = "MILD_BEAR"
            label = "Mild Bear"
            label_kr = "약한 약세장"
            confidence = 60
        else:
            regime = "TRANSITION"
            label = "Transition / Choppy"
            label_kr = "전환 / 횡보"
            confidence = 40

        # Regime shift detection: compare 20d vs 60d
        shifting = False
        shift_direction = ""
        if sharpe_20 > 0.5 and sharpe_60 < 0:
            shifting = True
            shift_direction = "Bear → Bull reversal detected"
            shift_kr = "약세 → 강세 전환 감지"
        elif sharpe_20 < -0.5 and sharpe_60 > 0:
            shifting = True
            shift_direction = "Bull → Bear reversal detected"
            shift_kr = "강세 → 약세 전환 감지"
        else:
            shift_kr = ""

        # Consecutive up/down days
        recent = returns[-10:]
        up_days = sum(1 for r in recent if r > 0)
        down_days = sum(1 for r in recent if r < 0)

        return {
            "model": "Regime Switching",
            "regime": regime,
            "label": label,
            "label_kr": label_kr,
            "confidence": round(confidence, 1),
            "sharpe_20d": round(float(sharpe_20), 2),
            "sharpe_60d": round(float(sharpe_60), 2),
            "return_20d_ann": round(float(ret_20 * 100), 1),
            "vol_20d_ann": round(float(vol_20 * 100), 1),
            "shifting": shifting,
            "shift_direction": shift_direction,
            "shift_kr": shift_kr,
            "up_days_10": up_days,
            "down_days_10": down_days,
        }


class CrossAssetMomentum:
    """
    Cross-Asset Momentum Model
    Analyzes correlation between stocks, bonds, commodities, and FX
    to detect macro regime and relative strength.
    Uses yfinance for multi-asset data.
    """

    ASSETS = {
        "SPY": "US Stocks",
        "TLT": "US Bonds (20Y)",
        "GLD": "Gold",
        "USO": "Oil",
        "UUP": "US Dollar",
        "BTC-USD": "Bitcoin",
    }

    @classmethod
    def analyze(cls):
        """Analyze cross-asset momentum and correlations — batch download."""
        import yfinance as yf

        tickers = list(cls.ASSETS.keys())
        data = {}
        try:
            batch = yf.download(tickers, period="3mo", group_by="ticker",
                                threads=True, progress=False)
        except Exception:
            batch = pd.DataFrame()

        for ticker, name in cls.ASSETS.items():
            try:
                h = batch[ticker] if len(tickers) > 1 and ticker in batch.columns.get_level_values(0) else batch
                if h.empty or len(h) < 20:
                    continue
                closes = h["Close"].dropna().values
                if len(closes) < 20:
                    continue
                ret_1m = (closes[-1] - closes[-20]) / closes[-20] * 100
                ret_3m = (closes[-1] - closes[0]) / closes[0] * 100
                data[ticker] = {
                    "name": name,
                    "price": round(float(closes[-1]), 2),
                    "return_1m": round(float(ret_1m), 1),
                    "return_3m": round(float(ret_3m), 1),
                    "trend": "up" if ret_1m > 0 else "down",
                }
            except Exception:
                pass

        if len(data) < 3:
            return None

        # Macro regime detection
        spy = data.get("SPY", {})
        tlt = data.get("TLT", {})
        gld = data.get("GLD", {})

        spy_ret = spy.get("return_1m", 0)
        tlt_ret = tlt.get("return_1m", 0)
        gld_ret = gld.get("return_1m", 0)

        if spy_ret > 3 and tlt_ret < 0:
            macro = "RISK_ON"
            macro_label = "Risk-On: Stocks up, Bonds down"
            macro_kr = "위험선호: 주식 상승, 채권 하락"
        elif spy_ret < -3 and tlt_ret > 0:
            macro = "RISK_OFF"
            macro_label = "Risk-Off: Stocks down, Bonds up (flight to safety)"
            macro_kr = "위험회피: 주식 하락, 채권 상승 (안전자산 선호)"
        elif spy_ret < -3 and tlt_ret < -1:
            macro = "LIQUIDATION"
            macro_label = "Liquidation: Everything selling off"
            macro_kr = "투매: 모든 자산 하락"
        elif gld_ret > 5:
            macro = "INFLATION_HEDGE"
            macro_label = "Inflation Hedge: Gold surging"
            macro_kr = "인플레이션 헷지: 금 급등"
        else:
            macro = "NEUTRAL"
            macro_label = "Neutral: Mixed signals across assets"
            macro_kr = "중립: 자산 간 혼조세"

        # Rank by 1-month momentum
        ranked = sorted(data.items(), key=lambda x: x[1].get("return_1m", 0), reverse=True)

        return {
            "model": "Cross-Asset Momentum",
            "macro_regime": macro,
            "macro_label": macro_label,
            "macro_kr": macro_kr,
            "assets": data,
            "ranking": [{"ticker": t, **d} for t, d in ranked],
            "strongest": ranked[0][0] if ranked else None,
            "weakest": ranked[-1][0] if ranked else None,
        }


class VIXStrategy:
    """
    VIX-based position sizing strategy.
    Uses VIX levels to dynamically adjust portfolio exposure.
    Low VIX = aggressive, High VIX = defensive.
    """

    @staticmethod
    def analyze():
        """Get current VIX regime and recommended exposure."""
        import yfinance as yf
        try:
            h = yf.Ticker("^VIX").history(period="3mo")
            if h.empty or len(h) < 20:
                return None

            vix = float(h["Close"].iloc[-1])
            vix_20d_avg = float(h["Close"].rolling(20).mean().iloc[-1])
            vix_high = float(h["Close"].max())
            vix_low = float(h["Close"].min())

            # VIX percentile over 3 months
            vix_pct = (vix - vix_low) / (vix_high - vix_low) * 100 if vix_high != vix_low else 50

            # Strategy
            if vix < 13:
                regime = "EXTREME_LOW"
                exposure = 1.0  # 100% — complacency, but ride the trend
                action = "Full exposure. Low vol = strong trend. But watch for spike."
                action_kr = "풀 노출. 저변동 = 강한 추세. 급등 주의."
                color = "#00e5a0"
            elif vix < 18:
                regime = "LOW"
                exposure = 0.9  # 90%
                action = "Near-full exposure. Normal market conditions."
                action_kr = "거의 풀 노출. 정상 시장 상태."
                color = "#3fb950"
            elif vix < 25:
                regime = "ELEVATED"
                exposure = 0.6  # 60%
                action = "Reduce to 60%. Elevated uncertainty."
                action_kr = "60%로 축소. 불확실성 상승."
                color = "#d29922"
            elif vix < 35:
                regime = "HIGH"
                exposure = 0.3  # 30%
                action = "Defensive: 30% exposure. Consider hedges."
                action_kr = "방어적: 30% 노출. 헷지 고려."
                color = "#f85149"
            else:
                regime = "PANIC"
                exposure = 0.1  # 10%
                action = "PANIC: 10% exposure only. Cash is king. Wait for VIX to drop below 25."
                action_kr = "공포: 10% 노출만. 현금 보유. VIX 25 아래 대기."
                color = "#da3633"

            # VIX trend
            vix_5d = float(h["Close"].iloc[-5]) if len(h) >= 5 else vix
            vix_trend = "rising" if vix > vix_5d else "falling"

            return {
                "model": "VIX Strategy",
                "vix": round(vix, 1),
                "vix_20d_avg": round(vix_20d_avg, 1),
                "vix_percentile": round(vix_pct, 0),
                "regime": regime,
                "exposure": exposure,
                "action": action,
                "action_kr": action_kr,
                "color": color,
                "vix_trend": vix_trend,
                "vix_history": [round(float(v), 1) for v in h["Close"].values[-30:]],
            }
        except Exception as e:
            logger.error(f"VIX Strategy error: {e}")
            return None


class MLSignal:
    """
    Machine Learning Signal Generator
    Uses RandomForest on technical features to predict price direction.
    No external ML library needed — uses numpy only (simplified).
    """

    @staticmethod
    def generate(closes, highs, lows, volumes, lookahead=5):
        """
        Generate ML-style signal using ensemble of simple rules.
        Simulates RandomForest by voting across multiple feature windows.
        """
        if len(closes) < 100:
            return None

        closes = np.array(closes, dtype=float)
        highs = np.array(highs, dtype=float)
        lows = np.array(lows, dtype=float)
        volumes = np.array(volumes, dtype=float)

        # Feature calculation (last data point)
        features = {}

        # RSI variants
        for period in [7, 14, 21]:
            if len(closes) > period + 1:
                d = np.diff(closes[-(period+1):])
                g = np.mean(np.where(d > 0, d, 0))
                l = np.mean(np.where(d < 0, -d, 0))
                features[f"rsi_{period}"] = 100 - 100/(1+g/max(l,0.001))

        # Moving average ratios
        for period in [10, 20, 50]:
            if len(closes) > period:
                ma = np.mean(closes[-period:])
                features[f"ma_ratio_{period}"] = closes[-1] / ma

        # Volatility (normalized)
        if len(closes) > 20:
            returns = np.diff(np.log(closes[-21:]))
            features["vol_20"] = np.std(returns) * np.sqrt(252) * 100

        # Volume ratio
        if len(volumes) > 20:
            features["vol_ratio"] = volumes[-1] / np.mean(volumes[-20:])

        # Price momentum
        for days in [5, 10, 20]:
            if len(closes) > days:
                features[f"mom_{days}"] = (closes[-1] - closes[-days]) / closes[-days] * 100

        # Ensemble voting (simulated RandomForest)
        votes_up = 0
        votes_down = 0
        total_votes = 0

        # Rule 1: RSI consensus
        rsi_14 = features.get("rsi_14", 50)
        if rsi_14 < 35: votes_up += 2
        elif rsi_14 < 45: votes_up += 1
        elif rsi_14 > 65: votes_down += 1
        elif rsi_14 > 75: votes_down += 2
        total_votes += 2

        # Rule 2: MA alignment
        ma10 = features.get("ma_ratio_10", 1)
        ma20 = features.get("ma_ratio_20", 1)
        ma50 = features.get("ma_ratio_50", 1)
        if ma10 > 1 and ma20 > 1: votes_up += 2
        elif ma10 < 1 and ma20 < 1: votes_down += 2
        elif ma10 > ma20 > 0.98: votes_up += 1
        total_votes += 2

        # Rule 3: Momentum
        mom5 = features.get("mom_5", 0)
        mom20 = features.get("mom_20", 0)
        if mom5 > 2 and mom20 > 0: votes_up += 2
        elif mom5 < -2 and mom20 < 0: votes_down += 2
        elif mom5 > 0: votes_up += 1
        elif mom5 < 0: votes_down += 1
        total_votes += 2

        # Rule 4: Volume confirmation
        vr = features.get("vol_ratio", 1)
        if vr > 2 and mom5 > 0: votes_up += 1
        elif vr > 2 and mom5 < 0: votes_down += 1
        total_votes += 1

        # Rule 5: Volatility regime
        vol = features.get("vol_20", 20)
        if vol > 40: votes_down += 1  # High vol = risky
        elif vol < 15: votes_up += 1  # Low vol = calm
        total_votes += 1

        # Calculate probability
        prob_up = votes_up / max(total_votes, 1) * 100
        prob_down = votes_down / max(total_votes, 1) * 100
        confidence = abs(prob_up - prob_down)

        if prob_up > prob_down + 20:
            signal = "BULLISH"
            direction = "up"
        elif prob_down > prob_up + 20:
            signal = "BEARISH"
            direction = "down"
        else:
            signal = "NEUTRAL"
            direction = "flat"

        return {
            "model": "ML Signal",
            "signal": signal,
            "direction": direction,
            "prob_up": round(prob_up, 1),
            "prob_down": round(prob_down, 1),
            "confidence": round(confidence, 1),
            "votes_up": votes_up,
            "votes_down": votes_down,
            "total_votes": total_votes,
            "features": {k: round(v, 2) for k, v in features.items()},
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTIVE PARAMS — 3-Layer Dynamic Exit Parameter Engine
# ═══════════════════════════════════════════════════════════════════════════════

class AdaptiveParams:
    """
    3-Layer adaptive exit parameter engine for regime-aware trading.

    Layer 1: ATR-based volatility scaling (stock-specific)
             → eliminates hard-coded Korean/US distinction
    Layer 2: Regime matrix (VolatilityRegime × RegimeSwitching → strategy profile)
             → adapts to market conditions: bull/bear/sideways × calm/volatile
    Layer 3: ML confidence adjustment (MLSignal ensemble)
             → fine-tunes based on signal consensus strength

    Usage:
        params = AdaptiveParams.calculate(closes, highs, lows, volumes)
        # params["tp_pct"], params["sl_pct"], params["trail_pct"],
        # params["cooldown"], params["position_mult"], params["profile"]
    """

    # ── Strategy Profiles ─────────────────────────────────────────────────────
    # (tp_atr_mult, sl_atr_mult, trail_atr_mult, cooldown_days)
    PROFILES = {
        "trend_rider": {"tp": 30.0, "sl": 3.0, "trail": 5.0, "cooldown": 2,
                        "label": "Trend Rider", "label_kr": "추세 추종",
                        "desc": "Strong trend — ride it, exit only on trailing stop",
                        "tp_mode": "trailing_only"},  # TP very high → rely on trail
        "momentum":    {"tp": 14.0, "sl": 3.0, "trail": 4.0, "cooldown": 3,
                        "label": "Momentum", "label_kr": "모멘텀",
                        "desc": "Moderate trend — balanced risk/reward"},
        "scalper":     {"tp": 3.5, "sl": 2.0, "trail": 3.0, "cooldown": 3,
                        "label": "Scalper", "label_kr": "단타",
                        "desc": "Choppy market — take quick profits"},
        "defensive":   {"tp": 3.0, "sl": 3.0, "trail": 2.5, "cooldown": 5,
                        "label": "Defensive", "label_kr": "방어적",
                        "desc": "Weakening market — protect capital"},
        "survival":    {"tp": 2.0, "sl": 3.5, "trail": 2.0, "cooldown": 7,
                        "label": "Survival", "label_kr": "생존 모드",
                        "desc": "Bear market — minimal exposure"},
    }

    # ── Regime → Profile Mapping ──────────────────────────────────────────────
    # Key: (trend_regime, vol_regime) → profile name
    REGIME_MAP = {
        # BULL market
        ("BULL", "LOW_VOL"):    "trend_rider",
        ("BULL", "NORMAL"):     "trend_rider",
        ("BULL", "HIGH_VOL"):   "momentum",
        ("BULL", "CRISIS"):     "defensive",
        # MILD BULL — still a bull market, trend ride when vol allows
        ("MILD_BULL", "LOW_VOL"):  "trend_rider",
        ("MILD_BULL", "NORMAL"):   "trend_rider",
        ("MILD_BULL", "HIGH_VOL"): "momentum",
        ("MILD_BULL", "CRISIS"):   "defensive",
        # TRANSITION (sideways)
        ("TRANSITION", "LOW_VOL"):  "scalper",
        ("TRANSITION", "NORMAL"):   "scalper",
        ("TRANSITION", "HIGH_VOL"): "defensive",
        ("TRANSITION", "CRISIS"):   "survival",
        # MILD BEAR
        ("MILD_BEAR", "LOW_VOL"):  "scalper",
        ("MILD_BEAR", "NORMAL"):   "defensive",
        ("MILD_BEAR", "HIGH_VOL"): "survival",
        ("MILD_BEAR", "CRISIS"):   "survival",
        # BEAR
        ("BEAR", "LOW_VOL"):  "defensive",
        ("BEAR", "NORMAL"):   "survival",
        ("BEAR", "HIGH_VOL"): "survival",
        ("BEAR", "CRISIS"):   None,  # skip — don't trade
    }

    @staticmethod
    def calculate(closes, highs, lows, volumes):
        """
        Calculate adaptive exit parameters based on current market regime.

        Args:
            closes, highs, lows, volumes: numpy arrays of price data

        Returns:
            dict with tp_pct, sl_pct, trail_pct, cooldown, position_mult,
            profile, regime_info, skip_trade, layers_active
        """
        closes = np.array(closes, dtype=float)
        highs = np.array(highs, dtype=float)
        lows = np.array(lows, dtype=float)
        volumes = np.array(volumes, dtype=float)
        n = len(closes)

        # ── Layer 1: ATR-based volatility scaling ─────────────────────────────
        atr = AdaptiveParams._calc_atr(highs, lows, closes)
        price = closes[-1]
        atr_pct = (atr / price) * 100 if price > 0 else 2.0

        layers_active = ["ATR"]

        # ── Layer 2: Regime detection ─────────────────────────────────────────
        vol_regime = "NORMAL"
        trend_regime = "TRANSITION"
        position_mult = 1.0
        regime_confidence = 0
        shifting = False

        # VolatilityRegime (needs 60+ bars)
        if n >= 60:
            vr = VolatilityRegime.analyze(closes)
            if vr:
                vol_regime = vr["regime"]
                position_mult = vr["position_multiplier"]
                layers_active.append("VolRegime")
        elif n >= 20:
            # Fallback: simple vol classification
            vol_ann = np.std(np.diff(np.log(closes[-20:]))) * np.sqrt(252) * 100
            if vol_ann < 15:
                vol_regime = "LOW_VOL"
                position_mult = 1.3
            elif vol_ann < 30:
                vol_regime = "NORMAL"
                position_mult = 1.0
            elif vol_ann < 50:
                vol_regime = "HIGH_VOL"
                position_mult = 0.5
            else:
                vol_regime = "CRISIS"
                position_mult = 0.2
            layers_active.append("VolFallback")

        # RegimeSwitching (needs 80+ bars)
        if n >= 80:
            rs = RegimeSwitching.analyze(closes)
            if rs:
                trend_regime = rs["regime"]
                regime_confidence = rs.get("confidence", 50)
                shifting = rs.get("shifting", False)
                layers_active.append("RegimeSwitch")
        elif n >= 25:
            # Fallback: simple momentum classification
            ret_20 = (closes[-1] - closes[-20]) / closes[-20] * 100
            if ret_20 > 10:
                trend_regime = "BULL"
            elif ret_20 > 3:
                trend_regime = "MILD_BULL"
            elif ret_20 > -3:
                trend_regime = "TRANSITION"
            elif ret_20 > -10:
                trend_regime = "MILD_BEAR"
            else:
                trend_regime = "BEAR"
            layers_active.append("TrendFallback")

        # Look up profile from regime matrix
        profile_name = AdaptiveParams.REGIME_MAP.get(
            (trend_regime, vol_regime), "scalper"
        )

        # Skip trade signal
        if profile_name is None:
            return {
                "tp_pct": 0, "sl_pct": 0, "trail_pct": 0,
                "cooldown": 99, "position_mult": 0,
                "profile": "skip",
                "profile_label": "No Trade",
                "profile_label_kr": "거래 중단",
                "skip_trade": True,
                "regime_info": {
                    "vol_regime": vol_regime,
                    "trend_regime": trend_regime,
                    "shifting": shifting,
                },
                "layers_active": layers_active,
                "atr": round(atr, 4),
                "atr_pct": round(atr_pct, 2),
            }

        # If regime is shifting, use more conservative profile
        if shifting and profile_name in ("trend_rider", "momentum"):
            profile_name = "scalper"

        profile = AdaptiveParams.PROFILES[profile_name]

        # Convert ATR multipliers → percentages
        tp_pct = atr_pct * profile["tp"]
        sl_pct = atr_pct * profile["sl"]
        trail_pct = atr_pct * profile["trail"]
        cooldown = profile["cooldown"]

        # ── Layer 3: ML confidence adjustment ─────────────────────────────────
        ml_adj = {"applied": False}
        if n >= 100:
            ml = MLSignal.generate(closes, highs, lows, volumes)
            if ml:
                layers_active.append("MLSignal")
                conf = ml["confidence"]
                ml_dir = ml["direction"]
                ml_adj = {
                    "applied": True,
                    "confidence": conf,
                    "direction": ml_dir,
                    "signal": ml["signal"],
                }

                # High confidence → widen TP (let winners run)
                if conf > 70:
                    tp_pct *= 1.25
                    ml_adj["tp_boost"] = "+25%"
                elif conf > 50:
                    tp_pct *= 1.1
                    ml_adj["tp_boost"] = "+10%"

                # Low confidence → tighten everything
                if conf < 30:
                    tp_pct *= 0.8
                    sl_pct *= 1.2
                    ml_adj["risk_reduction"] = True

                # ML disagrees with regime → extra caution
                regime_bullish = trend_regime in ("BULL", "MILD_BULL")
                ml_bullish = ml_dir == "up"
                if regime_bullish != ml_bullish and ml_dir != "flat":
                    cooldown = int(cooldown * 1.5)
                    position_mult *= 0.7
                    ml_adj["conflict"] = True
                    ml_adj["conflict_msg"] = (
                        f"ML says {ml['signal']} but regime is {trend_regime}"
                    )

        # ── Apply floors & caps ───────────────────────────────────────────────
        # Trend rider: high TP floor forces trailing-stop-only exits
        is_trend_rider = profile_name == "trend_rider"
        tp_floor = 50.0 if is_trend_rider else 5.0
        tp_pct = max(tp_floor, min(80.0, tp_pct))
        sl_pct = max(2.0, min(25.0, sl_pct))
        trail_pct = max(2.0, min(20.0, trail_pct))
        cooldown = max(1, min(10, cooldown))

        return {
            "tp_pct": round(tp_pct, 1),
            "sl_pct": round(sl_pct, 1),
            "trail_pct": round(trail_pct, 1),
            "cooldown": cooldown,
            "position_mult": round(position_mult, 2),
            "profile": profile_name,
            "profile_label": profile["label"],
            "profile_label_kr": profile["label_kr"],
            "profile_desc": profile["desc"],
            "skip_trade": False,
            "regime_info": {
                "vol_regime": vol_regime,
                "trend_regime": trend_regime,
                "confidence": regime_confidence,
                "shifting": shifting,
            },
            "layers_active": layers_active,
            "atr": round(atr, 4),
            "atr_pct": round(atr_pct, 2),
            "ml_adjustment": ml_adj,
            # Adaptive buy/sell thresholds
            "buy_threshold": AdaptiveParams._calc_threshold(
                trend_regime, vol_regime, "buy"),
            "sell_threshold": AdaptiveParams._calc_threshold(
                trend_regime, vol_regime, "sell"),
        }

    @staticmethod
    def _calc_threshold(trend_regime, vol_regime, side):
        """Dynamic buy/sell score thresholds based on regime."""
        if side == "buy":
            # Bull market: lower bar to enter (ride the trend)
            # Bear market: higher bar (only enter on strong signals)
            base = {
                "BULL": 50, "MILD_BULL": 55, "TRANSITION": 60,
                "MILD_BEAR": 65, "BEAR": 70,
            }.get(trend_regime, 60)
            # High vol: raise threshold (more uncertainty)
            vol_adj = {
                "LOW_VOL": -3, "NORMAL": 0, "HIGH_VOL": 3, "CRISIS": 8,
            }.get(vol_regime, 0)
            return max(40, min(75, base + vol_adj))
        else:  # sell
            base = {
                "BULL": 20, "MILD_BULL": 25, "TRANSITION": 30,
                "MILD_BEAR": 35, "BEAR": 40,
            }.get(trend_regime, 30)
            vol_adj = {
                "LOW_VOL": -2, "NORMAL": 0, "HIGH_VOL": 2, "CRISIS": 5,
            }.get(vol_regime, 0)
            return max(15, min(45, base + vol_adj))

    @staticmethod
    def _calc_atr(highs, lows, closes, period=14):
        """Average True Range — volatility in price units."""
        n = len(closes)
        if n < 2:
            return abs(highs[-1] - lows[-1]) if n > 0 else 0

        period = min(period, n - 1)
        trs = []
        for i in range(-period, 0):
            h, l, pc = highs[i], lows[i], closes[i - 1]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        return np.mean(trs) if trs else 0
