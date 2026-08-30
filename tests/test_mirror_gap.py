"""Tests for services/mirror_gap.

Most of these guard a refusal. The product's one claim is that it reports
the user's own record back to them, so a gap must never appear unless the
record can support it — a confident sentence built on five trades is worse
than saying nothing, because the user cannot tell it was noise.
"""
from __future__ import annotations

import pytest

from services.mirror_gap import Declaration, compute_gap_report
from services.mirror_gap.declaration import DECLARATION_QUESTIONS


def _turnover(**over):
    base = {
        "sufficient_data": True, "period_days": 180, "trade_count": 24,
        "buy_count": 13, "sell_count": 11,
        "mean_hold_days": 4.0, "median_hold_days": 3.0, "by_currency": [],
    }
    base.update(over)
    return base


def _pl(win=5.0, lose=47.0, **over):
    base = {
        "sufficient_data": True, "one_sided": False, "total_closed_pairs": 11,
        "take_profit": {"count": 6, "mean_hold_days": win, "median_hold_days": win},
        "stop_loss": {"count": 5, "mean_hold_days": lose, "median_hold_days": lose},
    }
    base.update(over)
    return base


# ── declaration input ───────────────────────────────────────────────────

def test_questions_have_stable_unique_keys():
    # Keys are stored per user and compared months later; a rename silently
    # invalidates every declaration already on file.
    keys = [q.key for q in DECLARATION_QUESTIONS]
    assert keys == ["hold_days", "trades_per_month", "hold_longer"]
    assert len(set(keys)) == len(keys)


def test_reads_a_full_answer_set():
    decl, rejected = Declaration.from_answers(
        {"hold_days": 90, "trades_per_month": 3, "hold_longer": "profit"}
    )
    assert rejected == []
    assert (decl.hold_days, decl.trades_per_month, decl.hold_longer) == (90.0, 3.0, "profit")
    assert not decl.is_empty


def test_partial_answers_are_allowed():
    decl, rejected = Declaration.from_answers({"hold_days": 30})
    assert rejected == []
    assert decl.hold_days == 30
    assert decl.trades_per_month is None


@pytest.mark.parametrize("bad", [0, -1, "abc", "", float("nan"), float("inf"), True, 99999])
def test_unusable_numbers_are_rejected_not_coerced(bad):
    # A declaration is the fixed half of the comparison. A value quietly
    # clamped into range would misstate every future gap against it.
    decl, rejected = Declaration.from_answers({"hold_days": bad})
    assert decl.hold_days is None
    assert "hold_days" in rejected


def test_unknown_choice_is_rejected():
    decl, rejected = Declaration.from_answers({"hold_longer": "maybe"})
    assert decl.hold_longer is None
    assert "hold_longer" in rejected


def test_missing_keys_are_not_rejections():
    decl, rejected = Declaration.from_answers({})
    assert rejected == []
    assert decl.is_empty


def test_non_dict_input_does_not_raise():
    decl, rejected = Declaration.from_answers("nope")  # type: ignore[arg-type]
    assert decl.is_empty
    assert set(rejected) == {"hold_days", "trades_per_month", "hold_longer"}


# ── refusal: no record, no gap ──────────────────────────────────────────

def test_empty_declaration_yields_nothing():
    r = compute_gap_report(Declaration())
    assert r.gaps == [] and r.pending == []
    assert not r.has_any


def test_missing_mirrors_pend_rather_than_guess():
    decl, _ = Declaration.from_answers(
        {"hold_days": 90, "trades_per_month": 3, "hold_longer": "profit"}
    )
    r = compute_gap_report(decl, turnover=None, profit_loss=None)
    assert r.gaps == []
    assert {p["key"] for p in r.pending} == {"hold_days", "trades_per_month", "hold_longer"}


def test_insufficient_data_pends():
    decl, _ = Declaration.from_answers({"hold_days": 90})
    r = compute_gap_report(decl, turnover=_turnover(sufficient_data=False))
    assert r.gaps == []
    assert r.pending[0]["reason"] == "매매 기록이 아직 부족합니다."


def test_one_sided_record_cannot_answer_the_disposition_question():
    decl, _ = Declaration.from_answers({"hold_longer": "profit"})
    r = compute_gap_report(decl, profit_loss=_pl(one_sided=True))
    assert r.gaps == []
    assert "한쪽" in r.pending[0]["reason"]


def test_short_window_withholds_the_monthly_comparison():
    # Two weeks of records extrapolated to a month would overstate by ~2x
    # and read as a finding rather than an artefact of the window.
    decl, _ = Declaration.from_answers({"trades_per_month": 3})
    r = compute_gap_report(decl, turnover=_turnover(period_days=14, trade_count=6))
    assert r.gaps == []
    assert "짧습니다" in r.pending[0]["reason"]


# ── the gap itself ──────────────────────────────────────────────────────

