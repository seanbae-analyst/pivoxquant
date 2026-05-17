"""
PivoxQuant — Behavioral & Microstructure Signal Models

5 signal models with legal compliance classification:
  GREEN  = pure data analysis, no directional guidance
  YELLOW = display as indicator only, no buy/sell direction

References:
  1. Frazzini (2006) — "The Disposition Effect and Underreaction to News"
  2. Christie & Huang (1995) — "Following the Pied Piper"
  3. Cont, Kukanov & Stoikov (2014) — "The Price Impact of Order Book Events"
  4. George & Hwang (2004) — "The 52-Week High and Momentum Investing"
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)


# ==============================================================================
# Model 1: Disposition Effect Indicator
# Classification: YELLOW — display as data indicator only
# ==============================================================================

class DispositionEffect:
    """Capital Gains Overhang (CGO) — Frazzini (2006).

    Measures the fraction of holders sitting at a gain vs loss using a
    volume-weighted reference price as a proxy for the aggregate cost basis.

    CGO = (current_price - reference_price) / reference_price

    High CGO  -> most holders in profit -> selling pressure from disposition bias
    Low CGO   -> most holders underwater -> reluctance to sell (loss aversion)

    Legal: Display as indicator value only. No buy/sell direction.
    """

    MIN_WINDOW = 20

    @staticmethod
    def calculate(closes, volumes, window=252):
        """Compute volume-weighted reference price and CGO.

        Args:
            closes:  list/array of closing prices (oldest first)
            volumes: list/array of daily volumes (oldest first)
            window:  lookback in trading days (default 252 ~ 1 year)

        Returns:
            dict with cgo, reference_price, interpretation, turnover_ratio
            All values are numeric indicators. No directional signals.
        """
        if (len(closes) < DispositionEffect.MIN_WINDOW
                or len(volumes) < DispositionEffect.MIN_WINDOW):
            return {"cgo": None, "reference_price": None}

        n = min(window, len(closes), len(volumes))
        c = np.array(closes[-n:], dtype=np.float64)
        v = np.array(volumes[-n:], dtype=np.float64)

        # 2026-05-17 Wave D-2 F3: NaN leak guard. yfinance / KIS occasionally
        # returns a row with NaN Volume on illiquid days, which becomes
        # float64 NaN here. np.sum(v) → NaN, the `total_vol == 0` check
        # passes (NaN != 0), and the function returns NaN cgo / NaN
        # reference_price. cache_service.save_signal uses
        # json.dumps(..., allow_nan=False) → raises ValueError and the
        # silent-fallback in engine.py swallows it, but the cached payload
        # is corrupted. Filter NaN/Inf rows before the math so partial-data
        # tickers still produce a clean (or explicit-None) result.
        finite_mask = np.isfinite(c) & np.isfinite(v)
        if not finite_mask.all():
            c = c[finite_mask]
            v = v[finite_mask]
        if len(c) < DispositionEffect.MIN_WINDOW:
            return {"cgo": None, "reference_price": None}

        total_vol = float(np.sum(v))
        if total_vol <= 0:
            return {"cgo": None, "reference_price": None}

        # VWAP over the lookback as proxy for aggregate cost basis
        ref_price = float(np.sum(c * v) / total_vol)
        current = float(c[-1])
        cgo = (current - ref_price) / ref_price if ref_price != 0 else 0.0

        # Turnover ratio — higher means positions rotate faster,
        # reducing stale-position disposition bias
        avg_daily_vol = float(np.mean(v))

        # Proportion of volume in the most recent 20% of the window
        recent_slice = max(1, n // 5)
        recent_vol_share = float(np.sum(v[-recent_slice:])) / total_vol

        # Classify intensity
        if cgo > 0.15:
            interpretation = "high"
        elif cgo < -0.15:
            interpretation = "low"
        else:
            interpretation = "neutral"

        return {
            "cgo": round(cgo, 4),
            "reference_price": round(ref_price, 2),
            "current_price": round(current, 2),
            "window_days": n,
            "avg_daily_volume": round(avg_daily_vol, 0),
            "recent_volume_share": round(recent_vol_share, 4),
            "interpretation": interpretation,
            # NO buy/sell direction — legal requirement
        }


# ==============================================================================
# Model 2: Herding Intensity
# Classification: YELLOW — no direction, data only
# ==============================================================================

class HerdingIntensity:
    """Cross-Sectional Return Dispersion — Christie & Huang (1995).

    Measures how much individual stocks move together vs independently.
    Low dispersion during extreme market moves suggests herding behavior.

    CSAD = (1/N) * sum(|R_i - R_m|)  (cross-sectional absolute deviation)

    Legal: Display as indicator only. No directional guidance.
    """

    MIN_STOCKS = 3
    MIN_DAYS = 20

    @staticmethod
    def calculate(stock_returns_list, market_returns, window=60):
        """Compute cross-sectional dispersion and herding z-score.

        Args:
            stock_returns_list: list of arrays, each array is daily returns
                                for one stock (decimal, e.g. 0.01 = 1%)
            market_returns:     array of daily market returns (same length)
            window:             lookback in trading days

        Returns:
            dict with csad, herding_z_score, dispersion_level
            All values are numeric indicators. No directional signals.
        """
        if (not stock_returns_list
                or len(stock_returns_list) < HerdingIntensity.MIN_STOCKS):
            return {"csad": None, "herding_z_score": None,
                    "error": "Need at least 3 stocks"}

        # Trim all to the shortest common length
        min_len = min(len(r) for r in stock_returns_list)
        min_len = min(min_len, len(market_returns))

        if min_len < HerdingIntensity.MIN_DAYS:
            return {"csad": None, "herding_z_score": None,
                    "error": "Insufficient data"}

        n = min(window, min_len)
        mkt = np.array(market_returns[-n:], dtype=np.float64)

        # Compute daily CSAD
        daily_csad = np.zeros(n, dtype=np.float64)
        for stock_ret in stock_returns_list:
            sr = np.array(stock_ret[-n:], dtype=np.float64)
            daily_csad += np.abs(sr - mkt)
        daily_csad /= len(stock_returns_list)

        # Current CSAD and its z-score over the window
        current_csad = float(daily_csad[-1])
        mean_csad = float(np.mean(daily_csad))
        std_csad = float(np.std(daily_csad, ddof=1))

        if std_csad > 0:
            z_score = (current_csad - mean_csad) / std_csad
        else:
            z_score = 0.0

        # Herding detection: during extreme market moves (|Rm| > 2 sigma),
        # does CSAD drop? If so, stocks are moving in lockstep (herding).
        # 2026-05-17 Wave D-2 F2: zero-variance market guard. When mkt is
        # nearly constant (e.g. synthetic / closed-market data) np.std → 0
        # (or float-noise ~1e-18), then `|mkt| > 2 * 0` flags every day as
        # "extreme" → csad_during_normal becomes mean of empty slice (NaN +
        # RuntimeWarning) and the ratio collapses to a meaningless 1.0.
        # The original `if len(mkt) > 1` guard never triggers in practice
        # because callers always pass window-length arrays. Detect the
        # numerical-zero std explicitly and fall back to the same 0.01
        # constant the original code intended.
        raw_std = float(np.std(mkt, ddof=1)) if len(mkt) > 1 else 0.0
        mkt_std = raw_std if raw_std > 1e-12 else 0.01
        extreme_mask = np.abs(mkt) > 2 * mkt_std
        extreme_count = int(np.sum(extreme_mask))

        if extreme_count >= 3:
            csad_during_extreme = float(np.mean(daily_csad[extreme_mask]))
            csad_during_normal = float(np.mean(daily_csad[~extreme_mask]))
            herding_ratio = (csad_during_extreme / csad_during_normal
                            if csad_during_normal > 0 else 1.0)
        else:
            csad_during_extreme = None
            csad_during_normal = mean_csad
            herding_ratio = 1.0

        # Interpretation
        # ratio < 1 means less dispersion during extreme moves = herding
        if herding_ratio < 0.8:
            intensity = "high"
        elif herding_ratio < 0.95:
            intensity = "moderate"
        else:
            intensity = "low"

        return {
            "csad": round(current_csad, 6),
            "csad_mean": round(mean_csad, 6),
            "csad_z_score": round(z_score, 4),
            "herding_ratio": round(herding_ratio, 4),
            "herding_intensity": intensity,
            "extreme_days_in_window": extreme_count,
            "window_days": n,
            "num_stocks": len(stock_returns_list),
            # NO buy/sell direction — legal requirement
        }


# ==============================================================================
# Model 3: Sentiment-Price Divergence
# Classification: GREEN — pure data analysis
# ==============================================================================

class SentimentPriceDivergence:
    """Detects divergence between sentiment momentum and price momentum.

    When sentiment is improving but price is falling (or vice versa),
    it can indicate a potential shift. This is pure statistical analysis.

    Legal: GREEN — pure data analysis, no directional guidance.
    """

    MIN_DATA = 5

    @staticmethod
    def calculate(prices, sentiment_scores, window=21):
        """Compute rate-of-change for both sentiment and price, detect divergence.

        Args:
            prices:           list of closing prices (oldest first)
            sentiment_scores: list of sentiment values 0-100 (oldest first)
                              Must be same length as prices or will be aligned
            window:           lookback for rate-of-change calculation

        Returns:
            dict with price_roc, sentiment_roc, divergence_score, divergence_type
        """
        if (len(prices) < SentimentPriceDivergence.MIN_DATA
                or len(sentiment_scores) < SentimentPriceDivergence.MIN_DATA):
            return {"divergence_score": None,
                    "error": "Insufficient data"}

        # Align lengths
        n = min(len(prices), len(sentiment_scores))
        p = np.array(prices[-n:], dtype=np.float64)
        s = np.array(sentiment_scores[-n:], dtype=np.float64)

        w = min(window, n - 1)
        if w < 2:
            return {"divergence_score": None,
                    "error": "Window too small"}

        # Rate of change (most recent vs w periods ago)
        price_roc = (p[-1] - p[-(w + 1)]) / p[-(w + 1)] if p[-(w + 1)] != 0 else 0.0
        sent_roc = (s[-1] - s[-(w + 1)]) / 100.0  # normalize to similar scale

        # Rolling correlation between price changes and sentiment changes
        if n >= w + 1:
            price_changes = np.diff(p[-(w + 1):])
            sent_changes = np.diff(s[-(w + 1):])

            if np.std(price_changes) > 0 and np.std(sent_changes) > 0:
                correlation = float(np.corrcoef(price_changes, sent_changes)[0, 1])
            else:
                correlation = 0.0
        else:
            correlation = 0.0

        # Divergence score: negative when price and sentiment move opposite
        # Range roughly -1 to 1 (can exceed slightly)
        if abs(price_roc) > 0.001 and abs(sent_roc) > 0.001:
            # Sign agreement: same sign = convergence, opposite = divergence
            sign_agree = np.sign(price_roc) * np.sign(sent_roc)
            magnitude = min(abs(price_roc), abs(sent_roc)) / max(abs(price_roc), abs(sent_roc))
            divergence_score = float(-sign_agree * magnitude)
        else:
            divergence_score = 0.0

        # Classify divergence type
        if divergence_score > 0.3:
            div_type = "strong_divergence"
        elif divergence_score > 0.1:
            div_type = "mild_divergence"
        elif divergence_score < -0.3:
            div_type = "strong_convergence"
        elif divergence_score < -0.1:
            div_type = "mild_convergence"
        else:
            div_type = "neutral"

        return {
            "price_roc": round(price_roc, 4),
            "sentiment_roc": round(sent_roc, 4),
            "correlation": round(correlation, 4),
            "divergence_score": round(divergence_score, 4),
            "divergence_type": div_type,
            "current_price": round(float(p[-1]), 2),
            "current_sentiment": round(float(s[-1]), 1),
            "window_days": w,
        }


# ==============================================================================
# Model 4: Order Flow Imbalance
# Classification: YELLOW — data visualization only
# ==============================================================================

class OrderFlowImbalance:
    """Simplified daily Order Flow Imbalance — Cont, Kukanov & Stoikov (2014).

    Without tick-level data, we approximate OFI using daily OHLCV:
      OFI_daily = sign(close - vwap) * volume
    If no VWAP, use (close - open) as directional proxy.

    Accumulated OFI over a window reveals persistent buying/selling pressure.

    Legal: Display as data visualization only. No trading direction.
    """

    MIN_WINDOW = 5

    @staticmethod
    def calculate(opens, closes, volumes, vwaps=None, window=20):
        """Compute accumulated order flow imbalance.

        Args:
            opens:   list of opening prices
            closes:  list of closing prices
            volumes: list of daily volumes
            vwaps:   optional list of VWAP values (same length)
            window:  accumulation window

        Returns:
            dict with ofi_cumulative, ofi_normalized, pressure_level
            All values are numeric. No directional signals.
        """
        min_len = min(len(opens), len(closes), len(volumes))
        if vwaps is not None:
            min_len = min(min_len, len(vwaps))

        if min_len < OrderFlowImbalance.MIN_WINDOW:
            return {"ofi_cumulative": None, "error": "Insufficient data"}

        n = min(window, min_len)
        o = np.array(opens[-n:], dtype=np.float64)
        c = np.array(closes[-n:], dtype=np.float64)
        v = np.array(volumes[-n:], dtype=np.float64)

        # 2026-05-17 Wave D-2 F3: same NaN leak as DispositionEffect.
        # Partial-data days (None / NaN volume or O/C from the fetcher) must
        # be removed before any sum/ratio computation; otherwise
        # ofi_cumulative / total_volume go NaN and cache_service blows up
        # with allow_nan=False.
        finite_mask = np.isfinite(o) & np.isfinite(c) & np.isfinite(v)
        if not finite_mask.all():
            o = o[finite_mask]
            c = c[finite_mask]
            v = v[finite_mask]
        if len(c) < OrderFlowImbalance.MIN_WINDOW:
            return {"ofi_cumulative": None, "error": "Insufficient data"}

        if vwaps is not None and len(vwaps) >= n:
            vw = np.array(vwaps[-n:], dtype=np.float64)
            # vwaps may have been longer than the trimmed (o, c, v) — align
            # to the shortest valid arm after the finite-filter above.
            vw = vw[-len(c):] if len(vw) >= len(c) else vw
            if len(vw) != len(c):
                direction = c - o
            else:
                direction = c - vw
        else:
            # Proxy: close - open captures intraday direction
            direction = c - o

        # OFI = sign(direction) * volume
        ofi_daily = np.sign(direction) * v

        # Cumulative OFI over window
        ofi_cum = float(np.sum(ofi_daily))

        # Normalized OFI: divide by total volume to get -1 to 1 range
        total_vol = float(np.sum(v))
        ofi_norm = ofi_cum / total_vol if total_vol > 0 else 0.0

        # Rolling OFI for trend detection (split window in half)
        half = max(1, n // 2)
        first_half_ofi = float(np.sum(ofi_daily[:half]))
        second_half_ofi = float(np.sum(ofi_daily[half:]))

        # Is pressure accelerating or decelerating?
        if total_vol > 0:
            first_norm = first_half_ofi / float(np.sum(v[:half])) if np.sum(v[:half]) > 0 else 0
            second_norm = second_half_ofi / float(np.sum(v[half:])) if np.sum(v[half:]) > 0 else 0
            acceleration = second_norm - first_norm
        else:
            acceleration = 0.0

        # Volume-weighted close vs open ratio (alternative imbalance metric)
        buy_vol = float(np.sum(v[direction > 0]))
        sell_vol = float(np.sum(v[direction < 0]))
        vol_ratio = buy_vol / sell_vol if sell_vol > 0 else (2.0 if buy_vol > 0 else 1.0)

        # Classify pressure level (purely descriptive)
        if ofi_norm > 0.3:
            pressure = "high_positive"
        elif ofi_norm > 0.1:
            pressure = "moderate_positive"
        elif ofi_norm < -0.3:
            pressure = "high_negative"
        elif ofi_norm < -0.1:
            pressure = "moderate_negative"
        else:
            pressure = "neutral"

        return {
            "ofi_cumulative": round(ofi_cum, 0),
            "ofi_normalized": round(ofi_norm, 4),
            "volume_buy_sell_ratio": round(vol_ratio, 4),
            "acceleration": round(acceleration, 4),
            "pressure_level": pressure,
            "window_days": n,
            "total_volume": round(total_vol, 0),
            # NO buy/sell direction — legal requirement
        }


# ==============================================================================
# Model 5: Anchoring Bias Signal
# Classification: YELLOW — within existing POSITIVE/NEGATIVE framework
# ==============================================================================

class AnchoringBias:
    """George & Hwang (2004) enhanced — 52-week high proximity + CGO interaction.

    Investors anchor to the 52-week high. Stocks near the high tend to have
    muted reactions to good news (anchoring suppresses upward adjustment).

    Nearness = current_price / 52_week_high

    Combined with CGO from DispositionEffect for interaction:
    - High nearness + High CGO = strong anchoring + disposition overlap
    - Low nearness + Low CGO = potential underreaction zone

    Legal: Provide as indicator within existing POSITIVE/NEGATIVE framework.
    YELLOW models output only numeric indicators + high/low/neutral.
    """

    MIN_WINDOW = 60

    @staticmethod
    def calculate(closes, volumes, window=252):
        """Combine 52-week high proximity with CGO for interaction signal.

        Args:
            closes:  list of closing prices (oldest first)
            volumes: list of daily volumes (oldest first)
            window:  lookback in trading days (default 252 ~ 1 year)

        Returns:
            dict with nearness, cgo, interaction_score, anchoring_level
            All values are numeric. No directional signals.
        """
        if (len(closes) < AnchoringBias.MIN_WINDOW
                or len(volumes) < AnchoringBias.MIN_WINDOW):
            return {"nearness": None, "error": "Insufficient data"}

        n = min(window, len(closes), len(volumes))
        c = np.array(closes[-n:], dtype=np.float64)
        v = np.array(volumes[-n:], dtype=np.float64)

        # 2026-05-17 Wave D-2 F3: NaN leak guard (matches DispositionEffect /
        # OrderFlowImbalance). Without this, np.max / np.sum propagate NaN
        # into nearness / cgo / interaction_score and the entire payload
        # fails json.dumps(allow_nan=False) at cache write.
        finite_mask = np.isfinite(c) & np.isfinite(v)
        if not finite_mask.all():
            c = c[finite_mask]
            v = v[finite_mask]
        if len(c) < AnchoringBias.MIN_WINDOW:
            return {"nearness": None, "error": "Insufficient data"}

        current = float(c[-1])
        high_52w = float(np.max(c))
        low_52w = float(np.min(c))

        # Nearness to 52-week high (0 to 1)
        nearness = current / high_52w if high_52w > 0 else 0.0

        # Distance from 52-week low (for context)
        dist_from_low = ((current - low_52w) / low_52w
                         if low_52w > 0 else 0.0)

        # CGO calculation (reuse DispositionEffect logic inline)
        total_vol = float(np.sum(v))
        if total_vol > 0:
            ref_price = float(np.sum(c * v) / total_vol)
            cgo = (current - ref_price) / ref_price if ref_price > 0 else 0.0
        else:
            ref_price = current
            cgo = 0.0

        # Interaction score: nearness * |cgo|
        # High values = both anchoring and disposition effects are strong
        interaction = nearness * abs(cgo)

        # Percentile rank of current price within the window
        pct_rank = float(np.sum(c <= current)) / n

        # Volatility context: recent vs historical
        if n >= 20:
            recent_vol = float(np.std(c[-20:] / c[-21:-1], ddof=1)) if len(c) > 20 else 0
            hist_vol = float(np.std(c[1:] / c[:-1], ddof=1))
            vol_ratio = recent_vol / hist_vol if hist_vol > 0 else 1.0
        else:
            vol_ratio = 1.0

        # Classify anchoring level
        if nearness > 0.95:
            anchoring_level = "high"
        elif nearness > 0.85:
            anchoring_level = "moderate"
        elif nearness < 0.70:
            anchoring_level = "low"
        else:
            anchoring_level = "neutral"

        return {
            "nearness": round(nearness, 4),
            "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2),
            "current_price": round(current, 2),
            "distance_from_low": round(dist_from_low, 4),
            "cgo": round(cgo, 4),
            "reference_price": round(ref_price, 2),
            "interaction_score": round(interaction, 6),
            "percentile_rank": round(pct_rank, 4),
            "volatility_ratio": round(vol_ratio, 4),
            "anchoring_level": anchoring_level,
            "window_days": n,
            # NO buy/sell direction — legal requirement (YELLOW)
        }
