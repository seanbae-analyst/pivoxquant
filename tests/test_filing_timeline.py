"""tests/test_filing_timeline.py — 종목 기록의 미국 공시 (services/filing_timeline).

Pins: only the company's own periodic / current reports are shown (no Form 4,
no 13G, no 424B), named from a fixed list, 8-K item 2.02 as 실적 발표 (an
amendment is not a second release); the "after an earnings release" count
uses the official US filing date — the day after through three days after,
never the release day, never a date-only fill — and US Eastern dates across
DST; SEC is asked at most once a day per ticker (an hour after a failure) and
a duplicate never lands twice; the stock record carries filings only with
FILINGS_ENABLED on, only for US names the user has records on, and loads
without them when SEC fails. No network: SEC is stubbed everywhere.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from extensions import db
from models import CompanyFiling, TradeHistory
from services.filing_timeline import store
from services.filing_timeline.reaction import FillPoint, earnings_reaction, us_date
from services.filing_timeline.sec import filing_url, is_earnings, label_for, parse_recent

CIK = "0000320193"
NOW = datetime(2026, 8, 10, 3, 0, 0)


def _payload(rows):
    """rows: (form, filingDate, accession, items, primaryDocument) — SEC's parallel arrays."""
    cols = {"form": [], "filingDate": [], "accessionNumber": [], "items": [], "primaryDocument": []}
    for form, day, acc, items, doc in rows:
        cols["form"].append(form)
        cols["filingDate"].append(day)
        cols["accessionNumber"].append(acc)
        cols["items"].append(items)
        cols["primaryDocument"].append(doc)
    return {"cik": "320193", "name": "Apple Inc.", "filings": {"recent": cols}}


ROWS = [
    ("8-K", "2026-07-30", "0000320193-26-000018", "2.02,9.01", "aapl-20260730.htm"),
    ("4", "2026-07-29", "0000320193-26-000017", "", "xslF345X05/wk-form4.xml"),
    ("10-Q", "2026-05-01", "0000320193-26-000013", "", "aapl-20260328.htm"),
    ("8-K", "2026-04-30", "0000320193-26-000011", "2.02,9.01", "aapl-20260430.htm"),
    ("8-K", "2026-04-20", "0001140361-26-015711", "5.02", "ef20071035_8k.htm"),
    ("SC 13G/A", "2026-02-10", "0000950123-26-000001", "", "x.htm"),
    ("424B2", "2026-02-01", "0000950123-26-000002", "", "y.htm"),
    ("8-K/A", "2026-01-31", "0000320193-26-000005", "2.02", ""),
    ("10-K", "2025-10-31", "0000320193-25-000079", "", "aapl-20250927.htm"),
]


# ── sec.py ──────────────────────────────────────────────────────────────────


def test_parse_keeps_only_company_reports_with_fixed_names():
    rows = parse_recent(_payload(ROWS), CIK)
    assert [r.form for r in rows] == ["8-K", "10-Q", "8-K", "8-K", "8-K/A", "10-K"]
    assert [label_for(r.form, r.items) for r in rows] == [
        "실적 발표", "분기보고서", "실적 발표", "수시보고", "실적 발표 정정", "연간보고서",
    ]
    # The amendment of an earnings 8-K is not a second release.
    assert [is_earnings(r.form, r.items) for r in rows] == [True, False, True, False, False, False]
    assert rows[0].filed_on == date(2026, 7, 30)
    assert rows[0].url == (
        "https://www.sec.gov/Archives/edgar/data/320193/000032019326000018/aapl-20260730.htm"
    )
    # No primary document → the filing's index page.
    amended = rows[4]
    assert amended.url.endswith("/000032019326000005/0000320193-26-000005-index.htm")


def test_parse_skips_broken_rows_and_foreign_issuer_forms_are_named():
    payload = _payload([
        ("6-K", "2026-10-15", "0001046179-26-000726", "", "tsm-6k.htm"),
        ("20-F", "2026-04-15", "0001046179-26-000300", "", "tsm-20f.htm"),
        ("8-K", "", "0000320193-26-000099", "2.02", "z.htm"),     # no date
        ("10-Q", "2026-05-01", "", "", "w.htm"),                   # no accession
    ])
    rows = parse_recent(payload, "0001046179")
    assert [(r.form, label_for(r.form, r.items)) for r in rows] == [("6-K", "수시보고"), ("20-F", "연간보고서")]
    assert parse_recent({}, CIK) == [] and parse_recent(None, CIK) == []
    assert filing_url("1046179", "0001046179-26-000726", None).endswith("-index.htm")


# ── reaction.py ─────────────────────────────────────────────────────────────


def test_us_date_follows_eastern_dst():
    assert us_date(datetime(2026, 1, 15, 3, 0)) == date(2026, 1, 14)   # EST 22:00
    assert us_date(datetime(2026, 7, 15, 3, 0)) == date(2026, 7, 14)   # EDT 23:00
    assert us_date(datetime(2026, 7, 15, 4, 30)) == date(2026, 7, 15)  # EDT 00:30 (EST would be 7/14)


