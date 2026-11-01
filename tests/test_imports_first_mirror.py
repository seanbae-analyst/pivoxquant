"""tests/test_imports_first_mirror.py — starting from a fills file (2026-11-01).

Bulk approval with no reason, the double count against a registered holding,
the onboarding gate that accepts fills, and the one-time funnel events.
"""
from __future__ import annotations

import io

import pytest

BASE = "/api/portfolio/imports"
HEADER = "거래일자,종목명,종목코드,거래구분,수량,단가,거래금액,수수료"


@pytest.fixture(autouse=True)
def _fixed_fx(monkeypatch):
    monkeypatch.setattr("services.fx_service.get_rate", lambda: 1300.0)


def _upload(client, *rows: str):
    csv = "\n".join((HEADER, *rows)) + "\n"
    r = client.post(
        f"{BASE}/",
        data={"file": (io.BytesIO(csv.encode("utf-8")), "fills.csv"), "consent": "true"},
        content_type="multipart/form-data",
    )
    assert r.status_code == 201, r.get_json()
    return r.get_json()["pending"]


def _approve_all(client):
    r = client.post(f"{BASE}/pending/approve-all")
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _register(client, shares=10):
    r = client.post("/api/portfolio/positions", json={
        "ticker": "005930", "shares": shares, "avg_cost": 70000, "name": "삼성전자",
    })
    assert r.status_code == 200, r.get_json()


def _positions(app):
    from models import Position
    with app.app_context():
        return {p.ticker: p.shares for p in Position.query.all()}


def _funnel(app, event):
    from models import FunnelEvent
    with app.app_context():
        return FunnelEvent.query.filter_by(event=event).count()


class TestApproveAll:
    def test_records_fills_with_no_reason(self, client, auth_user, app):
        from models import TradeHistory
        _upload(
            client,
            "2026-08-03,삼성전자,005930,매수,10,70000,700000,0",
            "2026-08-20,삼성전자,005930,매도,10,75000,750000,0",
            "2026-09-01,SK하이닉스,000660,매수,5,100000,500000,0",
        )
        body = _approve_all(client)
        assert body["approved"] == 3
        assert body["remaining"] == 0
        assert _positions(app) == {"000660.KS": 5.0}
        with app.app_context():
            assert TradeHistory.query.count() == 3

    def test_file_order_does_not_matter(self, client, auth_user, app):
        # Newest first, as broker exports often are: the sell cannot go first.
        _upload(
            client,
            "2026-08-20,삼성전자,005930,매도,4,75000,300000,0",
            "2026-08-03,삼성전자,005930,매수,10,70000,700000,0",
        )
        body = _approve_all(client)
        assert body["approved"] == 2
        assert _positions(app) == {"005930.KS": 6.0}

    def test_buy_goes_first_on_a_date_only_day(self, client, auth_user, app):
        _upload(
            client,
            "2026-08-03,삼성전자,005930,매도,10,71000,710000,0",
            "2026-08-03,삼성전자,005930,매수,10,70000,700000,0",
        )
        assert _approve_all(client)["approved"] == 2
        assert _positions(app) == {}

    def test_sell_with_no_buy_stays_pending_and_the_rest_land(self, client, auth_user):
        _upload(
            client,
            "2026-08-03,삼성전자,005930,매도,10,70000,700000,0",
            "2026-08-05,SK하이닉스,000660,매수,5,100000,500000,0",
        )
        body = _approve_all(client)
        assert body["approved"] == 1
        assert body["failed"] == 1
        assert body["remaining"] == 1
        assert "삼성전자" in body["first_error"]

    def test_only_touches_own_rows(self, client, auth_user, app):
        from extensions import db
        from models import PendingTrade, User
        _upload(client, "2026-08-03,삼성전자,005930,매수,10,70000,700000,0")
        with app.app_context():
            other = User(email="other-first-mirror@example.com", name="other")
            db.session.add(other)
            db.session.flush()
            PendingTrade.query.update({"user_id": other.id})
            db.session.commit()
        assert _approve_all(client)["approved"] == 0
        assert _positions(app) == {}

    def test_unauthenticated_401(self, client):
        assert client.post(f"{BASE}/pending/approve-all").status_code == 401


