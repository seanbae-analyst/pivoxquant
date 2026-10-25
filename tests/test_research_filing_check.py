"""tests/test_research_filing_check.py — 가설 다시 보기 (services/filing_timeline/research_check).

Pins: an open research note gets one bell alert for the latest periodic report
or earnings release filed after the day it was written — not a current report,
not the writing day itself, not twice; a scored note and a name without a
source get nothing; the alert carries no words of the user's note (those are
encrypted at rest, alerts are not); bell + one push, both muted by the
research_filing setting row; flag off → no call at all. SEC is stubbed.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from extensions import db
from models import Alert, ResearchNote
from services.filing_timeline import store
from services.filing_timeline.research_check import KIND, run_once

NOW = datetime(2026, 8, 20, 0, 0, 0)
SECRET = "재고가 두 분기 연속 늘어난다"


def _payload(rows):
    cols = {"form": [], "filingDate": [], "accessionNumber": [], "items": [], "primaryDocument": []}
    for form, day, acc, items in rows:
        cols["form"].append(form)
        cols["filingDate"].append(day)
        cols["accessionNumber"].append(acc)
        cols["items"].append(items)
        cols["primaryDocument"].append("doc.htm")
    return {"filings": {"recent": cols}}


ROWS = [
    ("8-K", "2026-08-10", "0000320193-26-000030", "5.02"),       # current report — not a reason
    ("10-Q", "2026-07-31", "0000320193-26-000020", ""),          # ← the one
    ("8-K", "2026-07-30", "0000320193-26-000018", "2.02,9.01"),
    ("10-Q", "2026-05-01", "0000320193-26-000013", ""),          # before the note
]


@pytest.fixture
def sec(monkeypatch, app):
    from services.data.edgar import EdgarService

    calls = []

    def fake(cls, ticker, **_kw):
        calls.append(ticker)
        return "0000320193", _payload(ROWS)

    monkeypatch.setattr(EdgarService, "get_submissions", classmethod(fake))
    monkeypatch.setattr("services.name_resolver.resolve_stock_name", lambda t: "Apple" if t == "AAPL" else None)
    monkeypatch.setitem(app.config, "FILINGS_ENABLED", True)
    store.reset_sync_state()
    yield calls
    store.reset_sync_state()


def _note(uid, ticker, created, *, reviewed=False):
    n = ResearchNote(
        user_id=uid, ticker=ticker, business="", theses_json='["매출이 는다"]', invalidation=SECRET,
        review_on=date(2026, 12, 1), created_at=created,
        reviewed_at=created if reviewed else None,
    )
    db.session.add(n)
    db.session.commit()
    return n


def test_one_bell_for_the_latest_report_after_the_note(app, make_user, sec, monkeypatch):
    pushed = []
    monkeypatch.setattr("services.push_service.notify_bell_alert", lambda **kw: pushed.append(kw))
    me = make_user(email="rfc-me@test.com")["id"]
    with app.app_context():
        _note(me, "AAPL", datetime(2026, 7, 1, 3, 0))
        _note(me, "AAPL", datetime(2026, 7, 20, 3, 0))      # a second note → still one alert
        first = run_once(now=NOW)
        again = run_once(now=NOW)
        alerts = Alert.query.filter_by(user_id=me, kind=KIND).all()
        assert len(alerts) == 1
        a = alerts[0]
        assert a.title == "새 공시 · Apple 분기보고서 (7/31)"
        assert "7월 1일에 쓴 리서치" in a.body
        assert a.link == "/journal/stock/AAPL" and a.ticker == "AAPL"
        assert SECRET not in (a.title + a.body)
    assert first["alerts"] == 1 and again["alerts"] == 0
    assert sec == ["AAPL"]          # one sync per ticker per day
    assert [p["kind"] for p in pushed] == ["research_filing"]   # one push, with the bell


def test_setting_row_mutes_the_bell(app, make_user, sec):
    from models import User

    me = make_user(email="rfc-mute@test.com")["id"]
    with app.app_context():
        u = User.query.get(me)
        u.notification_prefs = {"research_filing": {"inapp": False, "push": False}}
        db.session.commit()
        _note(me, "AAPL", datetime(2026, 7, 1, 3, 0))
        out = run_once(now=NOW)
        assert Alert.query.filter_by(user_id=me, kind=KIND, push_only=False).count() == 0
    assert out["alerts"] == 0


def test_setting_row_is_visible_only_with_filings_on(app, monkeypatch):
    from models.user import visible_notification_event_ids

    with app.app_context():
        monkeypatch.setitem(app.config, "FILINGS_ENABLED", True)
        assert "research_filing" in visible_notification_event_ids()
        monkeypatch.setitem(app.config, "FILINGS_ENABLED", False)
        assert "research_filing" not in visible_notification_event_ids()


def test_scored_notes_same_day_and_no_source_get_nothing(app, make_user, sec):
    me = make_user(email="rfc-none@test.com")["id"]
    with app.app_context():
        _note(me, "AAPL", datetime(2026, 7, 1, 3, 0), reviewed=True)
        _note(me, "MSFT", datetime(2026, 7, 31, 3, 0))      # written on the filing day itself
        _note(me, "005930.KS", datetime(2026, 7, 1, 3, 0))  # no DART key in tests
        out = run_once(now=NOW)
        assert Alert.query.filter_by(user_id=me, kind=KIND).count() == 0
    assert out["notes"] == 1 and out["alerts"] == 0


def test_flag_off_calls_nothing(app, make_user, sec, monkeypatch):
    monkeypatch.setitem(app.config, "FILINGS_ENABLED", False)
    me = make_user(email="rfc-off@test.com")["id"]
    with app.app_context():
        _note(me, "AAPL", datetime(2026, 7, 1, 3, 0))
        assert run_once(now=NOW) == {"notes": 0, "tickers": 0, "synced": 0, "alerts": 0}
    assert sec == []