def test_counts_day_after_through_three_days_never_release_day():
    d = date(2026, 7, 30)  # 실적 발표 (Thu)
    fills = [
        FillPoint(datetime(2026, 7, 30, 15, 0), "buy"),            # 11:00 ET on D → before/at release, not counted
        FillPoint(datetime(2026, 7, 31, 2, 0), "buy"),             # 7/30 22:00 ET → still D in New York
        FillPoint(datetime(2026, 7, 31, 14, 0), "buy"),            # D+1 → counted
        FillPoint(datetime(2026, 8, 2, 14, 0), "sell"),            # D+3 → counted
        FillPoint(datetime(2026, 8, 3, 14, 0), "sell"),            # D+4 → not
        FillPoint(datetime(2026, 8, 1, 0, 0), "buy", untimed=True),  # date-only → set aside
    ]
    out = earnings_reaction(fills, [d], coverage_from=date(2026, 1, 1))
    assert out == {
        "window_days": 3, "buys_after": 1, "sells_after": 1, "timed_fills": 5, "untimed_fills": 1,
    }


def test_fills_before_coverage_are_not_judged():
    d = date(2026, 7, 30)
    fills = [
        FillPoint(datetime(2026, 7, 31, 14, 0), "buy"),   # within coverage+3 → judged
        FillPoint(datetime(2026, 7, 2, 14, 0), "buy"),    # too close to coverage start → skipped
    ]
    out = earnings_reaction(fills, [d], coverage_from=date(2026, 7, 1))
    assert out["timed_fills"] == 1 and out["buys_after"] == 1
    assert earnings_reaction(fills, [d], coverage_from=None)["timed_fills"] == 0


# ── store.py ────────────────────────────────────────────────────────────────


@pytest.fixture
def sec_stub(monkeypatch):
    """Stub SEC: returns ``state['payload']`` (or raises) and counts calls."""
    from services.data.edgar import EdgarService

    state = {"calls": 0, "payload": _payload(ROWS), "raise": False}

    def fake(ticker, **_kw):
        state["calls"] += 1
        if state["raise"]:
            raise RuntimeError("boom")
        return (CIK, state["payload"]) if state["payload"] else (None, None)

    monkeypatch.setattr(EdgarService, "get_submissions", classmethod(lambda cls, t, **kw: fake(t, **kw)))
    store.reset_sync_state()
    yield state
    store.reset_sync_state()


def test_sync_once_a_day_and_never_twice_the_same_filing(app, sec_stub):
    t0 = 1_800_000_000.0
    with app.app_context():
        assert store.sync_ticker("AAPL", now_ts=t0) is True
        assert len(store.stored_filings("AAPL")) == 6
        assert store.sync_ticker("AAPL", now_ts=t0 + 3600) is False      # same day → no call
        assert sec_stub["calls"] == 1
        sec_stub["payload"] = _payload([
            ("10-Q", "2026-07-31", "0000320193-26-000020", "", "aapl-20260627.htm"),
        ] + ROWS)
        assert store.sync_ticker("AAPL", now_ts=t0 + 25 * 3600) is True  # next day → one new row
        rows = store.stored_filings("AAPL")
        assert len(rows) == 7 and rows[0].filed_on == date(2026, 7, 31)
        assert CompanyFiling.query.filter_by(accession="0000320193-26-000018").count() == 1


def test_failed_sync_waits_an_hour(app, sec_stub):
    t0 = 1_800_000_000.0
    sec_stub["raise"] = True
    with app.app_context():
        assert store.sync_ticker("AAPL", now_ts=t0) is False
        assert store.sync_ticker("AAPL", now_ts=t0 + 600) is False
        assert sec_stub["calls"] == 1
        sec_stub["raise"] = False
        assert store.sync_ticker("AAPL", now_ts=t0 + 3601) is True
        assert sec_stub["calls"] == 2


# ── stock_record integration ────────────────────────────────────────────────


def _trade(uid, ticker, action, at, currency="USD"):
    t = TradeHistory(
        user_id=uid, ticker=ticker, name="", action=action, shares=1.0,
        price_per_share=100.0, total_value=100.0, currency=currency, traded_at=at,
    )
    db.session.add(t)
    db.session.commit()
    return t


@pytest.fixture
def filings_on(app, monkeypatch):
    monkeypatch.setitem(app.config, "FILINGS_ENABLED", True)


def _record(app, uid, ticker):
    from services.stock_record import stock_record
    with app.app_context():
        return stock_record(uid, ticker, now=NOW)


