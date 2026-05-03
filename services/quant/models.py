"""
PivoxQuant — Advanced Quant Models
1. OU Statistical Arbitrage (Pairs Trading)
2. Mean Reversion
3. Momentum Breakout
4. Volatility Regime Detection
"""

import numpy as np
import logging

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

    # Minimum absolute correlation required for pair trading.
    # Below this threshold, the pair is considered decoupled and signals are disabled.
    MIN_CORRELATION = 0.5

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

        len(spread)
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
            signal = "NEUTRAL"
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

        # Pair health classification based on correlation strength
        abs_corr = abs(corr)
        if abs_corr >= 0.7:
            pair_health = "healthy"
        elif abs_corr >= cls.MIN_CORRELATION:
            pair_health = "weakening"
        else:
            pair_health = "disabled"

        # Disable signals for decoupled pairs — trading zero-correlation pairs is gambling
        warning = None
        if abs_corr < cls.MIN_CORRELATION:
            signal = {
                **signal,
                "signal": "DISABLED",
                "action": "Pair correlation too low for statistical arbitrage",
                "action_kr": "페어 상관관계가 통계적 차익거래에 부적합",
                "confidence": 0,
            }
            warning = (
                f"Pair correlation ({corr:.3f}) below minimum threshold "
                f"({cls.MIN_CORRELATION}). Pair trading disabled."
            )

        result = {
            "pair": f"{name_a}/{name_b}",
            "name_a": name_a,
            "name_b": name_b,
            "correlation": round(corr, 3),
            "pair_health": pair_health,
            "params": params,
            "signal": signal,
            "spread_history": [round(float(s), 6) for s in spread[-50:]],
            "price_a": round(float(prices_a[-1]), 2),
            "price_b": round(float(prices_b[-1]), 2),
        }

        if warning:
            result["warning"] = warning

        return result


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

        signal = "POSITIVE" if score >= 65 else "NEGATIVE" if score < 35 else "NEUTRAL"

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

        signal = "POSITIVE" if score >= 65 else "NEGATIVE" if score < 35 else "NEUTRAL"

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
            vol_description = "Historically low volatility environment. Position sizing multiplier: 1.3x."
            vol_description_kr = "역사적으로 낮은 변동성 구간. 포지션 배수: 1.3x."
            position_mult = 1.3
        elif current_vol < vol_percentile[2]:
            regime = "NORMAL"
            label = "Normal"
            label_kr = "보통"
            vol_description = "Normal volatility range. Position sizing multiplier: 1.0x."
            vol_description_kr = "정상 변동성 범위. 포지션 배수: 1.0x."
            position_mult = 1.0
        elif current_vol < vol_percentile[2] * 1.5:
            regime = "HIGH_VOL"
            label = "High Volatility"
            label_kr = "고변동성"
            vol_description = "Elevated volatility detected. Historical position sizing multiplier: 0.5x."
            vol_description_kr = "변동성 확대 감지. 역사적 포지션 배수: 0.5x."
            position_mult = 0.5
        else:
            regime = "CRISIS"
            label = "Crisis"
            label_kr = "위기"
            vol_description = "Crisis-level volatility. Historical position sizing multiplier: 0.2x."
            vol_description_kr = "위기 수준 변동성. 역사적 포지션 배수: 0.2x."
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
            "vol_description": vol_description,
            "vol_description_kr": vol_description_kr,
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
    Uses FMP API for multi-asset data.
    """

    ASSETS = {
        "SPY": "US Stocks",
        "TLT": "US Bonds (20Y)",
        "GLD": "Gold",
        "USO": "Oil",
        "UUP": "US Dollar",
        "BTCUSD": "Bitcoin",
    }

    @classmethod
    def analyze(cls):
        """Analyze cross-asset momentum and correlations — FMP API."""
        import pandas as pd
        from services.data import fmp

        tickers = list(cls.ASSETS.keys())
        data = {}
        batch = {}
        for ticker in tickers:
            h = fmp.get_history(ticker, period="3mo")
            if h is not None and not h.empty:
                batch[ticker] = h

        for ticker, name in cls.ASSETS.items():
            try:
                h = batch.get(ticker, pd.DataFrame())
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
                logger.debug("silent-fallback: analyze", exc_info=True)
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
        """Get current VIX regime and historical exposure levels."""
        from services.data import fmp
        try:
            h = fmp.get_history("^VIX", period="3mo")
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
                vix_description = "Extremely low VIX. Historically calm market conditions."
                vix_description_kr = "극도로 낮은 VIX. 역사적으로 안정적인 시장 상황."
                color = "#00e5a0"
            elif vix < 18:
                regime = "LOW"
                exposure = 0.9  # 90%
                vix_description = "Low VIX range. Historically normal volatility."
                vix_description_kr = "낮은 VIX 범위. 역사적으로 정상적인 변동성."
                color = "#3fb950"
            elif vix < 25:
                regime = "ELEVATED"
                exposure = 0.6  # 60%
                vix_description = "Elevated VIX. Increased historical uncertainty."
                vix_description_kr = "VIX 상승. 역사적 불확실성 증가."
                color = "#d29922"
            elif vix < 35:
                regime = "HIGH"
                exposure = 0.3  # 30%
                vix_description = "High VIX. Historically volatile environment."
                vix_description_kr = "높은 VIX. 역사적으로 변동성이 큰 환경."
                color = "#f85149"
            else:
                regime = "PANIC"
                exposure = 0.1  # 10%
                vix_description = "Panic-level VIX. Historically extreme volatility."
                vix_description_kr = "공포 수준 VIX. 역사적으로 극단적인 변동성."
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
                "vix_description": vix_description,
                "vix_description_kr": vix_description_kr,
                "color": color,
                "vix_trend": vix_trend,
                "vix_history": [round(float(v), 1) for v in h["Close"].values[-30:]],
            }
        except Exception as e:
            logger.error(f"VIX Strategy error: {e}")
            return None


class MLSignal:
    """
    Machine Learning Signal Generator — AdaBoost Decision Stump Ensemble.

    Trains on recent historical data (last ~250 bars) using a real AdaBoost
    algorithm with decision stumps as weak learners. Each stump finds the
    single (feature, threshold, polarity) split that minimizes weighted
    classification error. Stumps are combined via exponential weighting.

    Implementation: numpy only — no sklearn or external ML libraries.

    Fallback: if insufficient data (<200 bars), reverts to a fixed heuristic
    ensemble (the original rule-based voter) so the signal is never None
    when at least 100 bars exist.

    Interface contract (unchanged):
        MLSignal.generate(closes, highs, lows, volumes, lookahead=5)
        -> dict with keys: model, signal, direction, prob_up, prob_down,
           confidence, votes_up, votes_down, total_votes, features
    """

    # Number of weak learners (decision stumps) in the ensemble
    N_STUMPS = 15
    # Minimum bars required to train the ML model
    MIN_TRAIN_BARS = 200
    # Number of candidate thresholds per feature during stump fitting
    N_THRESHOLDS = 20

    # ── Feature Extraction ────────────────────────────────────────────────────

    @staticmethod
    def _compute_features_single(closes, highs, lows, volumes, idx):
        """
        Compute feature vector for a single bar at position `idx`.
        Returns dict of feature_name -> float.
        Uses data up to and including `idx` (no lookahead).
        """
        feat = {}
        c = closes[:idx + 1]
        v = volumes[:idx + 1]
        n = len(c)

        # RSI variants
        for period in [7, 14, 21]:
            if n > period + 1:
                d = np.diff(c[-(period + 1):])
                g = np.mean(np.where(d > 0, d, 0))
                lo = np.mean(np.where(d < 0, -d, 0))
                feat[f"rsi_{period}"] = 100 - 100 / (1 + g / max(lo, 1e-8))
            else:
                feat[f"rsi_{period}"] = 50.0

        # Moving average ratios
        for period in [10, 20, 50]:
            if n > period:
                ma = np.mean(c[-period:])
                feat[f"ma_ratio_{period}"] = c[-1] / max(ma, 1e-8)
            else:
                feat[f"ma_ratio_{period}"] = 1.0

        # Annualized volatility (20-day)
        if n > 20:
            rets = np.diff(np.log(np.maximum(c[-21:], 1e-8)))
            feat["vol_20"] = float(np.std(rets) * np.sqrt(252) * 100)
        else:
            feat["vol_20"] = 20.0

        # Volume ratio
        if len(v) > 20 and np.mean(v[-20:]) > 0:
            feat["vol_ratio"] = float(v[idx] / np.mean(v[-20:]))
        else:
            feat["vol_ratio"] = 1.0

        # Price momentum
        for days in [5, 10, 20]:
            if n > days and c[-days] != 0:
                feat[f"mom_{days}"] = float(
                    (c[-1] - c[-days]) / c[-days] * 100
                )
            else:
                feat[f"mom_{days}"] = 0.0

        return feat

    @staticmethod
    def _build_feature_matrix(closes, highs, lows, volumes, start_idx, end_idx):
        """
        Build (N_samples, N_features) matrix and ordered feature name list.
        Rows correspond to bars from start_idx to end_idx (inclusive).
        """
        rows = []
        feat_names = None
        for i in range(start_idx, end_idx + 1):
            feat = MLSignal._compute_features_single(
                closes, highs, lows, volumes, i
            )
            if feat_names is None:
                feat_names = sorted(feat.keys())
            rows.append([feat[k] for k in feat_names])
        return np.array(rows, dtype=float), feat_names

    # ── AdaBoost Training ─────────────────────────────────────────────────────

    @staticmethod
    def _fit_stump(X, y, weights):
        """
        Find the best decision stump (single-feature threshold classifier)
        that minimizes weighted classification error.

        Returns: (feature_idx, threshold, polarity, error)
          polarity=+1 means: predict 1 if x >= threshold, else 0
          polarity=-1 means: predict 1 if x <  threshold, else 0
        """
        n_samples, n_features = X.shape
        best = {"feat": 0, "thresh": 0.0, "pol": 1, "err": float("inf")}

        for f_idx in range(n_features):
            col = X[:, f_idx]
            lo, hi = float(np.min(col)), float(np.max(col))
            if hi - lo < 1e-12:
                # Constant feature — skip
                continue
            thresholds = np.linspace(lo, hi, MLSignal.N_THRESHOLDS + 2)[1:-1]

            for pol in [1, -1]:
                for thr in thresholds:
                    if pol == 1:
                        preds = (col >= thr).astype(int)
                    else:
                        preds = (col < thr).astype(int)
                    err = float(np.sum(weights * (preds != y)))
                    if err < best["err"]:
                        best = {
                            "feat": f_idx, "thresh": float(thr),
                            "pol": pol, "err": err,
                        }

        return best["feat"], best["thresh"], best["pol"], best["err"]

    @staticmethod
    def _adaboost_train(X, y, n_stumps):
        """
        Train an AdaBoost ensemble of decision stumps.

        Returns: list of (feature_idx, threshold, polarity, alpha)
        where alpha is the stump's voting weight.
        """
        n_samples = X.shape[0]
        weights = np.ones(n_samples, dtype=float) / n_samples
        stumps = []

        for _ in range(n_stumps):
            f_idx, thresh, pol, err = MLSignal._fit_stump(X, y, weights)

            # Clamp error to avoid log(0) or division by zero
            err = max(err, 1e-10)
            err = min(err, 1.0 - 1e-10)

            # If error >= 0.5, this stump is no better than random — stop
            if err >= 0.5:
                break

            # Stump weight (alpha)
            alpha = 0.5 * np.log((1.0 - err) / err)

            # Predictions for weight update
            if pol == 1:
                preds = (X[:, f_idx] >= thresh).astype(int)
            else:
                preds = (X[:, f_idx] < thresh).astype(int)

            # Update weights: increase for misclassified, decrease for correct
            misclassified = (preds != y).astype(float)
            weights *= np.exp(alpha * (2 * misclassified - 1))
            weights /= np.sum(weights)  # re-normalize

            stumps.append((f_idx, thresh, pol, float(alpha)))

        return stumps

    @staticmethod
    def _adaboost_predict(X, stumps):
        """
        Predict using trained AdaBoost stumps.
        Returns (prob_up_array, predictions_array).
        prob_up is a soft probability in [0, 1].
        """
        n_samples = X.shape[0]
        if not stumps:
            return np.full(n_samples, 0.5), np.zeros(n_samples, dtype=int)

        # Weighted sum of stump predictions
        score = np.zeros(n_samples, dtype=float)
        alpha_sum = 0.0
        for f_idx, thresh, pol, alpha in stumps:
            if pol == 1:
                preds = (X[:, f_idx] >= thresh).astype(float)
            else:
                preds = (X[:, f_idx] < thresh).astype(float)
            # Map 0/1 to -1/+1 for AdaBoost scoring
            score += alpha * (2 * preds - 1)
            alpha_sum += alpha

        # Normalize to [-1, +1] range, then map to probability [0, 1]
        if alpha_sum > 0:
            score /= alpha_sum
        prob_up = 1.0 / (1.0 + np.exp(-3.0 * score))  # sigmoid squash
        predictions = (prob_up >= 0.5).astype(int)
        return prob_up, predictions

    # ── Heuristic Fallback (original rule-based voter) ────────────────────────

    @staticmethod
    def _heuristic_fallback(features):
        """
        Original rule-based ensemble for cases with insufficient training data.
        Uses 5 hand-tuned rules that vote on direction.
        """
        votes_up = 0
        votes_down = 0
        total_votes = 0

        # Rule 1: RSI consensus
        rsi_14 = features.get("rsi_14", 50)
        if rsi_14 < 35:
            votes_up += 2
        elif rsi_14 < 45:
            votes_up += 1
        elif rsi_14 > 65:
            votes_down += 1
        elif rsi_14 > 75:
            votes_down += 2
        total_votes += 2

        # Rule 2: MA alignment
        ma10 = features.get("ma_ratio_10", 1)
        ma20 = features.get("ma_ratio_20", 1)
        if ma10 > 1 and ma20 > 1:
            votes_up += 2
        elif ma10 < 1 and ma20 < 1:
            votes_down += 2
        elif ma10 > ma20 > 0.98:
            votes_up += 1
        total_votes += 2

        # Rule 3: Momentum
        mom5 = features.get("mom_5", 0)
        mom20 = features.get("mom_20", 0)
        if mom5 > 2 and mom20 > 0:
            votes_up += 2
        elif mom5 < -2 and mom20 < 0:
            votes_down += 2
        elif mom5 > 0:
            votes_up += 1
        elif mom5 < 0:
            votes_down += 1
        total_votes += 2

        # Rule 4: Volume confirmation
        vr = features.get("vol_ratio", 1)
        if vr > 2 and mom5 > 0:
            votes_up += 1
        elif vr > 2 and mom5 < 0:
            votes_down += 1
        total_votes += 1

        # Rule 5: Volatility regime
        vol = features.get("vol_20", 20)
        if vol > 40:
            votes_down += 1
        elif vol < 15:
            votes_up += 1
        total_votes += 1

        return votes_up, votes_down, total_votes

    # ── Public Interface ──────────────────────────────────────────────────────

    @staticmethod
    def generate(closes, highs, lows, volumes, lookahead=5):
        """
        Generate ML signal using AdaBoost decision stump ensemble.

        If >= 200 bars available: trains on historical data, predicts on
        the latest bar. This is real ML — stumps learn thresholds from data.

        If 100-199 bars: falls back to heuristic rule-based voting.

        If < 100 bars: returns None.

        Args:
            closes, highs, lows, volumes: price/volume arrays
            lookahead: forward return horizon for labeling (default 5 bars)

        Returns:
            dict with signal, confidence, probabilities, and diagnostics
        """
        if len(closes) < 100:
            return None

        closes = np.array(closes, dtype=float)
        highs = np.array(highs, dtype=float)
        lows = np.array(lows, dtype=float)
        volumes = np.array(volumes, dtype=float)
        n = len(closes)

        # Compute features for the latest bar (always needed for output)
        latest_features = MLSignal._compute_features_single(
            closes, highs, lows, volumes, n - 1
        )

        use_ml = n >= MLSignal.MIN_TRAIN_BARS
        model_type = "AdaBoost Stump Ensemble" if use_ml else "Heuristic Fallback"

        if use_ml:
            # ── Train and predict with AdaBoost ───────────────────────────
            # Training window: we need `lookahead` bars after each sample
            # for labeling, so trainable range is [50, n - 1 - lookahead]
            # (start at 50 to ensure enough history for feature computation)
            train_start = 50
            train_end = n - 1 - lookahead

            if train_end - train_start < 50:
                # Not enough trainable samples — fallback
                use_ml = False
                model_type = "Heuristic Fallback"
            else:
                # Build feature matrix for training samples
                X_train, feat_names = MLSignal._build_feature_matrix(
                    closes, highs, lows, volumes, train_start, train_end
                )

                # Labels: 1 if forward `lookahead`-day return > 0, else 0
                y_train = np.zeros(X_train.shape[0], dtype=int)
                for i, bar_idx in enumerate(range(train_start, train_end + 1)):
                    fwd_ret = closes[bar_idx + lookahead] - closes[bar_idx]
                    y_train[i] = 1 if fwd_ret > 0 else 0

                # Check label balance — skip ML if too skewed (>90% one class)
                pos_rate = np.mean(y_train)
                if pos_rate < 0.1 or pos_rate > 0.9:
                    use_ml = False
                    model_type = "Heuristic Fallback (skewed labels)"
                else:
                    # Train AdaBoost
                    stumps = MLSignal._adaboost_train(
                        X_train, y_train, MLSignal.N_STUMPS
                    )

                    if len(stumps) == 0:
                        use_ml = False
                        model_type = "Heuristic Fallback (no stumps)"
                    else:
                        # Predict on latest bar
                        latest_vec = np.array(
                            [[latest_features[k] for k in feat_names]],
                            dtype=float,
                        )
                        prob_up_arr, _ = MLSignal._adaboost_predict(
                            latest_vec, stumps
                        )
                        prob_up_ml = float(prob_up_arr[0]) * 100
                        prob_down_ml = 100.0 - prob_up_ml
                        confidence_ml = abs(prob_up_ml - prob_down_ml)

                        # Map stump count to votes for interface compatibility
                        n_stumps_trained = len(stumps)
                        # Count stumps voting bullish vs bearish on latest bar
                        v_up = 0
                        v_dn = 0
                        for f_idx, thresh, pol, alpha in stumps:
                            feat_val = latest_vec[0, f_idx]
                            if pol == 1:
                                pred = 1 if feat_val >= thresh else 0
                            else:
                                pred = 1 if feat_val < thresh else 0
                            if pred == 1:
                                v_up += 1
                            else:
                                v_dn += 1

        # ── Determine signal ──────────────────────────────────────────────────
        if use_ml:
            prob_up = prob_up_ml
            prob_down = prob_down_ml
            confidence = confidence_ml
            votes_up = v_up
            votes_down = v_dn
            total_votes = n_stumps_trained
        else:
            # Heuristic fallback
            votes_up, votes_down, total_votes = MLSignal._heuristic_fallback(
                latest_features
            )
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
            "model": f"ML Signal ({model_type})",
            "signal": signal,
            "direction": direction,
            "prob_up": round(prob_up, 1),
            "prob_down": round(prob_down, 1),
            "confidence": round(confidence, 1),
            "votes_up": votes_up,
            "votes_down": votes_down,
            "total_votes": total_votes,
            "features": {k: round(v, 2) for k, v in latest_features.items()},
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
    # trail_only: TP=9999 (never triggers), SL=8.0 (wide emergency ~16-24%)
    #   Exit is driven by EMA50 trend break + regime shift in backtester.py.
    # normal: standard TP/SL/trail logic.
    PROFILES = {
        "trend_rider": {"tp": 9999.0, "sl": 8.0, "trail": 4.0, "cooldown": 2,
                        "label": "Trend Rider", "label_kr": "추세 추종",
                        "desc": "Strong trend — hold until trend breaks (EMA50/regime)",
                        "tp_mode": "trail_only"},
        "momentum":    {"tp": 9999.0, "sl": 8.0, "trail": 3.5, "cooldown": 3,
                        "label": "Momentum", "label_kr": "모멘텀",
                        "desc": "Moderate trend — hold until trend breaks (EMA50/regime)",
                        "tp_mode": "trail_only"},
        "scalper":     {"tp": 6.0, "sl": 2.0, "trail": 3.0, "cooldown": 3,
                        "label": "Scalper", "label_kr": "단타",
                        "desc": "Choppy market — take quick profits",
                        "tp_mode": "normal"},
        "defensive":   {"tp": 3.0, "sl": 3.0, "trail": 2.5, "cooldown": 5,
                        "label": "Defensive", "label_kr": "방어적",
                        "desc": "Weakening market — protect capital",
                        "tp_mode": "normal"},
        "survival":    {"tp": 2.0, "sl": 3.5, "trail": 2.0, "cooldown": 7,
                        "label": "Survival", "label_kr": "생존 모드",
                        "desc": "Bear market — minimal exposure",
                        "tp_mode": "normal"},
    }

    # ── Regime → Profile Mapping ──────────────────────────────────────────────
    # Key: (trend_regime, vol_regime) → profile name
    REGIME_MAP = {
        # BULL market
        ("BULL", "LOW_VOL"):    "trend_rider",
        ("BULL", "NORMAL"):     "trend_rider",
        ("BULL", "HIGH_VOL"):   "trend_rider",
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
                "trend_strength": "neutral",
                "trend_override": False,
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

        # ── Trend Strength Filter ─────────────────────────────────────────
        # In strong trends, widen TP to let winners run longer.
        # In strong downtrends, tighten SL to cut losses faster.
        trend_override = False
        trend_strength = "neutral"
        if n >= 50:
            ma20 = np.mean(closes[-20:])
            ma50 = np.mean(closes[-50:])
            cur_price = closes[-1]

            if cur_price > ma20 > ma50:
                trend_strength = "strong_up"
                tp_pct *= 1.5
                trend_override = True
            elif cur_price < ma20 < ma50:
                trend_strength = "strong_down"
                sl_pct *= 0.8
                trend_override = False

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
        _tp_mode = profile.get("tp_mode", "normal")
        if _tp_mode == "trail_only":
            # Trend Hold: TP infinite, SL is wide emergency stop (backtester
            # enforces min 25% via EmergencySL), trail unused (no trail exit).
            tp_pct = max(9000.0, tp_pct)   # ensure TP never triggers
            sl_pct = max(15.0, min(35.0, sl_pct))  # wide emergency range
        else:
            tp_pct = max(5.0, min(80.0, tp_pct))
            sl_pct = max(2.0, min(25.0, sl_pct))
        trail_pct = max(2.0, min(20.0, trail_pct))
        cooldown = max(1, min(10, cooldown))

        return {
            "tp_pct": round(tp_pct, 1),
            "sl_pct": round(sl_pct, 1),
            "trail_pct": round(trail_pct, 1),
            "tp_mode": profile.get("tp_mode", "normal"),
            "cooldown": cooldown,
            "position_mult": round(position_mult, 2),
            "profile": profile_name,
            "profile_label": profile["label"],
            "profile_label_kr": profile["label_kr"],
            "profile_desc": profile["desc"],
            "skip_trade": False,
            "trend_strength": trend_strength,
            "trend_override": trend_override,
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
        """Dynamic buy/sell score thresholds based on regime.

        v7: Reverted to v3-era buy thresholds (55-75) which had the
        best entry timing.  Bull Hold + Bear Defend exit logic handles
        holding; these thresholds gate entry quality.
        Floor=50, Cap=80.
        """
        if side == "buy":
            # v7: v3-era thresholds — best entry quality
            base = {
                "BULL": 55, "MILD_BULL": 60, "TRANSITION": 65,
                "MILD_BEAR": 70, "BEAR": 75,
            }.get(trend_regime, 65)
            vol_adj = {
                "LOW_VOL": -3, "NORMAL": 0, "HIGH_VOL": 3, "CRISIS": 8,
            }.get(vol_regime, 0)
            return max(50, min(80, base + vol_adj))
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


# ═══════════════════════════════════════════════════════════════════════════════
# Momentum Strategy Suite (2026-04-12)
# ═══════════════════════════════════════════════════════════════════════════════

class VarianceRatioFilter:
    """Lo & MacKinlay (1988) — detects trending vs mean-reverting regime per stock."""

    @staticmethod
    def calculate(closes: list, k: int = 20) -> dict:
        if len(closes) < 252:
            return {"vr": 1.0, "regime": "unknown", "use_momentum": False}

        returns = np.diff(np.log(np.array(closes[-252:], dtype=float)))

        # Variance of 1-day returns
        var_1 = np.var(returns, ddof=1)
        if var_1 == 0:
            return {"vr": 1.0, "regime": "unknown", "use_momentum": False}

        # Variance of k-day returns
        k_returns = np.array([np.sum(returns[i:i+k]) for i in range(len(returns) - k + 1)])
        var_k = np.var(k_returns, ddof=1)

        vr = var_k / (k * var_1)

        if vr > 1.2:
            regime = "trending"
            use_momentum = True
        elif vr < 0.8:
            regime = "mean_reverting"
            use_momentum = False
        else:
            regime = "mixed"
            use_momentum = False

        return {"vr": round(vr, 3), "regime": regime, "use_momentum": use_momentum}


class TSMOM:
    """Moskowitz, Ooi, Pedersen (2012) — 12-month sign-based momentum."""

    @staticmethod
    def calculate(closes: list) -> dict:
        if len(closes) < 252:
            return {"signal": "NEUTRAL", "momentum_12m": 0, "strength": 0}

        arr = np.array(closes, dtype=float)
        ret_12m = (arr[-1] / arr[-252]) - 1  # 12-month return

        # Volatility-scaled strength
        returns = np.diff(np.log(arr[-63:]))
        vol_63d = np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0.2
        strength = min(abs(ret_12m) / max(vol_63d, 0.01), 2.0)  # capped at 2x

        if ret_12m > 0.05:  # 5% threshold to avoid noise
            signal = "POSITIVE"
        elif ret_12m < -0.05:
            signal = "NEGATIVE"
        else:
            signal = "NEUTRAL"

        return {
            "signal": signal,
            "momentum_12m": round(ret_12m * 100, 2),
            "strength": round(strength, 3),
            "vol_scaled_position": round(np.sign(ret_12m) * strength, 3),
        }


class FiftyTwoWeekHigh:
    """George & Hwang (2004) — nearness to 52-week high predicts returns."""

    @staticmethod
    def calculate(closes: list) -> dict:
        if len(closes) < 252:
            return {"ratio": 0, "signal": "NEUTRAL", "boost": 1.0}

        arr = np.array(closes, dtype=float)
        high_52w = np.max(arr[-252:])
        ratio = arr[-1] / high_52w if high_52w > 0 else 0

        # New high check: last 3 days all above previous 52-week high
        if len(arr) > 255:
            prev_high = np.max(arr[-255:-3])
            new_high_3d = np.all(arr[-3:] > prev_high)
        else:
            new_high_3d = False

        if ratio > 0.95:
            signal = "POSITIVE"
            boost = 1.3  # 30% score boost
        elif ratio > 0.85:
            signal = "NEUTRAL"
            boost = 1.0
        elif ratio < 0.7:
            signal = "NEGATIVE"
            boost = 0.7  # 30% score penalty
        else:
            signal = "NEUTRAL"
            boost = 1.0

        return {
            "ratio": round(ratio, 4),
            "signal": signal,
            "boost": boost,
            "new_high_3d": new_high_3d,
            "high_52w": round(float(high_52w), 2),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# DONCHIAN BREAKOUT — Turtle Trading Simplified
# ═══════════════════════════════════════════════════════════════════════════════

class DonchianBreakout:
    """Donchian Channel breakout strategy — Turtle Trading simplified.

    55-day high breakout entry, 20-day low exit.
    Based on the original Turtle Trading rules (Richard Dennis, 1983).

    Entry: price >= highest high over entry_period days.
    Exit:  price <= lowest low over exit_period days.
    """

    @staticmethod
    def calculate(highs, lows, closes, entry_period=55, exit_period=20):
        """Calculate Donchian breakout signal.

        Args:
            highs:  array-like of high prices
            lows:   array-like of low prices
            closes: array-like of closing prices
            entry_period: lookback for entry channel (default 55)
            exit_period:  lookback for exit channel (default 20)

        Returns:
            dict with signal, entry_level, exit_level, current price.
        """
        if len(closes) < entry_period:
            return {"signal": "NEUTRAL", "entry_level": None, "exit_level": None}

        h = np.array(highs, dtype=float)
        l = np.array(lows, dtype=float)
        entry_high = float(np.max(h[-entry_period:]))
        exit_low = float(np.min(l[-exit_period:]))
        current = float(closes[-1])

        if current >= entry_high:
            signal = "POSITIVE"
        elif current <= exit_low:
            signal = "NEGATIVE"
        else:
            signal = "NEUTRAL"

        return {
            "signal": signal,
            "entry_level": round(entry_high, 2),
            "exit_level": round(exit_low, 2),
            "current": round(current, 2),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# DUAL MOMENTUM — Antonacci (2014)
# ═══════════════════════════════════════════════════════════════════════════════

class DualMomentum:
    """Antonacci Dual Momentum — absolute + relative momentum.

    Combines two momentum screens:
      - Absolute: asset return > 0 (simplified risk-free proxy)
      - Relative: asset return > benchmark return

    Reference:
        Antonacci, G. (2014). "Dual Momentum Investing."
    """

    @staticmethod
    def calculate(closes, benchmark_closes, period=252):
        """Calculate Dual Momentum signal.

        Args:
            closes:           array-like of asset closing prices
            benchmark_closes: array-like of benchmark closing prices
            period:           lookback in trading days (default 252 = 1 year)

        Returns:
            dict with signal, asset/benchmark 12m returns, momentum flags.
        """
        if len(closes) < period or len(benchmark_closes) < period:
            return {
                "signal": "NEUTRAL",
                "absolute_momentum": None,
                "relative_momentum": None,
            }

        # Zero guard: prevent division by zero if historical price is 0 or near-0
        asset_ret = (closes[-1] / max(closes[-period], 1e-8)) - 1
        bench_ret = (benchmark_closes[-1] / max(benchmark_closes[-period], 1e-8)) - 1

        absolute = asset_ret > 0  # above risk-free (simplified)
        relative = asset_ret > bench_ret

        if absolute and relative:
            signal = "POSITIVE"
        elif not absolute:
            signal = "NEGATIVE"
        else:
            signal = "NEUTRAL"

        return {
            "signal": signal,
            "asset_return_12m": round(asset_ret * 100, 2),
            "benchmark_return_12m": round(bench_ret * 100, 2),
            "absolute_momentum": absolute,
            "relative_momentum": relative,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CORRELATION REGIME — Diversification Breakdown Detector
# ═══════════════════════════════════════════════════════════════════════════════

class CorrelationRegime:
    """Detects correlation regime shifts — when diversification breaks down.

    High correlation = systemic risk (positions move together).
    Low correlation  = stock-picking opportunity (idiosyncratic moves).

    Uses rolling pairwise Pearson correlations across a basket of returns.
    """

    @staticmethod
    def calculate(returns_list, window=60):
        """Compute average pairwise correlation and classify regime.

        Args:
            returns_list: list of array-like (daily returns per stock)
            window:       rolling window in trading days (default 60)

        Returns:
            dict with avg_correlation, regime, pair_count.
        """
        if not returns_list or len(returns_list) < 2:
            return {"avg_correlation": None, "regime": "unknown"}

        min_len = min(len(r) for r in returns_list)
        if min_len < window:
            return {"avg_correlation": None, "regime": "unknown"}

        n = len(returns_list)
        corrs = []
        for i in range(n):
            for j in range(i + 1, n):
                r1 = np.array(returns_list[i][-window:], dtype=float)
                r2 = np.array(returns_list[j][-window:], dtype=float)
                if len(r1) == len(r2) and len(r1) > 1:
                    c = np.corrcoef(r1, r2)[0, 1]
                    if not np.isnan(c):
                        corrs.append(c)

        if not corrs:
            return {"avg_correlation": None, "regime": "unknown"}

        avg = float(np.mean(corrs))

        if avg > 0.7:
            regime = "high_correlation"
        elif avg > 0.3:
            regime = "normal"
        else:
            regime = "low_correlation"

        return {
            "avg_correlation": round(avg, 3),
            "regime": regime,
            "pair_count": len(corrs),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# INTEREST RATE REGIME — Kim Min-gyeom's 4-Stage Cycle
# ═══════════════════════════════════════════════════════════════════════════════

class InterestRateRegime:
    """Kim Min-gyeom's 4-stage interest rate cycle classification.
    Uses FRED API data for Fed Funds Rate trajectory.

    Pure classification model; not investment advice.
    """

    @staticmethod
    def classify(fed_rate_current, fed_rate_6m_ago, gdp_growth=None, cpi=None):
        """
        5 regimes based on interest rate direction + economic growth:
        1. LOW_RATE_EXPANSION: rates falling + economy growing -> expansionary
        2. STABLE_RATE_EXPANSION: rates stable + economy growing -> expansionary
        3. HIGH_RATE_EXPANSION: rates rising + economy growing -> selective
        4. HIGH_RATE_CONTRACTION: rates high/stable + economy slowing -> defensive
        5. LOW_RATE_CONTRACTION: rates falling + economy contracting -> cautious
        """
        if fed_rate_current is None or fed_rate_6m_ago is None:
            return {"regime": "UNKNOWN", "confidence": 0}

        rate_rising = fed_rate_current > fed_rate_6m_ago + 0.25  # 25bp threshold
        rate_falling = fed_rate_current < fed_rate_6m_ago - 0.25
        rate_stable = not rate_rising and not rate_falling

        # GDP proxy: if not provided, use rate direction as proxy
        economy_growing = True  # default optimistic
        if gdp_growth is not None:
            economy_growing = gdp_growth > 0
        elif cpi is not None:
            economy_growing = cpi > 0 and cpi < 5  # moderate inflation = growing

        if rate_falling and economy_growing:
            regime = "LOW_RATE_EXPANSION"
            description = "Low/falling rates + economic growth -- expansionary environment"
            historical_regime_label = "expansionary"
        elif rate_stable and economy_growing:
            regime = "STABLE_RATE_EXPANSION"
            description = "Stable rates + economic growth -- steady environment"
            historical_regime_label = "expansionary"
        elif rate_rising and economy_growing:
            regime = "HIGH_RATE_EXPANSION"
            description = "Rising rates + economic growth -- selective environment"
            historical_regime_label = "selective"
        elif (rate_rising or rate_stable) and not economy_growing:
            regime = "HIGH_RATE_CONTRACTION"
            description = "High rates + economic slowdown -- defensive environment"
            historical_regime_label = "defensive"
        else:  # rate_falling and not economy_growing
            regime = "LOW_RATE_CONTRACTION"
            description = "Falling rates + contraction -- crisis/early recovery"
            historical_regime_label = "cautious"

        return {
            "regime": regime,
            "description": description,
            "historical_regime_label": historical_regime_label,
            "rate_current": fed_rate_current,
            "rate_6m_ago": fed_rate_6m_ago,
            "rate_direction": "rising" if rate_rising else "falling" if rate_falling else "stable",
            "economy_growing": economy_growing,
        }
