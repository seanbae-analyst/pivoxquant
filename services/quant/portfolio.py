"""
PivoxQuant — Portfolio Construction Models (Simulation Only)

Three academically-grounded allocation models:
  1. HRP  — Hierarchical Risk Parity (Lopez de Prado, 2016)
  2. TRP  — Tail Risk Parity (CVaR-equalisation)
  3. MDP  — Maximum Diversification Portfolio (Choueifaty & Coignard, 2008)

LEGAL DISCLAIMER: These models are simulation/educational tools ONLY.
They do NOT constitute investment advice, portfolio allocation
recommendations, or solicitations to buy/sell any security.
"""

import numpy as np
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

DISCLAIMER = (
    "Portfolio simulation for educational reference only. "
    "Does not constitute investment advice or portfolio allocation recommendation."
)


def _covariance_matrix(returns: np.ndarray) -> np.ndarray:
    """Sample covariance with Bessel correction."""
    n = returns.shape[0]
    if n < 2:
        raise ValueError("Need at least 2 observations for covariance")
    mean = returns.mean(axis=0)
    centered = returns - mean
    return (centered.T @ centered) / (n - 1)


def _correlation_matrix(returns: np.ndarray) -> np.ndarray:
    """Pearson correlation from returns matrix."""
    cov = _covariance_matrix(returns)
    std = np.sqrt(np.diag(cov))
    std[std == 0] = 1e-10  # guard against zero-vol assets
    d_inv = np.diag(1.0 / std)
    return d_inv @ cov @ d_inv


def _ledoit_wolf_shrink(returns: np.ndarray) -> np.ndarray:
    """Ledoit-Wolf constant-correlation shrinkage estimator.

    Target: constant-correlation matrix (scaled identity + mean-corr off-diag).
    Returns the shrunk covariance matrix. Pure numpy, no sklearn needed.
    """
    n, p = returns.shape
    if n < 2 or p < 2:
        return _covariance_matrix(returns)

    # Sample covariance
    mean = returns.mean(axis=0)
    X = returns - mean
    S = (X.T @ X) / n  # biased estimator (Ledoit-Wolf convention)

    # Target: constant-correlation model
    var = np.diag(S).copy()
    std = np.sqrt(var)
    std[std == 0] = 1e-10

    # Mean correlation (off-diagonal)
    corr = S / np.outer(std, std)
    np.fill_diagonal(corr, 0.0)
    rho_bar = np.sum(corr) / (p * (p - 1))

    # Target matrix F = diag(var) + rho_bar * outer(std, std) * (1 - I)
    F = rho_bar * np.outer(std, std)
    np.fill_diagonal(F, var)

    # --- Optimal shrinkage intensity (Ledoit-Wolf 2004, Eq. 2) ---

    # Squared Frobenius norm of (S - F)
    delta = S - F

    # pi_hat: sum of asymptotic variances of s_ij
    # For each element, Var(s_ij) ~ (1/n) * sum_t (x_it*x_jt - s_ij)^2
    Y = X  # (n, p) centered
    pi_mat = np.zeros((p, p))
    for t in range(n):
        outer_t = np.outer(Y[t], Y[t])
        diff = outer_t - S
        pi_mat += diff * diff
    pi_mat /= n
    pi_hat = np.sum(pi_mat)

    # gamma_hat: squared Frobenius distance between S and F
    gamma_hat = np.sum(delta * delta)

    # kappa: denominator — approximation
    kappa = (pi_hat - gamma_hat) / n
    if kappa < 0:
        kappa = 0

    # Shrinkage intensity, clamped to [0, 1]
    shrinkage = max(0.0, min(1.0, kappa / gamma_hat)) if gamma_hat > 1e-12 else 1.0

    # Shrunk covariance
    Sigma = (1 - shrinkage) * S + shrinkage * F

    # Convert from biased to unbiased scaling
    Sigma = Sigma * n / (n - 1)

    logger.debug("Ledoit-Wolf shrinkage intensity: %.4f", shrinkage)
    return Sigma


