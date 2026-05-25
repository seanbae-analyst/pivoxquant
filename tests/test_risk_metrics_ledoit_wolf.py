"""tests/test_risk_metrics_ledoit_wolf.py — FIX B (2026-05-25).

``LedoitWolfShrinkage.estimate`` divided the b_bar^2 estimation-error term by
``n * (n - 1)`` instead of ``n``. The summed term
``np.sum(X2.T @ X2 / n - S**2)`` is exactly the LW 2004 pi-hat, and the
optimal identity-target intensity is ``alpha = pi-hat / (n * gamma)`` where
gamma == d_bar_sq. Since the code forms ``alpha = b_bar_sq / d_bar_sq``,
b_bar_sq must be ``pi-hat / n``. The old ``n * (n - 1)`` divisor understated
it by ~n×, collapsing shrinkage_intensity to ≈0 (no shrinkage at all).

Ground truth: sklearn.covariance.LedoitWolf().shrinkage_ (identity target).
Across 20 seed/shape combinations the divisor ``n`` matches sklearn to 4
decimals (max abs diff 0.0000); ``n - 1`` is within 0.0012. We adopt ``n`` —
the exact LW 2004 definition and the exact sklearn match.

These tests run a self-contained canonical-LW reference (no external deps)
and, when scikit-learn is available, cross-check against sklearn directly.
"""
from __future__ import annotations

import numpy as np
import pytest

from services.quant.risk_metrics import LedoitWolfShrinkage


def _canonical_lw_alpha(X: np.ndarray) -> float:
    """Reference LW 2004 shrinkage intensity for the scaled-identity target.

    Self-contained (numpy only). alpha = clip(pi_hat / (n * gamma), 0, 1)
    with rho = 0 for the scaled-identity target.
    """
    n, p = X.shape
    Xc = X - X.mean(axis=0)
    S = Xc.T @ Xc / n
    mu = np.trace(S) / p
    F = mu * np.eye(p)
    gamma = float(np.sum((S - F) ** 2))
    # pi_hat = sum_ij mean_t (x_it x_jt - s_ij)^2
    #        = mean_t (||x_t||^2)^2 - sum_ij s_ij^2
    X2 = Xc ** 2
    pi_hat = float(np.mean(np.sum(X2, axis=1) ** 2) - np.sum(S ** 2))
    if gamma == 0:
        return 1.0
    return float(min(max(pi_hat / (n * gamma), 0.0), 1.0))


def _correlated_data(seed: int, n: int, p: int) -> np.ndarray:
    """Two-factor model so the optimal shrinkage is interior to (0, 1)."""
    rng = np.random.RandomState(seed)
    factors = rng.randn(n, 2)
    loadings = rng.randn(2, p)
    return factors @ loadings + 0.5 * rng.randn(n, p)


SHAPES = [(120, 6), (60, 10), (250, 4), (80, 8)]
SEEDS = [0, 1, 2, 3, 4]


class TestLedoitWolfAgainstCanonical:
    @pytest.mark.parametrize("seed", SEEDS)
    @pytest.mark.parametrize("shape", SHAPES)
    def test_matches_canonical_lw(self, seed, shape):
        n, p = shape
        X = _correlated_data(seed, n, p)
        out = LedoitWolfShrinkage.estimate(X)
        expected = round(_canonical_lw_alpha(X), 4)
        got = out["shrinkage_intensity"]
        assert abs(got - expected) < 1e-4, (
            f"shape={shape} seed={seed}: got {got}, canonical {expected}"
        )

    def test_correlated_data_has_meaningful_shrinkage(self):
        # Regression guard: the old n*(n-1) divisor collapsed alpha to ~0.
        # With a genuine factor structure alpha must be materially > 0.
        X = _correlated_data(0, 120, 6)
        out = LedoitWolfShrinkage.estimate(X)
        assert out["shrinkage_intensity"] > 0.01

    def test_iid_normal_high_shrinkage(self):
        # True covariance ≈ identity → LW shrinks heavily toward the target.
        X = np.random.RandomState(0).randn(120, 6)
        out = LedoitWolfShrinkage.estimate(X)
        assert out["shrinkage_intensity"] > 0.5

    def test_shrunk_cov_is_convex_combination(self):
        X = _correlated_data(1, 100, 5)
        out = LedoitWolfShrinkage.estimate(X)
        alpha = out["shrinkage_intensity"]
        S = out["sample_cov"]
        mu = out["target_variance"]
        F = mu * np.eye(S.shape[0])
        # shrinkage_intensity in the dict is rounded to 4 decimals, so the
        # reconstruction carries that rounding error — assert structural
        # convexity rather than bit-exactness.
        expected = (1 - alpha) * S + alpha * F
        assert np.allclose(out["shrunk_cov"], expected, rtol=1e-3, atol=1e-3)

    def test_intensity_in_unit_interval(self):
        for seed in SEEDS:
            for shape in SHAPES:
                out = LedoitWolfShrinkage.estimate(_correlated_data(seed, *shape))
                a = out["shrinkage_intensity"]
                assert 0.0 <= a <= 1.0


class TestLedoitWolfAgainstSklearn:
    @pytest.mark.parametrize("seed", SEEDS)
    @pytest.mark.parametrize("shape", SHAPES)
    def test_matches_sklearn_shrinkage(self, seed, shape):
        sklearn_cov = pytest.importorskip("sklearn.covariance")
        n, p = shape
        X = _correlated_data(seed, n, p)
        sk_alpha = sklearn_cov.LedoitWolf(assume_centered=False).fit(X).shrinkage_
        got = LedoitWolfShrinkage.estimate(X)["shrinkage_intensity"]
        # Tolerance per spec: abs diff < 0.05. Divisor `n` actually matches
        # sklearn to ~1e-4, so this is comfortable.
        assert abs(got - sk_alpha) < 0.05, (
            f"shape={shape} seed={seed}: code {got} vs sklearn {sk_alpha:.4f}"
        )
