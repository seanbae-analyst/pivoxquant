"""Regression guard for signal_detail timeout (bug-hunter P0 2026-05-15).

The /api/signals/<ticker> endpoint historically called engine.analyze()
synchronously with no timeout. When the FMP / data fetcher path hung
for a specific ticker (AAPL on prod 2026-05-15), the Flask thread
blocked indefinitely → SWR stayed in `loadingSignal=true` → the
/detail page rendered a forever-skeleton. Samsung (005930.KS) in the
same session returned 200, confirming the hang was ticker-specific
not systemic backend failure.

These tests pin down the fix:
  - when engine.analyze returns normally → behavior unchanged
  - when engine.analyze takes longer than the timeout → fall through
    to SignalCache, response includes is_stale=true + stale_reason
  - when engine.analyze times out AND cache is empty → 504 with
    structured error code (not indefinite skeleton)
"""
from __future__ import annotations

import json
import threading
import time
from unittest import mock

import pytest

from extensions import db
from models import SignalCache


def _set_analyze_to_block_forever():
    """Return a mock that blocks engine.analyze on a never-set Event.

    Caller is responsible for clearing the mock when the test ends.
    Using an Event ensures the worker thread sleeps cleanly instead of
    spinning — pytest cleanup doesn't leave CPU-burning ghosts.
    """
    blocker = threading.Event()

    def _hang(*args, **kwargs):
        blocker.wait(timeout=30)  # safety cap so leaked threads don't pile up
        return None

    return mock.patch(
        "services.container.engine.analyze",
        side_effect=_hang,
    ), blocker


class TestSignalDetailTimeout:
    """The 4 timeout-path branches."""

    def test_timeout_falls_through_to_signal_cache(self, client, auth_user, app):
        """When analyze times out AND cache has a stored signal → return
        the cached payload with is_stale=true + stale_reason emitted."""
        # Pre-seed SignalCache with a known good payload.
        ticker = "AAPL"
        cached_payload = {
            "ticker": ticker,
            "name": "Apple Inc.",
            "price": 198.0,
            "change_pct": 0.5,
            "signal": "POSITIVE",
            "score": 72,
        }
        with app.app_context():
            row = SignalCache(ticker=ticker, data_json=json.dumps(cached_payload))
            db.session.add(row)
            db.session.commit()
        # Also pre-seed a position so is_user_allowed_ticker passes.
        _seed_position(auth_user, ticker, app)

        ctx, _blocker = _set_analyze_to_block_forever()
        with ctx, mock.patch.dict(
            "os.environ", {"SIGNAL_DETAIL_TIMEOUT_S": "0.5"}
        ):
            r = client.get(f"/api/signals/{ticker}")

        assert r.status_code == 200
        body = r.get_json()
        assert body["price"] == 198.0
        assert body.get("is_stale") is True
        assert body.get("stale_reason") == "analyze_timeout"

    def test_timeout_empty_cache_returns_504(self, client, auth_user, app):
        """When analyze times out AND no SignalCache row exists → return
        504 with ANALYZE_TIMEOUT code (NOT an indefinite skeleton)."""
        ticker = "NOCACHE"
        _seed_position(auth_user, ticker, app)

        ctx, _blocker = _set_analyze_to_block_forever()
        with ctx, mock.patch.dict(
            "os.environ", {"SIGNAL_DETAIL_TIMEOUT_S": "0.5"}
        ):
            r = client.get(f"/api/signals/{ticker}")

        assert r.status_code == 504
        body = r.get_json()
        assert body.get("code") == "ANALYZE_TIMEOUT"

    def test_normal_analyze_unchanged(self, client, auth_user, app):
        """When analyze returns normally → response shape preserved (no
        is_stale tag, full 200, the analyze result)."""
        ticker = "HAPPY"
        _seed_position(auth_user, ticker, app)
        normal = {
            "ticker": ticker, "name": "Happy Co",
            "price": 100.0, "change_pct": 1.0,
            "signal": "POSITIVE", "score": 80,
        }
        with mock.patch(
            "services.container.engine.analyze", return_value=normal,
        ):
            r = client.get(f"/api/signals/{ticker}")

        assert r.status_code == 200
        body = r.get_json()
        assert body["price"] == 100.0
        # Normal path does NOT set is_stale.
        assert "stale_reason" not in body

    def test_analyze_returns_none_with_cache(self, client, auth_user, app):
        """Pre-existing branch: analyze returns falsy (None) and cache
        exists → return cache. This case existed BEFORE the timeout
        fix; the patch must preserve it."""
        ticker = "FALLBACK"
        _seed_position(auth_user, ticker, app)
        cached_payload = {
            "ticker": ticker, "name": "Fallback Inc",
            "price": 50.0, "signal": "NEUTRAL", "score": 50,
        }
        with app.app_context():
            row = SignalCache(ticker=ticker, data_json=json.dumps(cached_payload))
            db.session.add(row)
            db.session.commit()
        with mock.patch(
            "services.container.engine.analyze", return_value=None,
        ):
            r = client.get(f"/api/signals/{ticker}")

        assert r.status_code == 200
        body = r.get_json()
        assert body["price"] == 50.0
        # Falsy-return path is NOT marked stale (only timeout path is).
        assert body.get("stale_reason") is None


def _seed_position(user, ticker: str, app):
    """Add a position so is_user_allowed_ticker passes for `ticker`."""
    from models import Position
    with app.app_context():
        p = Position(
            user_id=user["id"], ticker=ticker, shares=1.0, avg_cost=1.0,
        )
        db.session.add(p)
        db.session.commit()