def _inverse_variance_weights(cov: np.ndarray, indices: list[int]) -> np.ndarray:
    """Allocate inversely proportional to diagonal variance for given asset indices."""
    variances = np.array([cov[i, i] for i in indices])
    variances[variances <= 0] = 1e-10
    inv_var = 1.0 / variances
    return inv_var / inv_var.sum()


# ---------------------------------------------------------------------------
# Model 1: Hierarchical Risk Parity
# ---------------------------------------------------------------------------

class HRP:
    """Hierarchical Risk Parity portfolio construction.

    Lopez de Prado (2016). Three stages:
      1. Distance matrix + single-linkage clustering
      2. Quasi-diagonalisation (reorder by dendrogram leaves)
      3. Recursive bisection with inverse-variance allocation

    Does NOT invert the covariance matrix — numerically stable even with
    noisy, singular, or highly correlated data.

    Legal: Simulation tool only. NOT investment advice.
    """

    @staticmethod
    def allocate(
        returns_matrix: np.ndarray,
        tickers: Optional[list[str]] = None,
    ) -> dict:
        """Run HRP allocation.

        Args:
            returns_matrix: (n_obs, n_assets) array of daily returns.
            tickers: optional list of ticker labels (length == n_assets).

        Returns:
            dict with keys: weights, dendrogram_order, cluster_info, tickers, disclaimer.
        """
        returns = np.asarray(returns_matrix, dtype=np.float64)
        n_obs, n_assets = returns.shape
        if n_obs < 5:
            raise ValueError(f"Need >= 5 observations, got {n_obs}")
        if n_assets < 2:
            raise ValueError(f"Need >= 2 assets, got {n_assets}")

        if tickers is None:
            tickers = [f"Asset_{i}" for i in range(n_assets)]

        corr = _correlation_matrix(returns)
        cov = _covariance_matrix(returns)

        # Stage 1 — Distance matrix from correlation
        # Clamp to [0, 1] range before sqrt to handle numerical noise
        dist = np.sqrt(np.maximum(0.0, 0.5 * (1.0 - corr)))
        np.fill_diagonal(dist, 0.0)

        # Stage 1b — Single-linkage clustering (nearest-neighbor chain)
        linkage = HRP._single_linkage(dist, n_assets)

        # Stage 2 — Quasi-diagonalisation: extract leaf order from linkage
        leaf_order = HRP._get_leaf_order(linkage, n_assets)

        # Stage 3 — Recursive bisection
        weights_ordered = HRP._recursive_bisection(cov, leaf_order)

        # Map back to original asset indices
        weights = np.zeros(n_assets)
        for i, asset_idx in enumerate(leaf_order):
            weights[asset_idx] = weights_ordered[i]

        # Build cluster info for display
        cluster_info = []
        for step in linkage:
            cluster_info.append({
                "merged": [int(step[0]), int(step[1])],
                "distance": round(float(step[2]), 6),
                "size": int(step[3]),
            })

        return {
            "weights": {tickers[i]: round(float(weights[i]), 6) for i in range(n_assets)},
            "dendrogram_order": [tickers[i] for i in leaf_order],
            "cluster_info": cluster_info,
            "tickers": tickers,
            "method": "Hierarchical Risk Parity (Lopez de Prado 2016)",
            "disclaimer": DISCLAIMER,
        }

    @staticmethod
    def _single_linkage(dist: np.ndarray, n: int) -> np.ndarray:
        """Single-linkage clustering via nearest-neighbor chain algorithm.

        Returns linkage matrix compatible with scipy format:
            Each row: [cluster_a, cluster_b, distance, new_cluster_size]
        """
        # Working copy — will be modified
        D = dist.copy()
        np.fill_diagonal(D, np.inf)

        # Track which original clusters each node contains
        active = list(range(n))  # active cluster IDs
        sizes = {i: 1 for i in range(n)}
        linkage_rows = []
        next_id = n  # new cluster IDs start at n

        for _ in range(n - 1):
            # Find the global minimum distance among active clusters
            min_dist = np.inf
            merge_a, merge_b = -1, -1
            for ii in range(len(active)):
                for jj in range(ii + 1, len(active)):
                    a, b = active[ii], active[jj]
                    if D[a, b] < min_dist:
                        min_dist = D[a, b]
                        merge_a, merge_b = a, b

            if merge_a < 0:
                break

            new_size = sizes[merge_a] + sizes[merge_b]
            linkage_rows.append([merge_a, merge_b, min_dist, new_size])

            # Update distance matrix: new cluster uses single-linkage (min) distances
            # Expand matrix to accommodate new cluster
            old_size = D.shape[0]
            new_D = np.full((old_size + 1, old_size + 1), np.inf)
            new_D[:old_size, :old_size] = D

            for k in active:
                if k == merge_a or k == merge_b:
                    continue
                new_d = min(D[merge_a, k], D[merge_b, k])
                new_D[next_id, k] = new_d
                new_D[k, next_id] = new_d

            D = new_D
            # Invalidate merged clusters
            D[merge_a, :] = np.inf
            D[:, merge_a] = np.inf
            D[merge_b, :] = np.inf
            D[:, merge_b] = np.inf

            # Update bookkeeping
            active.remove(merge_a)
            active.remove(merge_b)
            active.append(next_id)
            sizes[next_id] = new_size
            next_id += 1

        return np.array(linkage_rows)

    @staticmethod
    def _get_leaf_order(linkage: np.ndarray, n: int) -> list[int]:
        """Extract leaf ordering from linkage matrix (depth-first traversal)."""
        # Build tree structure: node_id -> (left_child, right_child)
        tree = {}
        for i, row in enumerate(linkage):
            node_id = n + i
            tree[node_id] = (int(row[0]), int(row[1]))

        root = n + len(linkage) - 1

        # Iterative DFS to avoid recursion depth issues
        leaves = []
        stack = [root]
        while stack:
            node = stack.pop()
            if node < n:
                # Leaf node (original asset)
                leaves.append(node)
            else:
                left, right = tree[node]
                # Push right first so left is processed first (DFS order)
                stack.append(right)
                stack.append(left)

        return leaves

    @staticmethod
    def _recursive_bisection(cov: np.ndarray, leaf_order: list[int]) -> np.ndarray:
        """Top-down recursive bisection with inverse-variance weighting.

        Returns weights array aligned with leaf_order (not original asset order).
        """
        n = len(leaf_order)
        weights = np.ones(n)

        # BFS-style recursive split
        clusters = [list(range(n))]  # indices into leaf_order
        while clusters:
            next_clusters = []
            for cluster in clusters:
                if len(cluster) <= 1:
                    continue
                mid = len(cluster) // 2
                left_idx = cluster[:mid]
                right_idx = cluster[mid:]

                # Map to original asset indices for covariance lookup
                left_assets = [leaf_order[i] for i in left_idx]
                right_assets = [leaf_order[i] for i in right_idx]

                # Cluster variance = w_iv' @ Cov_sub @ w_iv
                left_var = HRP._cluster_variance(cov, left_assets)
                right_var = HRP._cluster_variance(cov, right_assets)

                # Allocation: inversely proportional to cluster variance
                total_var = left_var + right_var
                if total_var < 1e-14:
                    alpha = 0.5
                else:
                    alpha = 1.0 - left_var / total_var  # left gets more if less risky

                for i in left_idx:
                    weights[i] *= alpha
                for i in right_idx:
                    weights[i] *= (1.0 - alpha)

                if len(left_idx) > 1:
                    next_clusters.append(left_idx)
                if len(right_idx) > 1:
                    next_clusters.append(right_idx)

            clusters = next_clusters

        return weights

    @staticmethod
    def _cluster_variance(cov: np.ndarray, asset_indices: list[int]) -> float:
        """Compute the variance of an inverse-variance-weighted sub-portfolio."""
        if len(asset_indices) == 1:
            return float(cov[asset_indices[0], asset_indices[0]])

        w_iv = _inverse_variance_weights(cov, asset_indices)
        sub_cov = cov[np.ix_(asset_indices, asset_indices)]
        return float(w_iv @ sub_cov @ w_iv)


