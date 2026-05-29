"""Regression test — Portfolio Segment Report multi-currency FX normalization.

Bug (C1, SHIP-BLOCKER): portfolio_segment_service.generate_for_user summed
`(end_px or avg_cost) * shares` raw across KR (KRW) and US (USD) positions
into `total_mv`, and fed the same raw `mv` into `_group_rows` for weight_pct
and weighted-return computation. A ₩75,000 KR holding was added to the same
total as a $100 US holding — over-weighting KR ~1000x in a USD-labelled
report, distorting every weight_pct, weighted return, and best/worst-segment
ranking.

Fix: `_normalize_mv` converts each position's native MV into the report
currency via `fx_service.get_rate()` (USD→KRW) before aggregation, mirroring
dividend_income_service / risk_board_service.
"""
from __future__ import annotations

from unittest.mock import patch

from services.artifacts import portfolio_segment_service as pss


# ── pure helper ───────────────────────────────────────────────────────────────

class TestNormalizeMv:
    FX = 1400.0  # USD → KRW

    def test_usd_report_kr_position_divided_by_fx(self):
        # ₩140,000,000 native → $100,000 in a USD report.
        assert pss._normalize_mv(140_000_000.0, "005930.KS", "USD", self.FX) == 100_000.0

    def test_usd_report_us_position_unchanged(self):
        assert pss._normalize_mv(5_000.0, "AAPL", "USD", self.FX) == 5_000.0

    def test_krw_report_us_position_multiplied_by_fx(self):
        # $5,000 native → ₩7,000,000 in a KRW report.
        assert pss._normalize_mv(5_000.0, "AAPL", "KRW", self.FX) == 7_000_000.0

    def test_krw_report_kr_position_unchanged(self):
        assert pss._normalize_mv(140_000_000.0, "005930.KS", "KRW", self.FX) == 140_000_000.0

    def test_kosdaq_suffix_treated_as_kr(self):
        assert pss._normalize_mv(1_400_000.0, "035720.KQ", "USD", self.FX) == 1_000.0


# ── integration: mixed book normalizes to a single numeraire ──────────────────

class TestMixedBookNormalization:
    def test_mixed_us_kr_weights_are_currency_coherent(
        self, app, make_user, add_position,
    ):
        """KR ₩140,000,000 + US $100,000 in a USD report should weight ~50/50,
        not ~99.9/0.1 (the raw-sum bug).
        """
        u = make_user(email="seg_fx@test.com", tier="premium")
        # KR: 005930.KS — 1,000 sh × ₩140,000 = ₩140,000,000 native
        add_position(user_id=u["id"], ticker="005930.KS",
                     shares=1_000.0, avg_cost=140_000.0)
        # US: AAPL — 1,000 sh × $100 = $100,000 native
        add_position(user_id=u["id"], ticker="AAPL",
                     shares=1_000.0, avg_cost=100.0)

        def fake_price_at(ticker, period_start):
            # (start_px, end_px) — end_px == avg_cost so MV is deterministic.
            if ticker == "005930.KS":
                return 140_000.0, 140_000.0
            return 100.0, 100.0

        def fake_snapshot(ticker):
            if ticker == "005930.KS":
                return {"sector": "Information Technology"}
            return {"sector": "Health Care"}

        with app.app_context(), \
                patch.object(pss, "_fx_rate", return_value=1400.0), \
                patch.object(pss, "_safe_price_at", side_effect=fake_price_at), \
                patch.object(pss, "_safe_snapshot", side_effect=fake_snapshot):
            out = pss.PortfolioSegmentService().generate_for_user(u["id"])

        # Report ccy is USD (book is mixed, not all-KR).
        assert out["portfolio_ccy"] == "USD"
        # Total MV in USD: $100,000 (KR) + $100,000 (US) = $200,000.
        assert abs(out["portfolio_value"] - 200_000.0) < 1.0, out["portfolio_value"]

        # Region rows: KR and US should each be ~50% weight.
        region_by_label = {r["label"]: r for r in out["region_rows"]}
        assert "KR" in region_by_label and "US" in region_by_label
        assert abs(region_by_label["KR"]["weight_pct"] - 50.0) < 1.0, region_by_label
        assert abs(region_by_label["US"]["weight_pct"] - 50.0) < 1.0, region_by_label
