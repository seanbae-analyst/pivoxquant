"""POST /api/portfolio/trades records an executed fill — ledger parity.

2026-09-29: TradeModalV2 ("이미 체결됨 · 기록만" and the 7문항 review mode
post the same body) writes through this endpoint. It used to gate a 매수 on
seed capital (every new user has 0 → 400 with no code), debit/credit the seed
on each fill, and drop the note. The import ledger
(services/imports/ledger.py) never touches seed capital and keeps the
approved thesis. These tests pin the endpoint to that behaviour.
"""
from __future__ import annotations

import json


def _login_zero_capital(client, make_user):
    u = make_user(email="zero@test.com", capital_usd=0.0, capital_krw=0.0)
    r = client.post("/api/auth/login", json={"email": u["email"], "password": u["password"]})
    assert r.status_code == 200
    return u


def _user_capital(app, uid):
    from extensions import db
    from models import User
    with app.app_context():
        u = db.session.get(User, uid)
        return u.available_capital, u.available_capital_krw


def _position(app, pid):
    from extensions import db
    from models import Position
    with app.app_context():
        return db.session.get(Position, pid)


def _notes(app, uid):
    from models import ObservationNote
    with app.app_context():
        return [
            (n.body, json.loads(n.tickers_json or "[]"), n.source)
            for n in ObservationNote.query.filter_by(user_id=uid).all()
        ]


def test_zero_capital_user_records_buy(client, make_user, add_position, app):
    u = _login_zero_capital(client, make_user)
    pid = add_position(u["id"], "AAPL", 10, 150.0)
    r = client.post("/api/portfolio/trades", json={
        "position_id": pid, "action": "buy", "quantity": 5, "price": 180.0,
        "date": "2024-03-01",
    })
    assert r.status_code == 200, r.get_json()
    p = _position(app, pid)
    assert p.shares == 15
    assert abs(p.avg_cost - (10 * 150 + 5 * 180) / 15) < 1e-9
    assert _user_capital(app, u["id"]) == (0.0, 0.0)


def test_zero_capital_user_records_kr_buy(client, make_user, add_position, app):
    u = _login_zero_capital(client, make_user)
    pid = add_position(u["id"], "005930.KS", 10, 70000.0, buy_fx=0.0)
    r = client.post("/api/portfolio/trades", json={
        "position_id": pid, "action": "buy", "quantity": 3, "price": 72000.0,
    })
    assert r.status_code == 200, r.get_json()
    assert _user_capital(app, u["id"]) == (0.0, 0.0)
    assert _position(app, pid).buy_fx_rate == 0.0


def test_buy_and_sell_leave_seed_capital_alone(client, auth_user, add_position, app):
    before = _user_capital(app, auth_user["id"])
    pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
    assert client.post("/api/portfolio/trades", json={
        "position_id": pid, "action": "buy", "quantity": 2, "price": 160.0,
    }).status_code == 200
    assert client.post("/api/portfolio/trades", json={
        "position_id": pid, "action": "sell", "quantity": 4, "price": 170.0,
    }).status_code == 200
    assert _user_capital(app, auth_user["id"]) == before


def test_note_fills_empty_thesis_on_buy(client, auth_user, add_position, app):
    pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
    r = client.post("/api/portfolio/trades", json={
        "position_id": pid, "action": "buy", "quantity": 1, "price": 160.0,
        "note": "  실적 발표 뒤 가이던스 확인하고 추가  ",
    })
    assert r.status_code == 200, r.get_json()
    p = _position(app, pid)
    assert p.thesis == "실적 발표 뒤 가이던스 확인하고 추가"
    assert p.thesis_created_at is not None
    assert _notes(app, auth_user["id"]) == []


def test_note_goes_to_observation_when_thesis_exists(client, auth_user, add_position, app):
    from extensions import db
    from models import Position
    pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
    with app.app_context():
        db.session.get(Position, pid).thesis = "처음 산 이유"
        db.session.commit()
    r = client.post("/api/portfolio/trades", json={
        "position_id": pid, "action": "buy", "quantity": 1, "price": 160.0,
        "note": "두 번째 매수 메모",
    })
    assert r.status_code == 200, r.get_json()
    assert _position(app, pid).thesis == "처음 산 이유"
    assert _notes(app, auth_user["id"]) == [("두 번째 매수 메모", ["AAPL"], "portfolio")]


def test_note_on_sell_persists_even_when_position_closes(client, auth_user, add_position, app):
    pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
    r = client.post("/api/portfolio/trades", json={
        "position_id": pid, "action": "sell", "quantity": 10, "price": 170.0,
        "note": "목표가 도달해 전량 정리",
    })
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["closed"] is True
    assert _notes(app, auth_user["id"]) == [("목표가 도달해 전량 정리", ["AAPL"], "portfolio")]


def test_empty_note_writes_nothing(client, auth_user, add_position, app):
    pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
    r = client.post("/api/portfolio/trades", json={
        "position_id": pid, "action": "sell", "quantity": 1, "price": 170.0, "note": "   ",
    })
    assert r.status_code == 200
    assert _notes(app, auth_user["id"]) == []
    assert _position(app, pid).thesis is None


def test_oversell_has_code(client, auth_user, add_position):
    pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
    r = client.post("/api/portfolio/trades", json={
        "position_id": pid, "action": "sell", "quantity": 11, "price": 170.0,
    })
    assert r.status_code == 400
    assert r.get_json()["code"] == "TRADE_SELL_EXCEEDS_HOLDING"