# ---------------------------------------------------------------------------
# Model 2: Tail Risk Parity
# ---------------------------------------------------------------------------

class TailRiskParity:
    """Tail Risk Parity — equalises CVaR (Expected Shortfall) contributions.

    Iteratively adjusts weights until each asset contributes equally to
    portfolio tail risk. Uses historical simulation (no distributional
    assumption).

    Legal: Simulation tool only. NOT investment advice.
    """

    @staticmethod
    def allocate(
        returns_matrix: np.ndarray,
        tickers: Optional[list[str]] = None,
        alpha: float = 0.05,
        max_iterations: int = 50,
        tolerance: float = 0.01,
    ) -> dict:
        """Run TRP allocation.

        Args:
            returns_matrix: (n_obs, n_assets) daily returns.
            tickers: optional ticker labels.
            alpha: tail probability (default 5% = 95% CVaR).
            max_iterations: convergence cap.
            tolerance: max allowed deviation from equal contribution (fraction).

        Returns:
            dict with weights, cvar_contributions, iterations, converged, disclaimer.
        """
        returns = np.asarray(returns_matrix, dtype=np.float64)
        n_obs, n_assets = returns.shape
        if n_obs < 20:
            raise ValueError(f"Need >= 20 observations for CVaR estimation, got {n_obs}")
        if n_assets < 2:
            raise ValueError(f"Need >= 2 assets, got {n_assets}")

        if tickers is None:
            tickers = [f"Asset_{i}" for i in range(n_assets)]

        # Start with equal weights
        weights = np.ones(n_assets) / n_assets

        converged = False
        iteration = 0
        target_contribution = 1.0 / n_assets

        # Learning rate decay: start aggressive, reduce over iterations
        base_lr = 0.3

        for iteration in range(1, max_iterations + 1):
            # Compute Component CVaR for current weights
            comp_cvar = TailRiskParity._component_cvar(returns, weights, alpha)
            total_cvar = comp_cvar.sum()

            if total_cvar < 1e-12:
                # Portfolio has near-zero tail risk — keep equal weights
                break

            # Normalised contribution fractions
            contributions = comp_cvar / total_cvar

            # Check convergence: max deviation from target
            max_deviation = float(np.max(np.abs(contributions - target_contribution)))
            if max_deviation <= tolerance:
                converged = True
                break

            # Adjust: reduce weight of highest contributor, increase lowest
            lr = base_lr / (1 + 0.05 * iteration)  # decay

            for i in range(n_assets):
                # Multiplicative update: shift toward target
                if contributions[i] > target_contribution:
                    weights[i] *= (1.0 - lr * (contributions[i] - target_contribution))
                else:
                    weights[i] *= (1.0 + lr * (target_contribution - contributions[i]))

            # Re-normalise to sum = 1, enforce minimum weight
            weights = np.maximum(weights, 1e-6)
            weights /= weights.sum()

        # Final component CVaR
        final_comp = TailRiskParity._component_cvar(returns, weights, alpha)
        total_cvar = final_comp.sum()

        return {
            "weights": {tickers[i]: round(float(weights[i]), 6) for i in range(n_assets)},
            "cvar_contributions": {
                tickers[i]: round(float(final_comp[i]), 6) for i in range(n_assets)
            },
            "cvar_contribution_pct": {
                tickers[i]: round(float(final_comp[i] / total_cvar * 100), 2)
                if total_cvar > 1e-12 else round(100.0 / n_assets, 2)
                for i in range(n_assets)
            },
            "total_portfolio_cvar": round(float(total_cvar), 6),
            "alpha": alpha,
            "iterations": iteration,
            "converged": converged,
            "tickers": tickers,
            "method": "Tail Risk Parity (CVaR equalisation)",
            "disclaimer": DISCLAIMER,
        }

    @staticmethod
    def _component_cvar(
        returns: np.ndarray, weights: np.ndarray, alpha: float
    ) -> np.ndarray:
        """Compute Component CVaR (Euler decomposition of Expected Shortfall).

        Component CVaR_i = w_i * E[r_i | r_portfolio <= VaR_alpha]

        This is the additive decomposition: sum(ComponentCVaR) = PortfolioCVaR.
        """
        n_obs, n_assets = returns.shape

        # Portfolio returns
        port_returns = returns @ weights  # (n_obs,)

        # VaR threshold (alpha-quantile of portfolio returns)
        cutoff = int(max(1, np.floor(n_obs * alpha)))
        sorted_idx = np.argsort(port_returns)
        tail_idx = sorted_idx[:cutoff]  # worst alpha% of days

        if len(tail_idx) == 0:
            return np.zeros(n_assets)

        # Tail returns for each asset on the worst portfolio days
        tail_returns = returns[tail_idx]  # (cutoff, n_assets)

        # Component CVaR: w_i * mean(r_i on tail days)
        # Negative sign: CVaR is typically reported as a positive loss
        mean_tail = tail_returns.mean(axis=0)  # (n_assets,)
        component_cvar = -weights * mean_tail

        # Ensure non-negative (assets that gain in tail scenarios get 0 contribution)
        component_cvar = np.maximum(component_cvar, 0.0)

        return component_cvar


