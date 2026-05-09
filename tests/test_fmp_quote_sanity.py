"""
PivoxQuant — FMP /quote sanity guard regression tests (2026-05-09)

Context: PR #189 follow-up. The single ``market_cap_drift`` invariant in
``_quote_price_sane`` was insufficient — when FMP's stale-drift bug bumps
``price``, ``sharesOutstanding`` AND ``marketCap`` together (observed on home
"Top Weight" panel as ``AAPL +877.73%``), the marketCap×shares cross-check
still passes and the insane payload poisons both ``batch_quote:*`` and
``quote:*`` caches.

Coverage:
  1. ``_quote_price_sane`` — five payload shape cases (sane, marketCap drift,
     yearHigh breach with co-drifted trio, yearLow breach, missing fields).
  2. ``get_quotes_batch`` batch path — partial-insane filtering (insane
     ticker excluded from result + per-ticker cache not poisoned).
  3. ``get_quotes_batch`` batch path — all-insane → falls through to
     per-ticker ``get_quote()`` fallback.
"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from services.data import fmp as fmp_service


# ── Helpers ──────────────────────────────────────────────────────────────────

def _clear_fmp_cache():
    with fmp_service._cache_lock:
        fmp_service._cache.clear()
        fmp_service._endpoint_402_counts.clear()
        fmp_service._endpoint_402_cooldown.clear()
    fmp_service._daily_calls = 0
    fmp_service._daily_calls_reset = time.time()


# ── 1. _quote_price_sane unit tests ──────────────────────────────────────────

class TestQuotePriceSane:
    """Direct unit tests for the sanity invariants."""

    def test_sane_payload_passes(self):
        """Healthy AAPL-like quote with all cross-check fields aligned."""
        quote = {
            "symbol": "AAPL",
            "price": 200.0,
            "yearHigh": 250.0,
            "yearLow": 180.0,
            "marketCap": 3_000_000_000_000,  # 3T
            "sharesOutstanding": 15_000_000_000,  # 15B → implied 3T ✓
        }
        assert fmp_service._quote_price_sane(quote) is True

    def test_market_cap_drift_rejected(self):
        """Regression: NFLX-style payload — price=92.27 vs 388.5B mc / 430M
        shares (implies ~$903/share). Existing guard must still fire."""
        quote = {
            "symbol": "NFLX",
            "price": 92.27,
            "marketCap": 388_500_000_000,
            "sharesOutstanding": 430_000_000,
        }
        assert fmp_service._quote_price_sane(quote) is False

    def test_year_high_breach_with_codrifted_trio_rejected(self):
        """The 2026-05-09 PR #189 case: price/shares/marketCap all stale-bumped
        together so price × shares ≈ marketCap (invariant 1 passes), but
        price > 2× yearHigh (invariant 2 fires).

        AAPL-style: actual yearHigh ~210, but FMP returned price=500 with
        shares and marketCap proportionally inflated so the cross-check
        passes. Without the yearHigh guard, this insane payload would slip
        through and surface as ``AAPL +877%`` on the home Top Weight panel.
        """
        price = 500.0
        shares = 15_000_000_000.0
        market_cap = price * shares  # exactly aligned → invariant 1 passes
        quote = {
            "symbol": "AAPL",
            "price": price,
            "yearHigh": 210.0,  # 500 / 210 = 2.38× → invariant 2 fires
            "yearLow": 180.0,
            "marketCap": market_cap,
            "sharesOutstanding": shares,
        }
        assert fmp_service._quote_price_sane(quote) is False

    def test_year_high_breach_below_threshold_passes(self):
        """Boundary check: price slightly below 2× yearHigh must still pass
        (false positive avoidance — split days can briefly look like 1.5×)."""
        quote = {
            "symbol": "AAPL",
            "price": 290.0,
            "yearHigh": 210.0,  # 290 / 210 = 1.38× — under 2.0× threshold
            "yearLow": 180.0,
        }
        assert fmp_service._quote_price_sane(quote) is True

    def test_year_low_breach_rejected(self):
        """Symmetric guard: price < yearLow × 0.2."""
        quote = {
            "symbol": "TSLA",
            "price": 10.0,
            "yearLow": 100.0,  # 10 / 100 = 0.10× — under 0.2× threshold
            "yearHigh": 150.0,
        }
        assert fmp_service._quote_price_sane(quote) is False

    def test_missing_fields_passes(self):
        """No yearHigh/yearLow/marketCap/shares → can't cross-check, must
        return True (no false negatives)."""
        quote = {"symbol": "OBSCURE", "price": 12.34}
        assert fmp_service._quote_price_sane(quote) is True

    def test_non_dict_passes(self):
        """Defensive: non-dict input must not crash."""
        assert fmp_service._quote_price_sane(None) is True  # type: ignore[arg-type]
        assert fmp_service._quote_price_sane("not a dict") is True  # type: ignore[arg-type]

    def test_zero_or_negative_fields_passes(self):
        """Garbage values (0, negative) must skip silently rather than crash
        or false-reject."""
        quote = {
            "symbol": "X",
            "price": 100.0,
            "yearHigh": 0,  # zero → skip
            "yearLow": -50,  # negative → skip
            "marketCap": 0,
            "sharesOutstanding": 0,
        }
        assert fmp_service._quote_price_sane(quote) is True

    def test_non_numeric_fields_passes(self):
        """String values (e.g. malformed FMP response) must not crash."""
        quote = {
            "symbol": "X",
            "price": "not-a-number",
            "yearHigh": "also-bad",
            "yearLow": None,
            "marketCap": "junk",
            "sharesOutstanding": "junk",
        }
        # price is non-numeric → all three invariants skip → True.
        assert fmp_service._quote_price_sane(quote) is True


# ── 2. get_quotes_batch — partial insane payload ────────────────────────────

class TestGetQuotesBatchSanityFilter:
    def setup_method(self):
        _clear_fmp_cache()

    def test_partial_insane_filtered_from_batch(self):
        """3 tickers: AAPL sane, NFLX insane (marketCap drift), TSLA sane.
        Result must contain only AAPL + TSLA, and NFLX per-ticker cache
        must NOT be poisoned."""
        sane_aapl = {
            "symbol": "AAPL",
            "price": 200.0,
            "yearHigh": 250.0,
            "yearLow": 180.0,
            "marketCap": 3_000_000_000_000,
            "sharesOutstanding": 15_000_000_000,
        }
        insane_nflx = {
            "symbol": "NFLX",
            "price": 92.27,
            "marketCap": 388_500_000_000,
            "sharesOutstanding": 430_000_000,  # implied 39.7B vs 388.5B — drift
        }
        sane_tsla = {
            "symbol": "TSLA",
            "price": 240.0,
            "yearHigh": 300.0,
            "yearLow": 150.0,
            "marketCap": 760_000_000_000,
            "sharesOutstanding": 3_170_000_000,  # implied 760.8B ≈ 760B ✓
        }

        def fake_fmp_get(endpoint, params=None, timeout=5):
            return [sane_aapl, insane_nflx, sane_tsla]

        with patch.object(fmp_service, "_fmp_get", side_effect=fake_fmp_get):
            out = fmp_service.get_quotes_batch(["AAPL", "NFLX", "TSLA"])

        assert "AAPL" in out, f"AAPL missing from batch result: {out.keys()}"
        assert "TSLA" in out, f"TSLA missing from batch result: {out.keys()}"
        assert "NFLX" not in out, (
            f"NFLX (insane) must be filtered out, got: {out.keys()}"
        )

        # Per-ticker quote cache: AAPL/TSLA must be present, NFLX must NOT be.
        aapl_cached = fmp_service._get_cache("quote:AAPL", fmp_service._quote_ttl())
        tsla_cached = fmp_service._get_cache("quote:TSLA", fmp_service._quote_ttl())
        nflx_cached = fmp_service._get_cache("quote:NFLX", fmp_service._quote_ttl())

        assert aapl_cached is not None, "AAPL per-ticker cache must be populated"
        assert tsla_cached is not None, "TSLA per-ticker cache must be populated"
        assert nflx_cached is None, (
            "NFLX per-ticker cache must NOT be populated (insane payload)"
        )

    def test_all_insane_falls_through_to_per_ticker(self):
        """All 3 batch items insane → must NOT cache batch result; must fall
        through to per-ticker get_quote() fallback loop."""
        insane_a = {
            "symbol": "AAA",
            "price": 1.0,
            "marketCap": 1_000_000_000_000,
            "sharesOutstanding": 1_000,  # implied 1k vs 1T → drift
        }
        insane_b = {
            "symbol": "BBB",
            "price": 1.0,
            "marketCap": 1_000_000_000_000,
            "sharesOutstanding": 1_000,
        }

        # Track that get_quote() was invoked per-ticker as fallback.
        get_quote_calls = []

        def fake_fmp_get(endpoint, params=None, timeout=5):
            sym = (params or {}).get("symbol", "")
            if "," in sym:
                # Batch call → return all-insane payload.
                return [insane_a, insane_b]
            return []  # single-ticker: empty (Alpaca patched to None below)

        def fake_get_quote(ticker):
            get_quote_calls.append(ticker)
            return None  # simulate Alpaca-also-empty

        with patch.object(fmp_service, "_fmp_get", side_effect=fake_fmp_get), \
             patch.object(fmp_service, "get_quote", side_effect=fake_get_quote), \
             patch.object(fmp_service, "_ama", return_value=None):
            out = fmp_service.get_quotes_batch(["AAA", "BBB"])

        # Batch all-insane → empty result.
        assert out == {}, f"all-insane batch must return {{}}, got: {out}"

        # Per-ticker fallback must have fired for each ticker.
        assert get_quote_calls == ["AAA", "BBB"], (
            f"per-ticker fallback expected for both tickers, got: {get_quote_calls}"
        )

        # batch_quote:* cache must NOT be populated.
        batch_cached = fmp_service._get_cache(
            "batch_quote:AAA,BBB", fmp_service._quote_ttl()
        )
        assert batch_cached is None, (
            "all-insane batch must not populate batch_quote cache"
        )
        # Per-ticker insane caches must also not be populated.
        assert fmp_service._get_cache(
            "quote:AAA", fmp_service._quote_ttl()
        ) is None
        assert fmp_service._get_cache(
            "quote:BBB", fmp_service._quote_ttl()
        ) is None
