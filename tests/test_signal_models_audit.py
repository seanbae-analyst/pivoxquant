"""
PivoxQuant — Wave D-2 behavior signal models audit regression tests.

Created 2026-05-17. Covers three findings from the behavior_models audit:

  F1 — engine.py SentimentPriceDivergence dead-code disable.
       Engine previously fed a constant `[news_score] * window_len` array,
       guaranteeing `sent_roc == 0` and `divergence_type == 'neutral'`. The
       ±10 score branch could never fire. This test confirms the engine
       does NOT call the model anymore and that the placeholder shape is
       preserved for downstream consumers.

  F2 — HerdingIntensity zero-variance market guard.
       When the market series has near-zero standard deviation,
       `2 * mkt_std ≈ 0` flagged every day as 'extreme', making
       `csad_during_normal` the mean of an empty slice (NaN +
       RuntimeWarning) and the ratio collapsed to 1.0. Now guarded so the
       fallback `0.01` constant the original code intended actually fires.

  F3 — NaN leak in DispositionEffect / OrderFlowImbalance / AnchoringBias.
       Partial-data rows (None / NaN volume from yfinance / KIS) became
       np.float64 NaN and propagated through sum / max / division. The
       cached payload then failed `json.dumps(..., allow_nan=False)` in
       cache_service.save_signal. Now those rows are filtered before any
       arithmetic and an explicit-None result is returned when too few
       finite rows remain.

Run:
    cd pivoxquant && python3 -m pytest tests/test_signal_models_audit.py -v
"""

import importlib.util
import json
import math
import os
import sys

import numpy as np
import pytest

# Direct import of the module to avoid pulling the whole services.quant
# package (which transitively imports Flask). All audit findings live in
# pure-numpy code so this is sufficient.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIGNALS_PATH = os.path.join(PROJECT_ROOT, "services", "quant", "signals.py")

spec = importlib.util.spec_from_file_location("signals_under_audit", SIGNALS_PATH)
signals_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signals_mod)

DispositionEffect = signals_mod.DispositionEffect
HerdingIntensity = signals_mod.HerdingIntensity
SentimentPriceDivergence = signals_mod.SentimentPriceDivergence
OrderFlowImbalance = signals_mod.OrderFlowImbalance
AnchoringBias = signals_mod.AnchoringBias


# ──────────────────────────────────────────────────────────────────────
# F2 — HerdingIntensity zero-variance market guard
# ──────────────────────────────────────────────────────────────────────

class TestHerdingZeroVarianceGuard:
    """Wave D-2 F2: mkt_std == 0 must hit the fallback path."""

    def test_constant_market_does_not_flag_all_days_extreme(self):
        """With a perfectly constant market, NO day should be 'extreme'."""
        # 60 days of constant 0.01 returns → np.std == 0 → 2*std == 0
        # Pre-fix: |0.01| > 0 → True for ALL 60 days
        mkt = [0.01] * 60
        sr = [[0.01] * 60 for _ in range(5)]
        r = HerdingIntensity.calculate(sr, mkt)
        assert r["extreme_days_in_window"] == 0, (
            f"Expected 0 extreme days for constant market, got "
            f"{r['extreme_days_in_window']} (zero-variance fallback failed)"
        )

    def test_constant_market_returns_csad_zero(self):
        """All stocks perfectly tracking constant market → CSAD = 0."""
        mkt = [0.01] * 60
        sr = [[0.01] * 60 for _ in range(3)]
        r = HerdingIntensity.calculate(sr, mkt)
        assert r["csad"] == 0.0
        # herding_ratio falls back to 1.0 because extreme_count < 3
        assert r["herding_ratio"] == 1.0
        # No NaN/Inf leak in any numeric field
        for k, v in r.items():
            if isinstance(v, float):
                assert math.isfinite(v) or v == 0.0, f"non-finite {k}={v}"

    def test_floating_point_noise_std_treated_as_zero(self):
        """np.std on identical floats can return ~1e-18 noise — still zero."""
        mkt = [0.005] * 60  # identical → std == numerical noise
        sr = [[0.005] * 60 for _ in range(4)]
        r = HerdingIntensity.calculate(sr, mkt)
        # Pre-fix: float noise std → 2 * 1e-18 ≈ 0 → all 60 days extreme
        assert r["extreme_days_in_window"] < 60, (
            "Float-noise std must fall back to 0.01, not flag all days"
        )


# ──────────────────────────────────────────────────────────────────────
# F3 — NaN leak guards (Disposition / OFI / Anchoring)
# ──────────────────────────────────────────────────────────────────────

