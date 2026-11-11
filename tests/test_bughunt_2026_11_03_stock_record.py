"""tests/test_bughunt_2026_11_03_stock_record.py — 2026-11-03 bug hunt.

Pins four fixes on 종목별 내 기록 and 내가 고른 회사들:

1. A date-only buy on the same KST day as a morning pause is a buy after it
   (friction_outcome's calendar-day rule), and sits after the pause on the
   timeline.
2. pick_facts spends its per-request sync budget on every source call, so a
   source outage cannot turn one request into one timeout per ticker.
3. Observation notes older than a year still show on the stock record.
4. Research and notes match the holding in any spelling (.KS / .KQ / bare).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from extensions import db
from models import ObservationNote, PreTradeReflection, TradeHistory

NOW = datetime(2026, 10, 20, 3, 0, 0)


def _trade(uid, ticker, action, at, shares=1.0, price=100.0, currency="KRW"):
    t = TradeHistory(
        user_id=uid, ticker=ticker, name="", action=action, shares=shares,
        price_per_share=price, total_value=shares * price, currency=currency,
        traded_at=at,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _build(uid, ticker, now=NOW):
    from services.stock_record import stock_record
    return stock_record(uid, ticker, now=now)


def test_date_only_buy_same_kst_day_follows_the_pause(app, make_user):
    me = make_user(email="bh-sr-dateonly@test.com")["id"]
    with app.app_context():
        pause_at = datetime(2026, 10, 15, 1, 0, 0)  # 10:00 KST
        db.session.add(PreTradeReflection(
            user_id=me, intended_ticker="005930.KS", intended_side="BUY", rationale="r",
            cooldown_started_at=pause_at, cooldown_ends_at=pause_at, cancelled_at=pause_at,
        ))
        db.session.commit()
        _trade(me, "005930.KS", "BUY", datetime(2026, 10, 15), price=70000)  # date-only
        out = _build(me, "005930")
    pause = next(e for e in out["events"] if e["kind"] == "pause")
    assert pause["bought_after"] is True
    assert out["counts"]["not_taken"] == 0
    assert [e["kind"] for e in out["events"]] == ["fill", "pause"]  # newest first
    fill = out["events"][0]
    assert fill["at"] == "2026-10-15T00:00:00"  # the stored date is unchanged


def test_pick_facts_budget_spent_on_failed_syncs(app, make_user, monkeypatch):
    import services.pick_facts.store as store
    from services.pick_facts import SYNC_BUDGET, pick_facts

    calls: list[str] = []

    def boom(source, key):
        calls.append(key)
        raise TimeoutError("read timed out")

    monkeypatch.setattr(store, "_fetch", boom)
    store.reset_sync_state()
    me = make_user(email="bh-pf-budget@test.com")["id"]
    tickers = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD"]
    now = datetime(2026, 10, 20)
    with app.app_context():
        app.config["FILINGS_ENABLED"] = True
        try:
            for i, tk in enumerate(tickers):
                _trade(me, tk, "BUY", now - timedelta(days=10 + i), currency="USD")
            out = pick_facts(me, now=now)
        finally:
            app.config["FILINGS_ENABLED"] = False
            store.reset_sync_state()
    assert len(calls) == SYNC_BUDGET
    assert out["pending"] == len(tickers)


def test_old_notes_stay_on_the_record(app, make_user):
    from services.observation_notes.service import create_note
    me = make_user(email="bh-sr-oldnote@test.com")["id"]
    with app.app_context():
        _trade(me, "AAPL", "BUY", NOW - timedelta(days=500), currency="USD")
        n = create_note(me, "애플 첫 메모", tickers=["AAPL"])
        db.session.get(ObservationNote, n["id"]).created_at = NOW - timedelta(days=400)
        db.session.commit()
        out = _build(me, "AAPL")
    assert [e["kind"] for e in out["events"]] == ["note", "fill"]
    assert out["counts"]["notes"] == 1


def test_research_and_notes_match_any_kr_spelling(app, make_user):
    from services.observation_notes.service import create_note
    from services.research_notes.service import create_research
    me = make_user(email="bh-sr-spelling@test.com")["id"]
    other = make_user(email="bh-sr-spelling-other@test.com")["id"]
    with app.app_context():
        _trade(me, "035720.KS", "BUY", NOW - timedelta(days=10), price=40000)
        create_research(me, {"ticker": "035720.KQ", "theses": ["카톡"], "review_months": 1})
        create_note(me, "카카오 메모", tickers=["035720.KQ"])
        create_note(me, "다른 종목", tickers=["0357201"])  # same prefix, another code
        create_research(other, {"ticker": "035720.KS", "theses": ["남의 것"], "review_months": 1})
        create_note(other, "남의 메모", tickers=["035720.KS"])
        views = {sp: _build(me, sp) for sp in ("035720.KS", "035720.KQ", "035720")}
    for sp, out in views.items():
        assert out["counts"]["research"] == 1, sp
        assert out["counts"]["notes"] == 1, sp
        assert out["counts"]["fills"] == 1, sp
