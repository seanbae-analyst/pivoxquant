"""tests/test_pre_trade_link.py — 매수 ↔ 멈춤 명시 연결 (2026-09-29).

services/pre_trade/link.py · TradeHistory.reflection_id

- 후보 목록: GET /api/pre-trade/list?ticker=&linkable=1 — 본인 · 같은 종목 ·
  매수 쪽 · 최근 30일 · 아직 안 이어진 멈춤만.
- POST /api/portfolio/trades (매수) 는 선택적 ``reflection_id`` 를 받아 매수
  행에 단다. 남의 것 · 다른 종목 · 매도 쪽 · 이미 쓰인 것 · 매도에 붙인 것은
  400 + api_error code.
- 가져오기 승인은 본문 ``reflection_id`` 가 있으면 그것을, 없으면 가져올 때
  추정해 둔 ``pre_trade_reflection_id`` 를 쓴다.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from extensions import db
from models import PreTradeReflection, SignalCache, TradeHistory


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _refl(user_id, ticker="AAPL", *, side="BUY", days_ago=2, proceeded=True, cancelled=False,
          rationale="실적 발표 전에 비중을 늘리려는 이유를 적어 둔다"):
    at = _now() - timedelta(days=days_ago)
    r = PreTradeReflection(
        user_id=user_id, intended_ticker=ticker, intended_side=side,
        rationale=rationale, created_at=at,
        cooldown_started_at=at, cooldown_ends_at=at,
        proceeded_at=at if proceeded and not cancelled else None,
        cancelled_at=at if cancelled else None,
    )
    db.session.add(r)
    db.session.commit()
    return r.id


@pytest.fixture
def seeded(app):
    with app.app_context():
        db.session.add(SignalCache(ticker="AAPL", data_json=json.dumps(
            {"name": "Apple", "is_korean": False, "currency": "USD", "price": 170.0})))
        db.session.commit()


def _buy(client, pid, **extra):
    body = {"position_id": pid, "action": "buy", "quantity": 1, "price": 100.0}
    body.update(extra)
    return client.post("/api/portfolio/trades", json=body)


def _latest_trade(app, user_id):
    with app.app_context():
        return (TradeHistory.query.filter_by(user_id=user_id)
                .order_by(TradeHistory.id.desc()).first())


# ── 후보 목록 ─────────────────────────────────────────────────────────

class TestLinkableList:
    def test_filters_to_recent_unlinked_buy_side_same_ticker(self, client, app, auth_user, make_user):
        uid = auth_user["id"]
        other = make_user(email="link-other@test.com")
        with app.app_context():
            keep = _refl(uid, "AAPL", days_ago=3)
            cancelled = _refl(uid, "AAPL", days_ago=5, cancelled=True)
            _refl(uid, "AAPL", days_ago=40)                 # 창 밖
            _refl(uid, "AAPL", side="SELL", days_ago=1)     # 매도 쪽  # // legal-ok — stored enum value
            _refl(uid, "MSFT", days_ago=1)                  # 다른 종목
            _refl(other["id"], "AAPL", days_ago=1)          # 남의 것
            used = _refl(uid, "AAPL", days_ago=2)
            db.session.add(TradeHistory(user_id=uid, ticker="AAPL", action="BUY",
                                        shares=1, price_per_share=1, total_value=1,
                                        reflection_id=used))
            db.session.commit()
        r = client.get("/api/pre-trade/list?ticker=aapl&linkable=1")
        assert r.status_code == 200
        ids = [x["id"] for x in r.get_json()["reflections"]]
        assert ids == [keep, cancelled]
        assert r.get_json()["reflections"][0]["rationale"].startswith("실적")

    def test_kr_suffix_matches_bare_code(self, client, app, auth_user):
        with app.app_context():
            rid = _refl(auth_user["id"], "005930", days_ago=1)
        r = client.get("/api/pre-trade/list?ticker=005930.KS&linkable=1")
        assert [x["id"] for x in r.get_json()["reflections"]] == [rid]

    def test_ticker_required(self, client, auth_user):
        r = client.get("/api/pre-trade/list?linkable=1")
        assert r.status_code == 400
        assert r.get_json()["code"] == "BAD_INPUT"


# ── POST /api/portfolio/trades ──────────────────────────────────────

class TestTradeLink:
    def test_buy_links_reflection(self, client, app, auth_user, add_position, seeded):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        with app.app_context():
            rid = _refl(auth_user["id"])
        r = _buy(client, pid, reflection_id=rid)
        assert r.status_code == 200, r.get_json()
        assert _latest_trade(app, auth_user["id"]).reflection_id == rid
        # 한 번 쓰인 멈춤은 후보에서 빠지고, 다시 이으면 거부된다.
        assert client.get("/api/pre-trade/list?ticker=AAPL&linkable=1").get_json()["reflections"] == []
        r2 = _buy(client, pid, reflection_id=rid)
        assert r2.status_code == 400
        assert r2.get_json()["code"] == "REFLECTION_LINK_ALREADY_USED"

    def test_buy_without_link_is_null(self, client, app, auth_user, add_position, seeded):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        assert _buy(client, pid).status_code == 200
        assert _latest_trade(app, auth_user["id"]).reflection_id is None

    @pytest.mark.parametrize("kind,code", [
        ("foreign", "REFLECTION_LINK_NOT_FOUND"),
        ("ticker", "REFLECTION_LINK_TICKER_MISMATCH"),
        ("side", "REFLECTION_LINK_SIDE_MISMATCH"),
        ("garbage", "REFLECTION_LINK_INVALID"),
    ])
    def test_invalid_link_rejected_and_nothing_written(
        self, client, app, auth_user, add_position, make_user, seeded, kind, code,
    ):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        with app.app_context():
            if kind == "foreign":
                rid = _refl(make_user(email="link-x@test.com")["id"])
            elif kind == "ticker":
                rid = _refl(auth_user["id"], "MSFT")
            elif kind == "side":
                rid = _refl(auth_user["id"], side="SELL")  # // legal-ok — stored enum value
            else:
                rid = "abc"
            before = TradeHistory.query.filter_by(user_id=auth_user["id"]).count()
        r = _buy(client, pid, reflection_id=rid)
        assert r.status_code == 400
        assert r.get_json()["code"] == code
        with app.app_context():
            assert TradeHistory.query.filter_by(user_id=auth_user["id"]).count() == before

    def test_sell_with_link_rejected(self, client, app, auth_user, add_position, seeded):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        with app.app_context():
            rid = _refl(auth_user["id"])
        r = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "sell", "quantity": 1, "price": 100.0,
            "reflection_id": rid,
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "REFLECTION_LINK_BUY_ONLY"


# ── POST /api/portfolio/positions (신규 진입 검토) ─────────────────────

POSITIONS = "/api/portfolio/positions"


class TestPositionReviewLink:
    """검토 모드 등록은 방금 찍은 멈춤을 보낸다 → 시드가 아니라 연결된 매수 행."""

    @pytest.fixture(autouse=True)
    def _no_network(self, monkeypatch):
        monkeypatch.setattr("services.fx_service.get_rate", lambda: 1300.0)
        monkeypatch.setattr("routes.portfolio.cache_service.cache_ticker", lambda *a, **k: None)

    def test_review_entry_writes_linked_buy_and_friction_outcome_counts_it(
        self, client, app, auth_user, seeded,
    ):
        from services.pre_trade.friction_outcome import compute_friction_outcome

        uid = auth_user["id"]
        with app.app_context():
            rid = _refl(uid, "AAPL", days_ago=0)
        r = client.post(POSITIONS, json={
            "symbol": "AAPL", "quantity": 2, "price": 100, "note": "실적 전 진입 이유",
            "reflection_id": rid,
        })
        assert r.status_code == 200, r.get_json()
        t = _latest_trade(app, uid)
        assert (t.action, t.source, t.reflection_id) == ("BUY", None, rid)  # // legal-ok — stored enum value
        assert abs((t.traded_at - _now()).total_seconds()) < 120
        # 매도해서 실현 쌍을 만든다 — 멈춤 경유 분포로 들어가야 한다.
        pid = int(r.get_json()["id"])
        s = client.post("/api/portfolio/trades", json={
            "position_id": pid, "action": "sell", "quantity": 2, "price": 120.0,
        })
        assert s.status_code == 200, s.get_json()
        with app.app_context():
            out = compute_friction_outcome(
                PreTradeReflection.query.filter_by(user_id=uid).all(),
                TradeHistory.query.filter_by(user_id=uid).all(),
            )
        assert out["stopped"]["proceeded"] == 1
        assert out["caveats"]["explicit_links"] == 1
        assert out["realised"]["with_friction"]["n"] == 1
        assert out["realised"]["without_friction"]["n"] == 0

    def test_holding_mode_still_seeds(self, client, app, auth_user, seeded):
        r = client.post(POSITIONS, json={"symbol": "AAPL", "quantity": 2, "price": 100})
        assert r.status_code == 200
        t = _latest_trade(app, auth_user["id"])
        assert (t.source, t.reflection_id) == ("holding_seed", None)

    def test_invalid_link_rejected_and_nothing_written(self, client, app, auth_user, seeded):
        from models import Position

        with app.app_context():
            rid = _refl(auth_user["id"], "MSFT")
        r = client.post(POSITIONS, json={
            "symbol": "AAPL", "quantity": 2, "price": 100, "reflection_id": rid,
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "REFLECTION_LINK_TICKER_MISMATCH"
        with app.app_context():
            assert TradeHistory.query.filter_by(user_id=auth_user["id"]).count() == 0
            assert Position.query.filter_by(user_id=auth_user["id"]).count() == 0


# ── 가져오기 승인 ─────────────────────────────────────────────────────

IMPORTS = "/api/portfolio/imports"


class TestImportApproveLink:
    @pytest.fixture(autouse=True)
    def _fx(self, monkeypatch):
        monkeypatch.setattr("services.fx_service.get_rate", lambda: 1300.0)

    def _pending(self, client, text):
        return client.post(f"{IMPORTS}/", json={
            "text": text, "source": "screenshot_text", "consent": True,
        }).get_json()["pending"][0]

    def test_inferred_match_is_linked_on_approve(self, client, app, auth_user):
        traded = datetime(2026, 9, 1, 10, 32)
        with app.app_context():
            r = PreTradeReflection(
                user_id=auth_user["id"], intended_ticker="005930.KS", intended_side="BUY",
                rationale="이틀 전 기록", cooldown_started_at=traded - timedelta(days=2),
                cooldown_ends_at=traded - timedelta(days=2), created_at=traded - timedelta(days=2),
            )
            db.session.add(r)
            db.session.commit()
            rid = r.id
        p = self._pending(client, "삼성전자 10주 매수 체결 71,200원 2026-09-01 10:32")
        assert p["pre_trade_reflection_id"] == rid
        a = client.post(f"{IMPORTS}/pending/{p['id']}/approve", json={"thesis": "반도체 업황 회복"})
        assert a.status_code == 200, a.get_json()
        with app.app_context():
            assert db.session.get(TradeHistory, a.get_json()["trade_id"]).reflection_id == rid

    def test_explicit_null_skips_inferred_link(self, client, app, auth_user):
        traded = datetime(2026, 9, 1, 10, 32)
        with app.app_context():
            db.session.add(PreTradeReflection(
                user_id=auth_user["id"], intended_ticker="005930.KS", intended_side="BUY",
                rationale="이틀 전 기록", cooldown_started_at=traded - timedelta(days=2),
                cooldown_ends_at=traded - timedelta(days=2), created_at=traded - timedelta(days=2),
            ))
            db.session.commit()
        p = self._pending(client, "삼성전자 10주 매수 체결 71,200원 2026-09-01 10:32")
        a = client.post(f"{IMPORTS}/pending/{p['id']}/approve",
                        json={"thesis": "반도체 업황 회복", "reflection_id": None})
        assert a.status_code == 200
        with app.app_context():
            assert db.session.get(TradeHistory, a.get_json()["trade_id"]).reflection_id is None

    def test_explicit_wrong_ticker_rejected(self, client, app, auth_user):
        with app.app_context():
            rid = _refl(auth_user["id"], "AAPL")
        p = self._pending(client, "삼성전자 10주 매수 체결 71,200원 2026-09-01 10:32")
        a = client.post(f"{IMPORTS}/pending/{p['id']}/approve",
                        json={"thesis": "반도체 업황 회복", "reflection_id": rid})
        assert a.status_code == 400
        assert a.get_json()["code"] == "REFLECTION_LINK_TICKER_MISMATCH"
