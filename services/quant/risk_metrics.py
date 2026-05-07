"""Foundational risk models for portfolio analytics.

Three statistically rigorous, legally unrestricted models:
  1. GKYZVolatility  — Garman-Klass-Yang-Zhang OHLC volatility estimator
  2. LedoitWolfShrinkage — Ledoit & Wolf (2004) shrinkage covariance
  3. ComponentES — Component Expected Shortfall (Euler decomposition)

All models are pure NumPy — no external dependencies beyond numpy.
"""

import numpy as np


class GKYZVolatility:
    """Garman-Klass-Yang-Zhang volatility estimator.

    Uses OHLC + previous close for 7-8x statistical efficiency vs close-to-close.
    Based on Yang & Zhang (2000), "Drift Independent Volatility Estimation
    Based on High, Low, Open, and Close Prices."

    Combines three variance components:
      - Overnight variance (close-to-open)
      - Rogers-Satchell variance (intraday range-based)
      - Open-to-close variance
    with an optimal weighting parameter k that minimises estimator variance.
    """

    @staticmethod
    def estimate(opens, highs, lows, closes, window=20):
        """Compute annualised GKYZ volatility from OHLC data.

        Args:
            opens:  array-like of opening prices  (length >= window + 1)
            highs:  array-like of high prices
            lows:   array-like of low prices
            closes: array-like of closing prices
            window: lookback window in trading days (default 20)

        Returns:
            dict with:
                vol_gkyz       — annualised volatility (%), GKYZ estimator
                vol_close      — annualised volatility (%), close-to-close (for comparison)
                efficiency_ratio — vol_close / vol_gkyz (>1 means GKYZ is tighter)
                window         — window used
        """
        n = len(closes)
        if n < window + 1:
            return {"vol_gkyz": None, "vol_close": None, "efficiency_ratio": None}

        # Slice to last `window` bars; need window+1 closes for c_prev
        o = np.array(opens[-window:], dtype=np.float64)
        h = np.array(highs[-window:], dtype=np.float64)
        l = np.array(lows[-window:], dtype=np.float64)
        c = np.array(closes[-window:], dtype=np.float64)
        c_prev = np.array(closes[-(window + 1):-1], dtype=np.float64)

        # Yang-Zhang log-return components
        log_oc = np.log(o / c_prev)   # overnight returns
        log_co = np.log(c / o)        # open-to-close returns
        log_ho = np.log(h / o)
        log_lo = np.log(l / o)

        # Overnight variance (open vs previous close)
        var_overnight = np.var(log_oc, ddof=1)

        # Open-to-close variance
        var_close = np.var(log_co, ddof=1)

        # Rogers-Satchell variance (range-based, drift-independent)
        rs = log_ho * (log_ho - log_co) + log_lo * (log_lo - log_co)
        var_rs = np.mean(rs)

        # Optimal combination weight (minimises estimator variance)
        k = 0.34 / (1.34 + (window + 1) / (window - 1))
        var_yz = var_overnight + k * var_close + (1 - k) * var_rs

        # Bug NEW-E fix: var_yz can drift slightly negative on quiet/illiquid
        # windows where the Rogers-Satchell mean dominates and noise pushes
        # the combined estimator below zero. np.sqrt(negative) -> NaN, which
        # then poisons every downstream metric. Clamp to 0.
        var_yz = max(var_yz, 0.0)

        vol_gkyz = float(np.sqrt(var_yz * 252)) * 100  # annualised %

        # Standard close-to-close volatility for comparison
        log_ret = np.diff(np.log(np.array(closes[-(window + 1):], dtype=np.float64)))
        vol_close = float(np.std(log_ret, ddof=1) * np.sqrt(252)) * 100

        efficiency = vol_close / vol_gkyz if vol_gkyz > 0 else 1.0

        return {
            "vol_gkyz": round(vol_gkyz, 2),
            "vol_close": round(vol_close, 2),
            "efficiency_ratio": round(efficiency, 3),
            "window": window,
        }


