"""FX-consistency regression — Pattern-7 (₩+$ raw sum) in artifact services.

A KR (.KS / KRW) trade's ``total_value`` / ``pnl`` is native KRW; a US trade's
is native USD. Summing them raw over-weights KR ~1000x and corrupts every
aggregate (same class as the v45.3 700× and the +52,281% equity-curve
corruptions). These tests pin the fix in five services:

    * monthly_brag_service._compute_monthly_stats   — realized return %
    * brag_card_service._compute_monthly_stats      — realized return %
    * quarterly_self_report_service._quarter_cash_flow — buys/sells/net (USD)
    * year_end_letter_service._amount_usd           — opening-value normaliser
    * kpi_dashboard_service._turnover_ratio          — turnover numerator

Each test seeds a mixed KR(.KS)+US book where the raw (buggy) sum and the
currency-normalised sum DIVERGE, then asserts the normalised result and that
the buggy value is NOT produced.

FX is pinned to 1000.0 (USD→KRW) via ``fx_service.set_rate`` for clean,
deterministic arithmetic.
"""
from __future__ import annotations

import time
from datetime import date, datetime

import pytest

from extensions import db
from models import TradeHistory, User
from services import fx_service


# Pinned spot so 1 USD == 1000 KRW exactly, for clean arithmetic.
_FX = 1000.0


@pytest.fixture
def _pin_fx(monkeypatch):
    """Pin USD/KRW to exactly 1000 for the test.

    ``set_rate`` is insufficient — the background ``init_async`` daemon thread
    fetches a live rate on app startup and can clobber the cached value
    mid-test. Monkeypatching ``get_rate`` makes the pin authoritative for every
    consumer (all services call ``fx_service.get_rate``) regardless of the
    async refresh.
    """
    monkeypatch.setattr(fx_service, "get_rate", lambda: _FX)
    yield _FX


def _mk_user() -> int:
    u = User(email=f"fxtest_{time.time()}@test.com",
             name="FX Tester", subscription_tier="premium",
             available_capital=0.0, available_capital_krw=0.0,
             birthdate=date(1990, 1, 1))
    u.set_pw("password123")
    db.session.add(u)
    db.session.commit()
    return u.id


def _seed_mixed_realized(user_id: int, when: datetime) -> None:
    """KR sells at 5% (₩) + US sells at 20% ($).

    KR: cost 1,000,000 KRW, pnl  50,000 KRW   →  5%
    US: cost     1,000 USD, pnl     200 USD   → 20%

    Normalised to KRW @1000:  pnl=50,000+200,000=250,000 ; cost=2,000,000 → 12.5%
    Raw buggy (₩+$):          pnl=50,000+200=50,200      ; cost=1,001,000 →  ~5.01%
    """
    rows = [
        # KR
        TradeHistory(user_id=user_id, ticker="005930.KS", currency="KRW",
                     action="BUY", shares=10, price_per_share=100_000,
                     total_value=1_000_000, pnl=0, traded_at=when),
        TradeHistory(user_id=user_id, ticker="005930.KS", currency="KRW",
                     action="SELL", shares=10, price_per_share=105_000,
                     total_value=1_000_000, pnl=50_000, traded_at=when),
        # US
        TradeHistory(user_id=user_id, ticker="AAPL", currency="USD",
                     action="BUY", shares=10, price_per_share=100,
                     total_value=1_000, pnl=0, traded_at=when),
        TradeHistory(user_id=user_id, ticker="AAPL", currency="USD",
                     action="SELL", shares=10, price_per_share=120,
                     total_value=1_000, pnl=200, traded_at=when),
    ]
    db.session.add_all(rows)
    db.session.commit()


# ── monthly_brag + brag_card: realized return % ──────────────────────────────

@pytest.mark.parametrize("module_path", [
    "services.artifacts.monthly_brag_service",
    "services.artifacts.brag_card_service",
])
def test_realized_return_pct_normalises_mixed_currency(app, _pin_fx, module_path):
    import importlib
    mod = importlib.import_module(module_path)
    with app.app_context():
        uid = _mk_user()
        # Mid-month so the window (any month) captures the trades regardless of
        # which month bounds the caller chose.
        when = datetime(2026, 3, 15, 12, 0, 0)
        _seed_mixed_realized(uid, when)

        stats = mod._compute_monthly_stats(
            uid, date(2026, 3, 1), date(2026, 3, 31))

    rp = stats["return_pct"]
    assert rp is not None
    # Normalised (KRW): 250,000 / 2,000,000 = 12.5%
    assert rp == pytest.approx(12.5, abs=0.2), (
        f"{module_path}: expected ~12.5% (KRW-normalised), got {rp}")
    # The buggy raw ₩+$ ratio would be ~5.01% — must NOT be produced.
    assert abs(rp - 5.01) > 1.0, (
        f"{module_path}: looks like raw ₩+$ ratio (Pattern-7) — got {rp}")


# ── quarterly: cash flow in USD numeraire ────────────────────────────────────