# ---------------------------------------------------------------------------
# Model 3: Maximum Diversification Portfolio
# ---------------------------------------------------------------------------

class MaxDiversification:
    """Maximum Diversification Portfolio (Choueifaty & Coignard, 2008).

    Maximises the Diversification Ratio:
        DR = (w' @ sigma) / sqrt(w' @ Sigma @ w)
    where sigma is the vector of individual volatilities and Sigma is the
    covariance matrix.

    Uses Ledoit-Wolf shrunk covariance for numerical stability.

    Legal: Simulation tool only. NOT investment advice.
    """

    @staticmethod
    def allocate(
        returns_matrix: np.ndarray,
        tickers: Optional[list[str]] = None,
    ) -> dict:
        """Run MDP allocation.

        Args:
            returns_matrix: (n_obs, n_assets) daily returns.
            tickers: optional ticker labels.

        Returns:
            dict with weights, diversification_ratio, shrinkage_info, disclaimer.
        """
        returns = np.asarray(returns_matrix, dtype=np.float64)
        n_obs, n_assets = returns.shape
        if n_obs < 10:
            raise ValueError(f"Need >= 10 observations, got {n_obs}")
        if n_assets < 2:
            raise ValueError(f"Need >= 2 assets, got {n_assets}")

        if tickers is None:
            tickers = [f"Asset_{i}" for i in range(n_assets)]

        # Ledoit-Wolf shrunk covariance
        Sigma = _ledoit_wolf_shrink(returns)
        sigma = np.sqrt(np.diag(Sigma))  # individual vols
        sigma[sigma < 1e-10] = 1e-10

        # Closed-form MDP weights:
        # w* = Sigma^{-1} @ sigma / (1' @ Sigma^{-1} @ sigma)
        # This maximises the diversification ratio under long-only + fully-invested.
        try:
            Sigma_inv = np.linalg.inv(Sigma)
        except np.linalg.LinAlgError:
            # Singular matrix — fall back to pseudo-inverse
            Sigma_inv = np.linalg.pinv(Sigma)
            logger.warning("MDP: covariance matrix singular, using pseudo-inverse")

        raw_w = Sigma_inv @ sigma
        ones = np.ones(n_assets)

        denom = ones @ raw_w
        if abs(denom) < 1e-14:
            # Degenerate case — fall back to equal weight
            weights = ones / n_assets
        else:
            weights = raw_w / denom

        # Handle negative weights: long-only projection via iterative clipping
        if np.any(weights < 0):
            weights = MaxDiversification._long_only_project(Sigma, sigma)

        # Compute Diversification Ratio
        weighted_vol_sum = float(weights @ sigma)
        portfolio_vol = float(np.sqrt(weights @ Sigma @ weights))
        dr = weighted_vol_sum / portfolio_vol if portfolio_vol > 1e-12 else 1.0

        # Annualised portfolio volatility
        annual_port_vol = portfolio_vol * np.sqrt(252)

        return {
            "weights": {tickers[i]: round(float(weights[i]), 6) for i in range(n_assets)},
            "diversification_ratio": round(dr, 4),
            "portfolio_vol_daily": round(portfolio_vol * 100, 4),
            "portfolio_vol_annual": round(float(annual_port_vol) * 100, 2),
            "individual_vols_annual": {
                tickers[i]: round(float(sigma[i] * np.sqrt(252)) * 100, 2)
                for i in range(n_assets)
            },
            "tickers": tickers,
            "method": "Maximum Diversification Portfolio (Choueifaty & Coignard 2008)",
            "disclaimer": DISCLAIMER,
        }

    @staticmethod
    def _long_only_project(
        Sigma: np.ndarray, sigma: np.ndarray, max_iter: int = 100
    ) -> np.ndarray:
        """Project MDP solution to long-only (non-negative) weights.

        Iteratively zeros out negative weights and re-solves on the
        remaining assets until all weights are non-negative.
        """
        n = len(sigma)
        mask = np.ones(n, dtype=bool)  # active assets

        for _ in range(max_iter):
            active_idx = np.where(mask)[0]
            if len(active_idx) == 0:
                return np.ones(n) / n  # fallback

            sub_Sigma = Sigma[np.ix_(active_idx, active_idx)]
            sub_sigma = sigma[active_idx]

            try:
                sub_inv = np.linalg.inv(sub_Sigma)
            except np.linalg.LinAlgError:
                sub_inv = np.linalg.pinv(sub_Sigma)

            sub_w = sub_inv @ sub_sigma
            denom = sub_w.sum()
            if abs(denom) < 1e-14:
                sub_w = np.ones(len(active_idx)) / len(active_idx)
            else:
                sub_w = sub_w / denom

            if np.all(sub_w >= -1e-10):
                # All non-negative — project onto full space
                weights = np.zeros(n)
                for i, idx in enumerate(active_idx):
                    weights[idx] = max(0.0, sub_w[i])
                total = weights.sum()
                if total > 1e-12:
                    weights /= total
                return weights
            else:
                # Remove the most negative weight and retry
                worst = active_idx[np.argmin(sub_w)]
                mask[worst] = False

        # If we exhaust iterations, return equal weight on active
        active_idx = np.where(mask)[0]
        weights = np.zeros(n)
        if len(active_idx) > 0:
            weights[active_idx] = 1.0 / len(active_idx)
        else:
            weights = np.ones(n) / n
        return weights


