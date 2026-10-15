"""tests/test_imports_bughunt_2026_10_15.py — Import Inbox + holdings resync.

1. Two genuine fills of one size and price at different times of one day are
   two fills: both land pending and both approve. One fill read twice stays
   one, and a manual date-only entry still blocks the same fill imported
   with a time (``services/imports/dedupe.py`` module doc, "Times").
2. A fill at 09:00 KST is 00:00 UTC. It used to read as date-only — linked
   to a pause written hours after it. The parser now says whether a time was
   printed (``RawTrade.time_given``) and a timed instant on UTC midnight is
   stored 1 µs later (``services.imports.as_timed``).
3. The import's pause matching uses the same-stock key of
   ``pre_trade.link.same_ticker`` (``.KS`` / ``.KQ`` are one stock).
4. Holdings resync: the same-stock key for ``existing`` / replace / close
   conflict, and a close with no rows (everything sold).
"""
from __future__ import annotations

from datetime import datetime

import pytest

IMPORTS = "/api/portfolio/imports"
PENDING = f"{IMPORTS}/pending"
HOLDINGS = "/api/portfolio/holdings-import"


@pytest.fixture(autouse=True)
def _fixed_fx(monkeypatch):
    monkeypatch.setattr("services.fx_service.get_rate", lambda: 1300.0)
    monkeypatch.setattr("routes.holdings_import._warm_async", lambda app, t: None)


def _paste(client, text):
    r = client.post(f"{IMPORTS}/", json={"text": text, "consent": True})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["pending"]


def _approve(client, pid):
    return client.post(f"{PENDING}/{pid}/approve", json={"thesis": "실적 발표 전에 샀다"})


def _manual_fill(app, user_id, traded_at, ticker="005930.KS", shares=1.0, price=71200.0):
    from extensions import db
    from models import TradeHistory
    with app.app_context():
        db.session.add(TradeHistory(
            user_id=user_id, ticker=ticker, name="삼성전자", action="BUY",  # // legal-ok
            shares=shares, price_per_share=price, total_value=shares * price,
            pnl=0.0, pnl_pct=0.0, currency="KRW", traded_at=traded_at,
        ))
        db.session.commit()


def _trade_count(app, user_id):
    from models import TradeHistory
    with app.app_context():
        return TradeHistory.query.filter_by(user_id=user_id).count()


def _reflection(app, user_id, created_at, ticker="005930.KS"):
    from extensions import db
    from models import PreTradeReflection
    with app.app_context():
        r = PreTradeReflection(
            user_id=user_id, intended_ticker=ticker, intended_side="BUY",
            rationale="멈춤", cooldown_started_at=created_at,
            cooldown_ends_at=created_at, created_at=created_at,
        )
        db.session.add(r)
        db.session.commit()
        return r.id


# ── 1. same day, same size and price ─────────────────────────────────

