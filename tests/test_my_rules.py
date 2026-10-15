"""tests/test_my_rules.py — 내 규칙 (services/profile/my_rules.py).

Pins: every line comes from the user's own onboarding bucket; each line is
crossed in ONE direction only (more trades, sooner sells, fewer names — doing
less is never 선 밖); counts come from their own rows only (registration rows
and seed lots never count); "this month" is the KST calendar month; fills
waiting in the import inbox count toward the month and are named as such; the
−10% answer is shown but never counted; ``confirmed`` follows
``rules_confirmed_at`` and, once set, only records from then on are counted;
holds are KST calendar days; the payload carries no score / grade / label
words and is a no-op for the legal scrub.
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
    rule_answers_changed,
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
    assert _item(out, "holding")["line"] == "7일 이상 들고 있다가 판다"
    assert _item(out, "positions")["line"] == "4종목 이상 나눠 담는다"
    assert _item(out, "drawdown")["line"] == "한 주에 10% 빠지면 그냥 둔다"


def test_confirmed_follows_rules_confirmed_at():
    out = compute_my_rules(ANSWERS, [], 6, NOW)
    assert out["confirmed"] is False and out["confirmed_at"] is None and out["confirmed_on"] is None
    # 2026-10-13 16:30 UTC = 2026-10-14 01:30 KST → adopted on the 14th (KST).
    at = datetime(2026, 10, 13, 16, 30)
    out = compute_my_rules(ANSWERS, [], 6, NOW, confirmed_at=at)
    assert out["confirmed"] is True
    assert out["confirmed_at"] == "2026-10-13T16:30:00"
    assert out["confirmed_on"] == "2026-10-14"
    # Nothing to adopt → never "confirmed", whatever the column says.
    assert compute_my_rules({}, [], 6, NOW, confirmed_at=at)["confirmed"] is False


def test_rule_answers_changed_ignores_the_record_habit_question():
    assert rule_answers_changed(ANSWERS, dict(ANSWERS, record_habit="never")) is False
    assert rule_answers_changed(ANSWERS, dict(ANSWERS, declared_frequency="moderate")) is True
    assert rule_answers_changed({}, ANSWERS) is True
    assert rule_answers_changed(None, None) is False


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


# ── adopted lines count from the adoption on (2026-10-15) ────────────────

# 2026-10-13 23:00 UTC = 2026-10-14 08:00 KST — adopted this morning.
ADOPTED = datetime(2026, 10, 13, 23, 0)


def test_fills_before_the_adoption_are_not_past_the_line():
    """The card says "2026-10-14부터" — six fills earlier this month must not
    make the line the user drew today read 선 밖."""
    before = [_t("BUY", datetime(2026, 10, d, 3, 0)) for d in range(1, 7)]
    after = [_t("SELL", NOW)]
    preview = _item(compute_my_rules(ANSWERS, before + after, 6, NOW), "frequency")
    assert preview["this_month"] == 7 and preview["status"] == "outside"      # unchanged
    f = _item(compute_my_rules(ANSWERS, before + after, 6, NOW, confirmed_at=ADOPTED), "frequency")
    assert f["this_month"] == 1 and f["status"] == "within"
    assert f["observed"] == "선을 정한 뒤 이번 달 1번 · 선 5번"
    assert month_fill_count(before + after, [], NOW, since=ADOPTED) == 1


def test_months_before_the_adoption_leave_the_series():
    rows = [_t("BUY", datetime(2026, 8, 10 + i)) for i in range(9)]           # Aug: 9 > 5
    rows += [_t("BUY", datetime(2026, 9, 20, 3, 0))]
    adopted = datetime(2026, 9, 15, 3, 0)
    f = _item(compute_my_rules(ANSWERS, rows, 6, NOW, confirmed_at=adopted), "frequency")
    assert [m["month"] for m in f["months"]] == ["2026-09", "2026-10"]
    assert f["months_over"] == 0
    assert f["observed"] == "이번 달 0번 · 선 5번"                          # adopted last month


def test_a_date_only_fill_on_the_adoption_day_counts():
    """00:00 = typed with a date only; the KST same-day rule
    (pre_trade.friction_outcome._at_or_after) keeps it."""
    rows = [_t("BUY", datetime(2026, 10, 14, 0, 0)), _t("BUY", datetime(2026, 10, 13, 0, 0))]
    pending = [datetime(2026, 10, 14, 0, 0), datetime(2026, 10, 13, 22, 0)]  # 2nd: before
    f = _item(compute_my_rules(ANSWERS, rows, 6, NOW, pending, confirmed_at=ADOPTED), "frequency")
    assert f["this_month"] == 2 and f["waiting"] == 1


def test_sells_before_the_adoption_do_not_count_for_holding():
    rows = _round_trip(2, 5, "EARLY")                                  # sooner, but before
    rows += _round_trip(10, 0, "LATE")
    h = _item(compute_my_rules(ANSWERS, rows, 6, NOW, confirmed_at=ADOPTED), "holding")
    assert (h["sells"], h["sooner"], h["status"]) == (1, 0, "within")
    assert h["observed"] == "선을 정한 뒤 매도 1번 · 모두 7일 이상 들고 있다가 팔았어요"
    none_yet = compute_my_rules(ANSWERS, _round_trip(2, 5, "EARLY"), 6, NOW, confirmed_at=ADOPTED)
    assert _item(none_yet, "holding")["observed"] == "선을 정한 뒤 매도 기록 없음"
    # Adopted before the 90-day window: the window is the cut, as before.
    old = compute_my_rules(ANSWERS, rows, 6, NOW, confirmed_at=NOW - timedelta(days=200))
    assert _item(old, "holding")["observed"].startswith("최근 90일 매도 2번")


# ── holding ──────────────────────────────────────────────────────────────

def _round_trip(days_held, sold_days_ago, ticker):
    sold = NOW - timedelta(days=sold_days_ago)
    return [_t("BUY", sold - timedelta(days=days_held), ticker=ticker), _t("SELL", sold, ticker=ticker)]


def test_only_selling_sooner_than_the_minimum_crosses_the_line():
    rows = _round_trip(2, 5, "A") + _round_trip(10, 5, "B") + _round_trip(20, 5, "C")
    rows += _round_trip(60, 5, "D")                                     # held longer: not 선 밖
    h = _item(compute_my_rules(ANSWERS, rows, 6, NOW), "holding")
    assert (h["sells"], h["sooner"], h["min_days"]) == (4, 1, 7.0)
    assert h["status"] == "outside"
    assert h["observed"] == "최근 90일 매도 4번 · 7일 전에 판 것 1번"


def test_holding_longer_than_said_is_within():
    rows = _round_trip(8, 3, "A") + _round_trip(400, 3, "B")
    h = _item(compute_my_rules(ANSWERS, rows, 6, NOW), "holding")
    assert h["status"] == "within"
    assert h["observed"] == "최근 90일 매도 2번 · 모두 7일 이상 들고 있다가 팔았어요"


def test_sells_outside_the_window_and_seed_lots_do_not_count():
    rows = _round_trip(2, 120, "OLD")                                   # sold 120 days ago
    seed_at = NOW - timedelta(days=1)
    rows += [_t("BUY", seed_at, ticker="SEED", source="holding_seed"), _t("SELL", NOW, ticker="SEED")]
    h = _item(compute_my_rules(ANSWERS, rows, 6, NOW), "holding")
    assert h["sells"] == 0 and h["status"] == "no_data"


def test_hold_is_counted_in_kst_calendar_days():
    """2026-10-15: "하루 안에 정리 / 며칠" is the same KST day vs a later one.
    A 14:00 buy sold at 10:00 next morning (20h) used to be "1일 전에 판 것"."""
    days = dict(ANSWERS, declared_holding="days")
    # Bought 2026-10-12 14:00 KST (05:00 UTC), sold 2026-10-13 10:00 KST (01:00 UTC).
    overnight = [_t("BUY", datetime(2026, 10, 12, 5, 0), ticker="O"),
                 _t("SELL", datetime(2026, 10, 13, 1, 0), ticker="O")]
    h = _item(compute_my_rules(days, overnight, 6, NOW), "holding")
    assert h["line"] == "산 날을 넘겨 들고 있다가 판다"
    assert (h["sooner"], h["status"]) == (0, "within")
    assert h["observed"] == "최근 90일 매도 1번 · 모두 산 날을 넘겨 들고 있다가 팔았어요"
    # Bought 09:30 KST, sold 15:00 KST the same day — under the line.
    same_day = [_t("BUY", datetime(2026, 10, 12, 0, 30), ticker="S"),
                _t("SELL", datetime(2026, 10, 12, 6, 0), ticker="S")]
    h = _item(compute_my_rules(days, same_day, 6, NOW), "holding")
    assert (h["sooner"], h["status"]) == (1, "outside")
    assert h["observed"] == "최근 90일 매도 1번 · 산 날 판 것 1번"
    # 7일: 10-01 14:00 KST → 10-08 10:00 KST is 7 calendar days (6.8 × 24h).
    week = [_t("BUY", datetime(2026, 10, 1, 5, 0), ticker="W"),
            _t("SELL", datetime(2026, 10, 8, 1, 0), ticker="W")]
    assert _item(compute_my_rules(ANSWERS, week, 6, NOW), "holding")["status"] == "within"


def test_intraday_has_no_minimum_to_fall_under():
    answers = dict(ANSWERS, declared_holding="intraday")
    h = _item(compute_my_rules(answers, _round_trip(0.1, 2, "A"), 6, NOW), "holding")
    assert h["status"] == "no_line" and h["min_days"] is None and h["sooner"] == 0


# ── positions ────────────────────────────────────────────────────────────

def test_only_fewer_names_than_the_minimum_crosses_the_line():
    def pos(n):
        return _item(compute_my_rules(ANSWERS, [], n, NOW), "positions")

    assert pos(6)["status"] == "within"
    assert pos(30)["status"] == "within"                                # more names: not 선 밖
    assert pos(2)["status"] == "outside" and pos(2)["observed"] == "지금 2종목 · 선보다 적음"
    assert pos(0)["status"] == "no_data"


def test_ultra_focused_has_no_minimum():
    answers = dict(ANSWERS, declared_positions="ultra_focused")
    p = _item(compute_my_rules(answers, [], 2, NOW), "positions")
    assert p["status"] == "no_line" and p["min_positions"] is None


# ── drawdown ─────────────────────────────────────────────────────────────

def test_drawdown_line_is_shown_but_never_counted():
    d = _item(compute_my_rules(ANSWERS, [], 6, NOW), "drawdown")
    assert d["measurable"] is False and d["status"] == "not_counted"


# ── summary + legal posture ──────────────────────────────────────────────

def test_summary_counts_only_lines_with_something_to_count():
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
