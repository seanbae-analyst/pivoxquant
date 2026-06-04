"""tests/test_turnover_report_currency.py — F-1 regression.

CEO 2026-06-05: "합산하지 말고 환율에 맞게 KRW/USD 다르게."
`routes.performance_quant.turnover_report` + `performance_ledger` previously
raw-summed ``total_value``/``pnl`` across currencies (₩ + $) — meaningless for a
multi-currency (US + KR) ledger. The fix normalises every cross-currency aggregate
to KRW at the current USD/KRW rate (KRW passthrough; USD × rate).

These endpoints are currently dormant (no live FE consumer) but must be
currency-correct for launch hygiene / future re-wiring.
"""
from datetime import datetime

import pytest

from routes.performance_quant import _to_krw, _is_krw_ccy


@pytest.fixture(autouse=True)
def _restore_fx_rate():
    """Save/restore the module-global USD/KRW so set_rate() here never leaks
    a non-default rate into other tests in the suite."""
    from services import fx_service
    saved = fx_service.get_rate()
    yield
    fx_service.set_rate(saved)


# ── Unit: the normalisation primitive ────────────────────────────────────────
def test_is_krw_ccy_by_currency_and_ticker():
    assert _is_krw_ccy("KRW", "AAPL") is True          # explicit currency wins
    assert _is_krw_ccy("USD", "005930.KS") is True      # KR ticker suffix
    assert _is_krw_ccy("usd", "068270.KQ") is True      # KOSDAQ suffix
    assert _is_krw_ccy("USD", "AAPL") is False
    assert _is_krw_ccy(None, None) is False             # default → not KRW (USD)


def test_to_krw_passthrough_and_convert():
    rate = 1300.0
    # KRW passes through untouched
    assert _to_krw(70000, "KRW", "005930.KS", rate) == 70000
    # USD multiplied by the rate
    assert _to_krw(100, "USD", "AAPL", rate) == 130000
    # None/blank amount is safe
    assert _to_krw(None, "USD", "AAPL", rate) == 0.0
    # KR ticker with blank currency still treated as KRW (passthrough)
    assert _to_krw(500, None, "035720.KS", rate) == 500


# ── Route: performance_ledger total_pnl is KRW-normalised, never raw-mixed ────
def _seed(app, uid, rows):
    from extensions import db
    from models.trade_history import TradeHistory
    with app.app_context():
        for r in rows:
            db.session.add(TradeHistory(
                user_id=uid, ticker=r["ticker"], action=r["action"],
                shares=1, price_per_share=r["total_value"],
                total_value=r["total_value"], currency=r["currency"],
                pnl=r.get("pnl", 0.0), pnl_pct=r.get("pnl_pct", 0.0),
                traded_at=r.get("when", datetime(2026, 1, 15)),
            ))
        db.session.commit()


def test_ledger_total_pnl_normalised_to_krw(client, auth_user, app):
    from services import fx_service
    fx_service.set_rate(1300.0)
    uid = auth_user["id"]
    # US SELL pnl=$100, KR SELL pnl=₩10,000.
    _seed(app, uid, [
        {"ticker": "AAPL", "action": "SELL", "currency": "USD",
         "total_value": 110.0, "pnl": 100.0, "pnl_pct": 10.0},
        {"ticker": "005930.KS", "action": "SELL", "currency": "KRW",
         "total_value": 77000.0, "pnl": 10000.0, "pnl_pct": 5.0},
    ])

    resp = client.get("/api/performance/ledger?period=all")
    assert resp.status_code == 200, resp.data
    data = resp.get_json()

    assert data["currency"] == "KRW"
    # KRW-normalised: $100 × 1300 + ₩10,000 = 140,000.  Raw-mixed bug = 10,100.
    assert data["total_pnl"] == pytest.approx(140000.0, abs=1.0)
    assert data["gross_gains"] == pytest.approx(140000.0, abs=1.0)


# ── Route: turnover handles a mixed-currency ledger without crashing ──────────
def test_turnover_mixed_currency_smoke(client, auth_user, app):
    from services import fx_service
    fx_service.set_rate(1300.0)
    uid = auth_user["id"]
    _seed(app, uid, [
        {"ticker": "AAPL", "action": "BUY", "currency": "USD", "total_value": 100.0,
         "when": datetime(2026, 1, 2)},
        {"ticker": "AAPL", "action": "SELL", "currency": "USD", "total_value": 110.0,
         "pnl": 10.0, "pnl_pct": 10.0, "when": datetime(2026, 2, 2)},
        {"ticker": "005930.KS", "action": "BUY", "currency": "KRW", "total_value": 70000.0,
         "when": datetime(2026, 1, 3)},
        {"ticker": "005930.KS", "action": "SELL", "currency": "KRW", "total_value": 77000.0,
         "pnl": 7000.0, "pnl_pct": 10.0, "when": datetime(2026, 2, 3)},
    ])

    resp = client.get("/api/analytics/turnover?period=all")
    assert resp.status_code == 200, resp.data
    data = resp.get_json()

    assert data["currency"] == "KRW"
    # Finite, non-negative — the raw ₩+$ mix used to produce a garbage ratio.
    assert data["annualized_turnover_pct"] >= 0
    assert data["estimated_annual_cost_pct"] >= 0