class TestSameDayFills:
    def test_two_genuine_fills_at_different_times_both_record(self, app, client, auth_user):
        rows = _paste(client, "삼성전자 1주 매수 체결 71,200원 2026-09-01 09:05\n"
                              "삼성전자 1주 매수 체결 71,200원 2026-09-01 10:30")
        assert [r["status"] for r in rows] == ["pending", "pending"]
        assert _approve(client, rows[0]["id"]).status_code == 200
        second = _approve(client, rows[1]["id"])
        assert second.status_code == 200, second.get_json()
        assert _trade_count(app, auth_user["id"]) == 2

    def test_a_later_import_of_another_time_is_not_a_duplicate(self, app, client, auth_user):
        first = _paste(client, "삼성전자 1주 매수 체결 71,200원 2026-09-01 09:05")[0]
        assert _approve(client, first["id"]).status_code == 200
        later = _paste(client, "삼성전자 1주 매수 체결 71,200원 2026-09-01 10:30")[0]
        assert later["status"] == "pending"

    def test_one_fill_read_twice_within_a_minute_is_one(self, app, client, auth_user):
        # A second-precision file row, then a source that printed 09:06 for the
        # same fill — different minute keys, 10 s apart.
        first = _paste(client, "삼성전자 1주 매수 체결 71,200원 2026-09-01 09:05:50")[0]
        assert _approve(client, first["id"]).status_code == 200
        again = _paste(client, "삼성전자 1주 매수 체결 71,200원 2026-09-01 09:06")[0]
        assert again["status"] == "duplicate"

    def test_approval_refuses_the_same_fill_read_twice(self, app, client, auth_user):
        rows = _paste(client, "삼성전자 1주 매수 체결 71,200원 2026-09-01 09:05:50\n"
                              "삼성전자 1주 매수 체결 71,200원 2026-09-01 09:06")
        assert [r["status"] for r in rows] == ["pending", "pending"]  # minute keys differ
        assert _approve(client, rows[0]["id"]).status_code == 200
        dup = _approve(client, rows[1]["id"])
        assert dup.status_code == 409 and dup.get_json()["code"] == "IMPORT_DUPLICATE"
        assert _trade_count(app, auth_user["id"]) == 1

    def test_manual_date_only_entry_still_blocks_a_timed_import(self, app, client, auth_user):
        _manual_fill(app, auth_user["id"], datetime(2026, 9, 1))
        row = _paste(client, "삼성전자 1주 매수 체결 71,200원 2026-09-01 14:30")[0]
        assert row["status"] == "duplicate"

    def test_manual_date_only_entry_after_intake_blocks_approval(self, app, client, auth_user):
        row = _paste(client, "삼성전자 1주 매수 체결 71,200원 2026-09-01 14:30")[0]
        _manual_fill(app, auth_user["id"], datetime(2026, 9, 1))
        r = _approve(client, row["id"])
        assert r.status_code == 409 and r.get_json()["code"] == "IMPORT_DUPLICATE"
        assert _trade_count(app, auth_user["id"]) == 1

    def test_manual_entry_stamped_at_entry_time_is_day_precision(self, app, client, auth_user):
        # No import wrote it, so its time is when it was typed, not a fill time.
        _manual_fill(app, auth_user["id"], datetime(2026, 9, 1, 6, 12, 3, 456))
        row = _paste(client, "삼성전자 1주 매수 체결 71,200원 2026-09-01 09:05")[0]
        assert row["status"] == "duplicate"

    def test_date_only_import_matches_a_timed_one(self, app, client, auth_user):
        first = _paste(client, "삼성전자 1주 매수 체결 71,200원 2026-09-01 10:30")[0]
        assert _approve(client, first["id"]).status_code == 200
        dated = _paste(client, "삼성전자 1주 매수 체결 71,200원 2026-09-01")[0]
        assert dated["traded_at"] == "2026-09-01T00:00:00"
        assert dated["status"] == "duplicate"


# ── 2. 09:00 KST vs the date-only shape ──────────────────────────────

class TestTimeGiven:
    def test_0900_kst_fill_is_timed_and_links_to_the_earlier_pause(self, app, client, auth_user):
        before = _reflection(app, auth_user["id"], datetime(2026, 8, 31, 23, 50))  # 08:50 KST
        _reflection(app, auth_user["id"], datetime(2026, 9, 1, 5, 0))               # 14:00 KST
        row = _paste(client, "삼성전자 10주 매수 체결 71,200원 2026-09-01 09:00")[0]
        assert row["traded_at"] == "2026-09-01T00:00:00.000001"
        assert row["pre_trade_reflection_id"] == before

    def test_approved_0900_fill_keeps_its_time(self, app, client, auth_user):
        from models import TradeHistory
        from services.imports import is_date_only
        row = _paste(client, "삼성전자 10주 매수 체결 71,200원 2026-09-01 09:00")[0]
        assert _approve(client, row["id"]).status_code == 200
        with app.app_context():
            t = TradeHistory.query.filter_by(user_id=auth_user["id"]).one()
            assert t.traded_at == datetime(2026, 9, 1, 0, 0, 0, 1)
            assert not is_date_only(t.traded_at)

    def test_date_only_paste_stays_date_only(self, app, client, auth_user):
        row = _paste(client, "삼성전자 10주 매수 체결 71,200원 2026-09-01")[0]
        assert row["traded_at"] == "2026-09-01T00:00:00"

    def test_patch_to_0900_kst(self, app, client, auth_user):
        row = _paste(client, "삼성전자 10주 매수 체결 71,200원 2026-09-01")[0]
        r = client.patch(f"{PENDING}/{row['id']}", json={"traded_at": "2026-09-02 09:00"})
        assert r.status_code == 200, r.get_json()
        assert r.get_json()["pending"]["traded_at"] == "2026-09-02T00:00:00.000001"
        r = client.patch(f"{PENDING}/{row['id']}", json={"traded_at": "2026-09-03"})
        assert r.get_json()["pending"]["traded_at"] == "2026-09-03T00:00:00"

    def test_us_fill_at_midnight_kst_moves_back_nine_hours(self):
        from services.imports import kst_to_utc
        from services.imports.text_parser import parse_text
        [t] = parse_text("AAPL 1주 매수 체결 $190 2026-09-01 00:00")
        assert t.time_given is True
        assert kst_to_utc(t.traded_at, has_time=t.time_given) == datetime(2026, 8, 31, 15, 0)

    def test_kst_to_utc_follows_the_parser_not_the_clock(self):
        from services.imports import kst_to_utc
        assert kst_to_utc(datetime(2026, 9, 1, 9, 0), has_time=True) == datetime(2026, 9, 1, 0, 0, 0, 1)
        assert kst_to_utc(datetime(2026, 9, 1, 9, 1), has_time=True) == datetime(2026, 9, 1, 0, 1)
        assert kst_to_utc(datetime(2026, 9, 1), has_time=False) == datetime(2026, 9, 1)

    @pytest.mark.parametrize("value, time_value, expected", [
        ("2026-09-01", None, (datetime(2026, 9, 1), False)),
        ("2026-09-01 00:00", None, (datetime(2026, 9, 1), True)),
        ("2026-09-01", "09:00", (datetime(2026, 9, 1, 9, 0), True)),
        # our own export re-imported: the stored 1 µs survives
        ("2026-09-01T00:00:00.000001", None, (datetime(2026, 9, 1, 0, 0, 0, 1), True)),
        (datetime(2026, 9, 1), None, (datetime(2026, 9, 1), False)),  # an xlsx date cell
    ])
    def test_parse_reports_whether_a_time_was_given(self, value, time_value, expected):
        from services.imports import parse_datetime_has_time
        assert parse_datetime_has_time(value, time_value) == expected

    def test_explicit_zone_on_utc_midnight_is_timed(self):
        from services.imports import parse_datetime_tz
        assert parse_datetime_tz("2026-09-01T09:00:00+09:00") == (datetime(2026, 9, 1), True, True)


