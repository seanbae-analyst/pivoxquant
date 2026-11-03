"""tests/test_bughunt_2026_11_03_filings.py — 공시 레이어 버그 사냥 회귀 (2026-11-03).

Pins four fixes in services/filing_timeline:
1. 가설 다시 보기 skips an account pending deletion (PIPA §21 — no bell, no push),
   like every other sender (services/alert.py, services/fill_memo.py).
2. The hourly sync budget goes to the tickers synced longest ago, so a name
   past the first ``ticker_budget`` in sort order still gets its turn.
3. Next year's report on the same month/day is a new filing, not a duplicate
   of this year's alert (the title has no year).
4. "실적 발표 N번" counts release days — a KR company filing 별도 and 연결
   잠정실적 on one day released once.
SEC / DART are stubbed.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from extensions import db
from models import Alert, ResearchNote
from services.filing_timeline import store
from services.filing_timeline.research_check import KIND, run_once


def _payload(rows):
    cols = {"form": [], "filingDate": [], "accessionNumber": [], "items": [], "primaryDocument": []}
    for form, day, acc, items in rows:
        cols["form"].append(form)
        cols["filingDate"].append(day)
        cols["accessionNumber"].append(acc)
        cols["items"].append(items)
        cols["primaryDocument"].append("doc.htm")
    return {"filings": {"recent": cols}}


@pytest.fixture
def sec(monkeypatch, app):
    from services.data.edgar import EdgarService

    calls = []
    rows = {
        "AAPL": [("10-Q", "2026-07-31", "0000320193-26-000020", "")],
        "ZM": [("10-Q", "2026-07-31", "0001585521-26-000020", "")],
    }

    def fake(cls, ticker, **_kw):
        calls.append(ticker)
        return "0000320193", _payload(rows.get(ticker, []))

    monkeypatch.setattr(EdgarService, "get_submissions", classmethod(fake))
    monkeypatch.setattr("services.name_resolver.resolve_stock_name", lambda t: None)
    monkeypatch.setitem(app.config, "FILINGS_ENABLED", True)
    store.reset_sync_state()
    yield calls, rows
    store.reset_sync_state()


def _note(uid, ticker, created):
    db.session.add(ResearchNote(
        user_id=uid, ticker=ticker, business="", theses_json='["매출이 는다"]', invalidation="x",
        review_on=date(2027, 12, 1), created_at=created,
    ))
    db.session.commit()


def test_account_pending_deletion_gets_no_bell_and_no_push(app, make_user, sec, monkeypatch):
    from models import User

    pushed = []
    monkeypatch.setattr("services.push_service.notify_bell_alert", lambda **kw: pushed.append(kw))
    me = make_user(email="bh1103-del@test.com")["id"]
    with app.app_context():
        User.query.get(me).deletion_requested_at = datetime(2026, 8, 1)
        db.session.commit()
        _note(me, "AAPL", datetime(2026, 7, 1, 3, 0))
        out = run_once(now=datetime(2026, 8, 20))
        assert Alert.query.filter_by(user_id=me, kind=KIND).count() == 0
    assert out["notes"] == 0 and out["alerts"] == 0
    assert pushed == []


def test_budget_reaches_tickers_past_the_first_ones(app, make_user, sec):
    calls, _rows = sec
    a = make_user(email="bh1103-a@test.com")["id"]
    b = make_user(email="bh1103-b@test.com")["id"]
    with app.app_context():
        _note(a, "AAPL", datetime(2026, 7, 1, 3, 0))
        _note(b, "ZM", datetime(2026, 7, 1, 3, 0))
        run_once(now=datetime(2026, 8, 20, 0), ticker_budget=1)
        run_once(now=datetime(2026, 8, 20, 1), ticker_budget=1)
        assert Alert.query.filter_by(user_id=b, kind=KIND).count() == 1
    assert calls == ["AAPL", "ZM"]   # the second hour goes to the one not yet synced


def _run_at(now):
    """run_once at ``now``, with the alerts it made stamped ``now`` (as in prod —
    Alert.created_at is the wall clock, the test clock is not)."""
    before = {a.id for a in Alert.query.all()}
    out = run_once(now=now)
    for a in Alert.query.all():
        if a.id not in before:
            a.created_at = now
    db.session.commit()
    return out


def test_next_years_filing_on_the_same_day_is_not_a_duplicate(app, make_user, sec):
    _calls, rows = sec
    me = make_user(email="bh1103-yr@test.com")["id"]
    with app.app_context():
        _note(me, "AAPL", datetime(2026, 7, 1, 3, 0))
        assert _run_at(datetime(2026, 8, 20))["alerts"] == 1
        assert _run_at(datetime(2026, 8, 20, 1))["alerts"] == 0        # same filing — once
        rows["AAPL"] = [("10-Q", "2027-07-31", "0000320193-27-000020", ""),
                        ("10-Q", "2026-07-31", "0000320193-26-000020", "")]
        store.reset_sync_state()
        assert _run_at(datetime(2027, 8, 2))["alerts"] == 1            # a new filing
        assert _run_at(datetime(2027, 8, 2, 1))["alerts"] == 0
        assert Alert.query.filter_by(user_id=me, kind=KIND).count() == 2


def test_kr_earnings_count_is_release_days(app, monkeypatch):
    from services.filing_timeline import dart, filing_timeline
    from services.filing_timeline.sec import ParsedFiling

    monkeypatch.setitem(app.config, "FILINGS_ENABLED", True)
    monkeypatch.setenv("DART_API_KEY", "test-key")
    rows = [
        ParsedFiling("20261030800001", "I002", "", date(2026, 10, 30), "u1", "영업(잠정)실적(공정공시)"),
        ParsedFiling("20261030800002", "I002", "", date(2026, 10, 30), "u2",
                     "연결재무제표기준영업(잠정)실적(공정공시)"),
        ParsedFiling("20241114000001", "A", "", date(2024, 11, 14), "u3", "분기보고서 (2024.09)"),
    ]
    monkeypatch.setattr(dart, "fetch", lambda code, **kw: ("00100000", rows))
    store.reset_sync_state()
    try:
        with app.app_context():
            out = filing_timeline("999990", fills=[], since=date(2026, 1, 1), market="kr")
    finally:
        store.reset_sync_state()
    assert out["reaction"]["earnings"] == 1
