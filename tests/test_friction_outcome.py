"""tests/test_friction_outcome.py — 멈춤의 귀결 거울

    services.pre_trade.friction_outcome.compute_friction_outcome(
        reflections, trades, ...)

여기서 고정하는 불변식
----------------------
- **순수 함수**: DB / 네트워크 / 시세 / FX 호출 없음. 영속되지 않은 평범한
  모델 인스턴스로 전부 계산된다.
- 취소를 **회피와 지연으로 가른다** — 취소 후 같은 종목을 결국 산 건 회피가
  아니다.
- 두 실현 수익률 분포는 표본이 :data:`MIN_GROUP_N` 미만이면 ``comparable=False``
  로 **비교를 거부**한다.
- 수익률은 슬라이스 체결가로 직접 계산한다 (``pnl_pct`` 를 신뢰하지 않는다) —
  한 매도가 여러 매수를 닫는 경우가 이 테스트로 고정된다.
- payload 에 **판정·조언·점수 어휘가 없다** (§17 / DECISIONS.md).
- 귀속 창(:data:`ATTRIBUTION_WINDOW_DAYS`) 밖의 매수는 멈춤 경유로 세지 않는다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from models import PreTradeReflection, TradeHistory
from services.pre_trade.friction_outcome import (
    ATTRIBUTION_WINDOW_DAYS,
    MIN_GROUP_N,
    compute_friction_outcome,
)

BASE = datetime(2026, 3, 2, 9, 0, 0)


# ═════════════════════════════════════════════════════════════════════
# Helpers — 영속되지 않은 행
# ═════════════════════════════════════════════════════════════════════

def _refl(ticker, *, created=None, proceeded=None, cancelled=None):
    return PreTradeReflection(
        user_id=1,
        intended_ticker=ticker,
        rationale="x" * 20,
        created_at=created or BASE,
        cooldown_started_at=created or BASE,
        cooldown_ends_at=created or BASE,
        proceeded_at=proceeded,
        cancelled_at=cancelled,
    )


def _trade(ticker, action, at, *, shares=10.0, price=100.0, pnl_pct=0.0):
    return TradeHistory(
        user_id=1, ticker=ticker, action=action, shares=shares,
        price_per_share=price, total_value=shares * price,
        pnl_pct=pnl_pct, currency="USD", traded_at=at,
    )


def _round_trip(ticker, buy_at, buy_px, sell_px, *, days=10, shares=10.0):
    """한 종목의 매수→매도 한 쌍."""
    return [
        _trade(ticker, "BUY", buy_at, shares=shares, price=buy_px),
        _trade(ticker, "SELL", buy_at + timedelta(days=days), shares=shares, price=sell_px),
    ]


# ═════════════════════════════════════════════════════════════════════
class TestStoppedCounts:
    def test_empty_is_insufficient(self):
        out = compute_friction_outcome([], [], now=BASE)
        assert out["insufficient"] is True
        assert out["stopped"] == {"started": 0, "proceeded": 0, "cancelled": 0, "open": 0}

    def test_three_way_split(self):
        refls = [
            _refl("AAPL", proceeded=BASE + timedelta(minutes=1)),
            _refl("MSFT", cancelled=BASE + timedelta(minutes=2)),
            _refl("NVDA"),  # 미결
        ]
        out = compute_friction_outcome(refls, [], now=BASE + timedelta(days=1))
        assert out["stopped"] == {"started": 3, "proceeded": 1, "cancelled": 1, "open": 1}

    def test_proceeded_wins_over_cancelled_when_both_stamped(self):
        """둘 다 찍힌 비정상 행은 진행으로 센다 — 이중 계상 금지."""
        r = _refl("AAPL", proceeded=BASE + timedelta(minutes=1),
                  cancelled=BASE + timedelta(minutes=2))
        out = compute_friction_outcome([r], [], now=BASE + timedelta(days=1))
        s = out["stopped"]
        assert s["proceeded"] == 1 and s["cancelled"] == 0 and s["open"] == 0


# ═════════════════════════════════════════════════════════════════════
class TestCancelledFollowthrough:
    def test_cancel_then_never_bought_is_avoidance(self):
        r = _refl("AAPL", cancelled=BASE)
        out = compute_friction_outcome([r], [], now=BASE + timedelta(days=30))
        cf = out["cancelled_followthrough"]
        assert cf["cancelled"] == 1
        assert cf["never_bought"] == 1
        assert cf["bought_later_anyway"] == 0
        assert cf["median_days_until_bought"] is None

    def test_cancel_then_bought_anyway_is_postponement(self):
        r = _refl("AAPL", cancelled=BASE)
        trades = [_trade("AAPL", "BUY", BASE + timedelta(days=2))]
        out = compute_friction_outcome([r], trades, now=BASE + timedelta(days=30))
        cf = out["cancelled_followthrough"]
        assert cf["bought_later_anyway"] == 1
        assert cf["never_bought"] == 0
        assert cf["median_days_until_bought"] == 2.0

    def test_buy_before_cancel_does_not_count(self):
        """취소 *이전*의 매수는 그 취소의 번복이 아니다."""
        r = _refl("AAPL", cancelled=BASE + timedelta(days=5))
        trades = [_trade("AAPL", "BUY", BASE)]
        out = compute_friction_outcome([r], trades, now=BASE + timedelta(days=30))
        assert out["cancelled_followthrough"]["bought_later_anyway"] == 0

    def test_other_ticker_buy_does_not_count(self):
        r = _refl("AAPL", cancelled=BASE)
        trades = [_trade("MSFT", "BUY", BASE + timedelta(days=1))]
        out = compute_friction_outcome([r], trades, now=BASE + timedelta(days=30))
        assert out["cancelled_followthrough"]["bought_later_anyway"] == 0

    def test_ticker_matching_is_case_insensitive(self):
        r = _refl("aapl", cancelled=BASE)
        trades = [_trade("AAPL", "BUY", BASE + timedelta(days=1))]
        out = compute_friction_outcome([r], trades, now=BASE + timedelta(days=30))
        assert out["cancelled_followthrough"]["bought_later_anyway"] == 1


# ═════════════════════════════════════════════════════════════════════
class TestRealisedDistributions:
    def test_below_min_group_refuses_comparison(self):
        trades = _round_trip("AAPL", BASE, 100.0, 110.0)
        out = compute_friction_outcome([], trades, now=BASE + timedelta(days=60))
        r = out["realised"]
        assert r["comparable"] is False
        assert r["min_group_n"] == MIN_GROUP_N
        # 숫자 자체는 계산해 두되, 비교해도 된다고 말하지 않는다.
        assert r["without_friction"]["n"] == 1

    def test_attributes_buy_inside_window_to_friction_group(self):
        proceeded_at = BASE
        buy_at = BASE + timedelta(days=1)
        refls = [_refl("AAPL", proceeded=proceeded_at)]
        trades = _round_trip("AAPL", buy_at, 100.0, 120.0)
        out = compute_friction_outcome(refls, trades, now=BASE + timedelta(days=60))
        r = out["realised"]
        assert r["with_friction"]["n"] == 1
        assert r["with_friction"]["median_pct"] == 20.0
        assert r["without_friction"]["n"] == 0

    def test_buy_outside_window_is_not_attributed(self):
        refls = [_refl("AAPL", proceeded=BASE)]
        buy_at = BASE + timedelta(days=ATTRIBUTION_WINDOW_DAYS + 1)
        trades = _round_trip("AAPL", buy_at, 100.0, 120.0)
        out = compute_friction_outcome(refls, trades, now=BASE + timedelta(days=90))
        assert out["realised"]["with_friction"]["n"] == 0
        assert out["realised"]["without_friction"]["n"] == 1

    def test_comparable_true_when_both_groups_reach_min(self):
        refls, trades = [], []
        # 멈춤 경유 5건
        for i in range(MIN_GROUP_N):
            t = f"AA{i}"
            at = BASE + timedelta(days=i)
            refls.append(_refl(t, proceeded=at))
            trades += _round_trip(t, at + timedelta(hours=1), 100.0, 110.0)
        # 미경유 5건
        for i in range(MIN_GROUP_N):
            t = f"BB{i}"
            trades += _round_trip(t, BASE + timedelta(days=i), 100.0, 90.0)
        out = compute_friction_outcome(refls, trades, now=BASE + timedelta(days=120))
        r = out["realised"]
        assert r["comparable"] is True
        assert r["with_friction"]["n"] == MIN_GROUP_N
        assert r["without_friction"]["n"] == MIN_GROUP_N
        assert r["with_friction"]["median_pct"] == 10.0
        assert r["without_friction"]["median_pct"] == -10.0

    def test_return_comes_from_prices_not_pnl_pct(self):
        """한 매도가 두 매수를 닫아도 슬라이스마다 자기 수익률을 갖는다.

        ``pnl_pct`` 를 그대로 썼다면 두 슬라이스가 같은 값을 공유해
        분포가 뭉갠다. 체결가로 직접 계산하므로 갈린다.
        """
        trades = [
            _trade("AAPL", "BUY", BASE, shares=10, price=100.0, pnl_pct=0.0),
            _trade("AAPL", "BUY", BASE + timedelta(days=1), shares=10, price=200.0, pnl_pct=0.0),
            # 한 번에 20주 매도 — 두 매수를 모두 닫는다
            _trade("AAPL", "SELL", BASE + timedelta(days=5), shares=20, price=150.0,
                   pnl_pct=999.0),
        ]
        out = compute_friction_outcome([], trades, now=BASE + timedelta(days=60))
        w = out["realised"]["without_friction"]
        assert w["n"] == 2
        # 100→150 = +50%, 200→150 = -25%  ⇒ median 12.5
        assert w["median_pct"] == 12.5

    def test_zero_buy_price_slice_is_skipped(self):
        trades = _round_trip("AAPL", BASE, 0.0, 120.0)
        out = compute_friction_outcome([], trades, now=BASE + timedelta(days=60))
        assert out["realised"]["without_friction"]["n"] == 0


# ═════════════════════════════════════════════════════════════════════
class TestWindow:
    def test_window_days_excludes_older_rows(self):
        old = _refl("AAPL", created=BASE - timedelta(days=100),
                    proceeded=BASE - timedelta(days=100))
        recent = _refl("MSFT", created=BASE, proceeded=BASE)
        out = compute_friction_outcome([old, recent], [], window_days=30, now=BASE)
        assert out["stopped"]["started"] == 1
        assert out["window_days"] == 30

    def test_none_window_keeps_everything(self):
        old = _refl("AAPL", created=BASE - timedelta(days=500), proceeded=BASE)
        out = compute_friction_outcome([old], [], now=BASE)
        assert out["stopped"]["started"] == 1
        assert out["window_days"] is None


# ═════════════════════════════════════════════════════════════════════
class TestNoVerdictLanguage:
    """§17 — 이 거울은 사실만 낸다. 판정·조언 어휘가 payload 에 없어야 한다."""

    def test_payload_has_no_judgement_keys_or_values(self):
        refls = [_refl("AAPL", proceeded=BASE), _refl("MSFT", cancelled=BASE)]
        trades = _round_trip("AAPL", BASE + timedelta(hours=1), 100.0, 130.0)
        out = compute_friction_outcome(refls, trades, now=BASE + timedelta(days=60))

        blob = repr(out).lower()
        for banned in (
            "score", "grade", "rank", "better", "worse", "improve",
            "should", "recommend", "advice", "win_rate", "verdict",
            "good", "bad", "효과", "추천", "조언", "개선",
        ):
            assert banned not in blob, f"판정/조언 어휘 '{banned}' 가 payload 에 있다"

    def test_caveats_are_always_shipped(self):
        """한계는 선택 항목이 아니다 — 결과와 같은 봉투에 항상 실린다."""
        out = compute_friction_outcome([], [], now=BASE)
        c = out["caveats"]
        assert c["not_randomised"] is True
        assert c["attribution_window_days"] == ATTRIBUTION_WINDOW_DAYS
        assert c["cooldown_seconds_currently"] == 0


# ═════════════════════════════════════════════════════════════════════
class TestPurity:
    def test_no_network_or_price_import_in_module(self):
        """다른 mirror 와 같은 규율 — 시세/FX 를 끌어오지 않는다."""
        import pathlib

        src = pathlib.Path("services/pre_trade/friction_outcome.py").read_text()
        code = "\n".join(
            ln for ln in src.split("\n") if not ln.strip().startswith("#")
        )
        for banned in ("container import", "fetcher", "realtime", "requests",
                       "fx_service", "get_quote"):
            assert banned not in code, f"순수성 위반: {banned}"
