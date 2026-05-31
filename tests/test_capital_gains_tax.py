"""tests/test_capital_gains_tax.py — pure 해외주식 양도소득세 estimator.

Covers ``services.tax.capital_gains`` in isolation: FIFO-pair → realised KRW
P&L with trade-date FX, the 250만원 기본공제, the 22% rate, KR 비과세 carve-out,
FX-miss → blank KRW (never fabricated), 손익통산 over negative lots, and
determinism. FX is injected as a deterministic mock — NO live FMP dependency.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from services.tax.capital_gains import (
    ANNUAL_BASIC_DEDUCTION_KRW,
    US_CGT_RATE,
    compute_capital_gain_lots,
    summarize_by_year,
)


# ── Helpers ──────────────────────────────────────────────────────────
def _pair(ticker, qty, buy_dt, sell_dt, buy_px, sell_px):
    """A duck-typed MatchedPair (only the attrs the estimator reads)."""
    return SimpleNamespace(
        ticker=ticker,
        quantity=qty,
        buy_time=buy_dt,
        sell_time=sell_dt,
        buy_price=buy_px,
        sell_price=sell_px,
        sell_pnl=0.0,
    )


def _fixed_fx(rate):
    """FX resolver that returns a constant rate for every date."""
    return lambda d: rate


def _date_fx(table, default=None):
    """FX resolver keyed by ISO date string; missing date → ``default``."""
    def _resolve(d):
        key = d.isoformat()[:10]
        return table.get(key, default)
    return _resolve


D = datetime  # alias


# ── Core US realised-gain math (trade-date FX) ───────────────────────
def test_us_lot_realized_pnl_uses_trade_date_fx():
    # Buy 10 @ $100 when FX=1000 → cost 1,000,000 KRW
    # Sell 10 @ $150 when FX=1200 → proceeds 1,800,000 KRW
    # realised = +800,000 KRW
    pairs = [_pair("AAPL", 10, D(2024, 1, 2), D(2024, 6, 3), 100.0, 150.0)]
    fx = _date_fx({"2024-01-02": 1000.0, "2024-06-03": 1200.0})
    lots = compute_capital_gain_lots(pairs, fx_resolver=fx)

    assert len(lots) == 1
    lot = lots[0]
    assert lot.taxable is True
    assert lot.buy_cost_krw == pytest.approx(1_000_000.0)
    assert lot.sell_proceeds_krw == pytest.approx(1_800_000.0)
    assert lot.realized_pnl_krw == pytest.approx(800_000.0)
    assert lot.attribution_year == 2024  # 양도일(SELL) 기준
    assert lot.note == ""


def test_attribution_year_is_sell_year_not_buy_year():
    pairs = [_pair("AAPL", 1, D(2023, 12, 30), D(2024, 1, 5), 100.0, 110.0)]
    lots = compute_capital_gain_lots(pairs, fx_resolver=_fixed_fx(1300.0))
    assert lots[0].attribution_year == 2024


# ── KR carve-out (비과세, never silently dropped) ─────────────────────
@pytest.mark.parametrize("ticker", ["005930.KS", "035720.KQ", "005930.ks"])
def test_kr_stock_is_non_taxable_and_surfaced(ticker):
    pairs = [_pair(ticker, 5, D(2024, 1, 2), D(2024, 3, 4), 70000.0, 80000.0)]
    lots = compute_capital_gain_lots(pairs, fx_resolver=_fixed_fx(1300.0))
    assert len(lots) == 1, "KR lot must still appear (not dropped)"
    lot = lots[0]
    assert lot.taxable is False
    assert lot.realized_pnl_krw is None
    assert "비과세" in lot.note
    # KR lots never contribute to the tax aggregate.
    summary = summarize_by_year(lots)
    assert summary == []


# ── FX miss → blank KRW, never fabricated ────────────────────────────
def test_fx_miss_on_either_leg_blanks_krw_with_note():
    # Sell-date FX missing → whole lot KRW must be None (no spot substitution).
    pairs = [_pair("AAPL", 10, D(2024, 1, 2), D(2024, 6, 3), 100.0, 150.0)]
    fx = _date_fx({"2024-01-02": 1000.0})  # 2024-06-03 absent → None
    lots = compute_capital_gain_lots(pairs, fx_resolver=fx)
    lot = lots[0]
    assert lot.taxable is True
    assert lot.sell_fx is None
    assert lot.buy_cost_krw is None
    assert lot.sell_proceeds_krw is None
    assert lot.realized_pnl_krw is None
    assert "환율" in lot.note


def test_fx_resolver_returning_zero_treated_as_miss():
    pairs = [_pair("AAPL", 1, D(2024, 1, 2), D(2024, 6, 3), 100.0, 150.0)]
    lots = compute_capital_gain_lots(pairs, fx_resolver=_fixed_fx(0.0))
    assert lots[0].realized_pnl_krw is None
    assert lots[0].buy_fx is None


def test_fx_resolver_exception_treated_as_miss():
    def _boom(_d):
        raise RuntimeError("upstream down")
    pairs = [_pair("AAPL", 1, D(2024, 1, 2), D(2024, 6, 3), 100.0, 150.0)]
    lots = compute_capital_gain_lots(pairs, fx_resolver=_boom)
    assert lots[0].realized_pnl_krw is None


def test_fx_missing_lot_excluded_from_year_aggregate_but_counted():
    good = _pair("AAPL", 10, D(2024, 1, 2), D(2024, 6, 3), 100.0, 200.0)
    bad = _pair("MSFT", 10, D(2024, 2, 2), D(2024, 7, 3), 100.0, 200.0)
    fx = _date_fx({
        "2024-01-02": 1000.0, "2024-06-03": 1000.0,  # AAPL ok
        "2024-02-02": 1000.0,                         # MSFT sell missing
    })
    lots = compute_capital_gain_lots([good, bad], fx_resolver=fx)
    summary = summarize_by_year(lots)
    assert len(summary) == 1
    yr = summary[0]
    assert yr.trade_count == 1          # only the FX-complete lot
    assert yr.fx_missing_count == 1     # the missing one disclosed
    assert yr.total_realized_pnl_krw == pytest.approx(1_000_000.0)


# ── 기본공제 250만 + 22% ──────────────────────────────────────────────
def test_basic_deduction_and_rate_above_threshold():
    # realised = +5,000,000 KRW. 과세표준 = 5,000,000 - 2,500,000 = 2,500,000.
    # tax = 2,500,000 * 0.22 = 550,000.
    pairs = [_pair("AAPL", 1, D(2024, 1, 2), D(2024, 6, 3), 0.0, 5000.0)]
    fx = _fixed_fx(1000.0)  # proceeds = 5000*1*1000 = 5,000,000; cost 0
    lots = compute_capital_gain_lots(pairs, fx_resolver=fx)
    summary = summarize_by_year(lots)
    yr = summary[0]
    assert yr.total_realized_pnl_krw == pytest.approx(5_000_000.0)
    assert yr.basic_deduction_krw == ANNUAL_BASIC_DEDUCTION_KRW == 2_500_000.0
    assert yr.taxable_base_krw == pytest.approx(2_500_000.0)
    assert yr.estimated_tax_krw == pytest.approx(550_000.0)
    assert US_CGT_RATE == 0.22


def test_gain_below_deduction_yields_zero_tax():
    # realised = +1,000,000 < 2,500,000 deduction → base 0, tax 0.
    pairs = [_pair("AAPL", 1, D(2024, 1, 2), D(2024, 6, 3), 0.0, 1000.0)]
    lots = compute_capital_gain_lots(pairs, fx_resolver=_fixed_fx(1000.0))
    yr = summarize_by_year(lots)[0]
    assert yr.taxable_base_krw == 0.0
    assert yr.estimated_tax_krw == 0.0


# ── 손익통산 (loss offsets gain, incl. negative lots) ─────────────────
def test_loss_offsets_gain_within_year():
    # Gain lot +6,000,000, loss lot -2,000,000 → net 4,000,000.
    # base = 4,000,000 - 2,500,000 = 1,500,000; tax = 330,000.
    gain = _pair("AAPL", 1, D(2024, 1, 2), D(2024, 3, 3), 0.0, 6000.0)
    loss = _pair("MSFT", 1, D(2024, 2, 2), D(2024, 4, 4), 5000.0, 3000.0)
    lots = compute_capital_gain_lots([gain, loss], fx_resolver=_fixed_fx(1000.0))
    yr = summarize_by_year(lots)[0]
    assert yr.trade_count == 2
    assert yr.total_realized_pnl_krw == pytest.approx(4_000_000.0)
    assert yr.taxable_base_krw == pytest.approx(1_500_000.0)
    assert yr.estimated_tax_krw == pytest.approx(330_000.0)


def test_net_loss_year_listed_with_zero_tax():
    # Net negative year still appears (loss context), tax 0.
    loss = _pair("AAPL", 1, D(2024, 1, 2), D(2024, 3, 3), 5000.0, 1000.0)
    lots = compute_capital_gain_lots([loss], fx_resolver=_fixed_fx(1000.0))
    yr = summarize_by_year(lots)[0]
    assert yr.total_realized_pnl_krw < 0
    assert yr.taxable_base_krw == 0.0
    assert yr.estimated_tax_krw == 0.0


def test_multiple_years_separated():
    a = _pair("AAPL", 1, D(2023, 1, 2), D(2023, 6, 3), 0.0, 4000.0)
    b = _pair("AAPL", 1, D(2024, 1, 2), D(2024, 6, 3), 0.0, 5000.0)
    lots = compute_capital_gain_lots([a, b], fx_resolver=_fixed_fx(1000.0))
    summary = summarize_by_year(lots)
    years = [y.attribution_year for y in summary]
    assert years == [2023, 2024]  # sorted ascending


# ── Determinism ──────────────────────────────────────────────────────
def test_deterministic_for_fixed_inputs():
    pairs = [
        _pair("AAPL", 3, D(2024, 1, 2), D(2024, 6, 3), 100.0, 150.0),
        _pair("005930.KS", 5, D(2024, 1, 2), D(2024, 3, 4), 70000.0, 80000.0),
        _pair("MSFT", 2, D(2024, 2, 2), D(2024, 7, 3), 200.0, 100.0),
    ]
    fx = _fixed_fx(1300.0)
    out1 = compute_capital_gain_lots(pairs, fx_resolver=fx)
    out2 = compute_capital_gain_lots(pairs, fx_resolver=fx)
    assert out1 == out2
    assert summarize_by_year(out1) == summarize_by_year(out2)


def test_empty_input_yields_empty_outputs():
    assert compute_capital_gain_lots([], fx_resolver=_fixed_fx(1300.0)) == []
    assert summarize_by_year([]) == []
