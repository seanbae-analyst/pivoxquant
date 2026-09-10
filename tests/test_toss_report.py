"""PivoxReport maths on the OpenAPI-example fixture. Pure functions, no I/O."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from decimal import Decimal

import pytest

from services.toss.report import KST, build_report, concentration, render_markdown, summarise_holdings

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "toss", "sample_raw.json")


@pytest.fixture
def raw():
    with open(FIX, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture
def report(raw):
    return build_report(
        account=raw["account"], holdings=raw["holdings"], closed_orders=raw["closed_orders"],
        open_orders=raw["open_orders"], fx=raw["fx"], window_days=90,
        as_of=datetime.fromisoformat(raw["fetched_at"]),
    )


def test_equity_value_converts_usd_leg_at_toss_rate(report):
    # 7,200,000 KRW + 1,785 USD × 1380.5
    assert report["valuation"]["equity_value_krw"] == 7_200_000 + round(1785 * 1380.5)
    assert report["valuation"]["unrealised_rate_pct"] == pytest.approx(11.79)
    assert report["valuation"]["usd_leg"] == 1785.0


def test_holdings_sorted_by_krw_value_with_weights_summing_to_100(report):
    rows = report["holdings"]
    assert [r["symbol"] for r in rows] == ["005930", "AAPL"]
    assert sum(r["weight_pct"] for r in rows) == pytest.approx(100, abs=0.01)
    assert rows[0]["weight_pct"] > rows[1]["weight_pct"]


def test_concentration_flags_the_30pct_line(report):
    c = report["concentration"]
    assert c["positions"] == 2
    assert c["top1_pct"] == pytest.approx(74.5, abs=0.2)
    assert "005930" in c["over_30pct"] and "AAPL" not in c["over_30pct"]
    assert c["kr_pct"] + c["us_pct"] == pytest.approx(100, abs=0.01)


def test_activity_counts_fills_cancels_rejects_and_ignores_out_of_window(report):
    a = report["activity"]
    # o6 (2025-12-01) is outside the 90-day window ending 2026-03-30.
    assert a["orders_in_window"] == 5
    assert (a["fills_in"], a["fills_out"], a["cancelled"], a["rejected"]) == (2, 1, 1, 1)
    assert a["bought"] == {"KRW": 700000 + 1240000}
    assert a["sold"] == {"USD": 370.5}
    assert a["traded_krw"] == round(1_940_000 + 370.5 * 1380.5)
    assert a["most_traded"][0] == {"symbol": "005930", "fills": 2}
    assert a["traded_but_not_held"] == []           # TSLA was rejected, never filled
    assert a["held_but_untouched"] == []


def test_follow_on_buy_below_current_average_is_surfaced(report):
    fo = report["activity"]["follow_on_buys_below_avg"]
    # o2 filled at 62,000 < today's 65,000 average; o1 at 70,000 is not below.
    assert [x["fill_price"] for x in fo] == [62000.0]


def test_turnover_is_relative_to_equity_value(report):
    a, v = report["activity"], report["valuation"]
    assert a["turnover_pct_of_equity"] == pytest.approx(a["traded_krw"] / v["equity_value_krw"] * 100, rel=1e-6)


def test_account_number_is_masked_in_output(report):
    assert report["account"]["account_no_masked"] == "***8901"
    assert "12345678901" not in json.dumps(report, ensure_ascii=False)
    assert "12345678901" not in render_markdown(report)


def test_empty_holdings_and_no_orders_render_without_error():
    rep = build_report(
        account={"accountNo": "1", "accountSeq": 1, "accountType": "BROKERAGE"},
        holdings={"items": [], "totalPurchaseAmount": {"krw": "0", "usd": None}},
        closed_orders=[], open_orders=[], fx={"rate": "1300"},
        as_of=datetime(2026, 9, 10, tzinfo=KST),
    )
    assert rep["valuation"]["equity_value_krw"] == 0
    assert rep["concentration"]["positions"] == 0
    assert rep["activity"]["turnover_pct_of_equity"] is None
    md = render_markdown(rep)
    assert "보유 종목 없음" in md


def test_bad_fx_is_refused_not_silently_zeroed(raw):
    with pytest.raises(ValueError):
        build_report(account=raw["account"], holdings=raw["holdings"], closed_orders=[], open_orders=[],
                     fx={"rate": None})


def test_summarise_holdings_handles_null_usd_leg():
    h = {"items": [], "marketValue": {"amount": {"krw": "100", "usd": None}}, "totalPurchaseAmount": {"krw": "90", "usd": None},
         "profitLoss": {"amount": {"krw": "10", "usd": None}, "rate": "0.1"}, "dailyProfitLoss": {"amount": {"krw": "0", "usd": None}}}
    out = summarise_holdings(h, Decimal("1000"))
    assert out["valuation"]["equity_value_krw"] == 100
    assert concentration(out["holdings"])["positions"] == 0


def test_markdown_is_observational_and_carries_the_limits(report):
    md = render_markdown(report)
    for word in ("추천", "조언", "권유", "recommend", "advice"):
        assert word not in md
    for lim in report["limits"]:
        assert lim in md
    assert "삼성전자" in md and "Apple" in md


def test_cli_renders_from_raw_without_network(tmp_path):
    out = tmp_path / "out"
    proc = subprocess.run(
        [sys.executable, "scripts/pivox_report.py", "--from-raw", FIX, "--out", str(out), "--json"],
        capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env={**os.environ, "TOSS_CLIENT_ID": "", "TOSS_CLIENT_SECRET": ""},
    )
    assert proc.returncode == 0, proc.stderr
    rep = json.loads(proc.stdout)
    assert rep["account"]["account_no_masked"] == "***8901"
    assert (out / "pivox_report_2026-03-30.md").exists()
    assert (out / "pivox_report_2026-03-30.json").exists()