def test_hold_period_gap_states_both_numbers():
    decl, _ = Declaration.from_answers({"hold_days": 90})
    r = compute_gap_report(decl, turnover=_turnover(mean_hold_days=4.0))
    gap = r.gaps[0]
    assert gap.key == "hold_days"
    assert "약 3개월" in gap.statement
    assert "4일" in gap.statement
    assert gap.magnitude == 22.5


def test_no_verdict_language_anywhere():
    # A gap is two numbers side by side. A verdict is something the user
    # can argue with, and arguing is how the observation gets dismissed.
    decl, _ = Declaration.from_answers(
        {"hold_days": 90, "trades_per_month": 2, "hold_longer": "profit"}
    )
    r = compute_gap_report(decl, turnover=_turnover(), profit_loss=_pl())
    banned = ["성급", "과도", "위험", "잘못", "실수", "나쁜", "개선", "추천", "조언",
              "점수", "등급", "순위"]
    for gap in r.gaps:
        for word in banned:
            assert word not in gap.statement, f"{word!r} in {gap.statement!r}"


def test_disposition_gap_names_the_contradiction():
    decl, _ = Declaration.from_answers({"hold_longer": "profit"})
    r = compute_gap_report(decl, profit_loss=_pl(win=5.0, lose=47.0))
    assert "반대입니다" in r.gaps[0].statement
    assert "47일" in r.gaps[0].statement


def test_agreement_is_reported_too():
    # A mirror that only speaks when the user is wrong is not a mirror.
    decl, _ = Declaration.from_answers({"hold_longer": "loss"})
    r = compute_gap_report(decl, profit_loss=_pl(win=5.0, lose=47.0))
    assert "기록도 같습니다" in r.gaps[0].statement


def test_unsure_gets_the_record_without_a_contradiction():
    decl, _ = Declaration.from_answers({"hold_longer": "unsure"})
    r = compute_gap_report(decl, profit_loss=_pl())
    statement = r.gaps[0].statement
    assert "반대" not in statement and "같습니다" not in statement
    assert "기록은" in statement


def test_largest_gap_comes_first():
    decl, _ = Declaration.from_answers({"hold_days": 90, "trades_per_month": 20})
    # hold: 90 vs 4 → 22.5x. frequency: 20 vs 4/month → 5.0x.
    r = compute_gap_report(decl, turnover=_turnover(trade_count=24, period_days=180))
    assert [g.key for g in r.gaps] == ["hold_days", "trades_per_month"]
    assert r.gaps[0].magnitude > r.gaps[1].magnitude


def test_report_serialises_for_the_api():
    decl, _ = Declaration.from_answers({"hold_days": 90})
    payload = compute_gap_report(decl, turnover=_turnover()).to_dict()
    assert set(payload) == {"gaps", "pending"}
    assert set(payload["gaps"][0]) == {
        "key", "label", "declared", "observed", "statement", "magnitude"
    }


@pytest.mark.parametrize("days,expected", [
    (0.4, "하루 미만"), (4.0, "4일"), (29.0, "29일"),
    (90.0, "약 3개월"), (400.0, "약 1.1년"),
])
def test_duration_wording_matches_the_scale(days, expected):
    decl, _ = Declaration.from_answers({"hold_days": days})
    r = compute_gap_report(decl, turnover=_turnover(mean_hold_days=days))
    assert expected in r.gaps[0].statement


# ── bug-hunt 2026-08-30 회귀 ────────────────────────────────────────────

@pytest.mark.parametrize("win,lose", [
    (89.9, 90.0),    # 0.1일 — 표시 반올림으로 양쪽 "90일"
    (90.0, 95.0),    # 90일 경계 — 양쪽 "약 3개월"
    (4.4, 4.4001),   # 일 단위 아래
    (365.0, 366.0),  # 연 단위 표시
])
def test_verdict_never_contradicts_the_numbers_shown(win, lose):
    """보이는 두 값이 같으면 "반대"라고 말할 수 없다.

    원래는 원본 float 로 비교하고 표시는 따로 반올림해서, 0.1일 차이가
    "기록은 반대입니다 — 손실 90일 · 수익 90일" 로 나왔다. 기록을 그대로
    돌려준다는 약속을 정면으로 깨는 출력이라, 판정을 표시값 기준으로 바꿨다.
    """
    decl, _ = Declaration.from_answers({"hold_longer": "same"})
    r = compute_gap_report(decl, profit_loss=_pl(win=win, lose=lose))
    statement = r.gaps[0].statement
    observed = r.gaps[0].observed_text

    # 같은 숫자가 두 번 나오면서 "반대" 라고 하는 조합은 불가능해야 한다.
    assert "반대" not in statement, f"동일 표시값에 반대 단언: {statement!r}"
    assert "양쪽 모두" in observed


def test_a_difference_large_enough_to_show_is_still_reported():
    """반올림 방어가 진짜 격차까지 삼키면 안 된다."""
    decl, _ = Declaration.from_answers({"hold_longer": "profit"})
    r = compute_gap_report(decl, profit_loss=_pl(win=5.0, lose=47.0))
    assert "반대입니다" in r.gaps[0].statement
    assert "47일" in r.gaps[0].statement and "5일" in r.gaps[0].statement