# ── 3. pause matching: one same-stock rule ───────────────────────────

class TestPauseTickerKey:
    def test_kq_pause_matches_a_ks_fill(self, app, auth_user):
        from services.imports.ledger import PreTradeIndex, match_pre_trade
        rid = _reflection(app, auth_user["id"], datetime(2026, 9, 1, 1, 0), ticker="035720.KQ")
        fill = datetime(2026, 9, 1, 2, 0)
        with app.app_context():
            assert match_pre_trade(auth_user["id"], "035720.KS", fill) == rid
            assert PreTradeIndex(auth_user["id"], {"035720.KS"}, fill, fill).match("035720.KS", fill) == rid

    def test_class_shares_stay_apart(self, app, auth_user):
        from services.imports.ledger import PreTradeIndex, match_pre_trade
        _reflection(app, auth_user["id"], datetime(2026, 9, 1, 1, 0), ticker="BRK")
        _reflection(app, auth_user["id"], datetime(2026, 9, 1, 1, 0), ticker="BRK.A")
        fill = datetime(2026, 9, 1, 2, 0)
        with app.app_context():
            assert match_pre_trade(auth_user["id"], "BRK.B", fill) is None
            assert PreTradeIndex(auth_user["id"], {"BRK.B"}, fill, fill).match("BRK.B", fill) is None


# ── 4. holdings resync ───────────────────────────────────────────────

def _row(ticker="035720.KS", shares=12, avg_cost=48000, currency="KRW", mode="replace"):
    return {"ticker": ticker, "shares": shares, "avg_cost": avg_cost, "currency": currency, "mode": mode}


def _positions(app, user_id):
    from models import Position
    with app.app_context():
        return {p.ticker: p.shares for p in Position.query.filter_by(user_id=user_id).all()}


