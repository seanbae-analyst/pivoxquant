"""B3 — cohort-scaled daily AI budget (services/ai_budget.py).

The business-model audit (docs/strategy/business_model_audit_2026-06-10.md
§B3) found the per-service AI budgets were FIXED global counters, so the
cap doubled as a paid-user ceiling: with weekly memo's 200/day, the 201st
entitled Pro user silently received placeholder content. DailyAiBudget
keeps the cost defence but scales the ceiling with the cohort the cron
notes (max(base, ceil(entitled × headroom))), adds an env override per
budget, and logs one WARNING per day at >= 80% so exhaustion is visible
before it bites a paying user.
"""
from __future__ import annotations

import logging
from datetime import date

from services.ai_budget import DailyAiBudget


def _fresh(base=5, **kw):
    return DailyAiBudget("test_kind", base, **kw)


# ── core semantics ──────────────────────────────────────────────────────────

def test_base_limit_enforced_then_day_roll_resets():
    b = _fresh(base=3)
    for _ in range(3):
        assert b.available()
        b.consume()
    assert not b.available()

    # Next UTC day → counters reset.
    b._today = lambda: date(2099, 1, 2)  # instance attr shadows staticmethod
    assert b.available()
    snap = b.snapshot()
    assert snap["count"] == 0 and snap["entitled"] == 0


def test_cohort_scales_ceiling_above_base():
    """THE B3 regression (scaled down): old fixed cap = 5 would starve the
    6th entitled user; with a noted cohort of 20 the ceiling becomes
    ceil(20 × 1.25) = 25 and everyone is served."""
    b = _fresh(base=5)
    b.note_entitled(20)
    assert b.snapshot()["limit"] == 25
    for _ in range(20):  # the whole cohort fits — nobody hits placeholders
        assert b.available()
        b.consume()
    assert b.available()  # 25% headroom remains for legitimate retries
    for _ in range(5):
        b.consume()
    assert not b.available()  # runaway beyond headroom still trips


def test_cohort_below_base_keeps_base_floor():
    b = _fresh(base=10)
    b.note_entitled(2)
    assert b.snapshot()["limit"] == 10  # max() semantics — base is a floor


def test_note_entitled_cumulative_within_day():
    """Prebrief's 10-minute scans note repeatedly; the tally accumulates
    (headroom only ever widens within a day)."""
    b = _fresh(base=5)
    b.note_entitled(3)
    b.note_entitled(4)
    snap = b.snapshot()
    assert snap["entitled"] == 7
    assert snap["limit"] == 9  # ceil(7 × 1.25)


def test_note_entitled_garbage_is_noop():
    b = _fresh(base=5)
    b.note_entitled(0)
    b.note_entitled(-3)
    b.note_entitled(None)
    b.note_entitled("not-a-number")
    assert b.snapshot()["entitled"] == 0


def test_env_override_and_bad_value_ignored(monkeypatch):
    b = _fresh(base=2, env_var="PIVOX_TEST_AI_LIMIT")
    monkeypatch.setenv("PIVOX_TEST_AI_LIMIT", "4")
    assert b.snapshot()["limit"] == 4
    monkeypatch.setenv("PIVOX_TEST_AI_LIMIT", "banana")
    assert b.snapshot()["limit"] == 2  # falls back to base, no raise
    monkeypatch.setenv("PIVOX_TEST_AI_LIMIT", "-9")
    assert b.snapshot()["limit"] == 2  # non-positive ignored


def test_warns_once_per_day_at_80pct(caplog):
    b = _fresh(base=10)
    with caplog.at_level(logging.WARNING, logger="services.ai_budget"):
        for _ in range(8):
            b.consume()
        warns = [r for r in caplog.records if "test_kind" in r.getMessage()]
        assert len(warns) == 1, "exactly one 80% warning"
        b.consume()
        warns = [r for r in caplog.records if "test_kind" in r.getMessage()]
        assert len(warns) == 1, "no repeat warning the same day"


def test_try_consume_atomic_exhaustion():
    b = _fresh(base=2)
    assert b.try_consume()
    assert b.try_consume()
    assert not b.try_consume()  # exhausted → False, count not incremented
    assert b.snapshot()["count"] == 2


def test_warn_fires_before_exhaustion_for_small_limits(caplog):
    """Bug-hunt #10: for limit<=4, `count >= WARN_PCT*limit` (float) warned AT
    exhaustion (0.8*4=3.2 → warns at count 4 == limit). floor() gives a genuine
    advance warning whenever limit>=2."""
    b = _fresh(base=5)
    with caplog.at_level(logging.WARNING, logger="services.ai_budget"):
        for _ in range(4):  # floor(0.8*5)=4 → warn fires at the 4th
            b.consume()
        warns = [r for r in caplog.records if "test_kind" in r.getMessage()]
        assert len(warns) == 1
        assert b.available(), "warning must fire BEFORE exhaustion (count 4 < limit 5)"


# ── earnings_tone budget remaining (bug-hunt #9) ─────────────────────────────

