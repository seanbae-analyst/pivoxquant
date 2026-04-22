"""
tests/test_lookup.py — /api/lookup/<ticker>
=============================================
Verifies that the route correctly delegates to DataFetcher.quick_lookup,
returns the expected shape for US/KR/unknown tickers, and never hits real
external APIs in tests.
"""
from unittest.mock import patch



class TestLookup:
    def test_us_ticker_response_shape(self, client):
        with patch("routes.market.fetcher") as m:
            m.quick_lookup.return_value = {
                "ok": True, "ticker": "AAPL", "name": "Apple Inc.",
                "price": 175.23, "price_display": "$175.23",
                "currency": "USD", "is_korean": False,
            }
            r = client.get("/api/lookup/AAPL")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ticker"] == "AAPL"
        assert d["currency"] == "USD"
        assert d["is_korean"] is False
        assert isinstance(d["price"], (int, float))
        assert d["price"] > 0
        assert "$" in d["price_display"]

    def test_kr_ticker_response_shape(self, client):
        with patch("routes.market.fetcher") as m:
            m.quick_lookup.return_value = {
                "ok": True, "ticker": "005930.KS", "name": "Samsung Electronics",
                "price": 82000.0, "price_display": "₩82,000",
                "currency": "KRW", "is_korean": True,
            }
            r = client.get("/api/lookup/005930.KS")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ticker"] == "005930.KS"
        assert d["currency"] == "KRW"
        assert d["is_korean"] is True
        assert "₩" in d["price_display"]

    def test_unknown_ticker_returns_404(self, client):
        with patch("routes.market.fetcher") as m:
            m.quick_lookup.return_value = None
            r = client.get("/api/lookup/ZZZZZ")
        assert r.status_code == 404
        assert r.get_json()["ok"] is False
