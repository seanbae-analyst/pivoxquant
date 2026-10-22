"""tests/test_sell_moment.py — 매도 순간의 거울.

services/sell_moment.py · routes/sell_moment.py · services/fill_memo.py::sell_note.
Pins: FIFO via fifo_util (partial closes, seed lots → no hold days, mixed
currency → no percent), only text written before the sell, nobody else's
rows, the route's auth/owner filter and verbatim user text through the
scrub, and the fill push — one pointer sentence for a lone 매도, never the
user's own words on the lock screen, never a raise.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.sell_moment import (
    MAX_WORDS,
    SOURCE_FILL_REASON,
    SOURCE_NOTE,
    SOURCE_PAUSE,
    SOURCE_RESEARCH,
    SellInput,
    Written,
    build_sell_moment,
    push_sentence,
)

T0 = datetime(2026, 9, 1, 1, 0)
NOW = datetime(2026, 10, 15, 3, 0)


def _trade(i, action, shares, price, at, *, ticker="AAPL", currency="USD", source=None):
    return SimpleNamespace(
        id=i, ticker=ticker, action=action, shares=shares, price_per_share=price,
        traded_at=at, currency=currency, source=source, pnl=0.0, pnl_pct=0.0,
    )


def _sell(shares=10.0, price=110.0, at=None, *, ticker="AAPL", currency="USD"):
    return SellInput(ticker=ticker, shares=shares, price=price, currency=currency,
                     traded_at=at or T0 + timedelta(days=30))


def _refl(text, at, *, ticker="AAPL", side="BUY", proceeded=False):
    return SimpleNamespace(intended_ticker=ticker, intended_side=side, rationale=text,
                           created_at=at, proceeded_at=at if proceeded else None)


def _research(theses, at, *, ticker="AAPL", invalidation=None):
    return SimpleNamespace(ticker=ticker, created_at=at, invalidation=invalidation,
                           theses_list=lambda: list(theses))


def _note(body, at, tickers=("AAPL",)):
    return SimpleNamespace(body=body, created_at=at, tickers_list=lambda: list(tickers))


# ── FIFO: hold days + vs cost ────────────────────────────────────────

def test_one_lot_hold_days_and_vs_cost():
    m = build_sell_moment(_sell(), trades=[_trade(1, "BUY", 10, 100.0, T0)], now=NOW)
    assert m["held_days"] == 30
    assert m["vs_cost_pct"] == pytest.approx(10.0)
    assert m["matched_shares"] == 10


def test_partial_close_takes_the_oldest_lots_first():
    trades = [
        _trade(1, "BUY", 5, 100.0, T0),
        _trade(2, "BUY", 10, 200.0, T0 + timedelta(days=20)),
    ]
    # Sell 10 on day 30 → 5 @100 (30 days) + 5 @200 (10 days).
    m = build_sell_moment(_sell(shares=10, price=165.0), trades=trades, now=NOW)
    assert m["held_days"] == 20  # share-weighted (30·5 + 10·5) / 10
    assert m["vs_cost_pct"] == pytest.approx(10.0)  # cost 150


def test_an_earlier_sell_already_used_the_first_lot():
    trades = [
        _trade(1, "BUY", 5, 100.0, T0),
        _trade(2, "BUY", 5, 200.0, T0 + timedelta(days=10)),
        _trade(3, "SELL", 5, 120.0, T0 + timedelta(days=15)),
    ]
    m = build_sell_moment(_sell(shares=5, price=180.0), trades=trades, now=NOW)
    assert m["held_days"] == 20
    assert m["vs_cost_pct"] == pytest.approx(-10.0)


def test_rows_after_the_sell_and_other_tickers_do_not_count():
    trades = [
        _trade(1, "BUY", 10, 100.0, T0),
        _trade(2, "BUY", 10, 500.0, T0 - timedelta(days=5), ticker="MSFT"),
        _trade(3, "SELL", 10, 999.0, T0 + timedelta(days=40)),
    ]
    m = build_sell_moment(_sell(), trades=trades, now=NOW)
    assert m["held_days"] == 30 and m["vs_cost_pct"] == pytest.approx(10.0)


def test_seed_lots_have_no_hold_days_but_a_cost():
    seed = _trade(1, "BUY", 10, 100.0, T0, source="holding_seed")
    m = build_sell_moment(_sell(), trades=[seed], now=NOW)
    assert m["held_days"] is None
    assert m["vs_cost_pct"] == pytest.approx(10.0)


def test_mixed_seed_and_dated_lots_hold_from_the_dated_ones():
    trades = [
        _trade(1, "BUY", 5, 100.0, T0 - timedelta(days=300), source="holding_seed"),
        _trade(2, "BUY", 5, 100.0, T0),
    ]
    m = build_sell_moment(_sell(), trades=trades, now=NOW)
    assert m["held_days"] == 30


def test_currency_mismatch_gives_no_percent():
    trades = [_trade(1, "BUY", 10, 100.0, T0, currency="KRW")]
    m = build_sell_moment(_sell(currency="USD"), trades=trades, now=NOW)
    assert m["held_days"] == 30
    assert m["vs_cost_pct"] is None


def test_no_lots_no_numbers():
    m = build_sell_moment(_sell(), trades=[], now=NOW)
    assert m["held_days"] is None and m["vs_cost_pct"] is None
    assert m["matched_shares"] == 0


def test_a_lot_without_price_gives_no_percent():
    m = build_sell_moment(_sell(), trades=[_trade(1, "BUY", 10, 0.0, T0)], now=NOW)
    assert m["held_days"] == 30 and m["vs_cost_pct"] is None


# ── Words ────────────────────────────────────────────────────────────

def test_words_only_before_the_sell_newest_first_with_sources():
    sell_at = T0 + timedelta(days=30)
    m = build_sell_moment(
        _sell(at=sell_at),
        reflections=[_refl("반도체 사이클 바닥이라고 봤다", T0 - timedelta(days=1))],
        fill_reasons=[Written("실적 발표 전에 들어간다", T0)],
        research=[_research(["서비스 매출이 오른다"], T0 - timedelta(days=3),
                            invalidation="두 분기 연속 감소")],
        notes=[_note("쓴 뒤의 메모", sell_at + timedelta(hours=1)),
               _note("가이던스가 약했다", T0 + timedelta(days=10))],
        now=NOW,
    )
    sources = [w["source"] for w in m["words"]]
    assert sources == [SOURCE_NOTE, SOURCE_FILL_REASON, SOURCE_PAUSE, SOURCE_RESEARCH]
    assert all("쓴 뒤" not in w["text"] for w in m["words"])
    research = m["words"][-1]
    assert research["invalidation"] == "두 분기 연속 감소"
    assert research["ticker"] == "AAPL" and research["at"].startswith("2026-08-29")


def test_words_cap_and_per_source_cap():
    notes = [_note(f"메모 {i}", T0 + timedelta(days=i)) for i in range(6)]
    refl = [_refl(f"멈춤 {i}", T0 - timedelta(days=i + 1)) for i in range(3)]
    m = build_sell_moment(_sell(), notes=notes, reflections=refl, now=NOW)
    assert len(m["words"]) == MAX_WORDS
    assert sum(1 for w in m["words"] if w["source"] == SOURCE_NOTE) == 2


def test_pause_sell_side_and_other_ticker_are_left_out_proceeded_first():
    m = build_sell_moment(
        _sell(),
        reflections=[
            _refl("팔려고 멈췄다", T0, side="SELL"),
            _refl("다른 종목", T0, ticker="MSFT"),
            _refl("나중 멈춤", T0 + timedelta(days=2)),
            _refl("실제로 산 멈춤", T0 - timedelta(days=5), proceeded=True),
            _refl("방향 없음", T0 + timedelta(days=1), side=None),
        ],
        now=NOW,
    )
    texts = [w["text"] for w in m["words"]]
    assert "팔려고 멈췄다" not in texts and "다른 종목" not in texts
    # proceeded pause is picked first, then the newest — two per source.
    assert set(texts) == {"실제로 산 멈춤", "나중 멈춤"}


def test_same_fill_reason_twice_is_one_quote():
    m = build_sell_moment(
        _sell(),
        fill_reasons=[Written("배당 보고 산다", T0), Written(" 배당 보고  산다", T0)],
        now=NOW,
    )
    assert [w["text"] for w in m["words"]] == ["배당 보고 산다"]


def test_long_text_is_clipped():
    m = build_sell_moment(_sell(), fill_reasons=[Written("가" * 900, T0)], now=NOW)
    assert len(m["words"][0]["text"]) <= 280


def test_words_cut_never_later_than_now():
    late = NOW + timedelta(days=1)
    m = build_sell_moment(
        _sell(at=late), fill_reasons=[Written("미래에 쓴 말", NOW + timedelta(hours=1))],
        now=NOW, words_before=late,
    )
    assert m["words"] == []


# ── Push sentence ────────────────────────────────────────────────────

def test_push_sentence_is_pointer_and_facts_only():
    s = push_sentence({"words": [{"text": "비밀스러운 내 이유"}], "held_days": 34, "vs_cost_pct": -4.04})
    assert s == "이 종목에 적어 둔 말이 있어요 · 34일 보유 · 산 값 대비 −4.0%."
    assert "비밀스러운" not in s


def test_push_sentence_empty_without_words_or_hold():
    assert push_sentence({"words": [], "held_days": None, "vs_cost_pct": 5.0}) == ""
    assert push_sentence({"words": [], "held_days": 0, "vs_cost_pct": None}) == "하루 미만 보유."


# ── DB: loader, route, push ──────────────────────────────────────────

def _seed_user_rows(user_id, *, ticker="005930.KS"):
    """A 매수 fill + an approved reason + a pause + a note, 30 days ago."""
    from extensions import db
    from models import ObservationNote, PreTradeReflection, TradeHistory
    from models.import_batch import ImportBatch, PendingTrade
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    bought = now - timedelta(days=30)
    db.session.add(TradeHistory(
        user_id=user_id, ticker=ticker, action="BUY", shares=10.0,
        price_per_share=70000.0, total_value=700000.0, currency="KRW", traded_at=bought,
    ))
    batch = ImportBatch(user_id=user_id, source="csv")
    db.session.add(batch)
    db.session.flush()
    db.session.add(PendingTrade(
        batch_id=batch.id, user_id=user_id, ticker=ticker, name="삼성전자", action="BUY",
        shares=10.0, price=70000.0, currency="KRW", traded_at=bought, status="approved",
        dedupe_key=f"b-{user_id}", approved_thesis="HBM 공급 계약을 보고 산다",
        approved_at=bought + timedelta(hours=1),
    ))
    db.session.add(PreTradeReflection(
        user_id=user_id, intended_ticker=ticker, intended_side="BUY",
        rationale="메모리 가격 반등을 기다렸다", cooldown_started_at=bought,
        cooldown_ends_at=bought, proceeded_at=bought, created_at=bought - timedelta(hours=2),
    ))
    db.session.add(ObservationNote(
        user_id=user_id, body="목표가 상향 기사를 읽었다", tickers_json=f'["{ticker}"]',
        created_at=bought + timedelta(days=3),
    ))
    db.session.commit()
    return batch.id


def _pending_sell(user_id, batch_id, *, price=66500.0, ticker="005930.KS", status="pending"):
    from extensions import db
    from models.import_batch import PendingTrade
    row = PendingTrade(
        batch_id=batch_id, user_id=user_id, ticker=ticker, name="삼성전자", action="SELL",
        shares=4.0, price=price, currency="KRW", traded_at=datetime.now(timezone.utc).replace(tzinfo=None),
        status=status, dedupe_key=f"s-{user_id}-{price}",
    )
    db.session.add(row)
    db.session.commit()
    return row.id


def test_route_pending_sell_returns_own_words_verbatim(client, app, auth_user):
    with app.app_context():
        batch = _seed_user_rows(auth_user["id"])
        pid = _pending_sell(auth_user["id"], batch)
    r = client.get(f"/api/sell-moment/pending/{pid}")
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["ok"] is True and body["disclaimer"]
    assert body["held_days"] == 30
    assert body["vs_cost_pct"] == pytest.approx(-5.0)
    texts = [w["text"] for w in body["words"]]
    # "목표가 상향" is a scrub target elsewhere — the user's own note stays.
    assert "목표가 상향 기사를 읽었다" in texts
    assert "HBM 공급 계약을 보고 산다" in texts
    assert "메모리 가격 반등을 기다렸다" in texts


def test_route_pending_buy_or_approved_row_is_empty(client, app, auth_user):
    with app.app_context():
        batch = _seed_user_rows(auth_user["id"])
        done = _pending_sell(auth_user["id"], batch, status="approved")
        from models.import_batch import PendingTrade
        buy = PendingTrade.query.filter_by(user_id=auth_user["id"], action="BUY").first().id
    for pid in (done, buy):
        body = client.get(f"/api/sell-moment/pending/{pid}").get_json()
        assert body["words"] == [] and body["held_days"] is None


def test_route_other_users_pending_is_404_and_rows_never_leak(client, app, make_user, auth_user):
    other = make_user(email="sm-other@test.com")
    with app.app_context():
        their_batch = _seed_user_rows(other["id"])
        theirs = _pending_sell(other["id"], their_batch)
    assert client.get(f"/api/sell-moment/pending/{theirs}").status_code == 404
    # A typed sell of the same ticker sees none of the other user's rows.
    body = client.get("/api/sell-moment?ticker=005930.KS&shares=4&price=66500").get_json()
    assert body["words"] == [] and body["held_days"] is None and body["vs_cost_pct"] is None


def test_route_typed_sell_uses_the_date_like_the_trade_route(client, app, auth_user):
    with app.app_context():
        _seed_user_rows(auth_user["id"])
    today = datetime.now(timezone.utc).date().isoformat()
    r = client.get(f"/api/sell-moment?ticker=005930&shares=4&price=77000&date={today}")
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["ticker"] == "005930.KS"
    assert body["vs_cost_pct"] == pytest.approx(10.0)
    assert body["held_days"] in (29, 30)  # date-grain: midnight of today
    assert len(body["words"]) == 3


def test_route_bad_input(client, auth_user):
    assert client.get("/api/sell-moment?ticker=AAPL&shares=0&price=1").status_code == 400
    assert client.get("/api/sell-moment?shares=1&price=1").status_code == 400
    assert client.get("/api/sell-moment?ticker=AAPL&shares=1&price=nan").status_code == 400


def test_route_requires_auth(client):
    assert client.get("/api/sell-moment?ticker=AAPL&shares=1&price=1").status_code in (401, 403)
    assert client.get("/api/sell-moment/pending/1").status_code in (401, 403)


# ── fill push (services/fill_memo.py) ────────────────────────────────

def test_lone_sell_fill_push_carries_one_pointer_sentence(app, make_user):
    from services import fill_memo
    u = make_user(email="sm-push@test.com")
    with app.app_context():
        batch = _seed_user_rows(u["id"])
        pid = _pending_sell(u["id"], batch)
        rows = [{"id": pid, "status": "pending", "action": "SELL", "name": "삼성전자", "shares": 4}]
        with patch("services.push_service.send_push_to_user") as send:
            assert fill_memo.notify_fill_memo(u["id"], rows) is True
    body = send.call_args.kwargs["body"]
    assert "이 종목에 적어 둔 말이 있어요 · 30일 보유 · 산 값 대비 −5.0%." in body
    assert len(body) <= 200 and "이유" in body
    for private in ("HBM", "메모리 가격", "목표가"):
        assert private not in body
    for word in ("매수", "매도", "BUY", "SELL", "추천", "조언"):
        assert word not in body


def test_buy_fill_push_is_unchanged(app, make_user):
    from services import fill_memo
    u = make_user(email="sm-buy@test.com")
    with app.app_context():
        _seed_user_rows(u["id"])
        from models.import_batch import PendingTrade
        buy = PendingTrade.query.filter_by(user_id=u["id"], action="BUY").first()
        buy.status = "pending"
        from extensions import db
        db.session.commit()
        rows = [{"id": buy.id, "status": "pending", "action": "BUY", "name": "삼성전자", "shares": 10}]
        assert fill_memo.sell_note(u["id"], rows) == ""
        with patch("services.push_service.send_push_to_user") as send:
            fill_memo.notify_fill_memo(u["id"], rows)
    assert send.call_args.kwargs["body"] == (
        "삼성전자 10주 체결이 들어왔습니다. 잊기 전에 이유를 한 줄 남겨 두세요."
    )


def test_sell_note_never_raises_and_needs_exactly_one_row(app, make_user):
    from services import fill_memo
    u = make_user(email="sm-raise@test.com")
    with app.app_context():
        batch = _seed_user_rows(u["id"])
        pid = _pending_sell(u["id"], batch)
        one = [{"id": pid, "status": "pending"}]
        two = one + [{"id": pid + 999, "status": "pending"}]
        assert fill_memo.sell_note(u["id"], two) == ""
        with patch("services.sell_moment.load_sell_moment", side_effect=RuntimeError("db")):
            assert fill_memo.sell_note(u["id"], one) == ""
        # Someone else's pending id reads as nothing.
        assert fill_memo.sell_note(u["id"] + 1000, one) == ""


# ── 2026-10-21 버그헌팅 ──────────────────────────────────────────────

def test_suffix_variants_are_one_stock_for_lots_and_words():
    """.KQ 로 적힌 매수·멈춤·노트·리서치가 .KS(또는 접미사 없는) 매도에 붙는다."""
    bought = T0
    kw = dict(
        trades=[_trade(1, "BUY", 10, 100.0, bought, ticker="035720.KQ", currency="KRW")],
        reflections=[_refl("본업 회복을 기다렸다", bought - timedelta(hours=1), ticker="035720.KQ")],
        research=[_research(["광고 매출 반등"], bought + timedelta(days=1), ticker="035720")],
        notes=[_note("실적 발표를 봤다", bought + timedelta(days=2), tickers=("035720.KQ",))],
        now=NOW,
    )
    for sold in ("035720.KS", "035720"):
        m = build_sell_moment(_sell(shares=4, price=125.0, ticker=sold, currency="KRW"), **kw)
        assert m["held_days"] == 30 and m["vs_cost_pct"] == pytest.approx(25.0)
        assert m["matched_shares"] == 4
        assert {w["source"] for w in m["words"]} == {SOURCE_PAUSE, SOURCE_RESEARCH, SOURCE_NOTE}


def test_end_of_day_is_the_end_of_the_kst_day():
    from services.sell_moment import end_of_day
    # 2026-10-16 (KST) 의 끝 = 10-16 15:00 UTC.
    assert end_of_day(datetime(2026, 10, 16)) == datetime(2026, 10, 16, 15, 0)


def test_date_only_sell_takes_words_from_that_kst_day_only():
    day = datetime(2026, 10, 16)  # 날짜만 — KST 10-16
    notes = [
        _note("D 오후 4시(KST)에 쓴 노트", datetime(2026, 10, 16, 7, 0)),
        _note("D+1 새벽 2시(KST)에 쓴 노트", datetime(2026, 10, 16, 17, 0)),
    ]
    # 날짜만 있는 매도(가져오기·대기 체결)는 words_before 없이도 그날 끝까지.
    m = build_sell_moment(_sell(at=day), notes=notes, now=datetime(2026, 10, 20))
    assert [w["text"] for w in m["words"]] == ["D 오후 4시(KST)에 쓴 노트"]


def test_route_typed_date_excludes_next_kst_morning(client, app, auth_user):
    from extensions import db
    from models import ObservationNote
    with app.app_context():
        for body, at in (("그날 쓴 노트", datetime(2026, 10, 16, 7, 0)),
                         ("다음날 새벽 노트", datetime(2026, 10, 16, 17, 0))):
            db.session.add(ObservationNote(user_id=auth_user["id"], body=body,
                                           tickers_json='["AAPL"]', created_at=at))
        db.session.commit()
    body = client.get("/api/sell-moment?ticker=AAPL&shares=1&price=10&date=2026-10-16").get_json()
    assert [w["text"] for w in body["words"]] == ["그날 쓴 노트"]


def test_route_pending_date_only_sell_keeps_that_days_words(client, app, auth_user):
    from extensions import db
    from models import ObservationNote
    from models.import_batch import ImportBatch, PendingTrade
    with app.app_context():
        batch = ImportBatch(user_id=auth_user["id"], source="csv")
        db.session.add(batch)
        db.session.flush()
        row = PendingTrade(
            batch_id=batch.id, user_id=auth_user["id"], ticker="AAPL", name="Apple", action="SELL",
            shares=1.0, price=10.0, currency="USD", traded_at=datetime(2026, 10, 16),
            status="pending", dedupe_key="s-date-only",
        )
        db.session.add(row)
        db.session.add(ObservationNote(user_id=auth_user["id"], body="그날 낮에 쓴 노트",
                                       tickers_json='["AAPL"]', created_at=datetime(2026, 10, 16, 3, 0)))
        db.session.commit()
        pid = row.id
    body = client.get(f"/api/sell-moment/pending/{pid}").get_json()
    assert [w["text"] for w in body["words"]] == ["그날 낮에 쓴 노트"]


def test_buy_time_reasons_are_not_pushed_out_by_newer_notes_and_research():
    m = build_sell_moment(
        _sell(),
        reflections=[_refl("멈춰서 적은 이유", T0 - timedelta(days=1))],
        fill_reasons=[Written("체결 때 적은 이유", T0)],
        research=[_research([f"가정{i}"], T0 + timedelta(days=5 + i)) for i in range(2)],
        notes=[_note(f"노트{i}", T0 + timedelta(days=10 + i)) for i in range(3)],
        now=NOW,
    )
    sources = [w["source"] for w in m["words"]]
    assert len(sources) == MAX_WORDS
    assert set(sources) == {SOURCE_PAUSE, SOURCE_FILL_REASON, SOURCE_RESEARCH, SOURCE_NOTE}
    ats = [w["at"] for w in m["words"]]
    assert ats == sorted(ats, reverse=True)


def test_same_kst_day_round_trip_is_under_a_day():
    # 날짜만 매수(KST 10-01) → 같은 KST 날 23:30 매도(= 14:30 UTC).
    buy = _trade(1, "BUY", 1, 100.0, datetime(2026, 10, 1))
    m = build_sell_moment(_sell(shares=1, at=datetime(2026, 10, 1, 14, 30)), trades=[buy], now=NOW)
    assert m["held_days"] == 0
    # 09:00 KST 매수(전날 UTC 자정 바로 뒤가 아니라 그날 00:00 UTC +1µs) → 다음 KST 날 매도 = 1일.
    buy = _trade(1, "BUY", 1, 100.0, datetime(2026, 10, 1, 0, 0, 0, 1))
    m = build_sell_moment(_sell(shares=1, at=datetime(2026, 10, 1, 16, 0)), trades=[buy], now=NOW)
    assert m["held_days"] == 1


def test_tiny_negative_percent_has_no_minus_sign():
    assert push_sentence({"words": [], "held_days": 3, "vs_cost_pct": -0.04}) == "3일 보유 · 산 값 대비 0.0%."
    assert push_sentence({"words": [], "held_days": 3, "vs_cost_pct": -0.05001}) == "3일 보유 · 산 값 대비 −0.1%."


def test_sell_note_rolls_back_after_a_failed_statement(app, make_user):
    from services import fill_memo
    u = make_user(email="sm-rollback@test.com")
    with app.app_context():
        batch = _seed_user_rows(u["id"])
        pid = _pending_sell(u["id"], batch)
        with patch("services.sell_moment.load_sell_moment", side_effect=RuntimeError("db")), \
                patch("extensions.db.session.rollback") as rollback:
            assert fill_memo.sell_note(u["id"], [{"id": pid, "status": "pending"}]) == ""
        assert rollback.called
