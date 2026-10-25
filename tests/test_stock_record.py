"""tests/test_stock_record.py — 종목별 내 기록 (services/stock_record).

Pins: only the caller's own records, matched as one holding across
spellings (005930 / 005930.KS); registration seeds show as "registered",
adjust rows not at all; a pause before buying that no buy followed counts as
not taken, a linked or later buy does not; research and notes come in whole;
events are newest first; the route is auth-gated, scrubbed, keeps the
user's own words verbatim and carries no score / grade words.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from extensions import db
from models import PreTradeReflection, TradeHistory

NOW = datetime(2026, 10, 20, 3, 0, 0)


def _trade(uid, ticker, action, at, shares=1.0, price=100.0, source=None, reflection_id=None,
           currency="USD"):
    t = TradeHistory(
        user_id=uid, ticker=ticker, name="", action=action, shares=shares,
        price_per_share=price, total_value=shares * price, currency=currency,
        traded_at=at, source=source, reflection_id=reflection_id,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _pause(uid, ticker, side, at, *, proceeded=False, cancelled=False, rationale="실적·숫자"):
    r = PreTradeReflection(
        user_id=uid, intended_ticker=ticker, intended_side=side, rationale=rationale,
        cooldown_started_at=at, cooldown_ends_at=at,
        proceeded_at=at if proceeded else None, cancelled_at=at if cancelled else None,
    )
    db.session.add(r)
    db.session.commit()
    return r


def _build(app, uid, ticker):
    from services.stock_record import stock_record
    with app.app_context():
        return stock_record(uid, ticker, now=NOW)


def test_one_holding_across_spellings_and_only_own_rows(app, make_user):
    me = make_user(email="sr-me@test.com")["id"]
    other = make_user(email="sr-other@test.com")["id"]
    with app.app_context():
        _trade(me, "005930.KS", "BUY", NOW - timedelta(days=30), shares=10, price=70000, currency="KRW")
        _trade(me, "005930", "SELL", NOW - timedelta(days=5), shares=4, price=65000, currency="KRW")
        _trade(me, "000660.KS", "BUY", NOW - timedelta(days=5))       # another stock
        _trade(other, "005930.KS", "BUY", NOW - timedelta(days=2))    # another user
    out = _build(app, me, "005930")
    assert out["ticker"] == "005930.KS"
    fills = [e for e in out["events"] if e["kind"] == "fill"]
    assert [(e["side"], e["shares"]) for e in fills] == [("sell", 4.0), ("buy", 10.0)]  # newest first
    assert out["counts"]["fills"] == 2 and out["counts"]["buys"] == 1 and out["counts"]["sells"] == 1


def test_registration_rows(app, make_user):
    me = make_user(email="sr-reg@test.com")["id"]
    with app.app_context():
        _trade(me, "AAPL", "BUY", NOW - timedelta(days=40), shares=5, price=150, source="holding_seed")
        _trade(me, "AAPL", "SELL", NOW - timedelta(days=30), shares=1, price=150, source="holding_adjust")
        _trade(me, "AAPL", "BUY", NOW - timedelta(days=3), shares=1, price=180)
    out = _build(app, me, "AAPL")
    kinds = [e["kind"] for e in out["events"]]
    assert kinds == ["fill", "registered"]
    assert out["counts"]["fills"] == 1


def test_not_taken_counts_pauses_no_buy_followed(app, make_user):
    me = make_user(email="sr-pause@test.com")["id"]
    with app.app_context():
        # paused, cancelled, never bought → not taken
        _pause(me, "TSLA", "BUY", NOW - timedelta(days=20), cancelled=True)
        # paused, proceeded, bought (linked) → taken
        r = _pause(me, "TSLA", "BUY", NOW - timedelta(days=10), proceeded=True)
        _trade(me, "TSLA", "BUY", NOW - timedelta(days=10) + timedelta(hours=1), reflection_id=r.id)
        # a pause before selling is never "not taken"
        _pause(me, "TSLA", "SELL", NOW - timedelta(days=2), cancelled=True)
    out = _build(app, me, "TSLA")
    assert out["counts"]["pauses"] == 3
    # the first pause is followed by the later (linked) buy → it is not counted
    # as not taken either; only pauses with no later buy are.
    assert out["counts"]["not_taken"] == 0
    pauses = [e for e in out["events"] if e["kind"] == "pause"]
    assert [p["side"] for p in pauses] == ["exit", "entry", "entry"]
    assert pauses[0]["bought_after"] is None


def test_a_pause_with_no_buy_after_is_not_taken(app, make_user):
    me = make_user(email="sr-nt@test.com")["id"]
    with app.app_context():
        _trade(me, "NVDA", "BUY", NOW - timedelta(days=30))
        _pause(me, "NVDA", "BUY", NOW - timedelta(days=10), cancelled=True)
    out = _build(app, me, "NVDA")
    assert out["counts"]["not_taken"] == 1
    assert [e for e in out["events"] if e["kind"] == "pause"][0]["bought_after"] is False


def test_research_and_notes_come_in_whole(app, make_user):
    from services.observation_notes.service import create_note
    from services.research_notes import create_research
    me = make_user(email="sr-rn@test.com")["id"]
    with app.app_context():
        create_research(me, {"ticker": "AAPL", "theses": ["서비스 매출이 오른다"]})
        create_research(me, {"ticker": "AAPL", "theses": ["교체 주기"], "invalidation": "두 분기 감소"})
        create_note(me, "거래량이 두껍다", tickers=["AAPL"])
        create_note(me, "다른 종목 얘기", tickers=["MSFT"])
    out = _build(app, me, "aapl")
    assert out["counts"]["research"] == 2 and out["counts"]["notes"] == 1
    research = [e for e in out["events"] if e["kind"] == "research"]
    assert {tuple(r["theses"]) for r in research} == {("서비스 매출이 오른다",), ("교체 주기",)}
    assert [e["body"] for e in out["events"] if e["kind"] == "note"] == ["거래량이 두껍다"]


def test_holding_summary_from_positions(app, make_user, add_position):
    me = make_user(email="sr-hold@test.com")["id"]
    add_position(me, ticker="AAPL", shares=10, avg_cost=150)
    out = _build(app, me, "AAPL")
    assert out["holding"]["shares"] == 10
    assert out["holding"]["avg_cost"] == pytest.approx(150)
    assert out["holding"]["currency"] == "USD"
    assert _build(app, me, "MSFT")["holding"] is None


def test_route_is_auth_gated_keeps_words_and_has_no_score(client, auth_user, app):
    assert client.get("/api/stock-record/AAPL").status_code in (200,)  # logged in
    with app.app_context():
        _pause(auth_user["id"], "AAPL", "BUY", NOW, cancelled=True,
               rationale="리포트에서 추천 종목이라고 봤다")  # the user's own words
    resp = client.get("/api/stock-record/AAPL")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True and body["disclaimer"]
    assert [e["rationale"] for e in body["events"] if e["kind"] == "pause"] == ["리포트에서 추천 종목이라고 봤다"]
    blob = json.dumps({k: v for k, v in body.items() if k not in ("events", "disclaimer")}, ensure_ascii=False)
    for word in ("score", "grade", "점수", "등급"):
        assert word not in blob


def test_route_requires_login(raw_client):
    assert raw_client.get("/api/stock-record/AAPL").status_code in (401, 302)
