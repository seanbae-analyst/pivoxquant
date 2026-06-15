"""Regression: weekly twin return must normalize KRW+USD (Pattern-7).

Before the 2026-06-15 fix, services/twin/twin_reporter._compute_twin_return
raw-summed mixed-currency SELLs, so a single ₩-scale position dominated the
percentage and a large US-dollar gain was lost. This pins the
currency-normalized behavior (the user leg + lifetime path already had it).
"""
from __future__ import annotations

from datetime import date, datetime


def test_weekly_twin_return_normalizes_mixed_currency(app, make_user, monkeypatch):
    from extensions import db
    from models import AITwinPortfolio, AITwinTrade
    from services.twin import twin_reporter
    import services.fx_service as fx_service

    # Deterministic FX so the assertion does not depend on a live rate.
    monkeypatch.setattr(fx_service, "get_rate", lambda *a, **k: 1350.0)

    user = make_user(email="twinfx@test.com")
    week_ending = date(2026, 6, 14)
    executed = datetime(2026, 6, 12, 10, 0, 0)  # inside [week_ending-6d, +1d)

    with app.app_context():
        twin = AITwinPortfolio(user_id=user["id"], persona_at_init="balanced")
        db.session.add(twin)
        db.session.commit()
        # US SELL — proceeds $300, pnl +$100 → cost $200 → +50%.
        db.session.add(AITwinTrade(
            twin_id=twin.id, ticker="AAPL", side="SELL",
            shares=10, price=30, pnl_at_close=100, executed_at=executed,
        ))
        # KR SELL — proceeds ₩77,000, pnl +₩3,500 → cost ₩73,500 → ~+4.8%.
        db.session.add(AITwinTrade(
            twin_id=twin.id, ticker="005930.KS", side="SELL",
            shares=10, price=7700, pnl_at_close=3500, executed_at=executed,
        ))
        db.session.commit()

        pct, n = twin_reporter._compute_twin_return(user["id"], week_ending)

    assert n == 2
    # Currency-normalized: cost-weighted in one base (KRW), the +50% US leg
    # dominates. The old raw-sum gave ~4.9% (the ₩-magnitude KR cost swamped
    # the US gain). >30% proves the legs were normalized before summing.
    assert pct is not None and pct > 30.0
