"""B-06 regression suite — KIS endpoint verification + KOSPI sanity bounds.

Backstop for the 2026-05-10 (B-06) autonomous KIS API verification that
disproved the 2026-05-10 W-04 "3x scaling glitch" hypothesis:

  * KIS 0001 (KOSPI) returned 7498.00 on 2026-05-10 — stable across
    repeated calls; consistent with KIS daily-history uptrend
    5052 -> 5778 -> 6475 -> 6598 -> 7498 across 2026-Q2
  * Ratio KOSPI / KOSPI-200 = 7498 / 1151 = 6.51x — NOT the ~3x that
    the scaling-glitch hypothesis predicted
  * No alternative ISCD ("K2I", "U001") or tr_id (FHKUP03500100,
    FHPUP02110100) returns a "corrected" KOSPI level on KIS Open API

Bounds (post-B-06 fix):
    routes/market.py            ^KS11    [1500, 50000]
                                ^KQ11    [500,  50000]
                                ^KS200   [300,  10000]
                                ^KQ150   [500,  10000]
    services/data/fetcher.py    PIVOX_KOSPI_RANGE  [1500, 50000]
                                PIVOX_KOSDAQ_RANGE [500,  50000]

These tests guard against future autonomous-agent narrowing without
parallel KIS-side verification. Memory [공식 라이선스만] preserved —
no pykrx/yfinance/네이버. KIS Open API only.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


# ─────────────────────────────────────────────────────────────────────
# routes/market.py — _kis_index_snapshot per-ticker bounds
# ─────────────────────────────────────────────────────────────────────


class TestRoutePerTickerBounds:
    """The wide [1500, 50000] bound for ^KS11 must accept legitimate
    2026 KOSPI levels (7498) while still rejecting 100x unit-confusion
    glitches (749,800)."""

    def _kis_mock(self, kospi_price):
        class _MockKIS:
            kis_available = True
            def __init__(self_inner): pass
            def get_index_price(self_inner, code):
                if code == "0001":
                    return {"index_code": code, "price": kospi_price,
                            "change": 0.0, "change_pct": 0.3, "volume": 0}
                if code == "1001":
                    return {"index_code": code, "price": 1207.0,
                            "change": 0.0, "change_pct": 0.0, "volume": 0}
                if code == "2001":
                    return {"index_code": code, "price": 337.0,
                            "change": 0.0, "change_pct": 0.0, "volume": 0}
                if code == "2203":
                    return {"index_code": code, "price": 1240.0,
                            "change": 0.0, "change_pct": 0.0, "volume": 0}
                return None
            def get_index_history(self_inner, code, period="1y"):
                return None
        return _MockKIS

    @pytest.mark.parametrize("kospi_value", [
        # Pre-B-06 bound [1500, 4500] would have rejected all of these.
        # Post-B-06 [1500, 50000] accepts the entire legitimate range.
        2540.0,    # 2025 baseline
        4400.0,    # near the old narrow ceiling
        6641.0,    # the 2026-04-28 incident value (real KOSPI re-rate)
        7498.0,    # 2026-05-10 live KIS value (verified authentic)
        12_000.0,  # forward-looking head-room
        49_999.0,  # just under the wide ceiling
    ])
    def test_kospi_within_wide_bound_surfaces(
        self, client, auth_user, kospi_value,
    ):
        """KOSPI levels inside the post-B-06 [1500, 50000] bound must
        surface in the /api/market/indices payload."""
        from services import fx_service
        fx_service.set_rate(1380.0)
        from routes.market import _indices_cache
        _indices_cache.clear()

        MockKIS = self._kis_mock(kospi_value)
        with patch("routes.market.fetcher") as m_f, \
                patch("services.container.realtime") as m_rt, \
                patch("services.kis.service.KISService", MockKIS), \
                patch("services.data.fmp.get_history", return_value=None):
            m_rt.kis_available = True
            m_f.get_price_history.return_value = None
            r = client.get("/api/market/indices?region=kr")

        assert r.status_code == 200
        names = {e["name"]: e for e in r.get_json()}
        assert "KOSPI" in names, (
            f"KOSPI {kospi_value} (in-band) was incorrectly dropped. "
            f"B-06 regression — narrow-bound revert detected."
        )
        assert names["KOSPI"]["level"] == pytest.approx(kospi_value)

    @pytest.mark.parametrize("kospi_value", [
        # 100x unit-confusion glitches — must still drop after B-06.
        749_800.0,    # 7498 * 100 (unit-confusion of the real KOSPI)
        66_410_200.0, # 6641 * 10000 (rare but observed in adapters)
    ])
    def test_kospi_outside_wide_bound_drops(
        self, client, auth_user, kospi_value,
    ):
        """The 100x unit-confusion guard must remain after B-06 widened
        the upper bound — values above 50,000 still drop cleanly."""
        from services import fx_service
        fx_service.set_rate(1380.0)
        from routes.market import _indices_cache
        _indices_cache.clear()

        MockKIS = self._kis_mock(kospi_value)
        with patch("routes.market.fetcher") as m_f, \
                patch("services.container.realtime") as m_rt, \
                patch("services.kis.service.KISService", MockKIS), \
                patch("services.data.fmp.get_history", return_value=None), \
                patch("services.data.fmp.get_quote", return_value=None):
            m_rt.kis_available = True
            m_f.get_price_history.return_value = None
            r = client.get("/api/market/indices?region=kr")

        assert r.status_code == 200
        names = [e["name"] for e in r.get_json()]
        assert "KOSPI" not in names, (
            f"KOSPI {kospi_value} (100x glitch) should have been dropped. "
            f"100x unit-confusion guard regressed after B-06 widening."
        )


# ─────────────────────────────────────────────────────────────────────
# services/data/fetcher.py — get_enhanced_macro KOSPI bounds
# ─────────────────────────────────────────────────────────────────────


class TestFetcherWideBounds:
    """Mirror of the route-level bound test against the macro path —
    services/data/fetcher.py:_KOSPI_RANGE / _KOSDAQ_RANGE must also
    use the wide [1500, 50000] / [500, 50000] policy."""

    @patch("services.data.fetcher.fmp")
    def test_macro_kospi_7498_published(self, mock_fmp):
        """The live KIS value (7498 on 2026-05-10) must surface via
        get_enhanced_macro() under the post-B-06 fetcher bound."""
        from services.data.fetcher import DataFetcher

        mock_fmp.get_quote.return_value = None
        mock_fmp.get_quotes_batch.return_value = {}
        mock_fmp.get_fx_rate.return_value = None

        f = DataFetcher()
        with patch("services.container.realtime") as mock_rt, \
             patch("services.kis.service.KISService") as MockKis:
            mock_rt.kis_available = True
            MockKis.return_value.get_index_price.side_effect = lambda code: (
                {"price": 7498.0, "change_pct": 0.11} if code == "0001"
                else {"price": 1207.0, "change_pct": 0.71}
            )
            m = f.get_enhanced_macro()

        assert m.get("kospi", {}).get("price") == pytest.approx(7498.0), (
            "KOSPI 7498 (real 2026-05-10 KIS value) must surface in macro. "
            "fetcher.py narrow-bound revert detected."
        )
        assert m.get("kosdaq", {}).get("price") == pytest.approx(1207.0)

    @patch("services.data.fetcher.fmp")
    def test_macro_kospi_100x_glitch_dropped(self, mock_fmp):
        """The 100x unit-confusion guard remains active in the macro
        path — 749,800 is above 50,000 ceiling and must drop."""
        from services.data.fetcher import DataFetcher

        mock_fmp.get_quote.return_value = None
        mock_fmp.get_quotes_batch.return_value = {}
        mock_fmp.get_fx_rate.return_value = None

        f = DataFetcher()
        with patch("services.container.realtime") as mock_rt, \
             patch("services.kis.service.KISService") as MockKis:
            mock_rt.kis_available = True
            MockKis.return_value.get_index_price.side_effect = lambda code: (
                {"price": 749_800.0, "change_pct": 0.0} if code == "0001"
                else {"price": 1207.0, "change_pct": 0.71}
            )
            m = f.get_enhanced_macro()

        assert "kospi" not in m, (
            "KOSPI 749,800 (100x glitch) must drop via fetcher sanity guard"
        )
        # KOSDAQ unaffected.
        assert m.get("kosdaq", {}).get("price") == pytest.approx(1207.0)


# ─────────────────────────────────────────────────────────────────────
# Documentation guard — KIS endpoint contract
# ─────────────────────────────────────────────────────────────────────


class TestKISEndpointContract:
    """Codifies the KIS Open API contract relied on by
    services/kis/service.py:get_index_price / get_index_history.

    These are NOT live API tests (they don't hit KIS). They lock in the
    request shape (endpoint path + tr_id + params) so a future refactor
    cannot silently change to a non-existent endpoint without surfacing
    a test failure.
    """

    def test_get_index_price_uses_documented_endpoint(self):
        """KISService.get_index_price uses
        /uapi/domestic-stock/v1/quotations/inquire-index-price
        with tr_id=FHPUP02100000 (the only working endpoint per the
        2026-05-10 B-06 verification — alternative tr_ids returned
        404 / rt_cd!=0)."""
        from services.kis import service as kis_service

        # Verify the source declares the expected endpoint shape.
        # (We can't import _USE_REAL or call the live API, but we can
        # spot-check the source for the documented strings.)
        import inspect
        src = inspect.getsource(kis_service.KISService.get_index_price)
        assert "/uapi/domestic-stock/v1/quotations/inquire-index-price" in src, (
            "get_index_price must use the documented inquire-index-price "
            "endpoint. Alternative endpoints (FHKUP03500100, "
            "FHPUP02110100, K2I/U001 ISCDs) all failed B-06 verification."
        )
        assert "FHPUP02100000" in src, (
            "tr_id FHPUP02100000 is the only KIS index price tr_id that "
            "returned valid data in the B-06 verification."
        )
        # The 'U' division code is required for index queries (vs 'J'
        # for stocks).
        assert '"FID_COND_MRKT_DIV_CODE": "U"' in src, (
            "FID_COND_MRKT_DIV_CODE must be 'U' for index queries; 'J' "
            "is for individual stocks and returns rt_cd!=0 for indices."
        )

    def test_get_index_history_uses_documented_endpoint(self):
        """KISService.get_index_history uses
        /uapi/domestic-stock/v1/quotations/inquire-index-daily-price
        with tr_id=FHPUP02120000."""
        from services.kis import service as kis_service
        import inspect

        src = inspect.getsource(kis_service.KISService.get_index_history)
        assert (
            "/uapi/domestic-stock/v1/quotations/inquire-index-daily-price"
            in src
        ), (
            "get_index_history must use the documented "
            "inquire-index-daily-price endpoint."
        )
        assert "FHPUP02120000" in src, (
            "tr_id FHPUP02120000 is required for the daily-price endpoint."
        )

    def test_get_index_history_anchors_on_today_not_period_start(self):
        """Regression (2026-05-21): the KIS daily-index TR anchors on
        FID_INPUT_DATE_1 as the MOST-RECENT date and returns ~100 rows back
        from it. Passing the period-START date returned exactly-one-year-stale
        data (KOSPI tailed 2025-05-21 / 2,625.58 while the live quote was
        2026-05-21 / 7,815.59), which falsely tripped the is_stale cross-check
        and leaked the year-old level into the home ribbon. DATE_1 must be
        today. Verified live before this guard landed."""
        from datetime import datetime
        from unittest.mock import patch, MagicMock
        from services.kis import service as kis_service

        captured: dict = {}

        def _fake_get(url, headers=None, params=None, timeout=None):
            captured.update(params or {})
            resp = MagicMock()
            resp.ok = True
            resp.json.return_value = {
                "rt_cd": "0",
                "output2": [
                    {"stck_bsop_date": "20260521", "bstp_nmix_prpr": "7815.59"},
                ],
            }
            return resp

        svc = kis_service.KISService.__new__(kis_service.KISService)
        svc.available = True
        svc.app_key = "k"
        svc.app_secret = "s"
        svc.base_url = "https://example.invalid"

        with patch.object(kis_service.KISService, "_get_token", return_value="tok"), \
             patch.object(kis_service.requests, "get", side_effect=_fake_get):
            rows = svc.get_index_history("0001")

        today = datetime.now().strftime("%Y%m%d")
        assert captured.get("FID_INPUT_DATE_1") == today, (
            f"FID_INPUT_DATE_1 must anchor on today ({today}); got "
            f"{captured.get('FID_INPUT_DATE_1')} — a period-start value returns "
            "year-stale index history (the KOSPI 2,625 flap)."
        )
        assert rows and rows[-1]["date"] == "20260521"