# ---------------------------------------------------------------------------
# Model 4: Equal Risk Contribution
# ---------------------------------------------------------------------------

class EqualRiskContribution:
    """Equal Risk Contribution portfolio — each position contributes
    equally to total portfolio variance.

    Simpler than HRP (no clustering), simpler than MDP (no inverse-vol
    maximisation). Iteratively adjusts weights so that each asset's
    marginal risk contribution converges to 1/N of total risk.

    Legal: Simulation tool only. NOT investment advice.
    """

    @staticmethod
    def allocate(
        returns_matrix: np.ndarray,
        tickers: Optional[list[str]] = None,
    ) -> dict:
        """Run ERC allocation.

        Args:
            returns_matrix: (n_obs, n_assets) array of daily returns.
            tickers: optional list of ticker labels.

        Returns:
            dict with weights, method, disclaimer.
        """
        returns = np.asarray(returns_matrix, dtype=np.float64)
        n_obs, n_assets = returns.shape

        if n_assets < 2:
            return {"weights": None, "error": "Need at least 2 assets"}

        if tickers is None:
            tickers = [f"Asset_{i}" for i in range(n_assets)]

        cov = _covariance_matrix(returns)
        n = cov.shape[0]

        # Start with equal weights
        w = np.ones(n) / n

        # Iterative adjustment (30 iterations)
        for _ in range(30):
            marginal = cov @ w
            total_risk = np.sqrt(w @ cov @ w)
            target_risk = total_risk / n

            for i in range(n):
                if marginal[i] > 0:
                    w[i] = target_risk / marginal[i]

            w = np.maximum(w, 0)
            w_sum = np.sum(w)
            if w_sum > 1e-12:
                w /= w_sum
            else:
                # Bug NEW-C fix: near-singular covariance can collapse all
                # weights to zero, silently returning a degenerate (un-
                # investable) allocation. Fall back to equal weights and
                # warn so callers + log readers can spot the condition.
                logger.warning(
                    "ERC near-singular covariance; falling back to equal "
                    "weights (n=%d)",
                    n,
                )
                w = np.ones(n) / n

        return {
            "weights": {tickers[i]: round(float(w[i]), 6) for i in range(n_assets)},
            "tickers": tickers,
            "method": "Equal Risk Contribution",
            "disclaimer": DISCLAIMER,
        }