def test_stock_record_lays_filings_between_own_records(app, make_user, sec_stub, filings_on):
    me = make_user(email="ft-on@test.com")["id"]
    with app.app_context():
        _trade(me, "AAPL", "BUY", datetime(2026, 7, 31, 14, 0))     # D+1 of the 7/30 release
        _trade(me, "AAPL", "SELL", datetime(2026, 8, 5, 14, 0))     # D+6 → not counted
        _trade(me, "AAPL", "BUY", datetime(2026, 5, 1, 0, 0))       # date-only (KST 00:00)
    out = _record(app, me, "AAPL")
    filings = [e for e in out["events"] if e["kind"] == "filing"]
    # Since a month before the first record (2026-05-01 → 2026-04-01): 7/30, 5/1, 4/30, 4/20.
    assert [(e["filed_on"], e["label"]) for e in filings] == [
        ("2026-07-30", "실적 발표"), ("2026-05-01", "분기보고서"),
        ("2026-04-30", "실적 발표"), ("2026-04-20", "수시보고"),
    ]
    assert all(e["source"] == "SEC EDGAR" and e["url"].startswith("https://www.sec.gov/") for e in filings)
    assert out["counts"]["filings"] == 4
    assert out["filing_reaction"] == {
        "window_days": 3, "buys_after": 1, "sells_after": 0,
        "timed_fills": 2, "untimed_fills": 1, "earnings": 2,
    }
    # Newest first across kinds; the release sits under the next day's buy.
    kinds = [(e["kind"], e["at"][:10]) for e in out["events"]][:3]
    assert kinds == [("fill", "2026-08-05"), ("fill", "2026-07-31"), ("filing", "2026-07-30")]


def test_flag_off_or_korean_or_no_records_never_calls_sec(app, make_user, sec_stub, monkeypatch):
    me = make_user(email="ft-off@test.com")["id"]
    with app.app_context():
        _trade(me, "AAPL", "BUY", datetime(2026, 7, 31, 14, 0))
        _trade(me, "005930.KS", "BUY", datetime(2026, 7, 31, 1, 0), currency="KRW")
    out = _record(app, me, "AAPL")                    # flag off (default)
    assert out["counts"]["filings"] == 0 and out["filing_reaction"] is None
    monkeypatch.setitem(app.config, "FILINGS_ENABLED", True)
    out = _record(app, me, "005930")                  # Korean name → not SEC's
    assert out["counts"]["filings"] == 0 and out["filing_reaction"] is None
    out = _record(app, me, "MSFT")                    # no records on this name
    assert out["events"] == [] and out["counts"]["filings"] == 0
    assert sec_stub["calls"] == 0


def test_sec_failure_still_loads_the_page(app, make_user, sec_stub, filings_on):
    me = make_user(email="ft-fail@test.com")["id"]
    sec_stub["raise"] = True
    with app.app_context():
        _trade(me, "AAPL", "BUY", datetime(2026, 7, 31, 14, 0))
    out = _record(app, me, "AAPL")
    assert [e["kind"] for e in out["events"]] == ["fill"]
    assert out["counts"]["filings"] == 0 and out["filing_reaction"] is None


def test_route_carries_filings_with_source(client, auth_user, app, sec_stub, filings_on):
    with app.app_context():
        _trade(auth_user["id"], "AAPL", "BUY", datetime(2026, 7, 31, 14, 0))
    body = client.get("/api/stock-record/AAPL").get_json()
    assert body["ok"] is True
    filings = [e for e in body["events"] if e["kind"] == "filing"]
    assert filings and {e["source"] for e in filings} == {"SEC EDGAR"}
    assert body["filing_reaction"]["buys_after"] == 1


# ── edgar.py ────────────────────────────────────────────────────────────────


def test_failed_cik_map_is_retried_not_kept_for_a_week(monkeypatch):
    import services.data.edgar as edgar

    monkeypatch.setattr(edgar, "_TICKER_TO_CIK", None)
    monkeypatch.setattr(edgar, "_CIK_MAP_FAILED_AT", 0.0)
    monkeypatch.setattr(edgar, "_CACHE", {})
    calls = {"n": 0}
    clock = {"t": 1_800_000_000.0}

    def fake_get(url, retries=2, timeout=15):
        calls["n"] += 1
        return None if calls["n"] == 1 else {"0": {"ticker": "AAPL", "cik_str": 320193}}

    monkeypatch.setattr(edgar.EdgarService, "_get", staticmethod(fake_get))
    monkeypatch.setattr(edgar.time, "time", lambda: clock["t"])
    assert edgar.EdgarService.get_cik("AAPL") is None
    assert edgar.EdgarService.get_cik("AAPL") is None and calls["n"] == 1   # inside the retry window
    clock["t"] += edgar._CIK_MAP_RETRY_SECONDS + 1
    assert edgar.EdgarService.get_cik("AAPL") == "0000320193" and calls["n"] == 2


def test_submissions_tries_the_dash_form_for_class_shares(monkeypatch):
    import services.data.edgar as edgar

    monkeypatch.setattr(edgar, "_TICKER_TO_CIK", {"BRK-B": "0001067983"})
    seen = []

    def fake_get(url, retries=2, timeout=15):
        seen.append((url, retries, timeout))
        return {"filings": {"recent": {}}}

    monkeypatch.setattr(edgar.EdgarService, "_get", staticmethod(fake_get))
    cik, payload = edgar.EdgarService.get_submissions("BRK.B")
    assert cik == "0001067983" and payload == {"filings": {"recent": {}}}
    assert seen == [("https://data.sec.gov/submissions/CIK0001067983.json", 1, 8)]
    assert edgar.EdgarService.get_submissions("NOPE") == (None, None)
