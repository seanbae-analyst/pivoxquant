"""tests/test_signals_kr_name_consistency.py — BUG-01 follow-up regression (2026-05-10).

Source: 2026-05-10 verify-ux wave (BUG-01).

PR #227 fixed the *source* of KR display names — ``services/data/fetcher.py``
now queries ``kr_stock_registry`` first so new SignalCache rows carry
"삼성전자" instead of "Samsung Electronics". But SignalCache rows persisted
**before** PR #227 still hold the English label, and the original
``routes/signals.py`` backfill logic
(``if not d.get("name") or d.get("name") == t``) only overwrites empty /
ticker-equals values. So legacy rows continued to surface English on the
detail H1 until they were re-cached.

This follow-up routes every name surface through
``services.name_resolver.canonical_display_name``, which forces Korean
for every KR ticker regardless of cached value. The suite pins:

1. Pure helper correctness (KR overrides English, US passes through).
2. ``/api/signals/<t>`` returns Korean even when SignalCache stores
   "Samsung Electronics" (the legacy data scenario).
3. ``/api/signals`` (list) backfills Korean for KR tickers in cache.
4. US tickers untouched (Apple stays "Apple Inc.").
5. ``/api/market/profile/<t>`` continues to return Korean for KR.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest


# ───────────────────────── Pure helper tests ─────────────────────────
class TestCanonicalDisplayNameHelper:
    def test_kr_korean_wins_over_cached_english(self):
        """Old SignalCache rows carry English KR names — Korean must win."""
        from services.name_resolver import canonical_display_name
        assert canonical_display_name("Samsung Electronics", "005930.KS") == "삼성전자"

    def test_kr_kosdaq_korean_canonical(self):
        from services.name_resolver import canonical_display_name
        assert canonical_display_name("Ecopro BM", "247540.KQ") == "에코프로비엠"

    def test_us_keeps_cached_english(self):
        from services.name_resolver import canonical_display_name
        assert canonical_display_name("Apple Inc.", "AAPL") == "Apple Inc."

    def test_us_resolves_when_cached_missing(self):
        from services.name_resolver import canonical_display_name
        out = canonical_display_name(None, "AAPL")
        assert out and "Apple" in out

    def test_kr_unmapped_falls_back_to_cached(self):
        """KR registry miss + KIS miss — fall back to whatever is cached."""
        from services.name_resolver import canonical_display_name
        with patch("services.kr_stock_registry.get_name", return_value=None), \
                patch("services.name_resolver._kis_name", return_value=None):
            out = canonical_display_name("Some Cached Name", "999999.KS")
        assert out == "Some Cached Name"

    def test_total_miss_returns_ticker(self):
        from services.name_resolver import canonical_display_name
        with patch("services.kr_stock_registry.get_name", return_value=None), \
                patch("services.name_resolver._kis_name", return_value=None):
            assert canonical_display_name(None, "999999.KS") == "999999.KS"

    def test_empty_inputs_safe(self):
        from services.name_resolver import canonical_display_name
        assert canonical_display_name(None, "") == ""
        assert canonical_display_name("", "AAPL")  # non-empty fallback


# ───────────────────────── Wire contract helpers ─────────────────────────
def _seed_signal_with_name(app, ticker: str, name: str):
    """Insert a SignalCache row with a specific name (simulating legacy data)."""
    from extensions import db
    from models import SignalCache
    payload = {
        "ticker": ticker,
        "label": "POSITIVE",
        "score": 75,
        "name": name,
    }
    with app.app_context():
        db.session.add(SignalCache(
            ticker=ticker,
            data_json=json.dumps(payload),
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ))
        db.session.commit()


def _seed_position(app, user_id: int, ticker: str):
    from extensions import db
    from models import Position
    with app.app_context():
        db.session.add(Position(
            user_id=user_id, ticker=ticker, shares=10, avg_cost=100.0,
        ))
        db.session.commit()


# ───────────────────────── Wire contract tests ─────────────────────────
class TestSignalsListKoreanName:
    def test_kr_legacy_english_overwritten_to_korean(self, client, auth_user, app):
        """``/api/signals`` must surface 삼성전자 even when SignalCache
        carries the legacy English label."""
        _seed_position(app, auth_user["id"], "005930.KS")
        _seed_signal_with_name(app, "005930.KS", "Samsung Electronics")

        r = client.get("/api/signals")
        assert r.status_code == 200
        sigs = r.get_json().get("signals") or []
        assert len(sigs) == 1
        assert sigs[0]["ticker"] == "005930.KS"
        assert sigs[0]["name"] == "삼성전자", f"got {sigs[0]['name']!r}"

    def test_us_ticker_keeps_english(self, client, auth_user, app):
        _seed_position(app, auth_user["id"], "AAPL")
        _seed_signal_with_name(app, "AAPL", "Apple Inc.")

        r = client.get("/api/signals")
        assert r.status_code == 200
        sigs = r.get_json().get("signals") or []
        assert len(sigs) == 1
        assert sigs[0]["ticker"] == "AAPL"
        assert sigs[0]["name"] == "Apple Inc."


class TestSignalDetailKoreanName:
    """``/api/signals/<t>`` powers the detail H1 — root surface for BUG-01."""

    def test_kr_detail_cache_path_returns_korean(self, client, auth_user, app):
        """When ``engine.analyze()`` returns None (test isolation: no FMP),
        the route falls through to the cached blob. Legacy English KR
        labels must be overwritten with Korean."""
        _seed_position(app, auth_user["id"], "005930.KS")
        _seed_signal_with_name(app, "005930.KS", "Samsung Electronics")

        with patch("routes.signals.engine.analyze", return_value=None):
            r = client.get("/api/signals/005930.KS")
        assert r.status_code == 200
        body = r.get_json()
        assert body["name"] == "삼성전자", f"got {body['name']!r}"

    def test_kr_detail_engine_result_overridden_to_korean(
        self, client, auth_user, app
    ):
        """When ``engine.analyze()`` returns a result, its name is the
        snapshot["name"]. PR #227 fixes new snapshots to Korean, but a
        snapshot-cache that pre-dates the deploy may still carry English.
        Belt-and-suspenders: route layer also forces Korean for KR."""
        _seed_position(app, auth_user["id"], "005930.KS")
        engine_result = {
            "ticker": "005930.KS",
            "name": "Samsung Electronics",
            "label": "POSITIVE",
            "score": 80,
            "signal": "POSITIVE",
        }
        with patch("routes.signals.engine.analyze", return_value=engine_result), \
                patch("routes.signals.cache_service.save_signal"):
            r = client.get("/api/signals/005930.KS")
        assert r.status_code == 200
        body = r.get_json()
        assert body["name"] == "삼성전자", f"got {body['name']!r}"

    def test_us_detail_keeps_english(self, client, auth_user, app):
        _seed_position(app, auth_user["id"], "AAPL")
        engine_result = {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "label": "POSITIVE",
            "score": 80,
        }
        with patch("routes.signals.engine.analyze", return_value=engine_result), \
                patch("routes.signals.cache_service.save_signal"):
            r = client.get("/api/signals/AAPL")
        assert r.status_code == 200
        assert r.get_json()["name"] == "Apple Inc."


class TestProfileKoreanName:
    """``/api/market/profile/<t>`` — pin Korean canonical for KR even
    when FMP returns an English ``shortName``."""

    def test_kr_profile_returns_korean_even_when_fmp_returns_english(
        self, client, auth_user, app
    ):
        with patch("services.data.fmp.get_info", return_value={
            "shortName": "Samsung Electronics",
            "longBusinessSummary": "",
            "sector": "",
        }):
            r = client.get("/api/market/profile/005930.KS")
        assert r.status_code == 200
        body = r.get_json()
        assert body["name"] == "삼성전자", f"got {body['name']!r}"

    def test_us_profile_uses_fmp_shortname(self, client, auth_user, app):
        with patch("services.data.fmp.get_info", return_value={
            "shortName": "Apple Inc.",
            "longBusinessSummary": "",
            "sector": "Technology",
        }):
            r = client.get("/api/market/profile/AAPL")
        assert r.status_code == 200
        assert r.get_json()["name"] == "Apple Inc."
