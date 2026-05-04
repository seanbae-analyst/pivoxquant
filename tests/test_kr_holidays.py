"""tests/test_kr_holidays.py — KR market holiday detection.

Covers the static holiday set in services/market_status.py. The 2026
추석 sequence is the headline assertion: 2026-09-25 (금) is the actual
추석, 9/24, 9/26 are 연휴, and 9/28 (월) is the substitute holiday
because 9/26 falls on a Saturday. 9/27 is Sunday, so the weekend branch
should still flag tradable=False even though it isn't a named holiday.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from services.market_status import KST, _kr_status_now, is_kr_holiday


@pytest.mark.parametrize(
    "year,month,day,expected_is_holiday",
    [
        # 2026 정규 공휴일
        (2026, 1, 1, True),    # 신정
        (2026, 2, 17, True),   # 설날
        (2026, 3, 1, True),    # 삼일절
        (2026, 5, 5, True),    # 어린이날
        (2026, 5, 15, True),   # 부처님오신날
        (2026, 6, 6, True),    # 현충일
        (2026, 8, 15, True),   # 광복절
        # 2026 추석 시퀀스
        (2026, 9, 24, True),   # 추석 연휴
        (2026, 9, 25, True),   # 추석
        (2026, 9, 26, True),   # 추석 연휴
        (2026, 9, 28, True),   # 추석 대체공휴일 (9/26이 토요일)
        (2026, 10, 3, True),   # 개천절
        (2026, 10, 9, True),   # 한글날
        (2026, 12, 25, True),  # 성탄절
        # 2027 sample
        (2027, 1, 1, True),    # 신정
        (2027, 9, 15, True),   # 추석
        # Negatives
        (2026, 5, 4, False),   # 평일
        (2026, 9, 27, False),  # 일요일 (weekend, not a named holiday)
    ],
)
def test_kr_holiday_set(year, month, day, expected_is_holiday):
    is_hol, _reason = is_kr_holiday(datetime(year, month, day, 12, 0))
    assert is_hol is expected_is_holiday, f"{year}-{month:02d}-{day:02d}"


def test_chuseok_2026_market_closed():
    """2026-09-28 (추석 대체공휴일) → tradable=False, label에 '휴장'."""
    fake_now = datetime(2026, 9, 28, 12, 0, tzinfo=KST)
    with patch("services.market_status.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        # Allow non-mocked attribute access for datetime constructors
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        status = _kr_status_now()
    assert status["tradable"] is False
    assert "휴장" in status["label"]


def test_2026_09_27_sunday_not_tradable():
    """일요일 (2026-09-27) — weekend branch returns tradable=False."""
    fake_now = datetime(2026, 9, 27, 12, 0, tzinfo=KST)
    with patch("services.market_status.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        status = _kr_status_now()
    assert status["tradable"] is False


def test_regular_weekday_holiday_check_passes():
    """평일 (2026-05-04 월) → not a holiday."""
    is_hol, reason = is_kr_holiday(datetime(2026, 5, 4, 12, 0))
    assert is_hol is False
    assert reason == ""
