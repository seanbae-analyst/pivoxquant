"""tests/test_holding_seed.py — 보유 등록 시드 매수 행 (2026-09-29).

보유 등록 경로(POST /api/portfolio/positions · /position · 보유 캡처 가져오기)가
``positions`` 만 쓰고 ``trade_history`` 를 쓰지 않아서, FIFO 로 로트를 다시
세우는 거울들이 등록 종목의 매도를 버리고 추가매수를 새 진입으로 읽었다.

잠그는 것:
1. 등록이 주식을 더하면 ``source="holding_seed"`` 매수 행이 하나 생긴다
   (보유 캡처 replace 는 늘어난 만큼만, 줄어들면 없음).
2. 시드는 로트(수량·평단)에는 들어가지만 보유기간 통계·체결 수·추가매수
   수·"결국 샀다"·관찰 페르소나의 체결 축에는 들어가지 않는다.
3. 백필 스크립트는 기본 dry-run, ``--apply`` 로 쓰고, 두 번 돌려도 같다.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from models import TradeHistory
from models.trade_history import HOLDING_SEED_SOURCE


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _row(ticker, action, days_ago, shares=10.0, price=100.0, *, seed=False,
         pnl_pct=0.0, rid=None):
    return TradeHistory(
        id=rid, ticker=ticker, name=ticker, action=action, shares=shares,
        price_per_share=price, total_value=shares * price, pnl=0.0,
        pnl_pct=pnl_pct, currency="USD",
        traded_at=_now() - timedelta(days=days_ago),
        source=HOLDING_SEED_SOURCE if seed else None,
    )


def _history(app, uid):
    with app.app_context():
        rows = (TradeHistory.query.filter_by(user_id=uid)
                .order_by(TradeHistory.id.asc()).all())
        return [(r.ticker, r.action, r.shares, r.price_per_share, r.source,
                 r.currency, r.name) for r in rows]


# ═════════════════════════════════════════════════════════════════════
# 1. registration paths write seeds
# ═════════════════════════════════════════════════════════════════════

class TestRegistrationWritesSeed:
    def test_create_position_alias_new_and_merge(self, client, auth_user, app):
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r1 = client.post("/api/portfolio/positions", json={
                "symbol": "AAPL", "quantity": 10, "price": 150,
                "purchase_date": "2024-01-02",
            })
            r2 = client.post("/api/portfolio/positions", json={
                "symbol": "AAPL", "quantity": 5, "price": 180,
            })
        assert r1.status_code == 200 and r2.status_code == 200
        hist = _history(app, auth_user["id"])
        assert [(h[0], h[1], h[2], h[3], h[4], h[5]) for h in hist] == [
            ("AAPL", "BUY", 10.0, 150.0, HOLDING_SEED_SOURCE, "USD"),
            ("AAPL", "BUY", 5.0, 180.0, HOLDING_SEED_SOURCE, "USD"),
        ]
        with app.app_context():
            ts = TradeHistory.query.filter_by(user_id=auth_user["id"]).first().traded_at
        # registration time, not the declared purchase date
        assert abs((ts - _now()).total_seconds()) < 120

    def test_add_position_kr_currency(self, client, auth_user, app):
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/position", json={
                "ticker": "005930.KS", "shares": 3, "avg_cost": 70000,
            })
        assert r.status_code == 200, r.get_json()
        hist = _history(app, auth_user["id"])
        assert len(hist) == 1
        ticker, action, shares, price, source, currency, name = hist[0]
        assert (ticker, action, shares, price, source, currency) == (
            "005930.KS", "BUY", 3.0, 70000.0, HOLDING_SEED_SOURCE, "KRW")
        assert name  # resolved display name, never blank

    def test_rejected_add_writes_nothing(self, client, auth_user, app, add_position):
        for t in ("AAPL", "MSFT", "GOOG"):
            add_position(auth_user["id"], t, 1, 100)
        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/positions", json={
                "symbol": "AMZN", "quantity": 1, "price": 100,
            })
        assert r.status_code == 403
        assert _history(app, auth_user["id"]) == []


class TestHoldingsImportSeeds:
    @pytest.fixture(autouse=True)
    def _no_network(self, monkeypatch):
        monkeypatch.setattr("services.fx_service.get_rate", lambda: 1300.0)
        monkeypatch.setattr("routes.holdings_import._warm_async", lambda app, t: None)

    def _commit(self, client, *rows):
        return client.post("/api/portfolio/holdings-import/commit",
                           json={"consent": True, "rows": list(rows)})

    def _r(self, ticker, shares, avg, currency="USD", mode="add"):
        return {"ticker": ticker, "shares": shares, "avg_cost": avg,
                "currency": currency, "mode": mode}

    def test_create_add_replace(self, client, auth_user, app, add_position):
        uid = auth_user["id"]
        add_position(uid, "AAPL", 10, 150)   # replace up → delta seed
        add_position(uid, "MSFT", 10, 300)   # replace down → no seed
        r = self._commit(
            client,
            self._r("AAPL", 14, 160, mode="replace"),
            self._r("MSFT", 4, 310, mode="replace"),
            self._r("NVDA", 2, 500),
        )
        assert r.status_code == 200, r.get_json()
        seeds = {(h[0], h[2], h[3]) for h in _history(app, uid)
                 if h[4] == HOLDING_SEED_SOURCE}
        assert seeds == {("AAPL", 4.0, 160.0), ("NVDA", 2.0, 500.0)}

        r = self._commit(client, self._r("NVDA", 3, 520, mode="add"))
        assert r.status_code == 200, r.get_json()
        nv = [h for h in _history(app, uid) if h[0] == "NVDA"]
        assert [(h[2], h[4]) for h in nv] == [(2.0, HOLDING_SEED_SOURCE),
                                             (3.0, HOLDING_SEED_SOURCE)]


# ═════════════════════════════════════════════════════════════════════
# 2. the sell of a registered holding now reaches the mirrors
# ═════════════════════════════════════════════════════════════════════

class TestSellAfterRegistration:
    def test_profit_loss_counts_the_sell_without_hold_days(self, client, auth_user, app):
        from services.behavior.profit_loss_mirror import compute_profit_loss_mirror
        from services.behavior.turnover_mirror import compute_turnover_mirror
        from services.profile.holding_mirror import compute_holding_mirror

        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/positions", json={
                "symbol": "AAPL", "quantity": 10, "price": 100,
            })
        pid = int(r.get_json()["id"])
        r = client.post(f"/api/portfolio/position/{pid}/sell",
                        json={"shares": 10, "price": 120})
        assert r.status_code == 200, r.get_json()

        with app.app_context():
            trades = TradeHistory.query.filter_by(user_id=auth_user["id"]).all()
            pl = compute_profit_loss_mirror(trades, min_pairs=1)
            hm = compute_holding_mirror(trades, min_pairs=1)
            tm = compute_turnover_mirror(trades, min_trades=1)
        # before seeds the 매도 hit an empty queue and was dropped (0 pairs)
        assert pl["sufficient_data"] is True
        assert pl["total_closed_pairs"] == 1
        assert pl["take_profit"]["count"] == 1
        assert pl["take_profit"]["median_gain_pct"] == 20.0
        # the seed's buy time is the registration time — no hold days
        assert pl["take_profit"]["median_hold_days"] is None
        assert hm["total_closed_pairs"] == 0
        # the seed is not a fill
        assert tm["trade_count"] == 1
        assert tm["buy_count"] == 0 and tm["sell_count"] == 1
        assert tm["median_hold_days"] is None


# ═════════════════════════════════════════════════════════════════════
# 3. pure consumers
# ═════════════════════════════════════════════════════════════════════

class TestFifoSeedFlag:
    def test_pairs_carry_buy_is_seed(self):
        from services.profile.fifo_util import (
            collapse_pairs_by_sell, fifo_match_closed_trades,
            fifo_match_closed_trades_with_pnl, fifo_open_position_ages,
        )
        rows = [
            _row("A", "BUY", 50, shares=5, seed=True, rid=1),
            _row("A", "BUY", 40, shares=5, rid=2),
            _row("A", "SELL", 10, shares=8, rid=3),
        ]
        pairs = fifo_match_closed_trades(rows)
        assert [(p.quantity, p.buy_is_seed) for p in pairs] == [(5, True), (3, False)]
        merged = collapse_pairs_by_sell(fifo_match_closed_trades_with_pnl(rows))
        assert len(merged) == 1
        pair = merged[0][0]
        assert pair.buy_is_seed is False
        # hold days from the non-seed slice only (40 - 10 = 30)
        assert round(pair.hold_days, 6) == 30.0
        # cost from every slice
        assert pair.quantity == 8
        ages_all = fifo_open_position_ages(rows, reference_time=_now())
        ages_real = fifo_open_position_ages(rows, reference_time=_now(), include_seeds=False)
        assert len(ages_all) == 1 and len(ages_real) == 1  # 2 left, real lot
        only_seed = [_row("B", "BUY", 5, seed=True, rid=4)]
        assert fifo_open_position_ages(only_seed, include_seeds=False) == []
        assert len(fifo_open_position_ages(only_seed)) == 1

    def test_all_seed_sell_is_flagged(self):
        from services.profile.fifo_util import (
            collapse_pairs_by_sell, fifo_match_closed_trades_with_pnl,
        )
        rows = [_row("A", "BUY", 50, seed=True, rid=1), _row("A", "SELL", 1, rid=2)]
        merged = collapse_pairs_by_sell(fifo_match_closed_trades_with_pnl(rows))
        assert merged[0][0].buy_is_seed is True


class TestAveragingDownWithSeeds:
    def test_seed_sets_average_but_is_never_a_follow_on(self):
        from services.behavior.averaging_down_mirror import compute_averaging_down_mirror
        rows = [
            _row("A", "BUY", 30, price=100, seed=True, rid=1),
            _row("A", "BUY", 20, price=80, rid=2),            # below seed avg
            _row("B", "BUY", 30, price=50, rid=3),
            _row("B", "BUY", 20, price=60, seed=True, rid=4),  # seed on a held ticker
        ]
        res = compute_averaging_down_mirror(rows, min_follow_on=1)
        assert res["follow_on_count"] == 1
        assert res["below_avg_count"] == 1


class TestFrictionOutcomeIgnoresSeeds:
    def test_seed_is_not_bought_later_anyway(self):
        from models import PreTradeReflection
        from services.pre_trade.friction_outcome import compute_friction_outcome
        base = _now() - timedelta(days=10)
        refl = PreTradeReflection(
            user_id=1, intended_ticker="AAPL", intended_side="BUY",
            rationale="x" * 20, created_at=base, cooldown_started_at=base,
            cooldown_ends_at=base, cancelled_at=base,
        )
        seed = _row("AAPL", "BUY", 5, seed=True, rid=1)
        out = compute_friction_outcome([refl], [seed], now=_now())
        follow = out["cancelled_followthrough"]
        assert follow["cancelled"] == 1
        assert follow["bought_later_anyway"] == 0
        assert follow["never_bought"] == 1


class TestTurnoverWindowAnchor:
    def test_seed_does_not_move_the_period_anchor(self):
        from services.behavior.turnover_mirror import compute_turnover_mirror
        rows = [_row(f"T{i}", "BUY", 100, rid=i + 1) for i in range(3)]
        rows.append(_row("Z", "BUY", 0, seed=True, rid=10))
        res = compute_turnover_mirror(rows, period_days=30, min_trades=1)
        # anchored on the last fill (100 days ago), not on the seed (today)
        assert res["trade_count"] == 3


class TestClassifierIgnoresSeedFills:
    def test_seeds_are_not_window_trades(self, app, make_user):
        from extensions import db
        from services.profile.persona_classifier_v2 import classify_persona_multi
        user = make_user(email="seedclf@test.com")
        with app.app_context():
            for i in range(12):
                db.session.add(TradeHistory(
                    user_id=user["id"], ticker=f"S{i}", name="", action="BUY",
                    shares=1, price_per_share=10, total_value=10, currency="USD",
                    traded_at=_now() - timedelta(days=1), source=HOLDING_SEED_SOURCE,
                ))
            db.session.commit()
            out = classify_persona_multi(user["id"], window_days=30)
        assert out["trade_count"] == 0


# ═════════════════════════════════════════════════════════════════════
# 4. backfill script
# ═════════════════════════════════════════════════════════════════════

class TestBackfill:
    def test_dry_run_apply_idempotent(self, app, make_user, add_position):
        from extensions import db
        from scripts.backfill_holding_seeds import run

        user = make_user(email="backfill@test.com")
        uid = user["id"]
        opened = datetime(2025, 3, 4, 9, 0, 0)
        add_position(uid, "AAPL", 10, 150.0, added_at=opened)   # no history → seed 10
        add_position(uid, "MSFT", 5, 300.0)                     # fully explained → none
        add_position(uid, "NVDA", 8, 500.0)                     # 3 explained → seed 5
        with app.app_context():
            db.session.add_all([
                TradeHistory(user_id=uid, ticker="MSFT", action="BUY", shares=5,
                             price_per_share=300, total_value=1500, currency="USD",
                             traded_at=datetime(2025, 1, 1)),
                TradeHistory(user_id=uid, ticker="NVDA", action="BUY", shares=4,
                             price_per_share=450, total_value=1800, currency="USD",
                             traded_at=datetime(2025, 1, 1)),
                TradeHistory(user_id=uid, ticker="NVDA", action="SELL", shares=1,
                             price_per_share=460, total_value=460, currency="USD",
                             traded_at=datetime(2025, 2, 1)),
            ])
            db.session.commit()

            planned = run(apply=False)
            assert sorted((p["ticker"], p["shares"]) for p in planned
                          if p["user_id"] == uid) == [("AAPL", 10.0), ("NVDA", 5.0)]
            assert TradeHistory.query.filter_by(
                user_id=uid, source=HOLDING_SEED_SOURCE).count() == 0

            run(apply=True)
            seeds = {s.ticker: s for s in TradeHistory.query.filter_by(
                user_id=uid, source=HOLDING_SEED_SOURCE)}
            assert set(seeds) == {"AAPL", "NVDA"}
            assert seeds["AAPL"].shares == 10.0
            assert seeds["AAPL"].price_per_share == 150.0
            assert seeds["AAPL"].traded_at == opened
            assert seeds["AAPL"].action == "BUY"
            assert seeds["NVDA"].shares == 5.0

            assert [p for p in run(apply=False) if p["user_id"] == uid] == []
            run(apply=True)
            assert TradeHistory.query.filter_by(
                user_id=uid, source=HOLDING_SEED_SOURCE).count() == 2
