"""tests/test_holdings_import.py — 잔고(보유종목) 캡처 → 포지션 (server half).

The browser OCRs the holdings screen; the server gets JSON rows only.
Contract: strict validation, nothing written on any 400, currency never
changed, free-plan cap applied per row, user isolation.
"""
from __future__ import annotations

import io

import pytest

BASE = "/api/portfolio/holdings-import"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr("services.fx_service.get_rate", lambda: 1300.0)
    warmed = []
    monkeypatch.setattr("routes.holdings_import._warm_async", lambda app, t: warmed.extend(t))
    return warmed


def _c(ticker="005930.KS", shares=10, avg_cost=71200, currency="KRW", mode="add", **kw):
    return {"ticker": ticker, "shares": shares, "avg_cost": avg_cost, "currency": currency,
            "mode": mode, **kw}


def _commit(client, *rows, consent=True):
    return client.post(f"{BASE}/commit", json={"consent": consent, "rows": list(rows)})


def _preview(client, *rows):
    return client.post(f"{BASE}/preview", json={"rows": list(rows)})


def _positions(app, user_id):
    from models import Position
    with app.app_context():
        return {p.ticker: p for p in Position.query.filter_by(user_id=user_id).all()}


def _login(client, make_user, **kw):
    u = make_user(**kw)
    r = client.post("/api/auth/login", json={"email": u["email"], "password": u["password"]})
    assert r.status_code == 200
    return u


# ── contract ─────────────────────────────────────────────────────────

class TestContract:
    def test_auth_required(self, client):
        assert _commit(client, _c()).status_code == 401
        assert _preview(client, {"name": "삼성전자"}).status_code == 401

    @pytest.mark.parametrize("consent", [False, None, "true", 1])
    def test_consent_must_be_true(self, client, auth_user, app, consent):
        r = _commit(client, _c(), consent=consent)
        assert r.status_code == 400 and r.get_json()["code"] == "IMPORT_CONSENT_REQUIRED"
        assert _positions(app, auth_user["id"]) == {}

    def test_empty_rows(self, client, auth_user):
        assert _commit(client).get_json()["code"] == "IMPORT_INVALID_FIELD"
        assert _preview(client).status_code == 400

    def test_over_200_rows(self, client, auth_user):
        rows = [_c(ticker=f"{i:06d}") for i in range(201)]
        r = client.post(f"{BASE}/commit", json={"consent": True, "rows": rows})
        assert r.status_code == 400 and r.get_json()["code"] == "IMPORT_INVALID_FIELD"
        r = client.post(f"{BASE}/preview", json={"rows": [{"name": "x"}] * 201})
        assert r.status_code == 400

    def test_multipart_rejected(self, client, auth_user, app):
        for ep in ("commit", "preview"):
            r = client.post(f"{BASE}/{ep}",
                            data={"image": (io.BytesIO(b"\x89PNG"), "c.png"), "consent": "true"},
                            content_type="multipart/form-data")
            assert r.status_code == 400
        assert _positions(app, auth_user["id"]) == {}

    def test_response_is_scrubbed(self, client, auth_user, monkeypatch):
        import services.legal_filter as lf
        calls = []
        real = lf.scrub_response
        monkeypatch.setattr(lf, "scrub_response", lambda *a, **k: calls.append(1) or real(*a, **k))
        _commit(client, _c())
        _preview(client, {"name": "삼성전자"})
        assert len(calls) >= 2


# ── commit validation (nothing written) ──────────────────────────────