class TestHoldingsSameStock:
    def test_preview_finds_a_holding_stored_under_the_other_suffix(self, client, auth_user, add_position):
        pid = add_position(auth_user["id"], "035720.KQ", 7, 50000, buy_fx=0.0)
        rows = client.post(f"{HOLDINGS}/preview", json={"rows": [{"code": "035720"}]}).get_json()["rows"]
        assert rows[0]["ticker"] == "035720.KS"
        assert rows[0]["existing"]["id"] == pid

    def test_replace_updates_that_holding_instead_of_opening_a_second(self, app, client, auth_user,
                                                                       add_position):
        from models import TradeHistory
        add_position(auth_user["id"], "035720.KQ", 7, 50000, buy_fx=0.0)
        r = client.post(f"{HOLDINGS}/commit", json={"consent": True, "rows": [_row()]})
        assert r.status_code == 200, r.get_json()
        assert [x["ticker"] for x in r.get_json()["replaced"]] == ["035720.KQ"]
        assert _positions(app, auth_user["id"]) == {"035720.KQ": 12}
        with app.app_context():
            seeds = TradeHistory.query.filter_by(user_id=auth_user["id"]).all()
            assert {t.ticker for t in seeds} == {"035720.KQ"}  # lots stay on one spelling

    def test_close_conflicts_with_a_row_of_the_same_stock(self, app, client, auth_user, add_position):
        pid = add_position(auth_user["id"], "035720.KQ", 7, 50000, buy_fx=0.0)
        r = client.post(f"{HOLDINGS}/commit", json={"consent": True, "rows": [_row()], "close": [pid]})
        assert r.status_code == 400 and r.get_json()["code"] == "IMPORT_CLOSE_CONFLICT"
        assert _positions(app, auth_user["id"]) == {"035720.KQ": 7}


class TestHoldingsCloseOnly:
    @pytest.mark.parametrize("body", [{"rows": []}, {}])
    def test_everything_sold_closes_with_no_rows(self, app, client, auth_user, add_position, body):
        a = add_position(auth_user["id"], "AAPL", 4, 150.0)
        b = add_position(auth_user["id"], "005930.KS", 10, 60000, buy_fx=0.0)
        r = client.post(f"{HOLDINGS}/commit", json={"consent": True, "close": [a, b], **body})
        assert r.status_code == 200, r.get_json()
        assert sorted(x["ticker"] for x in r.get_json()["closed"]) == ["005930.KS", "AAPL"]
        assert _positions(app, auth_user["id"]) == {}

    @pytest.mark.parametrize("body", [{"rows": []}, {"rows": [], "close": []}, {}])
    def test_no_rows_and_no_close_is_still_refused(self, app, client, auth_user, add_position, body):
        add_position(auth_user["id"], "AAPL", 4, 150.0)
        r = client.post(f"{HOLDINGS}/commit", json={"consent": True, **body})
        assert r.status_code == 400 and r.get_json()["field"] == "rows"
        assert _positions(app, auth_user["id"]) == {"AAPL": 4}


# ── 5. review 2026-10-15: order clocks and arrival stamps ────────────

class TestReviewFollowUps:
    @staticmethod
    def _csv(time_header: str) -> bytes:
        return (f"체결일자,{time_header},종목명,종목코드,매매구분,체결수량,체결단가\n"
                "2026-09-01,08:55:10,삼성전자,005930,매수,1,71200\n").encode("utf-8")

    def test_order_time_column_imports_date_only(self):
        # A limit order placed 08:55 that filled 09:20: the file's clock is not
        # the fill time, so the row keeps the day and dedupes on it.
        from services.imports.csv_parser import parse_table
        row = parse_table(self._csv("주문시간"), "orders.csv").rows[0]
        assert row.time_given is False

    def test_fill_time_column_wins_over_an_order_time_column(self):
        # Both clocks in one file, order first and the same header length.
        from services.imports.csv_parser import parse_table
        data = ("체결일자,주문시간,체결시간,종목명,종목코드,매매구분,체결수량,체결단가\n"
                "2026-09-01,08:55:10,09:20:05,삼성전자,005930,매수,1,71200\n").encode("utf-8")
        result = parse_table(data, "both.csv")
        assert result.mapping["time"] == "체결시간"
        row = result.rows[0]
        assert row.time_given is True
        assert (row.traded_at.hour, row.traded_at.minute) == (9, 20)

    def test_fill_time_column_stays_timed(self):
        from services.imports.csv_parser import parse_table
        row = parse_table(self._csv("체결시간"), "fills.csv").rows[0]
        assert row.time_given is True

    def test_arrival_stamp_matches_any_printed_time_up_to_it(self):
        # Shortcut sent at 13:00 KST for a 09:20 fill; the file later prints 09:20.
        from services.imports.dedupe import ARRIVAL, READ, _same_time
        arrival, fill = datetime(2026, 9, 1, 4, 0), datetime(2026, 9, 1, 0, 20)
        assert _same_time(ARRIVAL, arrival, READ, fill)
        assert _same_time(READ, fill, ARRIVAL, arrival)
        # A printed time after the arrival cannot be the fill that arrived.
        assert not _same_time(ARRIVAL, arrival, READ, datetime(2026, 9, 1, 5, 0))