class TestNaNLeakGuards:
    """Wave D-2 F3: None / NaN in OHLCV rows must not leak into the result."""

    def test_disposition_with_none_volumes_returns_explicit_none(self):
        """All-None volumes → explicit None result, not NaN."""
        closes = [100.0] * 25
        vols = [None] * 25
        r = DispositionEffect.calculate(closes, vols)
        assert r["cgo"] is None
        # No NaN must surface — explicit None is the only legal sentinel
        for v in r.values():
            assert not (isinstance(v, float) and math.isnan(v)), \
                f"NaN leaked into DispositionEffect output: {r}"

    def test_disposition_with_partial_nan_volumes_filters_and_computes(self):
        """A few NaN rows → filter them and produce a valid cgo."""
        np.random.seed(42)
        closes = list(100 + np.cumsum(np.random.randn(60) * 0.5))
        vols = [1e6] * 60
        # inject NaN at random positions
        for i in [5, 17, 33, 41]:
            vols[i] = float("nan")
        r = DispositionEffect.calculate(closes, vols)
        # cgo must be a real number, not NaN
        assert r["cgo"] is not None
        assert math.isfinite(r["cgo"]), f"cgo NaN despite filter: {r}"

    def test_disposition_output_survives_json_allow_nan_false(self):
        """The whole cache write boundary uses allow_nan=False."""
        closes = [100.0] * 25
        vols = [None] * 25  # all-None → explicit None branch
        r = DispositionEffect.calculate(closes, vols)
        # Replace None with json-serialisable null (cache does this too)
        # The critical contract: no NaN survives to json.dumps
        try:
            json.dumps(r, allow_nan=False)
        except ValueError as e:
            pytest.fail(f"json.dumps(allow_nan=False) failed: {e}")

    def test_ofi_with_none_volumes_returns_explicit_error(self):
        """All-None volumes → insufficient-data error, no NaN cumulative."""
        opens = [10.0] * 10
        closes = [11.0] * 10
        vols = [None] * 10
        r = OrderFlowImbalance.calculate(opens, closes, vols)
        # After finite-filter the array is empty → MIN_WINDOW guard fires
        assert r["ofi_cumulative"] is None
        for v in r.values():
            assert not (isinstance(v, float) and math.isnan(v)), \
                f"NaN leaked into OFI output: {r}"

    def test_ofi_partial_nan_filters_and_computes(self):
        """Mixed valid + NaN rows → filter and compute a clean OFI."""
        opens = [100.0 + i for i in range(20)]
        closes = [101.0 + i for i in range(20)]
        vols = [1e6] * 20
        vols[3] = float("nan")
        vols[11] = float("nan")
        r = OrderFlowImbalance.calculate(opens, closes, vols)
        assert r["ofi_cumulative"] is not None
        assert math.isfinite(r["ofi_cumulative"])
        json.dumps(r, allow_nan=False)  # contract: must serialise

    def test_anchoring_with_nan_inputs_does_not_leak(self):
        """AnchoringBias with NaN rows → either filter or explicit None."""
        closes = [100.0 + i * 0.1 for i in range(100)]
        vols = [1e6] * 100
        closes[10] = float("nan")
        vols[20] = float("nan")
        r = AnchoringBias.calculate(closes, vols)
        # Either it filtered enough rows to compute, OR returned explicit None
        if r.get("nearness") is not None:
            for v in r.values():
                assert not (isinstance(v, float) and math.isnan(v)), \
                    f"NaN leaked into Anchoring output: {r}"
            json.dumps(r, allow_nan=False)


# ──────────────────────────────────────────────────────────────────────
# F1 — engine.py SentimentPriceDivergence dead-code disable
# ──────────────────────────────────────────────────────────────────────

class TestEngineSPDDisabled:
    """Wave D-2 F1: engine no longer calls SPD with a constant array."""

    def test_constant_sentiment_yields_zero_roc_baseline(self):
        """The model itself still computes correctly — bug was at caller."""
        closes = [100 + i * 0.5 for i in range(30)]
        sentiment = [50.0] * 30  # the exact pattern engine USED to pass
        r = SentimentPriceDivergence.calculate(closes, sentiment)
        # Verify the dead-code reality: sent_roc is always 0 with constant
        assert r["sentiment_roc"] == 0.0
        assert r["divergence_type"] == "neutral"
        assert r["divergence_score"] == 0.0

    def test_engine_no_longer_imports_spd(self):
        """Grep guard: SentimentPriceDivergence symbol not at engine top."""
        engine_path = os.path.join(
            PROJECT_ROOT, "services", "quant", "engine.py"
        )
        with open(engine_path, encoding="utf-8") as f:
            src = f.read()
        # The import line must no longer pull SPD as an active symbol.
        # We accept the symbol appearing inside a comment (Wave D-2 marker).
        import_lines = [
            l for l in src.splitlines()
            if l.startswith("from services.quant.signals import")
        ]
        for line in import_lines:
            # Strip comment then check imported names
            code = line.split("#", 1)[0]
            assert "SentimentPriceDivergence" not in code, (
                f"engine.py still actively imports SPD: {line}"
            )

    def test_engine_spd_placeholder_shape_preserved(self):
        """Downstream tuple unpacking still works — spd_result has
        divergence_type and divergence_score keys."""
        engine_path = os.path.join(
            PROJECT_ROOT, "services", "quant", "engine.py"
        )
        with open(engine_path, encoding="utf-8") as f:
            src = f.read()
        # The placeholder dict must contain the two keys downstream expects
        assert "\"divergence_type\": \"none\"" in src
        assert "\"divergence_score\": None" in src
        assert "\"skipped_reason\"" in src, (
            "Skipped_reason marker missing — please document the disable"
        )