class LedoitWolfShrinkage:
    """Ledoit & Wolf (2004) shrinkage covariance estimator.

    Produces a well-conditioned covariance matrix even when the number
    of assets approaches or exceeds the number of observations.

    Shrinks the sample covariance toward a scaled identity matrix
    (the "constant correlation" target) with an analytically optimal
    shrinkage intensity that minimises expected Frobenius loss.

    Reference:
        Ledoit, O. & Wolf, M. (2004). "A well-conditioned estimator for
        large-dimensional covariance matrices." JMVA 88(2), 365-411.
    """

    @staticmethod
    def estimate(returns_matrix):
        """Compute the shrinkage covariance matrix.

        Args:
            returns_matrix: numpy array of shape (n_observations, n_assets),
                            each row is a return vector for one time period.

        Returns:
            dict with:
                shrunk_cov          — (n_assets x n_assets) shrinkage covariance matrix
                sample_cov          — (n_assets x n_assets) raw sample covariance
                shrinkage_intensity — optimal alpha in [0, 1] (higher = more shrinkage)
                target_variance     — average variance used for the identity target
                n_observations      — rows used
                n_assets            — columns used
        """
        X = np.array(returns_matrix, dtype=np.float64)
        n, p = X.shape

        if n < 2 or p < 1:
            return {"shrunk_cov": None, "shrinkage_intensity": None}

        # Demean returns
        X = X - X.mean(axis=0)

        # Sample covariance (1/n normalisation for the LW estimator)
        S = X.T @ X / n

        # Target: scaled identity with average variance on diagonal
        mu = np.trace(S) / p
        F = mu * np.eye(p)

        # Distance between sample and target
        delta = S - F
        d_bar_sq = float(np.sum(delta ** 2))

        # Estimation error of sample covariance (b_bar^2)
        X2 = X ** 2
        b_bar_sq = float(np.sum(X2.T @ X2 / n - S ** 2)) / (n * (n - 1))
        b_bar_sq = max(b_bar_sq, 0.0)  # numerical safety

        # Optimal shrinkage intensity
        if d_bar_sq == 0:
            alpha = 1.0
        else:
            alpha = min(b_bar_sq / d_bar_sq, 1.0)

        # Shrunk covariance
        shrunk = (1 - alpha) * S + alpha * F

        return {
            "shrunk_cov": shrunk,
            "sample_cov": S,
            "shrinkage_intensity": round(alpha, 4),
            "target_variance": round(float(mu), 6),
            "n_observations": n,
            "n_assets": p,
        }


