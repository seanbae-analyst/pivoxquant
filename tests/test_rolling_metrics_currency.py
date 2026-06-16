"""Regression: sector-tilt HHI must normalize KRW+USD (Pattern-7).

services/profile/rolling_metrics._sector_tilt_hhi raw-summed total_value
across currencies, so a ₩-scale KR position dominated the sector weights and
the concentration HHI was wrong for any mixed US+KR book. This pins the
currency-normalized behavior.
"""
from __future__ import annotations


def test_sector_tilt_hhi_normalizes_currency(app, monkeypatch):
    from services.profile import rolling_metrics
    import services.fx_service as fx_service
    from models import TradeHistory

    monkeypatch.setattr(fx_service, "get_rate", lambda *a, **k: 1350.0)

    # Equal ECONOMIC value in two distinct sectors: US $200 vs KR ₩270,000
    # (= $200 at 1350). Correct HHI sees ~50/50 → ~0.5. The buggy raw-sum saw
    # $200 vs ₩270,000 → KR ~99.9% weight → HHI ~0.998.
    with app.app_context():
        trades = [
            TradeHistory(ticker="AAPL", total_value=200, currency="USD", shares=1),
            TradeHistory(ticker="005930.KS", total_value=270000, currency="KRW", shares=1),
        ]
        sector_map = {"AAPL": "TECH_US", "005930.KS": "TECH_KR"}
        hhi = rolling_metrics._sector_tilt_hhi(trades, sector_map)

    assert 0.45 <= hhi <= 0.55, f"expected ~0.5 (currency-normalized), got {hhi}"