def test_earnings_tone_budget_remaining_no_nameerror(monkeypatch):
    """Previously referenced a deleted `_earnings_tone_usage` dict (NameError if
    ever called) and a fixed constant. Now reads the live snapshot."""
    import services.cache_service as cs
    monkeypatch.setattr(
        cs, "_earnings_tone_budget", DailyAiBudget("earnings_tone", 5),
    )
    assert cs.earnings_tone_budget_remaining() == 5
    cs.earnings_tone_budget_check_and_increment()
    cs.earnings_tone_budget_check_and_increment()
    assert cs.earnings_tone_budget_remaining() == 3  # tracks the SAME counter


# ── interactive AI daily ceiling (bug-hunt #2) ───────────────────────────────

def _stub_ai(available: bool):
    return type("StubAI", (), {"available": available})()


def test_interactive_ai_guard_429_when_exhausted(app, monkeypatch):
    import routes.ai as rai
    monkeypatch.setattr(rai, "ai", _stub_ai(True))
    monkeypatch.setattr(rai, "_interactive_ai_budget", DailyAiBudget("interactive_ai", 1))

    @rai._interactive_ai_budget_guard
    def ok_view():
        return {"ok": True}, 200

    calls = {"n": 0}

    @rai._interactive_ai_budget_guard
    def counted_view():
        calls["n"] += 1
        return {"ok": True}, 200

    with app.app_context():
        _, status = ok_view()            # spends the only unit (2xx → consume)
        assert status == 200
        resp = counted_view()            # budget gone → 429, handler skipped
        assert resp[1] == 429
        assert calls["n"] == 0


def test_interactive_ai_guard_does_not_consume_on_503(app, monkeypatch):
    """An Anthropic outage returns 503 fast — those must NOT consume budget,
    or a sustained outage would trip the breaker and lock everyone out."""
    import routes.ai as rai
    monkeypatch.setattr(rai, "ai", _stub_ai(True))
    b = DailyAiBudget("interactive_ai", 5)
    monkeypatch.setattr(rai, "_interactive_ai_budget", b)

    @rai._interactive_ai_budget_guard
    def failing_view():
        return {"error": "AI down"}, 503

    with app.app_context():
        for _ in range(10):
            failing_view()
    assert b.snapshot()["count"] == 0


def test_interactive_ai_guard_skips_when_ai_unconfigured(app, monkeypatch):
    import routes.ai as rai
    monkeypatch.setattr(rai, "ai", _stub_ai(False))
    b = DailyAiBudget("interactive_ai", 1)
    monkeypatch.setattr(rai, "_interactive_ai_budget", b)

    @rai._interactive_ai_budget_guard
    def view():
        return {"ok": True}, 200

    with app.app_context():
        for _ in range(3):
            view()
    assert b.snapshot()["count"] == 0  # never gated when AI is unavailable


def test_interactive_ai_guard_present_on_on_demand_routes():
    """Source-level lock: the six on-demand AI routes must carry the daily
    ceiling guard (regression for the enforcement gap). Same convention as
    test_crons_note_their_cohorts_in_source."""
    import inspect
    import routes.ai as rai

    src = inspect.getsource(rai)
    for name in ("swot", "competitor", "sector_trend",
                 "commentary", "morning_summary", "coaching"):
        marker = f"@_interactive_ai_budget_guard\ndef {name}("
        assert marker in src, f"{name} missing @_interactive_ai_budget_guard"


# ── call-site wiring ────────────────────────────────────────────────────────

def test_weekly_memo_wrappers_delegate(monkeypatch):
    import services.artifacts.weekly_memo_service as wms

    monkeypatch.setattr(wms, "_AI_BUDGET", DailyAiBudget("weekly_memo", 1))
    assert wms._ai_budget_available()
    wms._ai_budget_consume()
    assert not wms._ai_budget_available()


def test_prebrief_wrappers_delegate(monkeypatch):
    import services.artifacts.earnings_prebrief_service as eps

    monkeypatch.setattr(eps, "_AI_BUDGET", DailyAiBudget("earnings_prebrief", 1))
    assert eps._ai_budget_available()
    eps._ai_budget_consume()
    assert not eps._ai_budget_available()


def test_crons_note_their_cohorts_in_source():
    """run_weekly() and run_scan() must record the entitled fan-out so the
    ceiling scales — source-level lock (same convention as the force-fire
    tier test)."""
    import inspect

    import services.artifacts.weekly_memo_service as wms
    import services.artifacts.earnings_prebrief_service as eps

    assert "note_entitled" in inspect.getsource(wms.WeeklyMemoService.run_weekly)
    assert "note_entitled" in inspect.getsource(eps.EarningsPreBriefService.run_scan)


def test_earnings_tone_stays_global_with_env_lever(monkeypatch):
    """Tone budget keeps global semantics (per-ticker shared cache) but is
    now env-tunable and atomic via try_consume."""
    import services.cache_service as cs

    monkeypatch.setattr(
        cs, "_earnings_tone_budget",
        DailyAiBudget("earnings_tone", 1, env_var="PIVOX_EARNINGS_TONE_DAILY_LIMIT"),
    )
    assert cs.earnings_tone_budget_check_and_increment()
    assert not cs.earnings_tone_budget_check_and_increment()
    # env raise takes effect without restart (read at check time)
    monkeypatch.setenv("PIVOX_EARNINGS_TONE_DAILY_LIMIT", "3")
    assert cs.earnings_tone_budget_check_and_increment()
