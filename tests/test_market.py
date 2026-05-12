"""
tests/test_market.py — Market data routes
============================================
/api/prices, /api/market/status, /api/market/overview, /api/chart/<ticker>,
/api/market/profile/<ticker>. All upstream APIs (Alpaca, FMP, KIS) are mocked.
"""
from unittest.mock import patch



class TestMarketStatus:
    def test_market_status_returns_us_and_kr(self, client):
        r = client.get("/api/market/status")
        assert r.status_code == 200
        d = r.get_json()
        assert "us" in d and "kr" in d
        # services/market_status.py uses lowercase status tokens:
        # regular / pre_market / after_hours / closed
        for region in ("us", "kr"):
            assert d[region]["status"] in (
                "regular", "closed", "pre_market", "after_hours",
            )


class TestPrices:
    def test_prices_empty_portfolio(self, client, auth_user):
        r = client.get("/api/prices")
        assert r.status_code == 200
        assert r.get_json()["prices"] == {}

    def test_prices_unauth(self, client):
        r = client.get("/api/prices")
        assert r.status_code == 401


class TestMarketOverview:
    def test_market_overview_uses_mocked_data(self, client, auth_user):
        with patch("routes.market.fetcher") as m:
            m.get_enhanced_macro.return_value = {
                "usdkrw": {"price": 1380.0},
                "spy": {"price": 450.0},
            }
            m.generate_gs_view.return_value = {"regime": "neutral"}
            r = client.get("/api/market/overview")
        assert r.status_code == 200
        d = r.get_json()
        assert "macro" in d
        assert "gs_view" in d


class TestChart:
    def test_chart_invalid_period_falls_back_gracefully(self, client, auth_user):
        """Unknown period → default to 6mo, never crash."""
        import pandas as pd
        with patch("routes.market.fetcher") as m_fetcher, \
             patch("routes.market.realtime") as m_rt:
            m_rt.alpaca_available = False
            m_fetcher.get_price_history.return_value = pd.DataFrame()
            # Also patch fmp_service import inside the function scope.
            with patch("services.data.fmp.get_history", return_value=pd.DataFrame()):
                r = client.get("/api/chart/AAPL?period=wrongvalue")
        assert r.status_code == 200
        d = r.get_json()
        # Even with empty data, should return a consistent envelope.
        assert d["ticker"] == "AAPL"
        assert "data" in d


class TestProfile:
    def test_company_profile_returns_shape(self, client, auth_user):
        with patch("services.data.fmp.get_info") as m_info:
            m_info.return_value = {
                "shortName": "Apple Inc.",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "website": "https://apple.com",
                "fullTimeEmployees": 164000,
                "country": "US",
                "marketCap": 3000000000000,
                "longBusinessSummary": "Apple designs phones.",
            }
            r = client.get("/api/market/profile/AAPL")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ticker"] == "AAPL"
        assert d["name"] == "Apple Inc."
        assert d["currency"] == "USD"

    def test_company_profile_korean_ticker(self, client, auth_user):
        with patch("services.data.fmp.get_info") as m_info:
            m_info.return_value = {"shortName": "Samsung", "sector": "Tech",
                                    "industry": "Semi", "website": "", "country": "KR",
                                    "marketCap": 0, "longBusinessSummary": ""}
            r = client.get("/api/market/profile/005930.KS")
        assert r.status_code == 200
        assert r.get_json()["currency"] == "KRW"


# ═══════════════════════════════════════════════════════════════════════════
# /api/market/indices?region=kr — regression tests for BUG-3 + BUG-4
# (2026-04-24). Bugs fixed:
#   BUG-3: KIS "0001" returned inflated KOSPI levels (~2.56x real).
#   BUG-4a: KOSPI 200 entry missing from the payload entirely.
#   BUG-4b: USD/KRW `range_52w` was hardcoded [0.0, 0.0].
# ═══════════════════════════════════════════════════════════════════════════


