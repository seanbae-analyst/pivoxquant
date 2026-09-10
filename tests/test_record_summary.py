"""tests/test_record_summary.py — the record half of the periodic emails.

`services/email/record_summary.py` exists so the retention mails state the
reader's OWN counts instead of generic product copy. Two properties matter
more than the wording and are pinned here:

  1. **The silence rule.** No record → no summary → the caller must not send.
     An email that says "you did nothing this week" is a nudge, and the whole
     point of this module is to stop these mails being nudges (정통망법 §50).
  2. **No verdict, no directive.** The composed lines are counts in past
     tense. They must never carry FORBIDDEN_DIRECTIVE_TERMS — the send path
     asserts on those and would raise at dispatch time, which is far too late.
"""
from __future__ import annotations

import pytest

from services.email.record_summary import (
    MIN_EVENTS_TO_SPEAK,
    _compose,
    _count_trades_in_window,
)


def _lines(**kw) -> list[str]:
    base = dict(
        window_days=7, started=0, proceeded=0, cancelled=0,
        never_bought=0, bought_later=0, trade_count=0,
    )
    base.update(kw)
    return _compose(**base)


class TestSilenceRule:
    def test_nothing_recorded_produces_nothing_to_say(self):
        assert _lines() == []

    def test_min_events_constant_is_above_zero(self):
        # A single stray fill is not a pattern and must not earn an email.
        assert MIN_EVENTS_TO_SPEAK >= 2


class TestComposedSentences:
    def test_pauses_and_their_outcomes_are_stated(self):
        out = _lines(started=3, proceeded=2, cancelled=1, never_bought=1)
        joined = " ".join(out)
        assert "3번 멈춰" in joined
        assert "2번은 그대로 진행하셨" in joined
        assert "1번은 취소하셨" in joined

    def test_cancellation_split_names_both_outcomes(self):
        out = " ".join(_lines(started=12, cancelled=5,
                              never_bought=3, bought_later=2))
        assert "3건은 그 뒤로 담지 않으셨" in out
        assert "2건은 나중에 결국 담으셨" in out

    @pytest.mark.parametrize("kw", [
        dict(started=3, proceeded=3),                       # 진행만
        dict(started=3, cancelled=3, never_bought=3),        # 취소만
        dict(started=5, proceeded=2, cancelled=3,
             never_bought=2, bought_later=1),                # 둘 다
    ])
    def test_no_sentence_ends_on_a_connective(self, kw):
        """Korean clauses joined with '-고' must not terminate a sentence.

        The first draft produced "…담지 않으셨고." whenever only one clause
        was present, because the connective was baked into every fragment.
        """
        for line in _lines(**kw):
            assert not line.rstrip().endswith("고."), line
            assert line.rstrip().endswith("."), line

    def test_trade_count_reported_separately(self):
        out = _lines(trade_count=5)
        assert out == ["지난 7일 동안 체결 기록은 5건입니다."]

    def test_window_days_appears_verbatim(self):
        assert "지난 30일" in " ".join(_lines(window_days=30, trade_count=4))


class TestLegalPosture:
    """The lines ship straight into an email the send path asserts on."""

    @pytest.mark.parametrize("kw", [
        dict(started=4, proceeded=2, cancelled=2, never_bought=1,
             bought_later=1, trade_count=9),
        dict(started=1, proceeded=1, trade_count=1),
        dict(trade_count=30),
    ])
    def test_composed_lines_pass_assert_legal_safe(self, kw):
        from services.legal import assert_legal_safe
        for line in _lines(**kw):
            # Raises ValueError on a forbidden directive term.
            assert_legal_safe(line, "record_summary")

    def test_no_verdict_vocabulary(self):
        banned = ("개선", "악화", "잘함", "못함", "효과", "점수", "등급",
                  "성과가", "우수", "부진")
        out = " ".join(_lines(started=9, proceeded=5, cancelled=4,
                              never_bought=3, bought_later=1, trade_count=12))
        for w in banned:
            assert w not in out, f"verdict word leaked: {w}"


class TestTradeWindow:
    def test_counts_only_fills_inside_the_window(self):
        from datetime import datetime, timedelta, timezone

        class _T:
            def __init__(self, days_ago):
                self.traded_at = (
                    datetime.now(timezone.utc).replace(tzinfo=None)
                    - timedelta(days=days_ago)
                )

        trades = [_T(1), _T(3), _T(20), _T(60)]
        assert _count_trades_in_window(trades, 7) == 2
        assert _count_trades_in_window(trades, 30) == 3
        assert _count_trades_in_window(trades, 365) == 4

    def test_rows_without_a_timestamp_are_ignored(self):
        class _T:
            traded_at = None
        assert _count_trades_in_window([_T(), _T()], 7) == 0
