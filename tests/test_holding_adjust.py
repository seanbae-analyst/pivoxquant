"""tests/test_holding_adjust.py — 기록된 매도 없이 보유가 줄 때의 조정 행 (2026-09-29).

보유 등록 시드(a70c7e2)는 등록이 주식을 *더할* 때만 행을 썼다. 보유 캡처
replace 로 수량을 낮추거나 PUT /position/<id> 로 주식 수를 줄이면 이력은 그대로
남아, FIFO 로트가 실제 보유보다 많아졌다 — 그 뒤의 매도가 "등록했지만 이미
없는" 로트를 닫았다.

잠그는 것:
1. 등록 경로가 주식을 줄이면 ``source="holding_adjust"`` 매도 행 1줄
   (수량 = 줄어든 만큼, 단가 = 그때의 평단, pnl 0, 통화 = 종목 통화).
   PUT /position/<id> 는 늘어난 만큼 시드 매수 행도 쓴다.
2. 조정 매도는 FIFO 로트를 소모하지만 관찰된 매도가 아니다 — 보유기간·손익처분·
   회전·멈춤 실현 수익률·분류기·기록 요약 체결 수 어디에도 나오지 않는다.
3. 백필은 보유가 이력보다 적으면(S − N < −0.0001) 그 차이만큼 조정 행을 계획한다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from models import TradeHistory
from models.trade_history import HOLDING_ADJUST_SOURCE, HOLDING_SEED_SOURCE


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _row(ticker, action, days_ago, shares=10.0, price=100.0, *, source=None,
         pnl_pct=0.0, rid=None, currency="USD"):
    return TradeHistory(
        id=rid, ticker=ticker, name=ticker, action=action, shares=shares,
        price_per_share=price, total_value=shares * price, pnl=0.0,
        pnl_pct=pnl_pct, currency=currency,
        traded_at=_now() - timedelta(days=days_ago), source=source,
    )


def _history(app, uid):
    with app.app_context():
        rows = (TradeHistory.query.filter_by(user_id=uid)
                .order_by(TradeHistory.id.asc()).all())
        return [(r.ticker, r.action, r.shares, r.price_per_share, r.source,
                 r.currency, r.pnl) for r in rows]


# ═════════════════════════════════════════════════════════════════════
# 1. registration paths write adjust rows
# ═════════════════════════════════════════════════════════════════════

class TestHoldingsImportReplaceDown:
    @pytest.fixture(autouse=True)
    def _no_network(self, monkeypatch):
        monkeypatch.setattr("services.fx_service.get_rate", lambda: 1300.0)
        monkeypatch.setattr("routes.holdings_import._warm_async", lambda app, t: None)

    def test_replace_down_writes_adjust_at_previous_avg(self, client, auth_user, app,
                                                        add_position):
        uid = auth_user["id"]
        add_position(uid, "MSFT", 10, 300)
        add_position(uid, "005930.KS", 20, 70000)
        r = client.post("/api/portfolio/holdings-import/commit", json={
            "consent": True, "rows": [
                {"ticker": "MSFT", "shares": 4, "avg_cost": 310,
                 "currency": "USD", "mode": "replace"},
                {"ticker": "005930.KS", "shares": 5, "avg_cost": 71000,
                 "currency": "KRW", "mode": "replace"},
            ],
        })
        assert r.status_code == 200, r.get_json()
        assert _history(app, uid) == [
            ("MSFT", "SELL", 6.0, 300.0, HOLDING_ADJUST_SOURCE, "USD", 0.0),
            ("005930.KS", "SELL", 15.0, 70000.0, HOLDING_ADJUST_SOURCE, "KRW", 0.0),
        ]

    def test_replace_same_count_writes_nothing(self, client, auth_user, app, add_position):
        uid = auth_user["id"]
        add_position(uid, "MSFT", 10, 300)
        r = client.post("/api/portfolio/holdings-import/commit", json={
            "consent": True, "rows": [
                {"ticker": "MSFT", "shares": 10, "avg_cost": 310,
                 "currency": "USD", "mode": "replace"},
            ],
        })
        assert r.status_code == 200, r.get_json()
        assert _history(app, uid) == []


class TestEditPosition:
    def _put(self, client, pid, shares, avg):
        with patch("routes.portfolio.cache_service.cache_ticker"), \
             patch("routes.portfolio._avg_cost_implausible", return_value=None):
            return client.put(f"/api/portfolio/position/{pid}",
                              json={"shares": shares, "avg_cost": avg})

    def test_down_writes_adjust_at_previous_avg(self, client, auth_user, app, add_position):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        assert self._put(client, pid, 6, 140.0).status_code == 200
        assert _history(app, auth_user["id"]) == [
            ("AAPL", "SELL", 4.0, 150.0, HOLDING_ADJUST_SOURCE, "USD", 0.0),
        ]

    def test_up_writes_seed_at_new_avg(self, client, auth_user, app, add_position):
        pid = add_position(auth_user["id"], "005930.KS", 10, 70000.0)
        assert self._put(client, pid, 14, 71000.0).status_code == 200
        assert _history(app, auth_user["id"]) == [
            ("005930.KS", "BUY", 4.0, 71000.0, HOLDING_SEED_SOURCE, "KRW", 0.0),
        ]

    def test_cost_only_edit_writes_nothing(self, client, auth_user, app, add_position):
        pid = add_position(auth_user["id"], "AAPL", 10, 150.0)
        assert self._put(client, pid, 10, 160.0).status_code == 200
        assert _history(app, auth_user["id"]) == []


# ═════════════════════════════════════════════════════════════════════
# 2. FIFO stays in sync; the adjust is not an observed 매도
# ═════════════════════════════════════════════════════════════════════

class TestRegisterReplaceSell:
    @pytest.fixture(autouse=True)
    def _no_network(self, monkeypatch):
        monkeypatch.setattr("services.fx_service.get_rate", lambda: 1300.0)
        monkeypatch.setattr("routes.holdings_import._warm_async", lambda app, t: None)

    def test_register_100_replace_60_sell_60(self, client, auth_user, app):
        from services.behavior.profit_loss_mirror import compute_profit_loss_mirror
        from services.behavior.turnover_mirror import compute_turnover_mirror
        from services.profile.fifo_util import (
            collapse_pairs_by_sell, fifo_match_closed_trades_with_pnl,
            fifo_open_position_ages,
        )

        with patch("routes.portfolio.cache_service.cache_ticker"):
            r = client.post("/api/portfolio/positions", json={
                "symbol": "AAPL", "quantity": 100, "price": 100,
            })
        assert r.status_code == 200, r.get_json()
        pid = int(r.get_json()["id"])
        r = client.post("/api/portfolio/holdings-import/commit", json={
            "consent": True, "rows": [{"ticker": "AAPL", "shares": 60, "avg_cost": 100,
                                       "currency": "USD", "mode": "replace"}],
        })
        assert r.status_code == 200, r.get_json()
        r = client.post(f"/api/portfolio/position/{pid}/sell",
                        json={"shares": 60, "price": 120})
        assert r.status_code == 200, r.get_json()

        with app.app_context():
            trades = TradeHistory.query.filter_by(user_id=auth_user["id"]).all()
            attributed = fifo_match_closed_trades_with_pnl(trades)
            observed = collapse_pairs_by_sell(attributed)
            # every share of the real 매도 found a lot — nothing hit an empty queue
            real = [p for p, _ in attributed if not p.sell_is_adjust]
            assert round(sum(p.quantity for p in real), 6) == 60.0
            # the adjust consumed the other 40 shares
            adj = [p for p, _ in attributed if p.sell_is_adjust]
            assert round(sum(p.quantity for p in adj), 6) == 40.0
            # exactly one observed 매도
            assert len(observed) == 1
            assert observed[0][0].quantity == 60.0
            assert observed[0][0].sell_is_adjust is False
            assert fifo_open_position_ages(trades) == []

            pl = compute_profit_loss_mirror(trades, min_pairs=1)
            tm = compute_turnover_mirror(trades, min_trades=1)
        assert pl["total_closed_pairs"] == 1
        assert tm["trade_count"] == 1 and tm["sell_count"] == 1


class TestAdjustNeverInStats:
    ROWS = staticmethod(lambda: [
        _row("A", "BUY", 50, shares=10, price=100, rid=1),
        _row("A", "SELL", 20, shares=4, price=100, source=HOLDING_ADJUST_SOURCE, rid=2),
        _row("A", "SELL", 10, shares=6, price=120, pnl_pct=20.0, rid=3),
    ])

    def test_pairs_carry_sell_is_adjust(self):
        from services.profile.fifo_util import (
            collapse_pairs_by_sell, fifo_match_closed_trades,
            fifo_match_closed_trades_with_pnl, is_holding_adjust, is_registration_row,
        )
        rows = self.ROWS()
        pairs = fifo_match_closed_trades(rows)
        assert [(p.quantity, p.sell_is_adjust) for p in pairs] == [(4, True), (6, False)]
        merged = collapse_pairs_by_sell(fifo_match_closed_trades_with_pnl(rows))
        assert [(p.quantity, p.sell_is_adjust) for p, _ in merged] == [(6, False)]
        assert is_holding_adjust(rows[1]) and not is_holding_adjust(rows[2])
        seed = _row("A", "BUY", 60, source=HOLDING_SEED_SOURCE)
        assert is_registration_row(seed) and is_registration_row(rows[1])
        assert not is_registration_row(rows[0])

    def test_mirrors(self):
        from services.behavior.profit_loss_mirror import compute_profit_loss_mirror
        from services.behavior.turnover_mirror import compute_turnover_mirror
        from services.profile.holding_mirror import compute_holding_mirror
        rows = self.ROWS()
        pl = compute_profit_loss_mirror(rows, min_pairs=1)
        assert pl["total_closed_pairs"] == 1
        assert pl["take_profit"]["count"] == 1
        assert pl["take_profit"]["median_hold_days"] == 40.0
        hm = compute_holding_mirror(rows, min_pairs=1)
        assert hm["total_closed_pairs"] == 1
        tm = compute_turnover_mirror(rows, min_trades=1)
        assert (tm["trade_count"], tm["buy_count"], tm["sell_count"]) == (2, 1, 1)
        assert tm["by_currency"] == [
            {"currency": "USD", "gross_value": 1720.0, "trade_count": 2}]
        assert tm["median_hold_days"] == 40.0

    def test_period_anchor_ignores_adjust(self):
        from services.behavior.turnover_mirror import compute_turnover_mirror
        rows = [_row(f"T{i}", "BUY", 100, rid=i + 1) for i in range(3)]
        rows.append(_row("T0", "SELL", 0, shares=1, source=HOLDING_ADJUST_SOURCE, rid=10))
        res = compute_turnover_mirror(rows, period_days=30, min_trades=1)
        assert res["trade_count"] == 3

    def test_friction_outcome_realised_skips_adjust(self):
        from services.pre_trade.friction_outcome import compute_friction_outcome
        out = compute_friction_outcome([], self.ROWS(), now=_now())
        assert out["realised"]["without_friction"]["n"] == 1

    def test_record_summary_count(self):
        from services.email.record_summary import _count_trades_in_window
        assert _count_trades_in_window(self.ROWS(), 365) == 2


class TestClassifierHoldingPeriod:
    def test_adjust_pair_is_not_a_hold_observation(self, app):
        from services.profile.persona_classifier_v2 import _extract_features
        now = _now()
        fills = [_row(f"F{i}", "BUY", 2, rid=i + 1) for i in range(10)]
        # a lot the adjust closes: with the adjust pair counted, the hold would
        # be ~59 days instead of the open lots' ~2-day age.
        with_adjust = fills + [
            _row("A", "BUY", 60, rid=100),
            _row("A", "SELL", 1, source=HOLDING_ADJUST_SOURCE, rid=101),
        ]
        with app.app_context():
            a = _extract_features(1, with_adjust, [], None, 90, now)
            b = _extract_features(1, fills, [], None, 90, now)
        assert a.values["holding_period"] == b.values["holding_period"]


class TestClassifierIgnoresAdjust:
    def test_adjust_is_not_a_window_trade(self, app, make_user):
        from extensions import db
        from services.profile.persona_classifier_v2 import classify_persona_multi
        user = make_user(email="adjclf@test.com")
        with app.app_context():
            for i in range(12):
                db.session.add(TradeHistory(
                    user_id=user["id"], ticker=f"S{i}", name="", action="SELL",
                    shares=1, price_per_share=10, total_value=10, currency="USD",
                    traded_at=_now() - timedelta(days=1), source=HOLDING_ADJUST_SOURCE,
                ))
            db.session.commit()
            out = classify_persona_multi(user["id"], window_days=30)
        assert out["trade_count"] == 0


# ═════════════════════════════════════════════════════════════════════
# 3. backfill writes an adjust when holdings are below history
# ═════════════════════════════════════════════════════════════════════

class TestBackfillAdjust:
    def test_gap_below_history_plans_adjust(self, app, make_user, add_position):
        from extensions import db
        from scripts.backfill_holding_seeds import run

        user = make_user(email="backfill-adj@test.com")
        uid = user["id"]
        add_position(uid, "NVDA", 6, 500.0)      # history explains 10 → adjust 4
        add_position(uid, "MSFT", 5, 300.0)      # exact → nothing
        with app.app_context():
            db.session.add_all([
                TradeHistory(user_id=uid, ticker="NVDA", action="BUY", shares=10,
                             price_per_share=450, total_value=4500, currency="USD",
                             traded_at=datetime(2025, 1, 1)),
                TradeHistory(user_id=uid, ticker="MSFT", action="BUY", shares=5,
                             price_per_share=300, total_value=1500, currency="USD",
                             traded_at=datetime(2025, 1, 1)),
            ])
            db.session.commit()

            planned = [p for p in run(apply=False) if p["user_id"] == uid]
            assert [(p["ticker"], p["action"], p["shares"], p["price"]) for p in planned] \
                == [("NVDA", "SELL", 4.0, 500.0)]
            assert TradeHistory.query.filter_by(
                user_id=uid, source=HOLDING_ADJUST_SOURCE).count() == 0

            run(apply=True)
            adj = TradeHistory.query.filter_by(user_id=uid, source=HOLDING_ADJUST_SOURCE).all()
            assert [(a.ticker, a.action, a.shares, a.price_per_share, a.pnl) for a in adj] \
                == [("NVDA", "SELL", 4.0, 500.0, 0.0)]

            assert [p for p in run(apply=False) if p["user_id"] == uid] == []


class TestMonthlyReportCount:
    def test_window_trade_count_skips_registration_rows(self, app, make_user):
        from extensions import db
        from services.reports.mirror_pdf import build_mirror_report
        uid = make_user(email="adj-report@test.com")["id"]
        with app.app_context():
            for action, source in (("BUY", HOLDING_SEED_SOURCE),
                                   ("SELL", HOLDING_ADJUST_SOURCE),
                                   ("BUY", None)):
                db.session.add(TradeHistory(
                    user_id=uid, ticker="A", name="A", action=action, shares=1,
                    price_per_share=10, total_value=10, currency="USD",
                    traded_at=_now() - timedelta(days=2), source=source,
                ))
            db.session.commit()
            data = build_mirror_report(uid, as_of=_now())
        assert data["window_trade_count"] == 1
