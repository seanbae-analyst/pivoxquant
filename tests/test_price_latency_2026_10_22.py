"""tests/test_price_latency_2026_10_22.py — "현황가격 업데이트가 너무 느려".

Pins the 2026-10-22 price-latency fixes:

- get_prices_batch serves a fresh shared-cache hit with no network call,
  writes FMP answers back to the cache, and concurrent callers for the same
  ticker share one fetch (single-flight).
- The KR / FMP collect deadlines bound the batch — a slow upstream no longer
  holds it until every worker finishes; the late answer still lands in cache.
- KR tickers never fall back to FMP (no KRX quotes there — it only spent the
  daily budget).
- A quote ``fmp.get_quote`` serves from old cache is marked stale and keeps
  that label through realtime → price_overlay (it read as live "realtime").
- /quote 402 cooldown is per symbol.
- The 3-min SignalCache refresh re-quotes only what display needs.
- FX does not burn the FMP budget once a rate is fresh / FX's share is spent.
- The SSE loop keeps a fixed cadence.

No real network: providers are monkeypatched.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from services.data import fmp as fmp_service
from services.data.realtime import RealtimeService


@pytest.fixture(autouse=True)
def _clean_fmp():
    def reset():
        with fmp_service._cache_lock:
            fmp_service._cache.clear()
            fmp_service._endpoint_402_counts.clear()
            fmp_service._endpoint_402_cooldown.clear()
        fmp_service._daily_calls = 0
        fmp_service._daily_calls_reset = time.time()
        fmp_service._recent_call_ts.clear()
    reset()
    yield
    reset()


def _svc(monkeypatch, *, kis=True):
    rt = RealtimeService()
    rt.alpaca_available = False
    rt.kis_available = kis
    monkeypatch.setattr(rt, "_ensure_kis_ws", lambda: None)
    return rt


def _kis_writer(rt, price, *, delay=0.0, calls=None):
    """Stand-in for _get_kis_price: like the real one, it seeds the cache."""
    def fake(ticker):
        if calls is not None:
            calls.append(ticker)
        if delay:
            time.sleep(delay)
        result = {"ticker": ticker, "price": price, "source": "kis", "_ts": time.time()}
        with rt._price_cache_lock:
            rt._price_cache[ticker.upper()] = result
        return result
    return fake


# ── B2: cache + single-flight ───────────────────────────────────────────

def test_batch_serves_fresh_cache_without_network(monkeypatch):
    rt = _svc(monkeypatch)
    rt._price_cache["AAPL"] = {"ticker": "AAPL", "price": 190.0, "_ts": time.time()}
    monkeypatch.setattr(rt, "_get_fmp_price", lambda t: pytest.fail("network call on a fresh hit"))
    out = rt.get_prices_batch(["AAPL"])
    assert out["AAPL"]["price"] == 190.0


def test_batch_writes_fmp_answer_back_to_cache(monkeypatch):
    rt = _svc(monkeypatch)
    calls = []

    def fmp(t):
        calls.append(t)
        return {"ticker": t, "price": 10.0, "source": "fmp"}

    monkeypatch.setattr(rt, "_get_fmp_price", fmp)
    rt.get_prices_batch(["AAPL"])
    rt.get_prices_batch(["AAPL"])
    assert calls == ["AAPL"]


def test_concurrent_callers_share_one_kis_fetch(monkeypatch):
    rt = _svc(monkeypatch)
    calls = []
    monkeypatch.setattr(rt, "_get_kis_price", _kis_writer(rt, 70000, delay=0.3, calls=calls))
    outs = []

    def caller():
        outs.append(rt.get_prices_batch(["005930.KS"]))

    threads = [threading.Thread(target=caller) for _ in range(3)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert calls == ["005930.KS"]
    assert [o["005930.KS"]["price"] for o in outs] == [70000] * 3


def test_concurrent_caller_gets_the_alpaca_batch_answer(monkeypatch):
    # The waiting caller reads the fetching caller's answer from the shared
    # cache — the Alpaca batch never wrote it there, so the second caller
    # got {} for every US ticker.
    rt = _svc(monkeypatch, kis=False)
    rt.alpaca_available = True

    class _Trade:
        price = 190.0
        timestamp = None

    class _Client:
        def get_stock_latest_trade(self, req):
            time.sleep(0.3)
            return {"AAPL": _Trade()}

        def get_stock_latest_bar(self, req):
            return {}

    rt.alpaca_client = _Client()
    monkeypatch.setattr(rt, "_get_fmp_price", lambda t: None)
    outs = []

    def caller():
        outs.append(rt.get_prices_batch(["AAPL"]))

    threads = [threading.Thread(target=caller) for _ in range(2)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert [o["AAPL"]["price"] for o in outs] == [190.0, 190.0]
    assert not any(o["AAPL"].get("stale") for o in outs)


# ── B3: deadlines are real ──────────────────────────────────────────────

def test_kr_deadline_bounds_the_batch_and_late_answer_is_cached(monkeypatch):
    rt = _svc(monkeypatch)
    monkeypatch.setattr(rt, "_KR_BATCH_DEADLINE", 0.2)
    monkeypatch.setattr(rt, "_get_kis_price", _kis_writer(rt, 71000, delay=0.8))
    t0 = time.time()
    out = rt.get_prices_batch(["000660.KS"])
    assert time.time() - t0 < 0.6
    assert "000660.KS" not in out
    time.sleep(0.9)
    assert rt._price_cache["000660.KS"]["price"] == 71000


def test_a_fetch_past_the_deadline_is_not_queued_again(monkeypatch):
    # The claim on a ticker is held until its fetch lands, not dropped at the
    # deadline: the next round waits on it and reads the late answer instead
    # of queueing a second KIS call behind the first.
    rt = _svc(monkeypatch)
    monkeypatch.setattr(rt, "_KR_BATCH_DEADLINE", 0.2)
    calls = []
    monkeypatch.setattr(rt, "_get_kis_price", _kis_writer(rt, 72000, delay=0.35, calls=calls))
    first = rt.get_prices_batch(["000660.KS"])
    assert "000660.KS" not in first or first["000660.KS"].get("stale")
    second = rt.get_prices_batch(["000660.KS"])
    assert calls == ["000660.KS"]
    assert second["000660.KS"]["price"] == 72000
    time.sleep(0.1)
    with rt._price_cache_lock:
        assert not rt.__dict__.get("_inflight")


# ── B1a: KR never falls back to FMP ─────────────────────────────────────

def test_kr_miss_does_not_spend_fmp(monkeypatch):
    rt = _svc(monkeypatch)
    monkeypatch.setattr(rt, "_get_kis_price", lambda t: None)
    monkeypatch.setattr(rt, "_get_fmp_price", lambda t: pytest.fail("FMP asked for a KR ticker"))
    rt._price_cache["005930.KS"] = {"ticker": "005930.KS", "price": 70000, "_ts": time.time() - 3600}
    rt._cache_ttl = 0
    out = rt.get_prices_batch(["005930.KS"])
    assert out["005930.KS"]["stale"] is True
    assert rt.get_price("005930.KS")["stale"] is True


# ── B1b: budget-stale quote keeps its stale label ───────────────────────

def test_budget_stale_quote_is_marked_and_keeps_its_time(monkeypatch):
    fetched_at = time.time() - 6 * 3600
    with fmp_service._cache_lock:
        fmp_service._cache["quote:AAPL"] = {"data": {"symbol": "AAPL", "price": 180.0}, "ts": fetched_at}
    monkeypatch.setattr(fmp_service, "_daily_calls", fmp_service._BUDGET_STALE_THRESHOLD)
    q = fmp_service.get_quote("AAPL")
    assert q["_stale_at"] == fetched_at
    assert "_stale_at" not in fmp_service._cache["quote:AAPL"]["data"]  # cache untouched

    out = RealtimeService()._get_fmp_price("AAPL")
    assert out["stale"] is True and out["source"] == "fmp_stale"
    assert out["timestamp"].startswith(
        datetime.fromtimestamp(fetched_at, timezone.utc).strftime("%Y-%m-%dT%H:%M")
    )


def test_overlay_does_not_relabel_a_stale_price_realtime(monkeypatch, app):
    from services import price_overlay

    monkeypatch.setattr(price_overlay.realtime, "get_prices_batch", lambda ts: {
        "AAPL": {"price": 180.0, "stale": True, "source": "fmp_stale", "timestamp": "2026-10-22T00:00:00Z"},
        "MSFT": {"price": 400.0, "source": "fmp", "timestamp": "2026-10-22T06:00:00Z"},
    })
    with app.app_context():
        out = price_overlay.overlay_prices(["AAPL", "MSFT"])
    assert out["AAPL"]["source"] == "fmp_stale" and out["AAPL"]["stale"] is True
    assert out["MSFT"]["source"] == "realtime" and "stale" not in out["MSFT"]


# ── B1e: 402 cooldown per symbol ────────────────────────────────────────

def test_one_symbols_402s_do_not_cool_quote_for_every_ticker(monkeypatch):
    monkeypatch.setattr(fmp_service, "FMP_KEY", "test-key")
    seen = []

    class R:
        def __init__(self, code):
            self.status_code = code

        def json(self):
            return [{"symbol": "AAPL", "price": 190.0}]

    def fake_get(url, params=None, timeout=None):
        seen.append(params["symbol"])
        return R(402 if params["symbol"] == "^KS11" else 200)

    monkeypatch.setattr(fmp_service.requests, "get", fake_get)
    for _ in range(fmp_service._ENDPOINT_402_THRESHOLD + 1):
        assert fmp_service._fmp_get("/quote", {"symbol": "^KS11"}) is None
    assert seen.count("^KS11") == fmp_service._ENDPOINT_402_THRESHOLD  # that symbol cooled
    assert fmp_service._fmp_get("/quote", {"symbol": "AAPL"}) is not None  # others still served


# ── B1c: refresh job re-quotes only what display needs ──────────────────

def test_refresh_job_with_display_off_only_warms_missing_or_day_old(app):
    from extensions import db
    from models import SignalCache
    from services.cache_service import tickers_due_for_refresh

    now = datetime(2026, 10, 22, 6, 0)
    with app.app_context():
        db.session.add(SignalCache(ticker="AAA", data_json="{}", updated_at=now - timedelta(hours=1)))
        db.session.add(SignalCache(ticker="BBB", data_json="{}", updated_at=now - timedelta(days=2)))
        db.session.commit()
        held = ["AAA", "BBB", "CCC"]
        assert tickers_due_for_refresh(held, display_on=False, now=now) == ["BBB", "CCC"]
        assert tickers_due_for_refresh(held, display_on=True, now=now) == held


# ── B1f: the daily budget window rolls over ────────────────────────────

def test_hard_stop_lifts_when_the_daily_window_ends(monkeypatch):
    # Past the hard stop _fmp_get returned before _track_call — the only
    # place the counter reset — so FMP stayed blocked until a restart.
    monkeypatch.setattr(fmp_service, "FMP_KEY", "k")
    monkeypatch.setattr(fmp_service, "_daily_calls", fmp_service._BUDGET_HARD_STOP)
    monkeypatch.setattr(fmp_service, "_daily_calls_reset", time.time() - 2 * 86400)
    seen = []

    class _Resp:
        status_code = 200

        def json(self):
            return [{"symbol": "AAPL"}]

    def fake_get(url, params=None, timeout=None):
        seen.append(url)
        return _Resp()

    monkeypatch.setattr(fmp_service.requests, "get", fake_get)
    assert fmp_service._fmp_get("/search-symbol", {"query": "AAPL"}) == [{"symbol": "AAPL"}]
    assert len(seen) == 1
    assert fmp_service._daily_calls == 1


def test_budget_stale_ends_with_the_daily_window(monkeypatch):
    monkeypatch.setattr(fmp_service, "_daily_calls", fmp_service._BUDGET_STALE_THRESHOLD)
    monkeypatch.setattr(fmp_service, "_daily_calls_reset", time.time() - 86400 - 1)
    assert fmp_service._is_budget_stale() is False


def test_budget_stale_holds_inside_the_daily_window(monkeypatch):
    monkeypatch.setattr(fmp_service, "_daily_calls", fmp_service._BUDGET_STALE_THRESHOLD)
    monkeypatch.setattr(fmp_service, "_daily_calls_reset", time.time() - 3600)
    assert fmp_service._is_budget_stale() is True


# ── B1d: FX spares the FMP budget ───────────────────────────────────────

def test_fx_skips_fmp_once_its_share_is_spent(monkeypatch):
    from services import fx_service

    monkeypatch.setattr(fmp_service, "_daily_calls", fmp_service._BUDGET_STALE_THRESHOLD // 2)
    monkeypatch.setattr(fmp_service, "get_fx_rate", lambda pair="USDKRW": pytest.fail("FMP FX call"))
    assert fx_service._fetch_from_fmp() is None


def test_fx_refresh_does_not_refetch_a_fresh_rate(monkeypatch):
    from services import fx_service

    monkeypatch.setattr(fx_service, "_usdkrw_ts", time.time() - 30)
    monkeypatch.setattr(fx_service, "_last_attempt_ts", 0.0)
    monkeypatch.setattr(fx_service, "_fetch_from_fmp", lambda: pytest.fail("refetched a fresh rate"))
    monkeypatch.setattr(fx_service, "_fetch_from_exchangerate_api", lambda: pytest.fail("refetched"))
    fx_service.refresh()


def test_fx_refresh_falls_back_when_fmp_is_skipped(monkeypatch):
    from services import fx_service

    monkeypatch.setattr(fx_service, "_usdkrw_ts", time.time() - 3600)
    monkeypatch.setattr(fx_service, "_last_attempt_ts", 0.0)
    monkeypatch.setattr(fmp_service, "_daily_calls", fmp_service._BUDGET_STALE_THRESHOLD)
    monkeypatch.setattr(fx_service, "_fetch_from_exchangerate_api", lambda: 1400.0)
    fx_service.refresh()
    assert fx_service._usdkrw == 1400.0


# ── B6: SSE cadence ─────────────────────────────────────────────────────

def test_sse_sleep_counts_from_tick_start():
    from routes.realtime import _MIN_STREAM_GAP, _next_sleep

    assert 3.5 < _next_sleep(time.monotonic() - 1.0, 5) <= 4.0
    assert _next_sleep(time.monotonic() - 9.0, 5) == _MIN_STREAM_GAP