class TestValidation:
    @pytest.mark.parametrize("patch,field", [
        ({"ticker": ""}, "ticker"), ({"ticker": None}, "ticker"),
        ({"ticker": "372500"}, "ticker"),            # 6 digits, not in KRX master
        ({"ticker": "ZZZZZZ", "currency": "USD"}, "ticker"),  # not in US master
        ({"currency": "JPY"}, "currency"), ({"currency": None}, "currency"),
        ({"shares": 0}, "shares"), ({"shares": -1}, "shares"), ({"shares": float("nan")}, "shares"),
        ({"shares": float("inf")}, "shares"), ({"shares": True}, "shares"), ({"shares": "ten"}, "shares"),
        ({"shares": 2e9}, "shares"), ({"shares": 1.5}, "shares"),   # KRW fractional
        ({"avg_cost": 0}, "avg_cost"), ({"avg_cost": None}, "avg_cost"), ({"avg_cost": "abc"}, "avg_cost"),
        ({"avg_cost": float("nan")}, "avg_cost"), ({"avg_cost": False}, "avg_cost"),
        ({"mode": "merge"}, "mode"), ({"mode": None}, "mode"),
    ])
    def test_bad_row_400_names_row_and_field(self, client, auth_user, app, add_position, patch, field):
        add_position(auth_user["id"], "000660.KS", 5, 150000, buy_fx=0.0)
        r = _commit(client, _c(ticker="000660.KS", mode="replace", shares=1, avg_cost=1), _c(**patch))
        assert r.status_code == 400, patch
        body = r.get_json()
        assert body["code"] == "IMPORT_INVALID_FIELD"
        assert body["row"] == 1 and body["field"] == field
        assert "rows[1]" in body["error"] and "rows[1]" in body["error_kr"]
        pos = _positions(app, auth_user["id"])
        assert set(pos) == {"000660.KS"} and pos["000660.KS"].shares == 5  # row 0 not applied

    def test_currency_mismatch(self, client, auth_user, app):
        r = _commit(client, _c(), _c(ticker="AAPL", currency="KRW", shares=1, avg_cost=312000))
        body = r.get_json()
        assert r.status_code == 400 and body["code"] == "IMPORT_CURRENCY_MISMATCH"
        assert body["row"] == 1
        assert _positions(app, auth_user["id"]) == {}

    def test_duplicate_ticker_including_skip(self, client, auth_user, app):
        r = _commit(client, _c(), _c(ticker="005930", mode="skip"))
        body = r.get_json()
        assert r.status_code == 400 and body["code"] == "IMPORT_DUPLICATE_TICKER" and body["row"] == 1
        assert _positions(app, auth_user["id"]) == {}

    def test_numeric_string_accepted(self, client, auth_user, app):
        r = _commit(client, _c(shares="3", avg_cost="70000.5"))
        assert r.status_code == 200, r.get_json()
        assert _positions(app, auth_user["id"])["005930.KS"].shares == 3


# ── preview ──────────────────────────────────────────────────────────

class TestPreview:
    def test_resolution(self, client, auth_user):
        r = _preview(client,
                     {"name": None, "code": "005930", "currency": "KRW"},
                     {"name": "SK하이닉스", "code": None, "currency": "KRW"},
                     {"name": "SK하이닉", "code": None, "currency": None},
                     {"name": "어떤이상한종목이름", "code": None, "currency": "KRW"},
                     {"name": "삼성전자", "code": "372500", "currency": "KRW"},
                     {"name": "삼성전자", "code": "000660", "currency": "KRW"},
                     {"name": "Apple", "code": "AAPL", "currency": "USD"},
                     {"name": "TIGER", "code": None, "currency": "KRW"})
        assert r.status_code == 200, r.get_json()
        rows = r.get_json()["rows"]
        assert [x["index"] for x in rows] == list(range(8))
        assert (rows[0]["ticker"], rows[0]["status"], rows[0]["currency"]) == ("005930.KS", "resolved", "KRW")
        assert (rows[1]["ticker"], rows[1]["status"]) == ("000660.KS", "resolved")
        assert (rows[2]["ticker"], rows[2]["status"]) == ("000660.KS", "needs_confirm")
        assert rows[2]["read_name"] == "SK하이닉" and rows[2]["name"] == "SK하이닉스"
        assert rows[3]["ticker"] is None and rows[3]["status"] == "needs_ticker" and rows[3]["currency"] is None
        assert (rows[4]["ticker"], rows[4]["status"]) == ("005930.KS", "resolved")  # price-shaped code ignored
        assert rows[5]["status"] == "needs_confirm"  # code/name conflict
        assert (rows[6]["ticker"], rows[6]["currency"], rows[6]["status"]) == ("AAPL", "USD", "resolved")
        assert rows[7]["ticker"] is None and rows[7]["status"] == "needs_ticker"
        assert all(x["existing"] is None and x["currency_mismatch"] is False for x in rows)

    def test_toss_names(self, client, auth_user):
        """Toss 내 투자: US stocks by Korean name, and the logo eating "SK"."""
        rows = _preview(client,
                        {"name": "뉴스케일파워", "code": None, "currency": None},
                        {"name": "조비 에비에이션", "code": None, "currency": None},
                        {"name": "조비에비에이선", "code": None, "currency": None},
                        {"name": "이하이닉스", "code": None, "currency": "KRW"}).get_json()["rows"]
        assert (rows[0]["ticker"], rows[0]["status"], rows[0]["currency"]) == ("SMR", "resolved", "USD")
        assert (rows[1]["ticker"], rows[1]["status"]) == ("JOBY", "resolved")
        assert (rows[2]["ticker"], rows[2]["status"]) == ("JOBY", "needs_confirm")
        assert (rows[3]["ticker"], rows[3]["status"], rows[3]["name"]) == ("000660.KS", "needs_confirm", "SK하이닉스")

    def test_us_kr_names_are_all_in_the_master(self):
        from services.imports.holdings_import import _us_kr_index, _us_known
        index = _us_kr_index()
        assert len(index) > 100
        assert [t for t in index.values() if not _us_known(t)] == []

    def test_currency_mismatch_flag(self, client, auth_user):
        rows = _preview(client, {"name": "애플", "code": "AAPL", "currency": "KRW"}).get_json()["rows"]
        assert rows[0]["ticker"] == "AAPL" and rows[0]["currency_mismatch"] is True

    def test_existing_position_included_and_isolated(self, client, auth_user, add_position, make_user):
        other = make_user(email="other@test.com")
        add_position(other["id"], "000660.KS", 99, 100000, buy_fx=0.0)
        pid = add_position(auth_user["id"], "005930.KS", 7, 60000, buy_fx=0.0)
        rows = _preview(client, {"code": "005930"}, {"name": "SK하이닉스"}).get_json()["rows"]
        assert rows[0]["existing"] == {"id": pid, "shares": 7, "avg_cost": 60000, "currency": "KRW"}
        assert rows[1]["existing"] is None  # other user's position never shown

    def test_preview_writes_nothing(self, client, auth_user, app):
        _preview(client, {"code": "005930", "currency": "KRW"})
        assert _positions(app, auth_user["id"]) == {}

    def test_bad_preview_field(self, client, auth_user):
        r = _preview(client, {"name": 5})
        assert r.status_code == 400 and r.get_json()["field"] == "name"
        r = _preview(client, {"name": "x", "currency": "JPY"})
        assert r.status_code == 400 and r.get_json()["field"] == "currency"