# ---------------------------------------------------------------------------
# Model 5: Minimum Variance Portfolio
# ---------------------------------------------------------------------------

class MinVariance:
    """Minimum Variance Portfolio — lowest possible portfolio volatility.

    Uses closed-form solution via inverse covariance matrix.
    Long-only constraint applied via non-negative projection.

    Reference:
        Markowitz, H. (1952). "Portfolio Selection."
        Journal of Finance 7(1), 77-91.

    Legal: Simulation tool only. NOT investment advice.
    """

    @staticmethod
    def allocate(
        returns_matrix: np.ndarray,
        tickers: Optional[list[str]] = None,
    ) -> dict:
        """Run Minimum Variance allocation.

        Args:
            returns_matrix: (n_obs, n_assets) array of daily returns.
            tickers: optional list of ticker labels.

        Returns:
            dict with weights, portfolio_vol (annualised %), method, disclaimer.
        """
        returns = np.asarray(returns_matrix, dtype=np.float64)
        n_obs, n_assets = returns.shape

        if n_assets < 2:
            return {"weights": None, "error": "Need at least 2 assets"}

        if tickers is None:
            tickers = [f"Asset_{i}" for i in range(n_assets)]

        cov = _covariance_matrix(returns)

        try:
            # Regularise slightly for numerical stability
            cov_inv = np.linalg.inv(cov + np.eye(cov.shape[0]) * 1e-8)
        except np.linalg.LinAlgError:
            return {"weights": None, "error": "Singular covariance matrix"}

        ones = np.ones(cov.shape[0])
        denom = ones @ cov_inv @ ones
        if abs(denom) < 1e-14:
            return {"weights": None, "error": "Degenerate covariance matrix"}

        w = cov_inv @ ones / denom

        # Long-only projection
        w = np.maximum(w, 0)
        w_sum = np.sum(w)
        if w_sum > 1e-12:
            w /= w_sum

        vol = float(np.sqrt(w @ cov @ w)) * np.sqrt(252) * 100

        return {
            "weights": {tickers[i]: round(float(w[i]), 6) for i in range(n_assets)},
            "portfolio_vol": round(vol, 2),
            "tickers": tickers,
            "method": "Minimum Variance Portfolio (Markowitz 1952)",
            "disclaimer": DISCLAIMER,
        }
