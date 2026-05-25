"""tests/test_market_status_us_holiday.py — FIX 3 (2026-05-22).

``_us_status_now`` skipped weekends but had no NYSE holiday calendar, so on
a weekday holiday (e.g. Christmas, Thanksgiving, Independence Day) it
returned status="regular"/tradable=True — a wrong "정규장" label, and
cache_ttl._is_market_open() reading True dropped quote/index/FX TTLs to
intraday values, hammering FMP on a closed market.

This locks in: a known NYSE weekday holiday returns closed / not-tradable,
mirroring the KR holiday handling.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from services import market_status
from services.market_status import ET


def _patch_now_et(dt_naive_et):
    """Patch datetime.now(ET) inside market_status to a fixed ET wall time."""
    aware = dt_naive_et.replace(tzinfo=ET)

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return aware

    return patch.object(market_status, "datetime", _FrozenDateTime)


class TestUsHolidayClosure:
    def test_christmas_2026_weekday_is_closed(self):
        # 2026-12-25 is a Friday (weekday) and an NYSE full closure.
        with _patch_now_et(datetime(2026, 12, 25, 11, 0)):
            st = market_status._us_status_now()
        assert st["status"] == market_status.S_CLOSED
        assert st["tradable"] is False
        assert "휴장" in st["label"]
        assert "Christmas" in st["label"]

    def test_thanksgiving_2026_is_closed(self):
        # 2026-11-26 Thursday — Thanksgiving.
        with _patch_now_et(datetime(2026, 11, 26, 14, 0)):
            st = market_status._us_status_now()
        assert st["status"] == market_status.S_CLOSED
        assert st["tradable"] is False

    def test_good_friday_2026_is_closed(self):
        # 2026-04-03 Good Friday — NYSE closes (not a federal holiday).
        with _patch_now_et(datetime(2026, 4, 3, 11, 0)):
            st = market_status._us_status_now()
        assert st["status"] == market_status.S_CLOSED
        assert st["tradable"] is False

    def test_regular_trading_weekday_unchanged(self):
        # 2026-12-23 Wednesday, 11:00 ET — a normal trading day during
        # regular hours. Must NOT be flagged closed.
        with _patch_now_et(datetime(2026, 12, 23, 11, 0)):
            st = market_status._us_status_now()
        assert st["status"] == market_status.S_REGULAR
        assert st["tradable"] is True

    def test_holiday_helper(self):
        assert market_status.is_us_holiday(datetime(2026, 7, 3))[0] is True   # observed July 4
        assert market_status.is_us_holiday(datetime(2027, 1, 1))[0] is True
        assert market_status.is_us_holiday(datetime(2026, 7, 4))[0] is False  # the Sat itself


class TestUsNextOpenSkipsHolidays:
    """FIX A (2026-05-25): the weekend and after-hours/closed branches of
    ``_us_status_now`` computed the next pre-open by skipping weekends only —
    they did NOT skip NYSE holidays. So when the next trading day landed on a
    holiday (e.g. the Saturday before Memorial Day Monday) the returned
    next_event_kst pointed at a closed market. KR already handled this; US was
    asymmetric. These tests lock in the holiday skip in both branches.
    """

    def _expected_kst(self, year, month, day):
        # Pre-open is 04:00 ET on the given trading day, expressed in KST.
        dt_et = datetime(year, month, day, market_status.US_PRE_OPEN.hour,
                         market_status.US_PRE_OPEN.minute, tzinfo=ET)
        return market_status._to_kst_str(dt_et)

    def test_saturday_before_memorial_day_skips_to_tuesday(self):
        # 2026-05-25 (Mon) is Memorial Day (NYSE closed). The preceding
        # Saturday 2026-05-23 must point the next open at Tue 2026-05-26,
        # NOT the holiday Monday.
        with _patch_now_et(datetime(2026, 5, 23, 10, 0)):  # Saturday
            st = market_status._us_status_now()
        assert st["status"] == market_status.S_CLOSED
        assert st["tradable"] is False
        assert st["next_event_kst"] == self._expected_kst(2026, 5, 26)

    def test_sunday_before_memorial_day_skips_to_tuesday(self):
        with _patch_now_et(datetime(2026, 5, 24, 10, 0)):  # Sunday
            st = market_status._us_status_now()
        assert st["status"] == market_status.S_CLOSED
        assert st["next_event_kst"] == self._expected_kst(2026, 5, 26)

    def test_friday_afterhours_before_holiday_monday_skips_to_tuesday(self):
        # Friday 2026-05-22, 21:00 ET (after 20:00 after-hours close → the
        # "closed" else branch). Next trading day must be Tue 2026-05-26,
        # skipping both the weekend AND Memorial Day Monday.
        with _patch_now_et(datetime(2026, 5, 22, 21, 0)):
            st = market_status._us_status_now()
        assert st["status"] == market_status.S_CLOSED
        assert st["tradable"] is False
        assert st["next_event_kst"] == self._expected_kst(2026, 5, 26)

    def test_weekday_afterhours_before_holiday_skips_holiday(self):
        # Wed 2026-12-23 22:00 ET (closed/after-hours). Thu 2026-12-24 is a
        # normal trading day → next open is 2026-12-24, NOT skipped.
        with _patch_now_et(datetime(2026, 12, 23, 22, 0)):
            st = market_status._us_status_now()
        assert st["status"] == market_status.S_CLOSED
        assert st["next_event_kst"] == self._expected_kst(2026, 12, 24)

    def test_thursday_afterhours_before_christmas_friday_skips_to_monday(self):
        # Thu 2026-12-24 22:00 ET. Fri 2026-12-25 is Christmas (closed), and
        # 26/27 are the weekend → next open is Mon 2026-12-28.
        with _patch_now_et(datetime(2026, 12, 24, 22, 0)):
            st = market_status._us_status_now()
        assert st["status"] == market_status.S_CLOSED
        assert st["next_event_kst"] == self._expected_kst(2026, 12, 28)

    def test_normal_friday_afterhours_points_to_monday(self):
        # Control: Fri 2026-12-18 22:00 ET, no holiday → next open Mon 12-21.
        with _patch_now_et(datetime(2026, 12, 18, 22, 0)):
            st = market_status._us_status_now()
        assert st["status"] == market_status.S_CLOSED
        assert st["next_event_kst"] == self._expected_kst(2026, 12, 21)
