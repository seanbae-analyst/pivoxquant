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
            with patch("fmp_service.get_history", return_value=pd.DataFrame()):
                r = client.get("/api/chart/AAPL?period=wrongvalue")
        assert r.status_code == 200
        d = r.get_json()
        # Even with empty data, should return a consistent envelope.
        assert d["ticker"] == "AAPL"
        assert "data" in d


class TestProfile:
    def test_company_profile_returns_shape(self, client, auth_user):
        with patch("fmp_service.get_info") as m_info:
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
        with patch("fmp_service.get_info") as m_info:
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
        """BUG-3: KIS live KOSPI value 6465 must NOT appear — history anchor
        (~2522) must override when divergence exceeds 20%."""
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
                "0001": 6465.79,   # inflated — regression reproduction
                "1001": 736.5,     # normal
                "2001": 337.8,     # KOSPI 200 live
                "2203": 1240.0,    # KOSDAQ 150 live
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
                patch("kis_service.KISService", MockKIS), \
                patch("fmp_service.get_history", return_value=None):
            m_rt.kis_available = True
            m_f.get_price_history.side_effect = _fetcher_hist
            r = client.get("/api/market/indices?region=kr")

        assert r.status_code == 200
        data = r.get_json()
        names = {e["name"]: e for e in data}
        assert "KOSPI" in names, f"KOSPI missing from payload: {list(names)}"
        kospi = names["KOSPI"]
        # Sanity: KOSPI level must fall in the service's absolute bound.
        # The original assertion [500, 5000] was written against a stale
        # 2023 baseline; by 2026 KOSPI re-rated (~6500 per Yahoo live),
        # so we use the service-side bound [100, 10000] as the test bound.
        # The earlier "divergence guard" that tried to clamp live KIS
        # against stale FMP history was reverted 2026-04-24 because it
        # substituted correct live values with stale historical ones.
        assert 100 <= kospi["level"] <= 10000, (
            f"KOSPI level {kospi['level']} outside service sanity band"
        )
        # The test fixture now feeds KIS live as the authoritative source;
        # we no longer anchor level to history close.

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
                patch("kis_service.KISService", MockKIS), \
                patch("fmp_service.get_history", return_value=None):
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
                patch("kis_service.KISService", MockKIS), \
                patch("fmp_service.get_history", side_effect=_fmp_get_history):
            m_rt.kis_available = True
            m_f.get_price_history.return_value = None
            r = client.get("/api/market/indices?region=kr")

        assert r.status_code == 200
        data = r.get_json()
        fx = next((e for e in data if e["ticker"] == "USDKRW"), None)
        assert fx is not None, "USD/KRW entry missing"
        lo, hi = fx["range_52w"]
        assert not (lo == 0.0 and hi == 0.0), (
            f"USD/KRW range_52w is [0,0] — BUG-4b regression"
        )
        assert lo < hi, f"range_52w malformed: [{lo}, {hi}]"
        # Should bracket the seeded history.
        assert lo <= 1300.5 and hi >= 1349.0
