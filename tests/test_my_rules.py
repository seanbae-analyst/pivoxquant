"""tests/test_my_rules.py — 내 규칙 (services/profile/my_rules.py).

Pins: every line comes from the user's own onboarding bucket; counts come
from their own rows only (registration rows and seed lots never count);
"this month" is the KST calendar month; fills waiting in the import inbox
count toward the month and are named as such; the −10% answer is shown but
never counted; the payload carries no score / grade / label words and is a
no-op for the legal scrub.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

from services.profile.my_rules import (
    compute_my_rules,
    frequency_ceiling,
    kst_month,
    kst_month_start_utc,
    month_fill_count,
)

# 2026-10-14 03:00 UTC = 2026-10-14 12:00 KST.
NOW = datetime(2026, 10, 14, 3, 0, 0)

ANSWERS = {
    "declared_holding": "weeks",          # 7~30일
    "declared_frequency": "few",          # ≤ 5 / month
    "declared_positions": "focused",      # 4~8
    "declared_drawdown_response": "hold",
    "record_habit": "sometimes",
}

_ids = iter(range(1, 10_000))


def _t(action, at, ticker="AAA", shares=1.0, price=100.0, source=None):
    return SimpleNamespace(
        id=next(_ids), ticker=ticker, action=action, shares=shares,
        price_per_share=price, pnl=0.0, pnl_pct=0.0, traded_at=at, source=source,
    )


def _item(payload, rule_id):
    return next(i for i in payload["items"] if i["id"] == rule_id)


# ── availability ─────────────────────────────────────────────────────────

def test_no_v3_answers_means_no_rules():
    out = compute_my_rules({}, [], 0, NOW)
    assert out["available"] is False and out["items"] == []
    assert compute_my_rules(None, [], 3, NOW)["available"] is False


def test_lines_come_from_the_users_own_buckets():
    out = compute_my_rules(ANSWERS, [], 6, NOW)
    assert [i["id"] for i in out["items"]] == ["frequency", "holding", "positions", "drawdown"]
    assert _item(out, "frequency")["line"] == "한 달에 매수·매도 5번 이하"
    assert "7~30일" in _item(out, "holding")["line"]
    assert _item(out, "positions")["line"] == "동시에 4~8종목을 들고 있다"
    assert _item(out, "drawdown")["line"] == "한 주에 10% 빠지면 그냥 둔다"


def test_frequency_ceiling_is_the_top_of_the_bucket():
    assert frequency_ceiling({"declared_frequency": "rare"}) == 2
    assert frequency_ceiling({"declared_frequency": "moderate"}) == 15
    assert frequency_ceiling({"declared_frequency": "daily"}) is None
    assert frequency_ceiling({}) is None
    assert frequency_ceiling(None) is None


# ── frequency ────────────────────────────────────────────────────────────

def test_this_month_over_the_line_is_outside():
    fills = [_t("BUY", NOW - timedelta(days=d)) for d in range(6)]   # 6 fills, Oct 9–14
    f = _item(compute_my_rules(ANSWERS, fills, 6, NOW), "frequency")
    assert f["this_month"] == 6 and f["ceiling"] == 5
    assert f["status"] == "outside"
    assert f["observed"] == "이번 달 6번 · 선 5번"
    assert f["months"][-1] == {"month": "2026-10", "count": 6, "over": True, "partial": True}


def test_at_the_line_is_within():
    fills = [_t("SELL", NOW - timedelta(days=d)) for d in range(5)]
    assert _item(compute_my_rules(ANSWERS, fills, 6, NOW), "frequency")["status"] == "within"


def test_registration_rows_are_not_fills():
    rows = [_t("BUY", NOW, source="holding_seed") for _ in range(9)]
    rows += [_t("SELL", NOW, source="holding_adjust") for _ in range(9)]
    f = _item(compute_my_rules(ANSWERS, rows, 6, NOW), "frequency")
    assert f["this_month"] == 0 and f["status"] == "within"


def test_month_is_the_kst_calendar_month():
    # 2026-09-30 16:00 UTC is 2026-10-01 01:00 KST → October.
    edge = datetime(2026, 9, 30, 16, 0)
    assert kst_month(edge) == "2026-10"
    assert kst_month(datetime(2026, 9, 30, 14, 59)) == "2026-09"
    assert kst_month_start_utc(NOW) == datetime(2026, 9, 30, 15, 0)
    f = _item(compute_my_rules(ANSWERS, [_t("BUY", edge)], 6, NOW), "frequency")
    assert f["this_month"] == 1


def test_series_starts_at_the_first_recorded_month_and_keeps_six():
    # First fill in March: Mar..Oct is 8 months → the newest 6 are shown.
    rows = [_t("BUY", datetime(2026, 3, 10)), _t("BUY", datetime(2026, 8, 10))]
    rows += [_t("BUY", datetime(2026, 8, 11 + i)) for i in range(5)]   # Aug: 6 fills
    f = _item(compute_my_rules(ANSWERS, rows, 6, NOW), "frequency")
    assert [m["month"] for m in f["months"]] == [
        "2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10",
    ]
    aug = next(m for m in f["months"] if m["month"] == "2026-08")
    assert aug["count"] == 6 and aug["over"] is True and aug["partial"] is False
    assert f["months_over"] == 1


def test_no_fills_shows_only_the_current_month():
    f = _item(compute_my_rules(ANSWERS, [], 6, NOW), "frequency")
    assert [m["month"] for m in f["months"]] == ["2026-10"]
    assert f["status"] == "within"


def test_waiting_inbox_fills_count_and_are_named():
    fills = [_t("BUY", NOW - timedelta(days=1)) for _ in range(4)]
    pending = [NOW, NOW - timedelta(hours=1), datetime(2026, 9, 2)]   # 2 this month
    f = _item(compute_my_rules(ANSWERS, fills, 6, NOW, pending), "frequency")
    assert f["this_month"] == 6 and f["waiting"] == 2
    assert f["status"] == "outside"
    assert "승인 대기 2번 포함" in f["observed"]
    assert month_fill_count(fills, pending, NOW) == 6


def test_forty_plus_has_no_line_to_cross():
    answers = dict(ANSWERS, declared_frequency="daily")
    f = _item(compute_my_rules(answers, [_t("BUY", NOW)] * 3, 6, NOW), "frequency")
    assert f["status"] == "no_line" and f["ceiling"] is None


# ── holding ──────────────────────────────────────────────────────────────

def _round_trip(days_held, sold_days_ago, ticker):
    sold = NOW - timedelta(days=sold_days_ago)
    return [_t("BUY", sold - timedelta(days=days_held), ticker=ticker), _t("SELL", sold, ticker=ticker)]


def test_each_sell_is_placed_against_the_declared_range():
    rows = _round_trip(2, 5, "A") + _round_trip(10, 5, "B") + _round_trip(20, 5, "C")
    rows += _round_trip(60, 5, "D")
    h = _item(compute_my_rules(ANSWERS, rows, 6, NOW), "holding")
    assert (h["sells"], h["shorter"], h["within"], h["longer"]) == (4, 1, 2, 1)
    assert h["status"] == "outside"
    assert h["observed"] == "최근 90일 매도 4번 중 선 안 2번 · 더 일찍 1번 · 더 오래 1번"


def test_all_sells_in_range_is_within():
    rows = _round_trip(8, 3, "A") + _round_trip(29, 3, "B")
    assert _item(compute_my_rules(ANSWERS, rows, 6, NOW), "holding")["status"] == "within"


def test_sells_outside_the_window_and_seed_lots_do_not_count():
    rows = _round_trip(2, 120, "OLD")                                   # sold 120 days ago
    seed_at = NOW - timedelta(days=1)
    rows += [_t("BUY", seed_at, ticker="SEED", source="holding_seed"), _t("SELL", NOW, ticker="SEED")]
    h = _item(compute_my_rules(ANSWERS, rows, 6, NOW), "holding")
    assert h["sells"] == 0 and h["status"] == "no_data"


def test_years_has_no_upper_edge():
    answers = dict(ANSWERS, declared_holding="years")
    rows = _round_trip(800, 2, "A")
    h = _item(compute_my_rules(answers, rows, 6, NOW), "holding")
    assert h["hi_days"] is None and h["within"] == 1 and h["status"] == "within"


# ── positions ────────────────────────────────────────────────────────────

def test_positions_within_under_over_and_unregistered():
    def pos(n):
        return _item(compute_my_rules(ANSWERS, [], n, NOW), "positions")

    assert pos(6)["status"] == "within" and pos(6)["side"] is None
    assert (pos(2)["status"], pos(2)["side"]) == ("outside", "under")
    assert (pos(12)["status"], pos(12)["side"]) == ("outside", "over")
    assert pos(0)["status"] == "no_data"


def test_broad_has_no_upper_edge():
    answers = dict(ANSWERS, declared_positions="broad")
    p = _item(compute_my_rules(answers, [], 40, NOW), "positions")
    assert p["status"] == "within" and p["line"] == "동시에 25종목 이상 들고 있다"


# ── drawdown ─────────────────────────────────────────────────────────────

def test_drawdown_line_is_shown_but_never_counted():
    d = _item(compute_my_rules(ANSWERS, [], 6, NOW), "drawdown")
    assert d["measurable"] is False and d["status"] == "not_counted"


# ── summary + legal posture ──────────────────────────────────────────────

def test_summary_counts_only_measured_lines():
    fills = [_t("BUY", NOW - timedelta(days=d), ticker=f"T{d}") for d in range(7)]   # over 5
    out = compute_my_rules(ANSWERS, fills, 6, NOW)
    # frequency (outside) + positions (within); holding has no sells, drawdown not counted.
    assert out["counted"] == 2 and out["outside"] == 1


def test_no_score_grade_or_label_words_and_scrub_is_a_no_op():
    from services.legal_filter import scrub_response

    rows = _round_trip(2, 5, "A") + [_t("BUY", NOW) for _ in range(7)]
    out = compute_my_rules(ANSWERS, rows, 12, NOW, [NOW])
    blob = json.dumps(out, ensure_ascii=False).lower()
    # /api/mirror-home's own invariant (tests/test_mirror_home.py) bans these
    # substrings anywhere in the payload this block is embedded in.
    for word in ("speculator", "daytrader", "value", "quant", "beginner"):
        assert word not in blob
    for word in ("score", "grade", "점수", "등급", "추천", "조언", "위반", "지키세요"):
        assert word not in blob
    assert scrub_response(out) == out
