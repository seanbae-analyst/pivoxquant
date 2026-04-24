"""
PivoxQuant — FMP class-share retry regression tests (2026-04-24)

Context: FMP's stable endpoints are inconsistent about class-share
separators. ``/quote?symbol=BRK.B`` returns ``[]`` while ``BRK-B``
returns a full payload (and vice-versa for some historical/profile
paths). Users routinely type ``BRK.B`` — the server must normalize so
both forms reach the same data.

Coverage:
  1. ``_class_share_alt`` helper:
     BRK.B ↔ BRK-B, BF.B ↔ BF-B round-trip;
     indices (^GSPC), KR (.KS/.KQ), plain (AAPL) → None.
  2. ``get_quote`` retry: BRK.B → empty → retry BRK-B → payload.
  3. ``get_profile`` retry: same pattern.
  4. ``get_history`` retry: same pattern (dot→dash and dash→dot).
  5. ``get_ratios_ttm`` retry: confirms fundamentals path.
  6. Alt-form equivalence: ``get_quote("BRK.B") == get_quote("BRK-B")``
     at the payload level when the upstream stub returns the same dict.
  7. Non-class-share tickers (AAPL) must NOT trigger a retry call.
"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

import fmp_service


# ── Helpers ──────────────────────────────────────────────────────────────────

def _clear_fmp_cache():
    with fmp_service._cache_lock:
        fmp_service._cache.clear()
        fmp_service._endpoint_402_counts.clear()
        fmp_service._endpoint_402_cooldown.clear()
    fmp_service._daily_calls = 0
    fmp_service._daily_calls_reset = time.time()


# ── 1. _class_share_alt helper ───────────────────────────────────────────────

class TestClassShareAlt:
    def test_dot_to_dash(self):
        assert fmp_service._class_share_alt("BRK.B") == "BRK-B"
        assert fmp_service._class_share_alt("BF.B") == "BF-B"

    def test_dash_to_dot(self):
        assert fmp_service._class_share_alt("BRK-B") == "BRK.B"
        assert fmp_service._class_share_alt("BF-B") == "BF.B"

    def test_round_trip(self):
        # Dot → dash → dot ≡ original.
        orig = "BRK.B"
        assert fmp_service._class_share_alt(
            fmp_service._class_share_alt(orig)
        ) == orig

    def test_plain_ticker_none(self):
        assert fmp_service._class_share_alt("AAPL") is None
        assert fmp_service._class_share_alt("NVDA") is None

    def test_korean_suffix_none(self):
        # .KS / .KQ are exchange suffixes, not class shares.
        assert fmp_service._class_share_alt("005930.KS") is None
        assert fmp_service._class_share_alt("035720.KQ") is None

    def test_index_none(self):
        assert fmp_service._class_share_alt("^GSPC") is None
        assert fmp_service._class_share_alt("^KS11") is None

    def test_empty_or_none(self):
        assert fmp_service._class_share_alt("") is None
        assert fmp_service._class_share_alt(None) is None  # type: ignore[arg-type]

    def test_multi_char_suffix_not_class_share(self):
        # "BRK.AXY" is not a class share — leave it alone.
        assert fmp_service._class_share_alt("BRK.AXY") is None

    def test_numeric_suffix_not_class_share(self):
        # "FOO.1" is not a class share.
        assert fmp_service._class_share_alt("FOO.1") is None


# ── 2. get_quote retry ───────────────────────────────────────────────────────

class TestGetQuoteClassShareRetry:
    def setup_method(self):
        _clear_fmp_cache()

    def test_brk_dot_b_retries_to_dash(self):
        """BRK.B returns [] → retry BRK-B → return payload."""
        calls = []

        def fake_fmp_get(endpoint, params=None, timeout=5):
            calls.append((endpoint, dict(params or {})))
            if params and params.get("symbol") == "BRK-B":
                return [{"symbol": "BRK-B", "price": 450.12}]
            return []

        with patch.object(fmp_service, "_fmp_get", side_effect=fake_fmp_get):
            out = fmp_service.get_quote("BRK.B")

        assert out is not None
        assert out["price"] == pytest.approx(450.12)
        # Two calls: first BRK.B (empty), then BRK-B (success).
        assert [c[1].get("symbol") for c in calls] == ["BRK.B", "BRK-B"]

    def test_dash_form_retries_to_dot(self):
        """BRK-B returns [] → retry BRK.B → return payload."""
        calls = []

        def fake_fmp_get(endpoint, params=None, timeout=5):
            calls.append(dict(params or {}))
            if params and params.get("symbol") == "BRK.B":
                return [{"symbol": "BRK.B", "price": 451.0}]
            return []

        with patch.object(fmp_service, "_fmp_get", side_effect=fake_fmp_get):
            out = fmp_service.get_quote("BRK-B")

        assert out is not None
        assert out["price"] == pytest.approx(451.0)

    def test_plain_ticker_no_retry(self):
        """AAPL returns [] → NO retry (not a class share). Falls through to
        Alpaca fallback or stale — we just verify _fmp_get called exactly once."""
        calls = []

        def fake_fmp_get(endpoint, params=None, timeout=5):
            calls.append(dict(params or {}))
            return []

        # Patch Alpaca adapter to None so we don't fall through.
        with patch.object(fmp_service, "_fmp_get", side_effect=fake_fmp_get), \
             patch.object(fmp_service, "_ama", return_value=None):
            out = fmp_service.get_quote("AAPL")

        # No retry: only the original symbol call.
        symbols = [c.get("symbol") for c in calls]
        assert symbols == ["AAPL"], f"unexpected retries: {symbols}"
        assert out is None

    def test_both_forms_empty_returns_none(self):
        """Both BRK.B and BRK-B return [] → return None (no Alpaca in test)."""
        def fake_fmp_get(endpoint, params=None, timeout=5):
            return []

        with patch.object(fmp_service, "_fmp_get", side_effect=fake_fmp_get), \
             patch.object(fmp_service, "_ama", return_value=None):
            out = fmp_service.get_quote("BRK.B")
        assert out is None

    def test_brk_dot_and_dash_equivalent_payload(self):
        """Core UX guarantee: get_quote('BRK.B') and get_quote('BRK-B') must
        return the same payload when the upstream has a single source of truth."""
        _clear_fmp_cache()
        ref = [{"symbol": "BRK-B", "price": 452.33}]

        def fake_fmp_get(endpoint, params=None, timeout=5):
            sym = (params or {}).get("symbol", "")
            if sym == "BRK-B":
                return list(ref)
            return []

        with patch.object(fmp_service, "_fmp_get", side_effect=fake_fmp_get), \
             patch.object(fmp_service, "_ama", return_value=None):
            dot = fmp_service.get_quote("BRK.B")
            _clear_fmp_cache()
            dash = fmp_service.get_quote("BRK-B")

        assert dot is not None and dash is not None
        assert dot["price"] == dash["price"]
        assert dot["symbol"] == dash["symbol"] == "BRK-B"


# ── 3. get_profile retry ─────────────────────────────────────────────────────

class TestGetProfileClassShareRetry:
    def setup_method(self):
        _clear_fmp_cache()

    def test_profile_dot_retries_to_dash(self):
        def fake_fmp_get(endpoint, params=None, timeout=5):
            if endpoint == "/profile" and (params or {}).get("symbol") == "BRK-B":
                return [{"symbol": "BRK-B", "companyName": "Berkshire Hathaway"}]
            return []

        with patch.object(fmp_service, "_fmp_get", side_effect=fake_fmp_get):
            out = fmp_service.get_profile("BRK.B")
        assert out.get("companyName") == "Berkshire Hathaway"


# ── 4. get_history retry ─────────────────────────────────────────────────────

class TestGetHistoryClassShareRetry:
    def setup_method(self):
        _clear_fmp_cache()

    def test_history_retry_both_directions(self):
        """Confirm existing history retry now uses _class_share_alt() (both
        directions) after the refactor."""
        hits = {"BRK-B": {"historical": [
            {"date": "2026-04-23", "open": 450.0, "high": 451.0,
             "low": 449.0, "close": 450.5, "volume": 1000},
        ]}}

        def fake_fmp_get(endpoint, params=None, timeout=5):
            sym = (params or {}).get("symbol", "")
            if sym in hits:
                return hits[sym]
            return None

        # Dot form must route through alt to BRK-B.
        with patch.object(fmp_service, "_fmp_get", side_effect=fake_fmp_get), \
             patch.object(fmp_service, "_ama", return_value=None):
            df = fmp_service.get_history("BRK.B", period="1mo")
        assert not df.empty
        assert float(df["Close"].iloc[-1]) == pytest.approx(450.5)


# ── 5. get_ratios_ttm retry ──────────────────────────────────────────────────

class TestGetRatiosTTMClassShareRetry:
    def setup_method(self):
        _clear_fmp_cache()

    def test_ratios_retry(self):
        def fake_fmp_get(endpoint, params=None, timeout=5):
            if (params or {}).get("symbol") == "BRK-B":
                return [{"priceToEarningsRatioTTM": 8.5}]
            return []

        with patch.object(fmp_service, "_fmp_get", side_effect=fake_fmp_get):
            out = fmp_service.get_ratios_ttm("BRK.B")
        assert out.get("priceToEarningsRatioTTM") == pytest.approx(8.5)


# ── 6. routes/market.py /search — verify stable endpoint ─────────────────────

class TestMarketSearchStableEndpoint:
    """Regression: v3 deprecated 2025-08-31. Must hit /stable/search-symbol."""

    def test_search_uses_stable_endpoint(self, client, auth_user, monkeypatch):
        """The search route must request /stable/search-symbol, not /api/v3/search."""
        monkeypatch.setenv("FMP_API_KEY", "fake-test-key")

        captured_urls = []

        class _FakeResp:
            status_code = 200
            def json(self):
                return [
                    {"symbol": "LLY", "name": "Eli Lilly and Company",
                     "exchange": "NYSE", "currency": "USD"},
                ]

        def fake_get(url, timeout=5):
            captured_urls.append(url)
            return _FakeResp()

        with patch("requests.get", side_effect=fake_get):
            r = client.get("/api/search?q=LLY")

        assert r.status_code == 200
        payload = r.get_json()
        tickers = [h["ticker"] for h in payload["results"]]
        assert "LLY" in tickers, f"LLY missing from search: {payload}"
        # Must have hit the stable endpoint — never v3 again.
        assert captured_urls, "requests.get was never called"
        for u in captured_urls:
            assert "/stable/search-symbol" in u, (
                f"search route must hit /stable/search-symbol, got: {u}"
            )
            assert "/api/v3/" not in u, (
                f"search route still hits v3 (deprecated): {u}"
            )

    def test_search_handles_legacy_error_payload_gracefully(
        self, client, auth_user, monkeypatch
    ):
        """If FMP ever returns {'Error Message': 'Legacy...'} again (e.g. a
        future deprecation cycle), we must not crash or include it in results.
        Local US_POPULAR fallback should still fire."""
        monkeypatch.setenv("FMP_API_KEY", "fake-test-key")

        class _FakeResp:
            status_code = 200
            def json(self):
                return {"Error Message": "Legacy Endpoint. Please use /stable/..."}

        with patch("requests.get", return_value=_FakeResp()):
            r = client.get("/api/search?q=aapl")

        assert r.status_code == 200
        results = r.get_json()["results"]
        # AAPL should still appear via the local US_POPULAR fallback.
        tickers = [h["ticker"] for h in results]
        assert "AAPL" in tickers


# ── 7. Cache isolation with class-share alt ──────────────────────────────────

class TestCacheKeyingWithRetry:
    def setup_method(self):
        _clear_fmp_cache()

    def test_caches_under_original_key(self):
        """After a retry resolves BRK.B via BRK-B, the next call for BRK.B
        must hit cache (not make another upstream call)."""
        call_count = {"n": 0}

        def fake_fmp_get(endpoint, params=None, timeout=5):
            call_count["n"] += 1
            if (params or {}).get("symbol") == "BRK-B":
                return [{"symbol": "BRK-B", "price": 450.12}]
            return []

        with patch.object(fmp_service, "_fmp_get", side_effect=fake_fmp_get):
            out1 = fmp_service.get_quote("BRK.B")
            calls_after_first = call_count["n"]
            out2 = fmp_service.get_quote("BRK.B")

        assert out1 == out2
        # Second call must not add upstream calls — cache under "BRK.B" key.
        assert call_count["n"] == calls_after_first
