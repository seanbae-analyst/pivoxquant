"""tests/test_portfolio_kr_ticker_normalization.py — Bug #1 regression guard.

Why this exists
---------------
2026-05-13 bug-hunter live evidence: KR users typing a bare 6-digit code
(e.g. "005930" Samsung Electronics) saw their position persist as
``ticker=005930`` — bypassing the KRX suffix routing. Downstream:

  * /api/portfolio/positions emitted ``currency="USD"`` / ``isKorean=false``
  * Portfolio UI rendered "$54,000" instead of "₩54,000"
  * Signals page rendered "005930 · 005930 · 중립" (name_resolver missed)
  * Home rendered raw "005930 +425.93%"

Root cause: ``routes/portfolio.py::add_position`` /
``create_position_alias`` / ``buy_new_position`` accepted the raw user
input verbatim (``strip().upper()``) and never piped it through
``services.ticker_normalizer.normalize_ticker``.

This test pins the normalization at every write-side entry point so a
future refactor can't silently regress the KR portfolio path.
"""
from unittest.mock import patch


class TestCreatePositionAliasNormalizesKR:
    """POST /api/portfolio/positions — the production endpoint."""

    def test_bare_005930_routes_to_KS(self, client, auth_user, mock_fetcher):
        # Samsung Electronics — KOSPI listing, must land as 005930.KS.
        r = client.post("/api/portfolio/positions", json={
            "symbol": "005930",
            "quantity": 10,
            "price": 54_000,
        })
        assert r.status_code == 200, r.data
        d = r.get_json()
        assert d["ok"] is True
        assert d["symbol"] == "005930.KS"
        assert d["isKorean"] is True
        assert d["is_korean"] is True

    def test_bare_000660_routes_to_KS(self, client, auth_user, mock_fetcher):
        # SK Hynix — also KOSPI.
        r = client.post("/api/portfolio/positions", json={
            "symbol": "000660",
            "quantity": 5,
            "price": 150_000,
        })
        assert r.status_code == 200, r.data
        d = r.get_json()
        assert d["symbol"] == "000660.KS"
        assert d["isKorean"] is True

    def test_bare_035720_routes_to_KS(self, client, auth_user, mock_fetcher):
        # Kakao — moved to KOSPI in 2017. Curated registry entry.
        r = client.post("/api/portfolio/positions", json={
            "symbol": "035720",
            "quantity": 100,
            "price": 50_000,
        })
        assert r.status_code == 200, r.data
        d = r.get_json()
        assert d["symbol"] == "035720.KS"

    def test_aapl_passes_through_unchanged(self, client, auth_user, mock_fetcher):
        # US ticker — must NOT acquire a KR suffix.
        r = client.post("/api/portfolio/positions", json={
            "symbol": "AAPL",
            "quantity": 10,
            "price": 200,
        })
        assert r.status_code == 200, r.data
        d = r.get_json()
        assert d["symbol"] == "AAPL"
        assert d["isKorean"] is False
        assert d["is_korean"] is False

    def test_lowercase_aapl_uppercased(self, client, auth_user, mock_fetcher):
        r = client.post("/api/portfolio/positions", json={
            "symbol": "aapl",
            "quantity": 1,
            "price": 200,
        })
        assert r.status_code == 200, r.data
        d = r.get_json()
        assert d["symbol"] == "AAPL"

    def test_explicit_kq_suffix_preserved(self, client, auth_user, mock_fetcher):
        # KOSDAQ ticker with explicit suffix — must NOT be rewritten to .KS.
        # 247540.KQ = Ecopro BM (KOSDAQ 150 constituent, curated registry).
        r = client.post("/api/portfolio/positions", json={
            "symbol": "247540.KQ",
            "quantity": 10,
            "price": 200_000,
        })
        assert r.status_code == 200, r.data
        d = r.get_json()
        assert d["symbol"] == "247540.KQ"
        assert d["isKorean"] is True

    def test_explicit_ks_suffix_preserved(self, client, auth_user, mock_fetcher):
        r = client.post("/api/portfolio/positions", json={
            "symbol": "005930.KS",
            "quantity": 1,
            "price": 54_000,
        })
        assert r.status_code == 200, r.data
        d = r.get_json()
        assert d["symbol"] == "005930.KS"

    def test_persisted_position_has_normalized_ticker(self, client, auth_user, mock_fetcher, app):
        from models import Position
        r = client.post("/api/portfolio/positions", json={
            "symbol": "005930",
            "quantity": 10,
            "price": 54_000,
        })
        assert r.status_code == 200, r.data
        with app.app_context():
            pos = Position.query.filter_by(user_id=auth_user["id"]).first()
            assert pos is not None
            assert pos.ticker == "005930.KS", (
                f"Position persisted as {pos.ticker!r}; normalize_ticker "
                "must rewrite bare 6-digit codes BEFORE the row hits the DB"
            )


class TestSingularAddPositionNormalizesKR:
    """POST /api/portfolio/position — legacy singular endpoint."""

    def test_bare_005930_routes_to_KS(self, client, auth_user, mock_fetcher):
        r = client.post("/api/portfolio/position", json={
            "ticker": "005930",
            "shares": 10,
            "avg_cost": 54_000,
        })
        assert r.status_code == 200, r.data
        d = r.get_json()
        assert d["ticker"] == "005930.KS"
        assert d["is_korean"] is True

    def test_aapl_passes_through(self, client, auth_user, mock_fetcher):
        r = client.post("/api/portfolio/position", json={
            "ticker": "AAPL",
            "shares": 10,
            "avg_cost": 200,
        })
        assert r.status_code == 200, r.data
        d = r.get_json()
        assert d["ticker"] == "AAPL"
        assert d["is_korean"] is False


class TestBuyNewPositionNormalizesKR:
    """POST /api/portfolio/position/buy-new — legacy buy-from-scratch path."""

    def test_bare_005930_routes_to_KS(self, client, auth_user, mock_fetcher, app):
        from models import Position
        r = client.post("/api/portfolio/position/buy-new", json={
            "ticker": "005930",
            "shares": 1,
            "price": 54_000,
        })
        # mock_fetcher.currency returns "KRW" for .KS — so we need KRW
        # capital. The default fixture seeds 1,000,000 KRW which covers
        # 1 share at 54,000.
        assert r.status_code == 200, r.data
        with app.app_context():
            pos = Position.query.filter_by(user_id=auth_user["id"]).first()
            assert pos is not None
            assert pos.ticker == "005930.KS"