class TestMarketIndicesKR:
    """Regression suite for the KR market indices payload."""

    def _kis_service_mock(self, price_map, hist_map=None):
        """Build a KISService() mock returning the given per-code prices.

        price_map: {kis_code: price_float} — None entries yield None returns.
        hist_map:  {kis_code: list_of_close_floats} (optional).
        """
        hist_map = hist_map or {}

        class _MockKIS:
            kis_available = True

            def __init__(self_inner):
                pass

            def get_index_price(self_inner, code):
                p = price_map.get(code)
                if p is None:
                    return None
                return {
                    "index_code": code, "price": p,
                    "change": 0.0, "change_pct": 0.3, "volume": 0,
                }

            def get_index_history(self_inner, code, period="1y"):
                vals = hist_map.get(code)
                if not vals:
                    return None
                return [{"date": "", "close": v} for v in vals]

        return _MockKIS

    def _fmp_history(self, closes):
        """Build a minimal FMP-like OHLCV DataFrame from a list of closes."""
        import pandas as pd
        return pd.DataFrame({
            "Open": closes, "High": closes, "Low": closes,
            "Close": closes, "Volume": [0] * len(closes),
        })

    def test_kospi_level_sanity_bounded(self, client, auth_user):
        """KIS live KOSPI value within per-ticker sanity bound [1500, 4500]
        must surface in payload. PR #188 (`ab3b55e`, 2026-05-09) introduced
        per-ticker bounds in `_kis_index_snapshot` to defend against KIS
        unit/code mismatch where ^KS11 was returning KOSPI200-scaled values
        like 7,498. Bound: ^KS11 [1500, 4500]. This test now verifies the
        happy path — live KIS within bounds → entry surfaces."""
        from services import fx_service
        # Seed fx_service with a realistic rate so USD/KRW tile appears.
        fx_service.set_rate(1380.0)
        # Clear the per-region indices cache so prior tests don't mask us.
        from routes.market import _indices_cache
        _indices_cache.clear()

        hist_closes_kospi = [2510.0 + i * 0.5 for i in range(60)]  # 2510 → 2540
        hist_closes_kosdaq = [720.0 + i * 0.1 for i in range(60)]

        MockKIS = self._kis_service_mock(
            price_map={
                "0001": 2540.0,    # KOSPI [1500, 4500] — within bound
                "1001": 736.5,     # KOSDAQ [500, 1500]
                "2001": 337.8,     # KOSPI 200 [300, 700]
                "2203": 1240.0,    # KOSDAQ 150 [800, 2000]
            },
            hist_map={
                "0001": hist_closes_kospi,
                "1001": hist_closes_kosdaq,
            },
        )

        def _fetcher_hist(ticker, period="1y"):
            if ticker == "^KS11":
                return self._fmp_history(hist_closes_kospi)
            if ticker == "^KQ11":
                return self._fmp_history(hist_closes_kosdaq)
            return None

        with patch("routes.market.fetcher") as m_f, \
                patch("services.container.realtime") as m_rt, \
                patch("services.kis.service.KISService", MockKIS), \
                patch("services.data.fmp.get_history", return_value=None):
            m_rt.kis_available = True
            m_f.get_price_history.side_effect = _fetcher_hist
            r = client.get("/api/market/indices?region=kr")

        assert r.status_code == 200
        data = r.get_json()
        names = {e["name"]: e for e in data}
        assert "KOSPI" in names, f"KOSPI missing from payload: {list(names)}"
        kospi = names["KOSPI"]
        # KOSPI level must fall within per-ticker sanity bound [1500, 4500]
        # introduced by PR #188. Out-of-band values (e.g. 6465 from KIS
        # unit/code mismatch quirk) are dropped at `_kis_index_snapshot`.
        assert 1500 <= kospi["level"] <= 4500, (
            f"KOSPI level {kospi['level']} outside per-ticker sanity band [1500,4500]"
        )

    def test_kospi_200_present(self, client, auth_user):
        """BUG-4a: KOSPI 200 must appear in the payload when KIS supplies a
        valid live level, even if FMP ^KS200 history is empty."""
        from services import fx_service
        fx_service.set_rate(1380.0)
        from routes.market import _indices_cache
        _indices_cache.clear()

        MockKIS = self._kis_service_mock(
            price_map={
                "0001": 2522.0,
                "1001": 736.5,
                "2001": 337.8,   # KOSPI 200 — should now surface
                "2203": 1240.0,
            },
        )

        with patch("routes.market.fetcher") as m_f, \
                patch("services.container.realtime") as m_rt, \
                patch("services.kis.service.KISService", MockKIS), \
                patch("services.data.fmp.get_history", return_value=None):
            m_rt.kis_available = True
            m_f.get_price_history.return_value = None
            r = client.get("/api/market/indices?region=kr")

        assert r.status_code == 200
        data = r.get_json()
        names = [e["name"] for e in data]
        assert "KOSPI 200" in names, (
            f"KOSPI 200 missing — BUG-4a regression. Got: {names}"
        )

    def test_usdkrw_range_52w_not_zero(self, client, auth_user):
        """BUG-4b: USD/KRW `range_52w` must be populated from FMP FX history
        when available — previously hardcoded to [0.0, 0.0]."""
        from services import fx_service
        fx_service.set_rate(1380.0)
        from routes.market import _indices_cache
        _indices_cache.clear()

        fx_closes = [1300.0 + i * 0.5 for i in range(100)]  # 1300 → 1350

        MockKIS = self._kis_service_mock(
            price_map={"0001": 2522.0, "1001": 736.5,
                       "2001": 337.8, "2203": 1240.0},
        )

        def _fmp_get_history(ticker, period="1y"):
            if ticker == "USDKRW":
                return self._fmp_history(fx_closes)
            return None

        with patch("routes.market.fetcher") as m_f, \
                patch("services.container.realtime") as m_rt, \
                patch("services.kis.service.KISService", MockKIS), \
                patch("services.data.fmp.get_history", side_effect=_fmp_get_history):
            m_rt.kis_available = True
            m_f.get_price_history.return_value = None
            r = client.get("/api/market/indices?region=kr")

        assert r.status_code == 200
        data = r.get_json()
        fx = next((e for e in data if e["ticker"] == "USDKRW"), None)
        assert fx is not None, "USD/KRW entry missing"
        lo, hi = fx["range_52w"]
        assert not (lo == 0.0 and hi == 0.0), (
            "USD/KRW range_52w is [0,0] — BUG-4b regression"
        )
        assert lo < hi, f"range_52w malformed: [{lo}, {hi}]"
        # Should bracket the seeded history.
        assert lo <= 1300.5 and hi >= 1349.0

    # ────────────────────────────────────────────────────────────────────
    # 2026-04-24 — BUG #RANGE-STALE: `_kis_index_snapshot` was pairing a
    # live KIS level (e.g., KOSPI 6475) with a stale FMP history
    # (~2500). The payload contradicted itself: range_52w[1] < level,
    # sparkline max was ~40% of the level. Tests below enforce the new
    # policy: prefer KIS history, and when it disagrees with live by
    # >30%, discard the series and mark is_stale rather than publishing
    # a self-contradictory row.
    # ────────────────────────────────────────────────────────────────────

    def test_kr_index_prefers_kis_history_over_fmp(self, client, auth_user):
        """KIS `inquire-index-daily-price` must be consulted FIRST for
        KR indices. FMP `^KS11` is known to lag on the Starter tier; a
        fresh KIS series must win even when FMP returns data.

        Each index uses level + history within its per-ticker sanity bound
        (PR #188): KOSPI [1500,4500], KOSDAQ [500,1500], KOSPI200 [300,700],
        KOSDAQ150 [800,2000]. FMP returns a stale 2023 baseline (~1500)
        which must be rejected in favor of fresh KIS history."""
        from services import fx_service
        fx_service.set_rate(1380.0)
        from routes.market import _indices_cache
        _indices_cache.clear()

        # KIS history is fresh (bracketing each live level within bound).
        kis_hist_kospi = [2510.0 + i * 0.5 for i in range(60)]    # 2510 → 2540
        kis_hist_kosdaq = [720.0 + i * 0.5 for i in range(60)]    # 720 → 750
        kis_hist_ks200 = [325.0 + i * 0.2 for i in range(60)]     # 325 → 337
        kis_hist_kq150 = [1210.0 + i * 0.5 for i in range(60)]    # 1210 → 1240
        # FMP history is stale (2023 baseline) — well outside KOSPI bound.
        fmp_hist = [1500.0 + i * 0.1 for i in range(60)]

        MockKIS = self._kis_service_mock(
            price_map={"0001": 2540.0, "1001": 750.0,
                       "2001": 337.0, "2203": 1240.0},
            hist_map={"0001": kis_hist_kospi, "1001": kis_hist_kosdaq,
                      "2001": kis_hist_ks200, "2203": kis_hist_kq150},
        )

        def _fetcher_hist(ticker, period="1y"):
            # FMP would return stale 1500 series — new code should ignore.
            return self._fmp_history(fmp_hist)

        with patch("routes.market.fetcher") as m_f, \
                patch("services.container.realtime") as m_rt, \
                patch("services.kis.service.KISService", MockKIS), \
                patch("services.data.fmp.get_history", return_value=None):
            m_rt.kis_available = True
            m_f.get_price_history.side_effect = _fetcher_hist
            r = client.get("/api/market/indices?region=kr")

        assert r.status_code == 200
        data = r.get_json()
        kospi = next((e for e in data if e["name"] == "KOSPI"), None)
        assert kospi is not None
        # With KIS history in play, sparkline must reflect KIS (~2510-2540),
        # NOT the stale FMP ~1500 tail.
        assert kospi["sparkline_30d"], "sparkline should be populated"
        spark_max = max(kospi["sparkline_30d"])
        assert spark_max > 2500, (
            f"sparkline max={spark_max} looks like FMP stale data — "
            f"KIS history should have won. Level={kospi['level']}"
        )
        # Level must be within range_52w.
        lo, hi = kospi["range_52w"]
        assert lo <= kospi["level"] <= hi * 1.01, (
            f"level {kospi['level']} outside range_52w [{lo}, {hi}]"
        )

    def test_kr_index_stale_history_discarded_with_flag(self, client, auth_user):
        """When the only history we can obtain (FMP) diverges from the
        live KIS level by >30%, discard the series and flag `is_stale`.
        range_52w must become None (not [0,0]) so the frontend renders
        N/A rather than a misleading bar chart.

        Live KIS level within sanity bound [1500,4500] (PR #188). FMP
        deeply stale (~800) → divergence >60% → series discarded with flag."""
        from services import fx_service
        fx_service.set_rate(1380.0)
        from routes.market import _indices_cache
        _indices_cache.clear()

        # KIS gives us the live level but NO history (returns None).
        # FMP returns a deeply stale series — divergence vs level >30%.
        fmp_stale = [800.0 + i * 0.1 for i in range(60)]   # 800 vs level 2540 → 68% gap

        MockKIS = self._kis_service_mock(
            price_map={"0001": 2540.0, "1001": 750.0,
                       "2001": 337.0, "2203": 1240.0},
            hist_map={},  # KIS history unavailable
        )

        def _fetcher_hist(ticker, period="1y"):
            return self._fmp_history(fmp_stale)

        with patch("routes.market.fetcher") as m_f, \
                patch("services.container.realtime") as m_rt, \
                patch("services.kis.service.KISService", MockKIS), \
                patch("services.data.fmp.get_history", return_value=None):
            m_rt.kis_available = True
            m_f.get_price_history.side_effect = _fetcher_hist
            r = client.get("/api/market/indices?region=kr")

        assert r.status_code == 200
        data = r.get_json()
        kospi = next((e for e in data if e["name"] == "KOSPI"), None)
        assert kospi is not None
        assert kospi["level"] == 2540.0
        assert kospi["is_stale"] is True, (
            "is_stale must be True when history is rejected as stale"
        )
        # No self-contradiction: empty sparkline, None range_52w.
        assert kospi["sparkline_30d"] == []
        assert kospi["range_52w"] is None, (
            f"range_52w must be None when history is discarded, got "
            f"{kospi['range_52w']}"
        )

    def test_kr_index_level_within_range_52w_when_fresh(self, client, auth_user):
        """Invariant: when range_52w is non-null, the live level must fit
        inside (or very close to) the 52-week window. This is the core
        sanity check that the original bug violated — level=6475 vs
        range_52w=[2293, 2671]."""
        from services import fx_service
        fx_service.set_rate(1380.0)
        from routes.market import _indices_cache
        _indices_cache.clear()

        kis_hist = [6400.0 + i * 1.0 for i in range(60)]  # 6400 → 6459

        MockKIS = self._kis_service_mock(
            price_map={"0001": 6475.0, "1001": 750.0,
                       "2001": 980.0, "2203": 2040.0},
            hist_map={"0001": kis_hist, "1001": kis_hist,
                      "2001": kis_hist, "2203": kis_hist},
        )

        with patch("routes.market.fetcher") as m_f, \
                patch("services.container.realtime") as m_rt, \
                patch("services.kis.service.KISService", MockKIS), \
                patch("services.data.fmp.get_history", return_value=None):
            m_rt.kis_available = True
            m_f.get_price_history.return_value = None
            r = client.get("/api/market/indices?region=kr")

        assert r.status_code == 200
        data = r.get_json()
        for entry in data:
            if entry["ticker"] == "USDKRW":
                continue  # USD/KRW has its own range semantics
            if entry["range_52w"] is None:
                continue  # stale path — separately tested
            lo, hi = entry["range_52w"]
            # Allow tiny headroom: live can exceed 52W high intraday.
            assert lo <= entry["level"] <= hi * 1.05, (
                f"{entry['name']}: level {entry['level']} outside "
                f"range_52w [{lo}, {hi}] — source mismatch regression"
            )

    # ────────────────────────────────────────────────────────────────────
    # 2026-05-09 — P0 graceful-degradation: KIS unit/code quirk fallback.
    # KIS `inquire-index-price` for `0001`/`2001`/`2203` was observed
    # returning levels ~2-3x the true value (e.g. KOSPI 7498 vs real
    # ~3,180). PR #188 added per-ticker sanity bounds that *correctly*
    # rejected the bogus value, but the side effect was the KOSPI tile
    # disappearing from the payload entirely. Fix: when KIS sanity fails,
    # try FMP `get_quote(ticker)` as a fallback live-level source. Sanity
    # bound is re-applied to the FMP value — only realistic readings
    # surface, so PR #188's defense is preserved verbatim.
    # ────────────────────────────────────────────────────────────────────

    def test_kospi_kis_sanity_fail_fmp_fallback_succeeds(self, client, auth_user):
        """KIS returns 749,800 (100x unit-glitch — outside [1500, 50000])
        → FMP returns 2540 (realistic) → KOSPI tile must surface with
        the FMP value.

        2026-05-10 (B-06): originally used 7498 against the narrow
        [1500, 4500] bound, but live KIS verification proved 7498 is
        the real KOSPI level. Test value upgraded to 749,800 (a true
        100x unit-confusion glitch) so the FMP-fallback contract still
        triggers under the wide [1500, 50000] bound."""
        from services import fx_service
        fx_service.set_rate(1380.0)
        from routes.market import _indices_cache
        _indices_cache.clear()

        MockKIS = self._kis_service_mock(
            price_map={
                "0001": 749_800.0,  # 100x unit-glitch — outside [1500, 50000]
                "1001": 1207.0,     # KOSDAQ in-band
                "2001": 337.0,
                "2203": 1240.0,
            },
            hist_map={},  # No KIS history — drives FMP into the fallback path
        )

        def _fmp_get_quote(t):
            if t == "^KS11":
                return {"price": 2540.0, "changesPercentage": 0.42}
            return None

        with patch("routes.market.fetcher") as m_f, \
                patch("services.container.realtime") as m_rt, \
                patch("services.kis.service.KISService", MockKIS), \
                patch("services.data.fmp.get_history", return_value=None), \
                patch("services.data.fmp.get_quote", side_effect=_fmp_get_quote):
            m_rt.kis_available = True
            m_f.get_price_history.return_value = None
            r = client.get("/api/market/indices?region=kr")

        assert r.status_code == 200
        data = r.get_json()
        names = {e["name"]: e for e in data}
        assert "KOSPI" in names, (
            f"KOSPI missing despite FMP fallback being available: {list(names)}"
        )
        kospi = names["KOSPI"]
        # Must reflect the FMP value, NOT the bogus KIS 100x glitch.
        assert kospi["level"] == 2540.0, (
            f"Expected FMP-fallback level 2540.0, got {kospi['level']}"
        )
        # And the FMP-derived d/d% should propagate.
        assert kospi["change_1d_pct"] == 0.42

    def test_kospi_kis_sanity_fail_fmp_none_drops_entry(self, client, auth_user):
        """KIS 100x glitch (sanity-fail) + FMP returns None → KOSPI
        must remain absent from the payload (PR #188 contract preserved
        under the post-2026-05-10 wide bound)."""
        from services import fx_service
        fx_service.set_rate(1380.0)
        from routes.market import _indices_cache
        _indices_cache.clear()

        MockKIS = self._kis_service_mock(
            price_map={
                "0001": 749_800.0,  # 100x unit-glitch
                "1001": 1207.0,
                "2001": 337.0,
                "2203": 1240.0,
            },
        )

        with patch("routes.market.fetcher") as m_f, \
                patch("services.container.realtime") as m_rt, \
                patch("services.kis.service.KISService", MockKIS), \
                patch("services.data.fmp.get_history", return_value=None), \
                patch("services.data.fmp.get_quote", return_value=None):
            m_rt.kis_available = True
            m_f.get_price_history.return_value = None
            r = client.get("/api/market/indices?region=kr")

        assert r.status_code == 200
        data = r.get_json()
        names = [e["name"] for e in data]
        assert "KOSPI" not in names, (
            "KOSPI should be absent when both KIS sanity-fails AND FMP "
            "returns None — got: " + str(names)
        )
        # KOSDAQ (in-band) must still surface — fallback path must not
        # poison sibling tickers.
        assert "KOSDAQ" in names

    def test_kospi_kis_in_band_no_fmp_call(self, client, auth_user):
        """KIS returns 2540 (in-band) → FMP MUST NOT be called. Guards
        against unnecessary upstream traffic + protects against FMP
        accidentally overriding a known-good KIS value."""
        from services import fx_service
        fx_service.set_rate(1380.0)
        from routes.market import _indices_cache
        _indices_cache.clear()

        MockKIS = self._kis_service_mock(
            price_map={
                "0001": 2540.0,    # in-band
                "1001": 1207.0,
                "2001": 337.0,
                "2203": 1240.0,
            },
        )

        from unittest.mock import MagicMock
        fmp_quote = MagicMock(return_value={"price": 9999.0})

        with patch("routes.market.fetcher") as m_f, \
                patch("services.container.realtime") as m_rt, \
                patch("services.kis.service.KISService", MockKIS), \
                patch("services.data.fmp.get_history", return_value=None), \
                patch("services.data.fmp.get_quote", fmp_quote):
            m_rt.kis_available = True
            m_f.get_price_history.return_value = None
            r = client.get("/api/market/indices?region=kr")

        assert r.status_code == 200
        data = r.get_json()
        kospi = next((e for e in data if e["name"] == "KOSPI"), None)
        assert kospi is not None and kospi["level"] == 2540.0
        # FMP fallback must have been bypassed entirely for ^KS11.
        called_tickers = [c.args[0] for c in fmp_quote.call_args_list]
        assert "^KS11" not in called_tickers, (
            f"FMP get_quote was called for ^KS11 despite KIS being "
            f"in-band — calls: {called_tickers}"
        )

    def test_kospi_kis_none_fmp_out_of_band_drops_entry(self, client, auth_user):
        """Both sources unreliable: KIS returns None AND FMP also returns
        an out-of-band value (e.g. plan-gated wrong asset). Sanity bound
        re-application must reject FMP — KOSPI absent from payload."""
        from services import fx_service
        fx_service.set_rate(1380.0)
        from routes.market import _indices_cache
        _indices_cache.clear()

        MockKIS = self._kis_service_mock(
            price_map={
                "0001": None,      # KIS missing
                "1001": 1207.0,
                "2001": 337.0,
                "2203": 1240.0,
            },
        )

        def _fmp_get_quote(t):
            if t == "^KS11":
                # 100x unit-glitch — outside the wide [1500, 50000] bound.
                return {"price": 749_800.0}
            return None

        with patch("routes.market.fetcher") as m_f, \
                patch("services.container.realtime") as m_rt, \
                patch("services.kis.service.KISService", MockKIS), \
                patch("services.data.fmp.get_history", return_value=None), \
                patch("services.data.fmp.get_quote", side_effect=_fmp_get_quote):
            m_rt.kis_available = True
            m_f.get_price_history.return_value = None
            r = client.get("/api/market/indices?region=kr")

        assert r.status_code == 200
        data = r.get_json()
        names = [e["name"] for e in data]
        assert "KOSPI" not in names, (
            "KOSPI must remain dropped when FMP fallback also fails sanity"
        )
        # Sibling KOSDAQ unaffected.
        assert "KOSDAQ" in names

    def test_kospi_fmp_fallback_discards_pre_fallback_sparkline(self, client, auth_user):
        """Pre-fallback path may have populated `sparkline`/`range_52w`
        from a series that was unit-consistent with the bogus KIS level
        (e.g. KIS history tail ~5778, divergent <30% from KIS 7498 so it
        survived the staleness guard). After FMP fallback overrides the
        level to a realistic 2540, the leftover series would render a
        self-contradictory tile (level=2540 but sparkline shows 5778+).
        The implementation must discard the artifact series."""
        from services import fx_service
        fx_service.set_rate(1380.0)
        from routes.market import _indices_cache
        _indices_cache.clear()

        # KIS history ~575_800 — survives 30% staleness vs live 749_800 (~22%
        # divergence) but is wildly outside the [1500, 50000] sanity bound.
        # PR #236 (2026-05-10) widened ^KS11 bound from (1500, 4500) →
        # (1500, 50000); sibling tests were updated but this one was missed.
        # Mock values rescaled to 100× so the bound check still rejects them.
        kis_hist_kospi = [575_000.0 + i * 50.0 for i in range(60)]

        MockKIS = self._kis_service_mock(
            price_map={
                "0001": 749_800.0,  # KIS quirk — well above 50_000 wide bound
                "1001": 1207.0,
                "2001": 337.0,
                "2203": 1240.0,
            },
            hist_map={"0001": kis_hist_kospi},
        )

        def _fmp_get_quote(t):
            if t == "^KS11":
                return {"price": 2540.0}
            return None

        with patch("routes.market.fetcher") as m_f, \
                patch("services.container.realtime") as m_rt, \
                patch("services.kis.service.KISService", MockKIS), \
                patch("services.data.fmp.get_history", return_value=None), \
                patch("services.data.fmp.get_quote", side_effect=_fmp_get_quote):
            m_rt.kis_available = True
            m_f.get_price_history.return_value = None
            r = client.get("/api/market/indices?region=kr")

        assert r.status_code == 200
        data = r.get_json()
        kospi = next((e for e in data if e["name"] == "KOSPI"), None)
        assert kospi is not None
        assert kospi["level"] == 2540.0
        # The pre-fallback sparkline (~5778) is incompatible with the
        # FMP-derived level 2540 → must be discarded, range_52w → None,
        # is_stale → True so the frontend renders "N/A".
        assert kospi["sparkline_30d"] == [], (
            f"sparkline must be discarded after FMP fallback: "
            f"{kospi['sparkline_30d'][:5]}..."
        )
        assert kospi["range_52w"] is None
        assert kospi["is_stale"] is True
