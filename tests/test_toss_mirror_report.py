"""PivoxReport v2 — history reconstruction, reconciliation, and the mirrors,
on a fixture whose book reconciles to the holdings payload exactly."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from datetime import datetime
from decimal import Decimal

import pytest

from services.toss.history import fills_from_orders, reconcile, reconstruct
from services.toss.mirror_report import build_mirror_report, render_mirror_markdown
from services.toss.report import KST

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "toss", "sample_raw_history.json")


@pytest.fixture
def raw():
    with open(FIX, encoding="utf-8") as fh:
        return json.load(fh)


def _build(raw):
    return build_mirror_report(
        account=raw["account"], holdings=raw["holdings"], closed_orders=raw["closed_orders"],
        open_orders=raw["open_orders"], fx=raw["fx"], history_since=raw["history_since"],
        window_days=90, names=raw["names"], prices=raw.get("prices"), as_of=datetime.fromisoformat(raw["fetched_at"]),
    )


# ── history ──────────────────────────────────────────────────────────────────
def test_fills_are_chronological_and_skip_unfilled_records(raw):
    fills = fills_from_orders(raw["closed_orders"])
    assert [f.order_id for f in fills] == ["o1", "o2", "o4", "o3", "o5", "o6", "o7", "o8", "o9"]  # o4 (01-15) precedes o3 (01-20)
    assert all(f.quantity > 0 for f in fills)


def test_average_cost_walk_matches_toss_to_the_won(raw):
    book = reconstruct(fills_from_orders(raw["closed_orders"]))
    p = book["005930"]
    # 10@60000 + 10@70000 → 65,000; sell 8 leaves 12@65,000; +3@62,000 → 966,000 / 15 = 64,400
    assert p.quantity == Decimal(15) and p.average_cost == Decimal("64400")
    assert p.buys == 3 and p.sells == 1
    assert p.opened_at.date().isoformat() == "2025-10-01"
    sell = p.sell_outcomes[0]
    assert sell.avg_cost_before == Decimal("65000")
    assert sell.realised_gross == Decimal("56000") and sell.realised_net == Decimal("53984")
    assert sell.pnl_pct == pytest.approx(10.77, abs=0.01)
    assert sell.held_days == pytest.approx(155, abs=1)


def test_follow_on_buys_are_classified_against_the_average_at_that_instant(raw):
    book = reconstruct(fills_from_orders(raw["closed_orders"]))
    rel = [(b.fill.order_id, b.follow_on, b.relation) for b in book["005930"].buy_outcomes]
    assert rel == [("o1", False, None), ("o5", True, "above"), ("o9", True, "below")]


def test_full_liquidation_resets_the_position(raw):
    book = reconstruct(fills_from_orders(raw["closed_orders"]))
    nvda = book["NVDA"]
    assert nvda.quantity == 0 and nvda.opened_at is None and nvda.average_cost is None
    assert nvda.sell_outcomes[0].pnl_pct == pytest.approx(-16.67, abs=0.01)


def test_reconcile_passes_when_the_book_equals_the_holdings(raw):
    book = reconstruct(fills_from_orders(raw["closed_orders"]))
    r = reconcile(book, raw["holdings"]["items"])
    assert r == {"complete": True, "checked": 2, "mismatches": []}


def test_reconcile_names_the_symbol_when_history_starts_too_late(raw):
    orders = [o for o in raw["closed_orders"] if o["orderId"] != "o1"]   # lose the first 삼성전자 buy
    book = reconstruct(fills_from_orders(orders))
    r = reconcile(book, raw["holdings"]["items"])
    assert r["complete"] is False
    syms = {m["symbol"] for m in r["mismatches"]}
    assert syms == {"005930"}
    assert "수량 불일치" in r["mismatches"][0]["reason"]


def test_reconcile_flags_a_symbol_held_but_absent_from_history(raw):
    book = reconstruct(fills_from_orders([o for o in raw["closed_orders"] if o["symbol"] != "AAPL"]))
    r = reconcile(book, raw["holdings"]["items"])
    assert [m["symbol"] for m in r["mismatches"]] == ["AAPL"]
    assert "이력에 이 종목의 체결이 없음" in r["mismatches"][0]["reason"]


# ── report ───────────────────────────────────────────────────────────────────
def test_realised_total_is_the_fee_adjusted_sum_in_krw(raw):
    rep = _build(raw)
    # 삼성전자 +53,984 · NAVER +38,460 · NVDA −100.5 USD × 1380.5 = −138,740
    assert rep["history"]["complete"] is True
    assert rep["history"]["realised_net_krw"] == pytest.approx(53984 + 38460 - 138740, abs=1)


def test_recent_window_keeps_the_full_history_cost_basis(raw):
    m = _build(raw)["mirrors"]
    w, a = m["window"], m["all"]
    # 90 days back from 2026-09-10: the 07-01 NAVER sell and the 08-06 삼성전자 add. The add is a
    # follow-on below the 65,000 average even though its first lot is outside the window.
    assert (w["turnover"]["buy_count"], w["turnover"]["sell_count"]) == (1, 1)
    assert (w["follow_on"]["follow_on_count"], w["follow_on"]["below_avg_count"]) == (1, 1)
    assert w["profit_loss"]["take_profit"]["count"] == 1 and w["profit_loss"]["stop_loss"] is None
    # Whole history: the product's own functions.
    assert (a["turnover"]["buy_count"], a["turnover"]["sell_count"]) == (6, 3)
    assert (a["follow_on"]["below_avg_count"], a["follow_on"]["above_avg_count"]) == (1, 1)
    assert a["profit_loss"]["take_profit"]["count"] == 2 and a["profit_loss"]["stop_loss"]["count"] == 1


def test_holdings_carry_their_history_and_departed_carry_realised(raw):
    rep = _build(raw)
    by = {h["symbol"]: h for h in rep["holdings"]}
    assert by["005930"]["opened_at"] == "2025-10-01" and by["005930"]["buys"] == 3 and by["005930"]["rebuilt_avg"] == 64400
    assert by["AAPL"]["held_days"] == 238 or by["AAPL"]["held_days"] == 237
    dep = {d["symbol"]: d for d in rep["departed"]}
    assert set(dep) == {"NVDA", "035420"}
    assert dep["035420"]["name"] == "NAVER" and dep["035420"]["realised_net_krw"] == 38460
    assert dep["NVDA"]["realised_net"] == -100.5


def test_incomplete_history_is_said_in_the_first_lines(raw):
    r2 = copy.deepcopy(raw)
    r2["closed_orders"] = [o for o in r2["closed_orders"] if o["orderId"] != "o1"]
    rep = _build(r2)
    md = render_mirror_markdown(rep)
    assert rep["history"]["complete"] is False
    assert "종목에서 다르다" in md and "005930" in md.split("## 평가")[0]
    assert "부분" in rep["history"]["realised_scope"]


def test_markdown_has_no_grading_vocabulary_and_no_index(raw):
    md = render_mirror_markdown(_build(raw))
    for word in ("추천", "조언", "권유", "recommend", "advice", "물타기", "HHI", "회전율", "과잉", "편향", "처분효과", "점수"):
        assert word not in md, word
    assert "토스 잔고와 전부 일치" in md
    assert "삼성전자 (005930)" in md and "엔비디아 (NVDA)" in md
    assert "12345678901" not in md


def test_cli_renders_v2_from_raw_without_network(tmp_path):
    out = tmp_path / "out"
    proc = subprocess.run(
        [sys.executable, "scripts/pivox_report.py", "--from-raw", FIX, "--out", str(out), "--json"],
        capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env={**os.environ, "TOSS_CLIENT_ID": "", "TOSS_CLIENT_SECRET": "", "RUN_SCHEDULER": "0", "POPULATE_CACHE_ON_BOOT": "0"},
    )
    assert proc.returncode == 0, proc.stderr
    rep = json.loads(proc.stdout)
    assert rep["version"] == 2 and rep["history"]["complete"] is True
    assert (out / "pivox_report_2026-09-10.md").exists()


def test_analysis_numbers_follow_from_the_book(raw):
    an = _build(raw)["analysis"]
    t, a, af = an["trades"], an["attribution"], an["after_selling"]
    assert (t["closed"], t["wins"], t["losses"], t["win_rate_pct"]) == (3, 2, 1, 66.7)
    assert t["expectancy_krw"] == round((53984 + 38460 - 138740) / 3)
    assert t["top5_share_pct"] == 100.0                     # two wins, both in the top five
    assert a["total_krw"] == a["realised_krw"] + a["unrealised_krw"]
    assert [r["symbol"] for r in a["bottom"]] == ["NVDA"]   # only symbols that lost money
    assert a["top"][0]["name"] == "Apple Inc."
    # After selling: NVDA sold at 100, now 130 → 5 shares × 30 × 1380.5; NAVER sold 220,000, now 210,000
    by = {r["symbol"]: r for r in af["rows"]}
    assert by["NVDA"]["since_sale_pct"] == 30.0 and by["NVDA"]["kept_delta_krw"] == 5 * 30 * 1380.5
    assert by["035420"]["kept_delta_krw"] == -20000
    assert af["kept_delta_krw"] == by["NVDA"]["kept_delta_krw"] + by["035420"]["kept_delta_krw"]
    assert len(an["headline"]) == 3 and all("₩" in h or "%" in h for h in an["headline"])


def test_analysis_without_prices_skips_after_selling_instead_of_guessing(raw):
    r2 = copy.deepcopy(raw)
    r2["prices"] = {}
    rep = build_mirror_report(
        account=r2["account"], holdings=r2["holdings"], closed_orders=r2["closed_orders"], open_orders=[],
        fx=r2["fx"], history_since=r2["history_since"], names=r2["names"], prices={},
        as_of=datetime.fromisoformat(r2["fetched_at"]),
    )
    assert rep["analysis"]["after_selling"] == {"available": False, "rows": []}
    assert "현재가를 받지 못해" in render_mirror_markdown(rep)


def test_asymmetry_phrase_never_reports_a_ratio_below_one():
    from services.toss.analysis import asymmetry_phrase
    assert asymmetry_phrase(3.2) == "손실 쪽이 3.2배 길다"
    assert asymmetry_phrase(0.5) == "이익 쪽이 2.0배 길다"
