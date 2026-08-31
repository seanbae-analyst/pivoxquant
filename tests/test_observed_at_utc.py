"""Regression guard: client-facing observation stamps carry an explicit UTC marker.

Bug (AUTOPILOT_BACKLOG 2026-07-12 P1): price providers stamped payloads with a
bare ``datetime.now().isoformat()``. The browser parses a naive ISO string as
LOCAL time, so KST users saw the *freshest* prices labelled "9h ago" behind an
amber "stale" dot, while genuinely stale cache entries (which already appended
"Z") rendered correctly.
"""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from services.time_utils import normalize_observed_at, observed_at_iso

REPO = Path(__file__).resolve().parents[1]
UTC_MARKED = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")


# ── helper contract ──────────────────────────────────────────────────

def test_observed_at_iso_is_utc_marked():
    assert UTC_MARKED.search(observed_at_iso())


def test_observed_at_iso_treats_naive_as_utc():
    assert observed_at_iso(datetime(2026, 8, 30, 7, 0, 0)) == "2026-08-30T07:00:00Z"


def test_observed_at_iso_converts_aware_to_utc():
    kst = timezone(timedelta(hours=9))
    assert observed_at_iso(datetime(2026, 8, 30, 16, 0, 0, tzinfo=kst)) == "2026-08-30T07:00:00Z"


def test_observed_at_iso_is_close_to_now():
    now = datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(observed_at_iso().replace("Z", "+00:00"))
    assert abs((parsed - now).total_seconds()) < 5


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("2026-08-30T07:00:00", "2026-08-30T07:00:00Z"),      # naive -> marked
        ("2026-08-30T07:00:00Z", "2026-08-30T07:00:00Z"),     # already marked
        ("2026-08-30T07:00:00+09:00", "2026-08-30T07:00:00+09:00"),
        ("not-a-timestamp", "not-a-timestamp"),               # never raises
    ],
)
def test_normalize_observed_at(value, expected):
    assert normalize_observed_at(value) == expected


def test_normalize_does_not_fabricate_freshness():
    """An unparseable stamp stays visible instead of silently becoming 'now'."""
    assert normalize_observed_at("garbage") == "garbage"


# ── source guard: the naive pattern must not come back ───────────────

def test_no_naive_isoformat_stamps_in_payload_paths():
    offenders = []
    for sub in ("services", "routes"):
        for path in (REPO / sub).rglob("*.py"):
            if path.name == "time_utils.py":
                continue
            for i, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
                if 'datetime.now().isoformat()' in line:
                    offenders.append(f"{path.relative_to(REPO)}:{i}")
    assert not offenders, (
        "naive (timezone-less) ISO stamps found — use services.time_utils."
        f"observed_at_iso() instead:\n  " + "\n  ".join(offenders)
    )
