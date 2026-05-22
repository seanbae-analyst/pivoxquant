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