class ComponentES:
    """Component Expected Shortfall decomposition (Euler principle).

    Decomposes portfolio-level tail risk (ES/CVaR) into per-position
    contributions that sum exactly to the portfolio ES.  This allows
    risk budgeting: you can see which positions drive tail-risk exposure.

    Uses historical simulation (no distributional assumptions).

    Reference:
        Tasche, D. (2002). "Expected shortfall and beyond."
        Journal of Banking & Finance 26(7), 1519-1533.
    """

    @staticmethod
    def decompose(returns_matrix, weights, alpha=0.05):
        """Decompose portfolio ES into per-asset contributions.

        Args:
            returns_matrix: (n_obs, n_assets) daily return matrix
            weights:        (n_assets,) portfolio weights summing to 1
            alpha:          tail probability (0.05 = 95th percentile ES)

        Returns:
            dict with:
                portfolio_es     — portfolio ES as negative percentage
                portfolio_var    — portfolio VaR as negative percentage
                alpha            — tail probability used
                n_tail_scenarios — number of observations in the tail
                component_es     — list of per-asset ES contributions (%)
                pct_contribution — list of per-asset % share of total ES
        """
        R = np.array(returns_matrix, dtype=np.float64)
        w = np.array(weights, dtype=np.float64)
        n, p = R.shape

        if n < 20 or p < 1 or len(w) != p:
            return {"portfolio_es": None, "components": None}

        # Portfolio returns
        port_returns = R @ w

        # VaR threshold (historical quantile)
        sorted_returns = np.sort(port_returns)
        var_idx = int(np.floor(n * alpha))
        var_idx = max(1, min(var_idx, n - 1))
        var_threshold = sorted_returns[var_idx]

        # Portfolio ES: mean of returns at or below VaR
        tail_mask = port_returns <= var_threshold
        if tail_mask.sum() == 0:
            return {"portfolio_es": 0.0, "components": {}}

        portfolio_es = float(np.mean(port_returns[tail_mask]))

        # Component ES via Euler decomposition:
        # For each asset, average that asset's return in tail scenarios, weighted
        component_returns = R[tail_mask]  # (n_tail, n_assets)
        component_es = np.mean(component_returns, axis=0) * w  # weighted contribution

        # Percentage contribution to total ES
        total_ces = float(np.sum(component_es))
        if total_ces != 0:
            pct_contribution = component_es / total_ces * 100
        else:
            pct_contribution = np.zeros(p)

        return {
            "portfolio_es": round(portfolio_es * 100, 3),   # as percentage
            "portfolio_var": round(float(var_threshold) * 100, 3),
            "alpha": alpha,
            "n_tail_scenarios": int(tail_mask.sum()),
            "component_es": [round(float(x) * 100, 4) for x in component_es],
            "pct_contribution": [round(float(x), 2) for x in pct_contribution],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CONDITIONAL DRAWDOWN AT RISK (CDDaR)
# ═══════════════════════════════════════════════════════════════════════════════

class ConditionalDrawdown:
    """Conditional Drawdown at Risk — average drawdown in worst X% of periods.

    CDDaR is to drawdowns what CVaR is to returns: the expected drawdown
    conditional on being in the worst alpha-percentile of drawdown episodes.

    Useful for portfolios where max drawdown alone is too sensitive to outliers.
    """

    @staticmethod
    def calculate(portfolio_values, alpha=0.05):
        """Compute CDDaR from a portfolio value series.

        Args:
            portfolio_values: array-like of portfolio equity values (not returns)
            alpha:            tail probability (default 0.05 = worst 5%)

        Returns:
            dict with cddar (%), alpha, max_dd (%).
        """
        if len(portfolio_values) < 20:
            return {"cddar": None}

        pv = np.array(portfolio_values, dtype=float)
        peak = np.maximum.accumulate(pv)
        dd = (pv - peak) / peak  # negative values

        sorted_dd = np.sort(dd)
        cutoff = int(len(sorted_dd) * alpha)
        cutoff = max(1, cutoff)
        cddar = float(np.mean(sorted_dd[:cutoff]))

        return {
            "cddar": round(cddar * 100, 2),
            "alpha": alpha,
            "max_dd": round(float(np.min(dd)) * 100, 2),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# TAIL RATIO
# ═══════════════════════════════════════════════════════════════════════════════

class TailRatio:
    """Tail Ratio — ratio of positive tail to negative tail.

    Computed as |95th percentile| / |5th percentile| of return distribution.
      > 1 = fatter right tail (favorable — larger gains than losses)
      < 1 = fatter left tail (unfavorable — larger losses than gains)

    A simple, intuitive measure of return distribution asymmetry.
    """

    @staticmethod
    def calculate(returns):
        """Compute Tail Ratio from daily returns.

        Args:
            returns: array-like of daily returns (decimal, e.g. 0.02 = 2%)

        Returns:
            dict with tail_ratio, p95 (%), p5 (%), interpretation.
        """
        if len(returns) < 20:
            return {"tail_ratio": None}

        r = np.array(returns, dtype=float)
        p95 = float(np.percentile(r, 95))
        p5 = float(np.percentile(r, 5))

        ratio = abs(p95 / p5) if p5 != 0 else 1.0

        return {
            "tail_ratio": round(ratio, 3),
            "p95": round(p95 * 100, 2),
            "p5": round(p5 * 100, 2),
            "interpretation": "favorable" if ratio > 1.0 else "unfavorable",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SORTINO BY POSITION
# ═══════════════════════════════════════════════════════════════════════════════

class SortinoByPosition:
    """Per-position Sortino ratio — risk-adjusted return using only downside deviation.

    Unlike Sharpe (which penalises both up and down volatility), Sortino
    only penalises downside moves below a minimum acceptable return (MAR).

    Reference:
        Sortino, F. & van der Meer, R. (1991). "Downside risk."
        Journal of Portfolio Management 17(4), 27-31.
    """

    @staticmethod
    def calculate(returns, risk_free_annual=0.045):
        """Compute Sortino ratio from daily returns.

        Args:
            returns:          array-like of daily returns (decimal)
            risk_free_annual: annualised risk-free rate (default 4.5%)

        Returns:
            dict with sortino, downside_dev (%), annualized_return (%).
        """
        if len(returns) < 20:
            return {"sortino": None}

        r = np.array(returns, dtype=float)
        rf_daily = risk_free_annual / 252
        excess = r - rf_daily

        downside = excess[excess < 0]
        if len(downside) == 0:
            return {
                "sortino": 999.0,
                "annualized_return": round(float(np.mean(r) * 252 * 100), 2),
            }

        downside_dev = float(np.std(downside, ddof=1)) * np.sqrt(252)
        mean_annual = float(np.mean(excess)) * 252

        sortino = mean_annual / downside_dev if downside_dev > 0 else 0

        return {
            "sortino": round(float(sortino), 3),
            "downside_dev": round(downside_dev * 100, 2),
            "annualized_return": round(float(np.mean(r) * 252 * 100), 2),
        }