# ── commit semantics ─────────────────────────────────────────────────

class TestCommit:
    def test_replace_keeps_other_fields(self, client, auth_user, app, add_position):
        from datetime import datetime
        from extensions import db
        from models import Position, TradeHistory
        opened = datetime(2024, 3, 1)
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0, buy_fx=1100.0, added_at=opened)
        with app.app_context():
            p = db.session.get(Position, pid)
            p.thesis = "서비스 매출 성장"
            db.session.commit()
        r = _commit(client, _c(ticker="AAPL", shares=12.5, avg_cost=180.25, currency="USD", mode="replace"))
        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        assert body["replaced"] == [{"ticker": "AAPL", "shares": 12.5, "avg_cost": 180.25, "currency": "USD",
                                     "prev_shares": 10, "prev_avg_cost": 150.0}]
        assert body["created"] == body["added"] == body["skipped"] == []
        with app.app_context():
            p = db.session.get(Position, pid)
            assert (p.shares, p.avg_cost, p.buy_fx_rate) == (12.5, 180.25, 1300.0)
            assert p.thesis == "서비스 매출 성장" and p.added_at == opened
            # 2026-09-29: replace seeds only the share increase (10 → 12.5) as a
            # holding-seed row — never a fill (tests/test_holding_seed.py).
            rows = TradeHistory.query.filter_by(user_id=auth_user["id"]).all()
            assert [(t.shares, t.price_per_share, t.source) for t in rows] == [
                (2.5, 180.25, "holding_seed")]

    def test_add_merges_like_create_position(self, client, auth_user, app, add_position):
        add_position(auth_user["id"], "AAPL", 10, 100.0, buy_fx=1000.0)
        body = _commit(client, _c(ticker="AAPL", shares=10, avg_cost=200.0, currency="USD")).get_json()
        a = body["added"][0]
        assert (a["shares"], a["avg_cost"], a["prev_shares"], a["prev_avg_cost"]) == (20, 150.0, 10, 100.0)
        p = _positions(app, auth_user["id"])["AAPL"]
        # cost-weighted fx: (1000*1000 + 1300*2000) / 3000
        assert p.buy_fx_rate == pytest.approx(1200.0)

    def test_add_matches_create_position_endpoint(self, client, auth_user, app, add_position, make_user):
        """Same merge result as POST /api/portfolio/positions on the same start state."""
        from unittest.mock import patch
        add_position(auth_user["id"], "AAPL", 3, 120.0, buy_fx=1250.0)
        _commit(client, _c(ticker="AAPL", shares=2, avg_cost=190.0, currency="USD"))
        mine = _positions(app, auth_user["id"])["AAPL"]
        client.post("/api/auth/logout")
        u2 = _login(client, make_user, email="twin@test.com")
        add_position(u2["id"], "AAPL", 3, 120.0, buy_fx=1250.0)
        with patch("routes.portfolio._cache_ticker_async"), \
                patch("routes.portfolio._avg_cost_implausible", return_value=None):
            assert client.post("/api/portfolio/positions",
                               json={"symbol": "AAPL", "quantity": 2, "price": 190.0}).status_code == 200
        twin = _positions(app, u2["id"])["AAPL"]
        assert (mine.shares, mine.avg_cost) == (twin.shares, twin.avg_cost)
        assert mine.buy_fx_rate == pytest.approx(twin.buy_fx_rate)

    def test_new_insert_either_mode_and_skip(self, client, auth_user, app, _no_network):
        body = _commit(client, _c(mode="replace"),
                       _c(ticker="AAPL", shares=0.5, avg_cost=231.5, currency="USD", mode="add"),
                       _c(ticker="000660.KS", mode="skip")).get_json()
        assert body["created"] == [
            {"ticker": "005930.KS", "shares": 10, "avg_cost": 71200, "currency": "KRW"},
            {"ticker": "AAPL", "shares": 0.5, "avg_cost": 231.5, "currency": "USD"}]
        assert body["skipped"] == [{"ticker": "000660.KS", "reason": "USER_SKIP"}]
        pos = _positions(app, auth_user["id"])
        assert set(pos) == {"005930.KS", "AAPL"}
        assert pos["005930.KS"].buy_fx_rate == 0.0 and pos["AAPL"].buy_fx_rate == 1300.0
        assert pos["AAPL"].thesis_status == "pending" and pos["AAPL"].thesis is None
        assert _no_network == ["005930.KS", "AAPL"]  # cache warm mirrors create_position

    def test_free_tier_cap_partial_in_request_order(self, client, auth_user, app, add_position):
        add_position(auth_user["id"], "MSFT", 1, 400.0)
        add_position(auth_user["id"], "AAPL", 1, 150.0)
        body = _commit(client,
                       _c(ticker="AAPL", shares=2, avg_cost=160.0, currency="USD", mode="replace"),
                       _c(ticker="000660.KS", shares=1, avg_cost=150000),
                       _c(ticker="005930.KS"),
                       _c(ticker="NVDA", shares=1, avg_cost=120.0, currency="USD")).get_json()
        assert [x["ticker"] for x in body["replaced"]] == ["AAPL"]  # existing: never capped
        assert [x["ticker"] for x in body["created"]] == ["000660.KS"]
        assert body["skipped"] == [{"ticker": "005930.KS", "reason": "TIER_LIMIT"},
                                   {"ticker": "NVDA", "reason": "TIER_LIMIT"}]
        assert set(_positions(app, auth_user["id"])) == {"MSFT", "AAPL", "000660.KS"}

    def test_paid_tier_uncapped(self, client, app, make_user, add_position):
        u = _login(client, make_user, email="paid@test.com", tier="premium")
        add_position(u["id"], "MSFT", 1, 400.0)
        add_position(u["id"], "AAPL", 1, 150.0)
        add_position(u["id"], "GOOG", 1, 150.0)
        body = _commit(client, _c(), _c(ticker="000660.KS", shares=1, avg_cost=150000)).get_json()
        assert len(body["created"]) == 2 and body["skipped"] == []

    def test_user_isolation(self, client, auth_user, app, make_user, add_position):
        other = make_user(email="other@test.com")
        add_position(other["id"], "005930.KS", 50, 50000, buy_fx=0.0)
        body = _commit(client, _c(mode="replace")).get_json()
        assert [x["ticker"] for x in body["created"]] == ["005930.KS"]
        theirs = _positions(app, other["id"])["005930.KS"]
        assert (theirs.shares, theirs.avg_cost) == (50, 50000)

    def test_race_rolls_back_whole_batch(self, client, auth_user, app, monkeypatch):
        from sqlalchemy.exc import IntegrityError
        from extensions import db
        real = db.session.commit

        def boom():
            raise IntegrityError("x", {}, Exception("uq"))
        monkeypatch.setattr(db.session, "commit", boom)
        r = _commit(client, _c(), _c(ticker="000660.KS", shares=1, avg_cost=150000))
        monkeypatch.setattr(db.session, "commit", real)
        assert r.status_code == 409 and r.get_json()["code"] == "POSITION_RACE"
        assert _positions(app, auth_user["id"]) == {}


class TestPostgres:
    def test_user_lock_query_has_no_join_on_postgres(self, app):
        from sqlalchemy.dialects import postgresql
        from services.position_writes import lock_user_row_query
        with app.app_context():
            sql = str(lock_user_row_query(1).statement.compile(dialect=postgresql.dialect()))
        assert "FOR UPDATE" in sql and "JOIN" not in sql.upper()
