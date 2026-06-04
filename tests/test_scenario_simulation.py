"""tests/test_scenario_simulation.py — "버그 가능 시뮬레이션, 모든 상황" (CEO 2026-06-05).

Sweeps the FE-used read endpoints across a matrix of user states and asserts that
NONE return a 5xx and NO response carries a non-finite float (NaN / Infinity) — the
two classic latent failures in untested state combinations (empty account, single
currency, multi-currency ₩+$, and pathological extreme magnitudes that overflow to
Infinity through `shares * price * fx`).

This is a discovery harness first, regression coverage second: each state is one test
so a failure names exactly "state X breaks endpoint Y".
"""
import math
from datetime import datetime

import pytest

# FE-consumed read endpoints (params-free GETs). Excludes ai/* (external Claude
# calls), auth/billing/broker mutations. 4xx is fine (missing param / empty) — we
# only flag 5xx crashes and non-finite numbers.
READ_ENDPOINTS = [
    "/api/portfolio", "/api/profile", "/api/profile/capital",
    "/api/risk/var", "/api/risk/drawdown", "/api/risk/stress-test",
    "/api/risk/component-es", "/api/risk/defense-status",
    "/api/signals", "/api/signals/herding",
    "/api/performance/ledger",
    "/api/analytics/turnover", "/api/analytics/benchmark", "/api/analytics/regime-report",
    "/api/behavior/averaging-down-mirror", "/api/behavior/concentration-mirror",
    "/api/behavior/holding-mirror", "/api/behavior/profit-loss-mirror",
    "/api/behavior/turnover-mirror",
    "/api/market/overview", "/api/market/fx", "/api/market/status",
    "/api/discover",
    "/api/artifacts/list", "/api/artifacts/stats",
    "/api/alerts", "/api/alerts/unread-count",
    "/api/growth/today", "/api/growth/weekly",
    "/api/twin/comparison", "/api/twin/portfolio", "/api/twin/trades",
    "/api/watchlist", "/api/macro", "/api/cross-asset", "/api/earnings",
]


def _bad_floats(obj, path="$"):
    out = []
    if isinstance(obj, bool):
        return out
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            out.append(path)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out += _bad_floats(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:50]):
            out += _bad_floats(v, f"{path}[{i}]")
    return out


def _sweep(client, label):
    failures = []
    for ep in READ_ENDPOINTS:
        try:
            resp = client.get(ep)
        except Exception as e:  # a route raising past the error handler = bug
            failures.append(f"{ep} → RAISED {type(e).__name__}: {e}")
            continue
        # 503 = deliberate graceful "data unavailable" (no upstream feed) — allowed.
        # 500/502/504 = true server faults → flagged as crashes.
        if resp.status_code >= 500 and resp.status_code != 503:
            failures.append(f"{ep} → {resp.status_code} {resp.get_data(as_text=True)[:140]}")
            continue
        raw = resp.get_data(as_text=True)
        if "NaN" in raw or "Infinity" in raw:
            failures.append(f"{ep} → body emits NaN/Infinity JSON token")
            continue
        data = resp.get_json(silent=True)
        if data is not None:
            bad = _bad_floats(data)
            if bad:
                failures.append(f"{ep} → non-finite float at {bad[:5]}")
    assert not failures, f"[{label}] {len(failures)} endpoint failure(s):\n  " + "\n  ".join(failures)


# ── State seeders ─────────────────────────────────────────────────────────────
def _pos(app, uid, ticker, shares, avg_cost, buy_fx=1300.0):
    from extensions import db
    from models import Position
    with app.app_context():
        db.session.add(Position(user_id=uid, ticker=ticker, shares=shares,
                                avg_cost=avg_cost, buy_fx_rate=buy_fx))
        db.session.commit()


def _trade(app, uid, ticker, action, total_value, currency, pnl=0.0, pnl_pct=0.0, when=None):
    from extensions import db
    from models.trade_history import TradeHistory
    with app.app_context():
        db.session.add(TradeHistory(
            user_id=uid, ticker=ticker, action=action, shares=1,
            price_per_share=total_value, total_value=total_value, currency=currency,
            pnl=pnl, pnl_pct=pnl_pct, traded_at=when or datetime(2026, 1, 15)))
        db.session.commit()


@pytest.fixture(autouse=True)
def _stable_fx():
    from services import fx_service
    saved = fx_service.get_rate()
    fx_service.set_rate(1300.0)
    yield
    fx_service.set_rate(saved)


# ── Scenarios ─────────────────────────────────────────────────────────────────
def test_sim_empty(client, auth_user):
    """Fresh account — every endpoint must handle zero data without a 5xx."""
    _sweep(client, "empty")


def test_sim_single_us(client, auth_user, app):
    uid = auth_user["id"]
    _pos(app, uid, "AAPL", 10, 150.0)
    _trade(app, uid, "AAPL", "BUY", 1500.0, "USD", when=datetime(2026, 1, 2))
    _trade(app, uid, "AAPL", "SELL", 1600.0, "USD", pnl=100.0, pnl_pct=6.67, when=datetime(2026, 2, 2))
    _sweep(client, "single_us")


def test_sim_single_kr(client, auth_user, app):
    uid = auth_user["id"]
    _pos(app, uid, "005930.KS", 10, 70000.0)
    _trade(app, uid, "005930.KS", "BUY", 700000.0, "KRW", when=datetime(2026, 1, 2))
    _trade(app, uid, "005930.KS", "SELL", 770000.0, "KRW", pnl=70000.0, pnl_pct=10.0, when=datetime(2026, 2, 2))
    _sweep(client, "single_kr")


def test_sim_multi_currency(client, auth_user, app):
    uid = auth_user["id"]
    _pos(app, uid, "AAPL", 10, 150.0)
    _pos(app, uid, "005930.KS", 10, 70000.0)
    _trade(app, uid, "AAPL", "BUY", 1500.0, "USD", when=datetime(2026, 1, 2))
    _trade(app, uid, "AAPL", "SELL", 1600.0, "USD", pnl=100.0, pnl_pct=6.67, when=datetime(2026, 2, 2))
    _trade(app, uid, "005930.KS", "BUY", 700000.0, "KRW", when=datetime(2026, 1, 3))
    _trade(app, uid, "005930.KS", "SELL", 770000.0, "KRW", pnl=70000.0, pnl_pct=10.0, when=datetime(2026, 2, 3))
    _sweep(client, "multi_currency")


def test_sim_extreme_values(client, auth_user, app):
    """Pathological magnitudes — guards must keep numbers finite, no Infinity."""
    uid = auth_user["id"]
    _pos(app, uid, "AAPL", 1_000_000.0, 1_000_000.0)        # 1e12 cost basis
    _pos(app, uid, "005930.KS", 0.0001, 0.0001)              # near-zero
    _trade(app, uid, "AAPL", "BUY", 1e12, "USD", when=datetime(2026, 1, 2))
    _trade(app, uid, "AAPL", "SELL", 1.1e12, "USD", pnl=1e11, pnl_pct=10.0, when=datetime(2026, 2, 2))
    _sweep(client, "extreme")