class TestRegisteredHoldingIsNotCountedTwice:
    ROW = "2026-08-03,삼성전자,005930,매수,10,70000,700000,0"

    def test_single_approve_refuses_an_older_fill(self, client, auth_user, app):
        _register(client)
        pending = _upload(client, self.ROW)
        r = client.post(f"{BASE}/pending/{pending[0]['id']}/approve", json={"thesis": "오래전에 산 것"})
        assert r.status_code == 400
        assert r.get_json()["code"] == "IMPORT_PREDATES_HOLDING"
        assert _positions(app) == {"005930.KS": 10.0}

    def test_bulk_leaves_it_pending(self, client, auth_user, app):
        _register(client)
        _upload(client, self.ROW)
        body = _approve_all(client)
        assert body["approved"] == 0
        assert body["predates_holding"] == 1
        assert body["remaining"] == 1
        assert _positions(app) == {"005930.KS": 10.0}

    def test_a_dateless_fill_today_is_not_older_than_a_holding_registered_today(
        self, client, auth_user, app,
    ):
        _register(client)
        r = client.post(f"{BASE}/", json={
            "text": "삼성전자 10주 매수 체결 71,200원", "source": "screenshot_text", "consent": True,
        })
        pid = r.get_json()["pending"][0]["id"]
        r = client.post(f"{BASE}/pending/{pid}/approve", json={"thesis": "오늘 더 샀다"})
        assert r.status_code == 200, r.get_json()
        assert _positions(app) == {"005930.KS": 20.0}

    def test_a_position_an_import_opened_still_takes_older_fills(self, client, auth_user, app):
        pending = _upload(
            client,
            "2026-08-20,삼성전자,005930,매수,10,75000,750000,0",
            "2026-08-03,삼성전자,005930,매수,5,70000,350000,0",
        )
        newest = next(p for p in pending if p["shares"] == 10)
        oldest = next(p for p in pending if p["shares"] == 5)
        for row in (newest, oldest):
            r = client.post(f"{BASE}/pending/{row['id']}/approve", json={"thesis": "실적 보고 샀다"})
            assert r.status_code == 200, r.get_json()
        assert _positions(app) == {"005930.KS": 15.0}


class TestOnboardingGate:
    def test_fills_alone_pass_when_nothing_is_held(self, client, auth_user, app):
        _upload(
            client,
            "2026-08-03,삼성전자,005930,매수,10,70000,700000,0",
            "2026-08-20,삼성전자,005930,매도,10,75000,750000,0",
        )
        _approve_all(client)
        assert _positions(app) == {}
        assert client.post("/api/profile/onboarding", json={"answers": {}}).status_code == 200

    def test_unapproved_fills_do_not(self, client, auth_user):
        _upload(client, "2026-08-03,삼성전자,005930,매수,10,70000,700000,0")
        r = client.post("/api/profile/onboarding", json={"answers": {}})
        assert r.get_json()["code"] == "ONBOARDING_HOLDINGS_REQUIRED"


class TestFunnel:
    def test_events_land_once(self, client, auth_user, app):
        _upload(client, "2026-08-03,삼성전자,005930,매수,10,70000,700000,0")
        _upload(client, "2026-08-05,삼성전자,005930,매수,1,70000,70000,0")
        _approve_all(client)
        client.post("/api/profile/onboarding", json={"answers": {}})
        client.post(f"{BASE}/pending/approve-all")
        assert _funnel(app, "import_done") == 1
        assert _funnel(app, "fill_approved") == 1
        assert _funnel(app, "onboarding_done") == 1

    def test_a_funnel_failure_does_not_fail_the_action(self, client, auth_user, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("funnel down")
        monkeypatch.setattr("services.funnel.FunnelEvent", type("X", (), {"query": property(boom)}))
        _upload(client, "2026-08-03,삼성전자,005930,매수,10,70000,700000,0")
        assert _approve_all(client)["approved"] == 1


def test_mirror_home_reports_every_fill(client, auth_user):
    _upload(client, "2026-03-03,삼성전자,005930,매수,10,70000,700000,0")
    _approve_all(client)
    body = client.get("/api/mirror-home").get_json()
    assert body["stage"] == "new"
    assert body["total_fills"] == 1


def test_mirror_home_does_not_count_a_registered_holding_as_a_fill(client, auth_user):
    _register(client)
    assert client.get("/api/mirror-home").get_json()["total_fills"] == 0
