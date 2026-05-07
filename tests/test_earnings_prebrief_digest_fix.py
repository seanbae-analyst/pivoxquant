"""Regression guard for the 2026-05-02 earnings prebrief digest fix.

CEO report (2026-05-02): morning digest emails listed 22 tickers, far
exceeding the user's actual same-day earnings load.

Three root causes confirmed via code read:

1. ``_parse_earnings_row_datetime`` defaulted unknown-time rows to amc
   (20:30 UTC). FMP rows with empty/null ``time`` field collapsed into
   the same UTC bucket → all caught by the 30-min ±6-min match window
   in a single scan.
2. ``get_upcoming_earnings`` emitted one row per ``Position``. A user
   with multiple lots of the same ticker (e.g. 3 AAPL buys) appeared
   3 times in the digest.
3. No upper bound on entries per digest — even with parser fix, a
   freak day with many real same-window earnings could bury the user.

Each guard below covers one of the three.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from services.artifacts.earnings_prebrief_service import (
    EarningsPreBriefService,
    _parse_earnings_row_datetime,
)


# ───────────────────── (1) parser fix ─────────────────────

class TestParserNoDefaultAmc:
    """Unknown-time FMP rows must NOT bucket into 20:30 UTC by default."""

    def test_empty_time_returns_none(self):
        assert _parse_earnings_row_datetime({
            "date": "2026-05-15", "time": "",
        }) is None

    def test_missing_time_field_returns_none(self):
        assert _parse_earnings_row_datetime({
            "date": "2026-05-15",
        }) is None

    def test_unknown_time_token_returns_none(self):
        # FMP occasionally emits e.g. "tba" or stray text.
        assert _parse_earnings_row_datetime({
            "date": "2026-05-15", "time": "tba",
        }) is None

    def test_invalid_hhmm_returns_none(self):
        assert _parse_earnings_row_datetime({
            "date": "2026-05-15", "time": "99:99",
        }) is None

    def test_explicit_bmo_still_parses(self):
        dt = _parse_earnings_row_datetime({
            "date": "2026-05-15", "time": "bmo",
        })
        assert dt == datetime(2026, 5, 15, 13, 30)

    def test_explicit_amc_still_parses(self):
        dt = _parse_earnings_row_datetime({
            "date": "2026-05-15", "time": "amc",
        })
        assert dt == datetime(2026, 5, 15, 20, 30)

    def test_explicit_hhmm_still_parses(self):
        dt = _parse_earnings_row_datetime({
            "date": "2026-05-15", "time": "16:30",
        })
        assert dt == datetime(2026, 5, 15, 16, 30)


# ───────────────────── (2) dedup fix ─────────────────────

class _FakePosition:
    def __init__(self, user_id: int, ticker: str, shares: float, avg_cost: float):
        self.user_id = user_id
        self.ticker = ticker
        self.shares = shares
        self.avg_cost = avg_cost


def _fake_calendar_row(d: date, time_token: str = "amc") -> dict:
    return {
        "date":          d.isoformat(),
        "time":          time_token,
        "symbol":        "AAPL",
        "epsEstimated":  1.0,
        "revenueEstimated": 1.0,
    }


class TestDedupSameTickerMultipleLots:
    """A user with N lots of the same ticker must produce one digest row,
    with shares summed across lots."""

    def test_three_lots_same_ticker_yields_one_row(self):
        svc = EarningsPreBriefService()
        # Pick a target dt always inside the 24h horizon. Using "amc"
        # (=20:30 UTC) with a relative date is flaky: when "now" sits
        # between 12:00 and 20:30 UTC, the synthetic event lands beyond
        # now+24h and the row is correctly filtered out — masking the
        # dedup behaviour we want to test. Use HH:MM that mirrors now+6h.
        target_dt = (
            datetime.now(timezone.utc).replace(tzinfo=None)
            + timedelta(hours=6)
        )
        cal = [_fake_calendar_row(target_dt.date(), target_dt.strftime("%H:%M"))]

        positions = [
            _FakePosition(user_id=42, ticker="AAPL", shares=10, avg_cost=100),
            _FakePosition(user_id=42, ticker="AAPL", shares=20, avg_cost=110),
            _FakePosition(user_id=42, ticker="AAPL", shares=30, avg_cost=120),
        ]

        with patch("services.artifacts.earnings_prebrief_service.User") as MockUser, \
             patch("services.artifacts.earnings_prebrief_service.Position") as MockPos, \
             patch(
                 "services.artifacts.earnings_prebrief_service._safe_get_earnings_calendar",
                 return_value=cal,
             ):
            class _U:
                id = 42
                subscription_tier = "premium"
            MockUser.query.filter.return_value.all.return_value = [_U()]
            MockPos.query.filter.return_value.all.return_value = positions

            rows = svc.get_upcoming_earnings(hours=24)

        assert len(rows) == 1, f"Expected 1 dedup'd row, got {len(rows)}: {rows}"
        r = rows[0]
        assert r["ticker"] == "AAPL"
        assert r["shares"] == 60  # 10+20+30
        # Weighted avg: (100*10 + 110*20 + 120*30) / 60 = (1000+2200+3600)/60 = 113.33
        assert abs(r["avg_cost"] - 113.333333) < 0.01


# ───────────────────── (3) digest cap ─────────────────────

class TestDigestEntriesCap:
    """Defensive cap of 8 entries per digest — surplus rows are dropped
    from the email but per-ticker Artifacts still persist via run_scan."""

    def test_cap_value_is_documented_constant(self):
        """Hard-codes the contract — if cap changes, this test forces
        a deliberate update + audit."""
        # Read the constant from source — drift-detection.
        import services.artifacts.earnings_prebrief_service as mod
        import inspect
        src = inspect.getsource(mod.EarningsPreBriefService.run_scan_digest)
        assert "DIGEST_TICKER_CAP = 8" in src, (
            "Hard cap on digest entries removed or value changed — "
            "re-confirm the UX assumption (was: 22-ticker emails too noisy)."
        )
