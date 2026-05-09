"""tests/test_signals_filter.py — W6-2 backend filter contract.

HANDOVER v26 W6-2 (HIGH): the frontend ``useSignals(filters)`` hook serializes
filters to a query string and uses that as the SWR cache key. Without backend
honoring the same contract, every filter toggle minted a new cache entry
against an unfiltered response — fragmentation, redundant fetches.

These tests pin the wire contract between
``frontend/src/lib/hooks.ts::useSignals`` and
``routes/signals.py::get_signals`` so the filter semantics are guaranteed
identical on both sides:

1. labels=POSITIVE returns only POSITIVE rows (or NEUTRAL placeholders if
   their label was requested explicitly — which it wasn't here).
2. strength_min=0.5 drops rows with score below 50.
3. symbol=AAPL narrows to a single ticker; mismatch returns empty list.
4. window=today drops rows with observed_at older than 24h.
5. Invalid label values (BUY/SELL) are silently dropped from the filter set.
6. NaN / out-of-bounds strength values fall back to defaults.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


def _seed_signal(app, user_id: int, *, ticker: str, label: str, score: int,
                 observed_at: datetime | None = None):
    """Insert a SignalCache row so /api/signals can return it."""
    from extensions import db
    from models import SignalCache
    if observed_at is None:
        observed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    elif observed_at.tzinfo is not None:
        observed_at = observed_at.astimezone(timezone.utc).replace(tzinfo=None)

    payload = {
        "ticker": ticker,
        "label": label,
        "score": score,
        "name": ticker,
    }
    with app.app_context():
        c = SignalCache(
            ticker=ticker,
            data_json=json.dumps(payload),
            updated_at=observed_at,
        )
        db.session.add(c)
        db.session.commit()


def _seed_position(app, user_id: int, ticker: str):
    from extensions import db
    from models import Position
    with app.app_context():
        p = Position(
            user_id=user_id,
            ticker=ticker,
            shares=10,
            avg_cost=100.0,
        )
        db.session.add(p)
        db.session.commit()


class TestLabelFilter:
    def test_label_positive_only(self, client, auth_user, app):
        _seed_position(app, auth_user["id"], "AAPL")
        _seed_position(app, auth_user["id"], "TSLA")
        _seed_signal(app, auth_user["id"], ticker="AAPL", label="POSITIVE", score=80)
        _seed_signal(app, auth_user["id"], ticker="TSLA", label="NEGATIVE", score=70)

        r = client.get("/api/signals?labels=POSITIVE")
        assert r.status_code == 200
        sigs = r.get_json().get("signals") or []
        tickers = {s["ticker"] for s in sigs}
        assert "AAPL" in tickers
        assert "TSLA" not in tickers


class TestStrengthFilter:
    def test_strength_min_drops_low_scores(self, client, auth_user, app):
        _seed_position(app, auth_user["id"], "AAPL")
        _seed_position(app, auth_user["id"], "TSLA")
        _seed_signal(app, auth_user["id"], ticker="AAPL", label="POSITIVE", score=80)
        _seed_signal(app, auth_user["id"], ticker="TSLA", label="POSITIVE", score=20)

        r = client.get("/api/signals?strength_min=0.5")
        assert r.status_code == 200
        sigs = r.get_json().get("signals") or []
        tickers = {s["ticker"] for s in sigs}
        assert "AAPL" in tickers
        assert "TSLA" not in tickers


class TestSymbolFilter:
    def test_symbol_narrows_to_one(self, client, auth_user, app):
        _seed_position(app, auth_user["id"], "AAPL")
        _seed_position(app, auth_user["id"], "TSLA")
        _seed_signal(app, auth_user["id"], ticker="AAPL", label="POSITIVE", score=80)
        _seed_signal(app, auth_user["id"], ticker="TSLA", label="POSITIVE", score=80)

        r = client.get("/api/signals?symbol=AAPL")
        assert r.status_code == 200
        sigs = r.get_json().get("signals") or []
        assert len(sigs) == 1
        assert sigs[0]["ticker"] == "AAPL"

    def test_symbol_outside_user_positions_returns_empty(self, client, auth_user, app):
        _seed_position(app, auth_user["id"], "AAPL")
        _seed_signal(app, auth_user["id"], ticker="AAPL", label="POSITIVE", score=80)

        r = client.get("/api/signals?symbol=NVDA")
        assert r.status_code == 200
        assert r.get_json().get("signals") == []


class TestWindowFilter:
    def test_window_today_drops_old_observations(self, client, auth_user, app):
        _seed_position(app, auth_user["id"], "AAPL")
        _seed_position(app, auth_user["id"], "TSLA")
        _seed_signal(app, auth_user["id"], ticker="AAPL", label="POSITIVE", score=80,
                     observed_at=datetime.now(timezone.utc))
        _seed_signal(app, auth_user["id"], ticker="TSLA", label="POSITIVE", score=80,
                     observed_at=datetime.now(timezone.utc) - timedelta(days=3))

        r = client.get("/api/signals?window=today")
        assert r.status_code == 200
        sigs = r.get_json().get("signals") or []
        tickers = {s["ticker"] for s in sigs}
        assert "AAPL" in tickers
        assert "TSLA" not in tickers


class TestInvalidValuesIgnored:
    def test_invalid_label_treated_as_no_label_filter(self, client, auth_user, app):
        """labels=BUY (banned vocabulary) — backend filter set ends up empty,
        which means no label filter applied (returns all)."""
        _seed_position(app, auth_user["id"], "AAPL")
        _seed_signal(app, auth_user["id"], ticker="AAPL", label="POSITIVE", score=80)

        r = client.get("/api/signals?labels=BUY,SELL")
        assert r.status_code == 200
        sigs = r.get_json().get("signals") or []
        # BUY/SELL are not in _VALID_LABELS — filter set ends up empty,
        # which short-circuits to "no filter" and returns everything.
        assert len(sigs) == 1
        assert sigs[0]["ticker"] == "AAPL"

    def test_strength_out_of_bounds_clamped(self, client, auth_user, app):
        _seed_position(app, auth_user["id"], "AAPL")
        _seed_signal(app, auth_user["id"], ticker="AAPL", label="POSITIVE", score=50)

        # strength_min=99 (way above 1.0) — should clamp to 1.0, drop the row.
        r = client.get("/api/signals?strength_min=99")
        assert r.status_code == 200
        sigs = r.get_json().get("signals") or []
        # 0.5 < 1.0 (clamped min) → row dropped.
        assert len(sigs) == 0

    def test_inverted_strength_range_falls_back_to_default(self, client, auth_user, app):
        _seed_position(app, auth_user["id"], "AAPL")
        _seed_signal(app, auth_user["id"], ticker="AAPL", label="POSITIVE", score=50)

        # min > max → fallback to (0.0, 1.0), no rows dropped.
        r = client.get("/api/signals?strength_min=0.9&strength_max=0.1")
        assert r.status_code == 200
        sigs = r.get_json().get("signals") or []
        assert len(sigs) == 1


class TestPlaceholderFilteredOut:
    def test_no_signal_data_emits_neutral_placeholder(self, client, auth_user, app):
        """Position without a SignalCache row → NEUTRAL placeholder."""
        _seed_position(app, auth_user["id"], "AAPL")
        # No _seed_signal — placeholder path.
        r = client.get("/api/signals")
        assert r.status_code == 200
        sigs = r.get_json().get("signals") or []
        assert len(sigs) == 1
        assert sigs[0]["ticker"] == "AAPL"
        assert sigs[0]["is_stale"] is True

    def test_placeholder_dropped_by_label_filter(self, client, auth_user, app):
        """Placeholder is NEUTRAL — labels=POSITIVE drops it."""
        _seed_position(app, auth_user["id"], "AAPL")
        r = client.get("/api/signals?labels=POSITIVE")
        assert r.status_code == 200
        sigs = r.get_json().get("signals") or []
        assert len(sigs) == 0

    def test_placeholder_dropped_by_strength_min(self, client, auth_user, app):
        """Placeholder scores 0 — strength_min=0.5 drops it."""
        _seed_position(app, auth_user["id"], "AAPL")
        r = client.get("/api/signals?strength_min=0.5")
        assert r.status_code == 200
        sigs = r.get_json().get("signals") or []
        assert len(sigs) == 0