def test_quarter_cash_flow_normalises_to_usd(app, _pin_fx):
    from services.artifacts import quarterly_self_report_service as q
    with app.app_context():
        uid = _mk_user()
        when = datetime(2026, 2, 10, 12, 0, 0)
        # KR BUY 1,000,000 KRW (=1000 USD) + US BUY 1,000 USD → 2000 USD buys
        db.session.add_all([
            TradeHistory(user_id=uid, ticker="005930.KS", currency="KRW",
                         action="BUY", shares=10, price_per_share=100_000,
                         total_value=1_000_000, pnl=0, traded_at=when),
            TradeHistory(user_id=uid, ticker="AAPL", currency="USD",
                         action="BUY", shares=10, price_per_share=100,
                         total_value=1_000, pnl=0, traded_at=when),
        ])
        db.session.commit()

        buys, sells, net = q._quarter_cash_flow(
            uid, date(2026, 1, 1), date(2026, 3, 31), _pin_fx)

    # USD numeraire: 1000 (KR→USD) + 1000 (US) = 2000. NOT 1,001,000 (raw ₩+$).
    assert buys == pytest.approx(2000.0, abs=2.0), (
        f"expected ~2000 USD buys, got {buys}")
    assert buys < 100_000, f"raw ₩+$ leak (Pattern-7) — got {buys}"
    assert sells == pytest.approx(0.0, abs=0.01)
    assert net == pytest.approx(-buys, abs=2.0)


def test_quarter_segments_pnl_normalises_to_usd(app, _pin_fx, monkeypatch):
    """Sector pnl buckets can mix KR(₩)+US($) tickers → must normalise to USD."""
    from services.artifacts import quarterly_self_report_service as q
    # Force both tickers into one sector so the bucket genuinely mixes ₩+$.
    monkeypatch.setattr(q, "_sector_for_ticker", lambda t: "Technology")
    with app.app_context():
        uid = _mk_user()
        when = datetime(2026, 2, 10, 12, 0, 0)
        db.session.add_all([
            # KR SELL pnl 100,000 KRW (=100 USD)
            TradeHistory(user_id=uid, ticker="005930.KS", currency="KRW",
                         action="SELL", shares=1, price_per_share=100_000,
                         total_value=100_000, pnl=100_000, traded_at=when),
            # US SELL pnl 100 USD
            TradeHistory(user_id=uid, ticker="AAPL", currency="USD",
                         action="SELL", shares=1, price_per_share=100,
                         total_value=100, pnl=100, traded_at=when),
        ])
        db.session.commit()

        segs = q._segments(uid, date(2026, 1, 1), date(2026, 3, 31))

    assert len(segs) == 1
    pnl = segs[0]["pnl"]
    # USD: 100 (KR→USD) + 100 (US) = 200. NOT 100,100 (raw ₩+$).
    assert pnl == pytest.approx(200.0, abs=1.0), f"expected ~200 USD, got {pnl}"
    assert pnl < 10_000, f"raw ₩+$ leak in sector pnl (Pattern-7) — got {pnl}"


# ── year_end: _amount_usd helper ─────────────────────────────────────────────

def test_year_end_amount_usd_helper():
    from services.artifacts.year_end_letter_service import _amount_usd
    # KR (.KS) native KRW → divide by fx
    assert _amount_usd(1_000_000, "KRW", "005930.KS", 1000.0) == pytest.approx(1000.0)
    # US native USD → unchanged
    assert _amount_usd(1_000, "USD", "AAPL", 1000.0) == pytest.approx(1000.0)
    # currency column wins over ticker suffix ambiguity
    assert _amount_usd(2_000_000, "KRW", "AAPL", 1000.0) == pytest.approx(2000.0)
    # ticker suffix fallback when currency missing
    assert _amount_usd(500_000, None, "035720.KQ", 1000.0) == pytest.approx(500.0)
    # zero / bad fx never divides by zero
    assert _amount_usd(1_000_000, "KRW", "005930.KS", 0.0) == 0.0


# ── kpi_dashboard: turnover numerator matches denominator numeraire ──────────

def test_turnover_ratio_normalises_numerator_to_ccy(app, _pin_fx):
    from services.artifacts import kpi_dashboard_service as k
    from datetime import timedelta, timezone
    with app.app_context():
        uid = _mk_user()
        # Recent (within 30d) so the turnover window captures them.
        recent = (datetime.now(timezone.utc).replace(tzinfo=None)
                  - timedelta(days=3))
        # KR notional 1,000,000 KRW (=1000 USD) + US notional 1,000 USD
        db.session.add_all([
            TradeHistory(user_id=uid, ticker="005930.KS", currency="KRW",
                         action="BUY", shares=10, price_per_share=100_000,
                         total_value=1_000_000, pnl=0, traded_at=recent),
            TradeHistory(user_id=uid, ticker="AAPL", currency="USD",
                         action="SELL", shares=10, price_per_share=100,
                         total_value=1_000, pnl=0, traded_at=recent),
        ])
        db.session.commit()

        # USD numeraire: numerator = 1000 + 1000 = 2000 USD; pv = 10,000 USD.
        ratio_usd = k._turnover_ratio(uid, 10_000.0, "USD")
        # KRW numeraire: numerator = 1,000,000 + 1,000,000 = 2,000,000 KRW;
        # pv = 10,000,000 KRW.
        ratio_krw = k._turnover_ratio(uid, 10_000_000.0, "KRW")

    assert ratio_usd == pytest.approx(0.2, abs=0.01), (
        f"USD turnover expected ~0.2, got {ratio_usd}")
    # Raw ₩+$ numerator (1,001,000) / 10,000 = ~100 — must NOT happen.
    assert ratio_usd < 1.0, f"raw ₩+$ leak in numerator — got {ratio_usd}"
    assert ratio_krw == pytest.approx(0.2, abs=0.01), (
        f"KRW turnover expected ~0.2, got {ratio_krw}")
