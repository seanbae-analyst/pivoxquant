"""Regression tests for B-01 — counterfactual 5y+ ticker resolution.

Symptom (pre-fix): a >5-year window (e.g. NVDA + 2020-03-23) hit FMP's
`/historical-price-eod/full` with a single from/to spanning >5 years.
On FMP Starter tier this commonly returned an empty payload, the route's
fallback `fetcher.get_price_history(ticker, period="5y")` *also* hit
endpoint cooldown and returned an empty DataFrame, and the route then
emitted a misleading 404 ``TICKER_NOT_FOUND`` for a perfectly valid ticker.

Fix: `_fetch_history_long` now SPLITS the long range into ≤5-year chunks
and concatenates results, working around the FMP Starter window limit
without a plan upgrade.

These tests:
1. Verify chunked-FMP path is taken for >5y windows AND multiple
   `_fmp_get` calls are issued.
2. Verify ≤5y windows still take the single fetcher path (no regression).
3. Verify the fetched DataFrame is properly merged + sorted + dedup'd
   across chunk boundaries.
4. Verify the 5y fallback still triggers when ALL FMP chunks fail.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd

from routes.counterfactual import _fetch_history_long


# ── Helpers ─────────────────────────────────────────────────────────────────

def _fake_fmp_payload(start: date, end: date, base_price: float = 100.0) -> dict:
    """Build a fake FMP `/historical-price-eod/full` response covering
    [start, end] inclusive, daily."""
    rows = []
    cur = start
    n = 0
    while cur <= end:
        rows.append({
            "date": cur.strftime("%Y-%m-%d"),
            "open": base_price + n * 0.1,
            "high": base_price + n * 0.1 + 0.5,
            "low": base_price + n * 0.1 - 0.5,
            "close": base_price + n * 0.1,
            "adjClose": base_price + n * 0.1,
            "volume": 1_000_000,
        })
        cur += timedelta(days=1)
        n += 1
    return {"historical": rows}


# ── Tests ───────────────────────────────────────────────────────────────────

class TestFetchHistoryLongChunking:
    """B-01: 5y+ windows must split into ≤5y chunks (not a single >5y call)."""

    def test_under_5y_takes_single_fetcher_path_no_regression(self):
        """≤5y window must NOT touch the long-path FMP code at all."""
        fake_df = pd.DataFrame(
            {"Open": [1.0], "High": [1.0], "Low": [1.0],
             "Close": [1.0], "Volume": [1]},
            index=pd.to_datetime(["2024-01-01"]),
        )
        mock_fetcher = MagicMock()
        mock_fetcher.get_price_history.return_value = fake_df

        # Mock the *bound* import in the function body. _fetch_history_long
        # does `from services.container import fetcher` at call time, so we
        # patch the source module.
        with patch("services.container.fetcher", mock_fetcher), \
             patch("services.data.fmp._fmp_get") as mock_fmp:
            start = date.today() - timedelta(days=365 * 3)  # 3 years ago
            result = _fetch_history_long("AAPL", start)

        assert result is fake_df
        mock_fetcher.get_price_history.assert_called_once()
        # Long-path FMP must NOT be called for ≤5y windows.
        mock_fmp.assert_not_called()

    def test_8y_window_issues_multiple_chunked_fmp_calls(self):
        """8-year window → at least 2 ≤5y chunks → at least 2 FMP calls."""
        today = date.today()
        start = today - timedelta(days=365 * 8)  # 8 years ago

        # Each call returns a non-empty payload so the merge path runs.
        def _side(endpoint, params=None, timeout=5):
            assert endpoint == "/historical-price-eod/full"
            from_d = date.fromisoformat(params["from"])
            to_d = date.fromisoformat(params["to"])
            # Window must be ≤ 5 years
            assert (to_d - from_d).days <= 365 * 5 + 1, \
                f"chunk {from_d}→{to_d} exceeds 5y limit"
            return _fake_fmp_payload(from_d, to_d)

        mock_fetcher = MagicMock()
        with patch("services.container.fetcher", mock_fetcher), \
             patch("services.data.fmp._fmp_get", side_effect=_side) as mock_fmp:
            result = _fetch_history_long("NVDA", start)

        # At least 2 chunks for an 8-year span.
        assert mock_fmp.call_count >= 2, \
            f"expected ≥2 chunked calls, got {mock_fmp.call_count}"
        # 5y-fallback must NOT have been called (chunks succeeded).
        mock_fetcher.get_price_history.assert_not_called()

        # Result is a non-empty, date-indexed, sorted DataFrame.
        assert result is not None
        assert not result.empty
        assert "Close" in result.columns
        # Sorted ascending
        idx = result.index
        assert (idx[:-1] <= idx[1:]).all()

    def test_chunks_concat_no_duplicate_dates(self):
        """Boundary dates between chunks must not produce duplicate rows."""
        today = date.today()
        start = today - timedelta(days=365 * 7)

        def _side(endpoint, params=None, timeout=5):
            from_d = date.fromisoformat(params["from"])
            to_d = date.fromisoformat(params["to"])
            return _fake_fmp_payload(from_d, to_d)

        mock_fetcher = MagicMock()
        with patch("services.container.fetcher", mock_fetcher), \
             patch("services.data.fmp._fmp_get", side_effect=_side):
            result = _fetch_history_long("NVDA", start)

        assert result is not None and not result.empty
        # Index should be unique (dedup'd)
        assert result.index.is_unique, \
            "duplicate dates in concatenated chunks — dedup logic broke"

    def test_all_chunks_fail_falls_back_to_5y(self):
        """If FMP returns None for every chunk, fall back to fetcher 5y."""
        today = date.today()
        start = today - timedelta(days=365 * 8)

        fallback_df = pd.DataFrame(
            {"Open": [1.0], "High": [1.0], "Low": [1.0],
             "Close": [50.0], "Volume": [1]},
            index=pd.to_datetime(["2024-01-01"]),
        )
        mock_fetcher = MagicMock()
        mock_fetcher.get_price_history.return_value = fallback_df

        with patch("services.container.fetcher", mock_fetcher), \
             patch("services.data.fmp._fmp_get", return_value=None) as mock_fmp:
            result = _fetch_history_long("NVDA", start)

        # All chunks attempted, all failed
        assert mock_fmp.call_count >= 2
        # 5y fallback was used
        mock_fetcher.get_price_history.assert_called_once_with(
            "NVDA", period="5y"
        )
        assert result is fallback_df

    def test_partial_chunk_failure_uses_what_succeeded(self):
        """If only some chunks succeed, we still merge what we got
        rather than falling back to the (much shorter) 5y path."""
        today = date.today()
        start = today - timedelta(days=365 * 8)

        call_log: list[tuple[str, str]] = []

        def _side(endpoint, params=None, timeout=5):
            call_log.append((params["from"], params["to"]))
            # First chunk fails, rest succeed.
            if len(call_log) == 1:
                return None
            from_d = date.fromisoformat(params["from"])
            to_d = date.fromisoformat(params["to"])
            return _fake_fmp_payload(from_d, to_d)

        mock_fetcher = MagicMock()
        with patch("services.container.fetcher", mock_fetcher), \
             patch("services.data.fmp._fmp_get", side_effect=_side):
            result = _fetch_history_long("NVDA", start)

        # 5y fallback NOT called — at least one chunk worked.
        mock_fetcher.get_price_history.assert_not_called()
        assert result is not None
        assert not result.empty
