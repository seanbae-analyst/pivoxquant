"""tests/test_holding_mirror.py — PivoxQuant Holding Mirror (처분효과 거울)

Covers the retrospective winner/loser holding-period mirror:

    services.profile.holding_mirror.compute_holding_mirror(trades, ...)
    GET /api/behavior/holding-mirror?period=30d|all

Invariants validated here
-------------------------
- Pure function: no DB / network. Operates on plain TradeHistory rows.
- winner = SELL pnl_pct > 0, loser = pnl_pct < 0, break-even (== 0)
  excluded from both buckets.
- median is the headline statistic, mean is the secondary.
- Edge cases: new user / < min_pairs / one-sided / break-even excluded /
  buy_price==0 guarded / traded_at None skipped / same-day (<1) holds.
- NO score / grade / ratio / index field ever appears in the output.
- examples surface display NAME (feedback_ticker_display), not naked KR
  ticker, and pull from the longest/shortest holds per side.
- API: ?period validation, auth required, disclaimer present.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from models import TradeHistory
from services.profile.holding_mirror import compute_holding_mirror


# ═════════════════════════════════════════════════════════════════════
# Helpers — build plain (unpersisted) TradeHistory rows
# ═════════════════════════════════════════════════════════════════════

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _trade(
    *,
    ticker: str,
    action: str,
    traded_at: datetime | None,
    shares: float = 10.0,
    price_per_share: float = 100.0,
    pnl_pct: float = 0.0,
    name: str = "",
) -> TradeHistory:
    return TradeHistory(
        ticker=ticker,
        name=name,
        action=action,
        shares=shares,
        price_per_share=price_per_share,
        total_value=shares * price_per_share,
        pnl=shares * pnl_pct,
        pnl_pct=pnl_pct,
        traded_at=traded_at,
    )


def _round_trip(
    *,
    ticker: str,
    pnl_pct: float,
    hold_days: float,
    sell_days_ago: float = 1.0,
    name: str = "",
    buy_price: float = 100.0,
) -> list[TradeHistory]:
    """A matched BUY→SELL pair held ``hold_days`` days."""
    now = _now()
    sell_at = now - timedelta(days=sell_days_ago)
    buy_at = sell_at - timedelta(days=hold_days)
    sell_price = buy_price * (1.0 + pnl_pct / 100.0)
    return [
        _trade(ticker=ticker, action="BUY", traded_at=buy_at,
               price_per_share=buy_price, name=name),
        _trade(ticker=ticker, action="SELL", traded_at=sell_at,
               price_per_share=sell_price, pnl_pct=pnl_pct, name=name),
    ]


_FORBIDDEN_SCORE_KEYS = {"ratio", "score", "grade", "index"}


def _assert_no_scoring(result: dict) -> None:
    """The mirror must never surface a score/grade/ratio/index anywhere."""
    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                assert k not in _FORBIDDEN_SCORE_KEYS, f"forbidden key {k!r}"
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(result)
    # MISTAKE_DISPOSITION label must not leak either.
    assert "disposition" not in repr(result).lower()


# ═════════════════════════════════════════════════════════════════════
# Edge case: brand-new user (zero closed pairs)
# ═════════════════════════════════════════════════════════════════════

class TestNewUser:
    def test_no_trades_insufficient(self):
        result = compute_holding_mirror([])
        assert result["sufficient_data"] is False
        assert result["one_sided"] is False
        assert result["total_closed_pairs"] == 0
        assert result["winners"] is None
        assert result["losers"] is None
        _assert_no_scoring(result)

    def test_only_open_buys_no_closed_pairs(self):
        """Open BUYs with no SELL → no closed pairs → insufficient."""
        now = _now()
        trades = [
            _trade(ticker="AAPL", action="BUY", traded_at=now - timedelta(days=3)),
            _trade(ticker="MSFT", action="BUY", traded_at=now - timedelta(days=2)),
        ]
        result = compute_holding_mirror(trades)
        assert result["sufficient_data"] is False
        assert result["total_closed_pairs"] == 0
        _assert_no_scoring(result)


# ═════════════════════════════════════════════════════════════════════
# Edge case: fewer than min_pairs classified
# ═════════════════════════════════════════════════════════════════════

class TestBelowMinPairs:
    def test_four_pairs_below_default_min_five(self):
        trades: list[TradeHistory] = []
        for i in range(4):
            trades += _round_trip(ticker=f"T{i}", pnl_pct=5.0, hold_days=2.0)
        result = compute_holding_mirror(trades)
        assert result["sufficient_data"] is False
        # numbers withheld
        assert result["winners"] is None
        assert result["losers"] is None
        # but the raw closed-pair count is still honest
        assert result["total_closed_pairs"] == 4
        _assert_no_scoring(result)

    def test_exactly_min_pairs_is_sufficient(self):
        trades: list[TradeHistory] = []
        for i in range(3):
            trades += _round_trip(ticker=f"W{i}", pnl_pct=5.0, hold_days=2.0)
        for i in range(2):
            trades += _round_trip(ticker=f"L{i}", pnl_pct=-5.0, hold_days=10.0)
        result = compute_holding_mirror(trades)  # 5 classified == min
        assert result["sufficient_data"] is True
        assert result["total_closed_pairs"] == 5
        _assert_no_scoring(result)

    def test_custom_min_pairs(self):
        trades: list[TradeHistory] = []
        for i in range(6):
            trades += _round_trip(ticker=f"T{i}", pnl_pct=5.0, hold_days=2.0)
        # 6 winners, 0 losers — but raise the bar to 10
        result = compute_holding_mirror(trades, min_pairs=10)
        assert result["sufficient_data"] is False


# ═════════════════════════════════════════════════════════════════════
# Edge case: one-sided (all winners / all losers)
# ═════════════════════════════════════════════════════════════════════

class TestOneSided:
    def test_all_winners(self):
        trades: list[TradeHistory] = []
        for i in range(6):
            trades += _round_trip(ticker=f"W{i}", pnl_pct=8.0, hold_days=3.0)
        result = compute_holding_mirror(trades)
        assert result["sufficient_data"] is True
        assert result["one_sided"] is True
        assert result["winners"] is not None
        assert result["winners"]["count"] == 6
        assert result["losers"] is None
        _assert_no_scoring(result)

    def test_all_losers(self):
        trades: list[TradeHistory] = []
        for i in range(6):
            trades += _round_trip(ticker=f"L{i}", pnl_pct=-8.0, hold_days=20.0)
        result = compute_holding_mirror(trades)
        assert result["sufficient_data"] is True
        assert result["one_sided"] is True
        assert result["winners"] is None
        assert result["losers"] is not None
        assert result["losers"]["count"] == 6
        _assert_no_scoring(result)


# ═════════════════════════════════════════════════════════════════════
# Edge case: break-even (pnl_pct == 0) excluded
# ═════════════════════════════════════════════════════════════════════

class TestBreakEvenExcluded:
    def test_break_even_pairs_not_classified_but_counted(self):
        trades: list[TradeHistory] = []
        for i in range(3):
            trades += _round_trip(ticker=f"W{i}", pnl_pct=5.0, hold_days=2.0)
        for i in range(3):
            trades += _round_trip(ticker=f"L{i}", pnl_pct=-5.0, hold_days=15.0)
        # two break-even round trips — must be ignored from buckets
        for i in range(2):
            trades += _round_trip(ticker=f"E{i}", pnl_pct=0.0, hold_days=7.0)
        result = compute_holding_mirror(trades)
        assert result["sufficient_data"] is True
        # total_closed counts ALL closed pairs incl. break-even (8)
        assert result["total_closed_pairs"] == 8
        # but classified buckets exclude the 2 break-even
        assert result["winners"]["count"] == 3
        assert result["losers"]["count"] == 3
        _assert_no_scoring(result)


# ═════════════════════════════════════════════════════════════════════
# Edge case: buy_price == 0 guard + traded_at None skip
# ═════════════════════════════════════════════════════════════════════

class TestDataQualityGuards:
    def test_zero_buy_price_still_pairs(self):
        """price_per_share==0 on the BUY leg must not crash; pair still
        forms (hold_days computable) and pnl_pct sign drives the bucket."""
        now = _now()
        trades: list[TradeHistory] = []
        for i in range(5):
            sell_at = now - timedelta(days=1)
            buy_at = sell_at - timedelta(days=4)
            trades.append(_trade(ticker=f"Z{i}", action="BUY", traded_at=buy_at,
                                 price_per_share=0.0))
            trades.append(_trade(ticker=f"Z{i}", action="SELL", traded_at=sell_at,
                                 price_per_share=10.0, pnl_pct=3.0))
        result = compute_holding_mirror(trades)
        assert result["sufficient_data"] is True
        assert result["winners"]["count"] == 5
        # example hold_days computed from timestamps, independent of price
        assert result["winners"]["examples"][0]["hold_days"] == 4.0

    def test_traded_at_none_skipped(self):
        """SELL with no traded_at can't FIFO-match → not classified."""
        now = _now()
        trades: list[TradeHistory] = []
        # 5 valid winners
        for i in range(5):
            trades += _round_trip(ticker=f"W{i}", pnl_pct=4.0, hold_days=2.0)
        # 1 broken pair: BUY ok, SELL with traded_at None
        buy_at = now - timedelta(days=5)
        trades.append(_trade(ticker="BAD", action="BUY", traded_at=buy_at))
        trades.append(_trade(ticker="BAD", action="SELL", traded_at=None,
                             pnl_pct=-9.0))
        result = compute_holding_mirror(trades)
        assert result["sufficient_data"] is True
        # the None-dated SELL never matched → still only 5 closed pairs
        assert result["total_closed_pairs"] == 5
        assert result["winners"]["count"] == 5
        assert result["losers"] is None


# ═════════════════════════════════════════════════════════════════════
# Edge case: same-day hold (hold_days < 1)
# ═════════════════════════════════════════════════════════════════════

class TestSameDayHold:
    def test_sub_day_hold_preserved_as_fraction(self):
        now = _now()
        trades: list[TradeHistory] = []
        for i in range(5):
            sell_at = now - timedelta(days=1)
            buy_at = sell_at - timedelta(hours=6)  # 0.25 day
            trades.append(_trade(ticker=f"D{i}", action="BUY", traded_at=buy_at))
            trades.append(_trade(ticker=f"D{i}", action="SELL", traded_at=sell_at,
                                 price_per_share=105.0, pnl_pct=5.0))
        result = compute_holding_mirror(trades)
        assert result["sufficient_data"] is True
        assert result["winners"]["median_hold_days"] == 0.2  # round(0.25,1)
        assert result["winners"]["examples"][0]["hold_days"] == 0.2


# ═════════════════════════════════════════════════════════════════════
# Statistics: median primary, mean secondary, extreme examples
# ═════════════════════════════════════════════════════════════════════

class TestStatistics:
    def test_median_resists_outlier(self):
        """One forgotten loser held 400d should NOT move the median much,
        while the mean blows up — proves median is the right headline."""
        trades: list[TradeHistory] = []
        # losers held ~10 days, plus one extreme 400-day outlier
        for d in (8.0, 9.0, 10.0, 11.0):
            trades += _round_trip(ticker=f"L{d}", pnl_pct=-5.0, hold_days=d)
        trades += _round_trip(ticker="LX", pnl_pct=-5.0, hold_days=400.0)
        # a couple of winners so it isn't one-sided
        for i in range(2):
            trades += _round_trip(ticker=f"W{i}", pnl_pct=5.0, hold_days=3.0)
        result = compute_holding_mirror(trades)
        losers = result["losers"]
        # median ~ 10 (middle of 8,9,10,11,400), mean dragged way up
        assert losers["median_hold_days"] == 10.0
        assert losers["mean_hold_days"] > 80.0

    def test_loser_examples_are_longest_held(self):
        trades: list[TradeHistory] = []
        for i in range(2):
            trades += _round_trip(ticker=f"W{i}", pnl_pct=5.0, hold_days=2.0)
        for d in (5.0, 30.0, 12.0, 60.0):
            trades += _round_trip(ticker=f"L{int(d)}", pnl_pct=-5.0, hold_days=d)
        result = compute_holding_mirror(trades, max_examples=3)
        ex_holds = [e["hold_days"] for e in result["losers"]["examples"]]
        # longest first, capped at 3
        assert ex_holds == [60.0, 30.0, 12.0]

    def test_winner_examples_are_shortest_held(self):
        trades: list[TradeHistory] = []
        for d in (5.0, 1.0, 3.0, 9.0):
            trades += _round_trip(ticker=f"W{int(d)}", pnl_pct=5.0, hold_days=d)
        for i in range(2):
            trades += _round_trip(ticker=f"L{i}", pnl_pct=-5.0, hold_days=20.0)
        result = compute_holding_mirror(trades, max_examples=3)
        ex_holds = [e["hold_days"] for e in result["winners"]["examples"]]
        # shortest first, capped at 3
        assert ex_holds == [1.0, 3.0, 5.0]

    def test_max_examples_zero(self):
        trades: list[TradeHistory] = []
        for i in range(6):
            trades += _round_trip(ticker=f"W{i}", pnl_pct=5.0, hold_days=2.0)
        result = compute_holding_mirror(trades, max_examples=0)
        assert result["winners"]["examples"] == []


# ═════════════════════════════════════════════════════════════════════
# feedback_ticker_display: display NAME, not naked KR ticker
# ═════════════════════════════════════════════════════════════════════

class TestTickerDisplay:
    def test_stored_name_preferred(self):
        trades: list[TradeHistory] = []
        for i in range(5):
            trades += _round_trip(ticker="005930.KS", pnl_pct=5.0,
                                  hold_days=float(i + 1), name="삼성전자")
        result = compute_holding_mirror(trades)
        ex = result["winners"]["examples"][0]
        assert ex["display_name"] == "삼성전자"
        assert ex["ticker"] == "005930.KS"

    def test_kr_ticker_resolved_when_name_blank(self, monkeypatch):
        """No stored name → kr_display_name resolves the hangul name; the
        raw .KS code must never be the display string when resolvable."""
        import services.profile.holding_mirror as hm

        monkeypatch.setattr(
            hm, "kr_display_name",
            lambda t: "삼성전자" if t == "005930.KS" else t,
        )
        trades: list[TradeHistory] = []
        for i in range(5):
            trades += _round_trip(ticker="005930.KS", pnl_pct=5.0,
                                  hold_days=float(i + 1), name="")
        result = compute_holding_mirror(trades)
        ex = result["winners"]["examples"][0]
        assert ex["display_name"] == "삼성전자"

    def test_ticker_fallback_when_unresolvable(self):
        trades: list[TradeHistory] = []
        for i in range(5):
            trades += _round_trip(ticker="AAPL", pnl_pct=5.0,
                                  hold_days=float(i + 1), name="")
        result = compute_holding_mirror(trades)
        ex = result["winners"]["examples"][0]
        # US ticker is its own display name (kr_display_name returns it as-is)
        assert ex["display_name"] == "AAPL"


# ═════════════════════════════════════════════════════════════════════
# Period window (30d vs all)
# ═════════════════════════════════════════════════════════════════════

class TestPeriodWindow:
    def test_period_days_filters_old_trades(self):
        trades: list[TradeHistory] = []
        # 5 recent winners within 30d
        for i in range(5):
            trades += _round_trip(ticker=f"R{i}", pnl_pct=5.0, hold_days=2.0,
                                  sell_days_ago=3.0)
        # 5 old losers ~60d ago — outside a 30d window
        for i in range(5):
            trades += _round_trip(ticker=f"O{i}", pnl_pct=-5.0, hold_days=2.0,
                                  sell_days_ago=60.0)
        all_result = compute_holding_mirror(trades)  # period None
        assert all_result["total_closed_pairs"] == 10

        win_result = compute_holding_mirror(trades, period_days=30)
        # only the 5 recent winners survive the window
        assert win_result["total_closed_pairs"] == 5
        assert win_result["winners"]["count"] == 5
        assert win_result["losers"] is None


# ═════════════════════════════════════════════════════════════════════
# API surface
# ═════════════════════════════════════════════════════════════════════

class TestApi:
    def _insert(self, app, user_id, trades):
        from extensions import db
        with app.app_context():
            for t in trades:
                t.user_id = user_id
                db.session.add(t)
            db.session.commit()

    def test_requires_auth(self, client):
        resp = client.get("/api/behavior/holding-mirror")
        assert resp.status_code in (401, 403)

    def test_new_user_insufficient(self, client, auth_user):
        resp = client.get("/api/behavior/holding-mirror")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["ok"] is True
        assert body["sufficient_data"] is False
        assert body["period"] == "all"
        assert "disclaimer" in body
        # no scoring keys leak through the envelope
        assert not (_FORBIDDEN_SCORE_KEYS & set(body))

    def test_invalid_period_rejected(self, client, auth_user):
        resp = client.get("/api/behavior/holding-mirror?period=bogus")
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "BAD_INPUT"

    def test_populated_response(self, client, auth_user, app):
        trades: list[TradeHistory] = []
        for i in range(4):
            trades += _round_trip(ticker=f"W{i}", pnl_pct=6.0, hold_days=2.0)
        for i in range(3):
            trades += _round_trip(ticker=f"L{i}", pnl_pct=-6.0, hold_days=20.0)
        self._insert(app, auth_user["id"], trades)

        resp = client.get("/api/behavior/holding-mirror?period=all")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["sufficient_data"] is True
        assert body["one_sided"] is False
        assert body["winners"]["count"] == 4
        assert body["losers"]["count"] == 3
        # winners sold quicker than losers held — the whole point
        assert (body["winners"]["median_hold_days"]
                < body["losers"]["median_hold_days"])
        _assert_no_scoring(body)

    def test_period_30d_param_passes_through(self, client, auth_user, app):
        resp = client.get("/api/behavior/holding-mirror?period=30d")
        assert resp.status_code == 200
        assert resp.get_json()["period"] == "30d"


# ═════════════════════════════════════════════════════════════════════
# Regression — same-day multiple SELLs on one ticker must not collide
#
# Bug (2026-05-31): pnl_pct was looked up via a plain
# {(ticker, traded_at): pnl_pct} dict. When two SELLs of the same ticker
# closed on the same date-grain traded_at, the LAST SELL's pnl_pct
# overwrote the earlier one, so a +30% take-profit pair was bucketed as a
# loss (sign reversal). Fixed by attributing pnl_pct per-pair inside
# fifo_match_closed_trades_with_pnl.
# ═════════════════════════════════════════════════════════════════════

class TestSameDaySellNoCollision:
    """Two same-ticker SELLs on identical traded_at → correct buckets."""

    @staticmethod
    def _scenario() -> list[TradeHistory]:
        """5 winner round trips (+8%) + AAPL: 2 BUYs each closed by a
        same-day SELL — one +30% (win), one -30% (loss).

        Expected classification: winners=5, losers=1.
        """
        trades: list[TradeHistory] = []
        # W0..W4 — five clean +8% winners, distinct days
        for i in range(5):
            trades += _round_trip(
                ticker=f"W{i}", pnl_pct=8.0, hold_days=3.0,
                sell_days_ago=10.0 + i, name=f"위너{i}",
            )

        # AAPL: two BUYs on distinct earlier days, two SELLs that BOTH
        # land on the SAME date-grain traded_at (midnight) — the
        # collision trigger. FIFO closes BUY#1 with SELL#1 (+30%) and
        # BUY#2 with SELL#2 (-30%).
        # Hold AAPL only ~1-2 days so its +30% winner ranks among the
        # top-3 *shortest* winner examples (the W winners are held 3d),
        # exercising the example builder's sign attribution too.
        base = datetime(2026, 5, 20, 0, 0, 0)  # date-grain midnight
        buy1 = datetime(2026, 5, 19, 0, 0, 0)   # held 1 day
        buy2 = datetime(2026, 5, 18, 0, 0, 0)   # held 2 days
        trades += [
            _trade(ticker="AAPL", action="BUY", traded_at=buy1,
                   shares=10.0, price_per_share=100.0, name="애플"),
            _trade(ticker="AAPL", action="BUY", traded_at=buy2,
                   shares=10.0, price_per_share=100.0, name="애플"),
            # SELL#1 closes BUY#1 at +30% (win)
            _trade(ticker="AAPL", action="SELL", traded_at=base,
                   shares=10.0, price_per_share=130.0, pnl_pct=30.0,
                   name="애플"),
            # SELL#2 closes BUY#2 at -30% (loss), SAME traded_at as SELL#1
            _trade(ticker="AAPL", action="SELL", traded_at=base,
                   shares=10.0, price_per_share=70.0, pnl_pct=-30.0,
                   name="애플"),
        ]
        return trades

    def test_buckets_not_sign_reversed(self):
        result = compute_holding_mirror(
            self._scenario(), period_days=None, min_pairs=5,
        )
        assert result["sufficient_data"] is True
        # 6 classified pairs: 5 winners (+8%) + AAPL +30% = 6 wins,
        # AAPL -30% = 1 loss. Pre-fix this came out 4/2 (sign reversal).
        assert result["winners"]["count"] == 6, result["winners"]
        assert result["losers"]["count"] == 1, result["losers"]
        assert result["total_closed_pairs"] == 7
        _assert_no_scoring(result)

    def test_example_preserves_take_profit_sign(self):
        """The AAPL +30% take-profit must appear as a WINNER example with
        a positive pnl_pct — never surfaced as a -30% loss example."""
        result = compute_holding_mirror(
            self._scenario(), period_days=None, min_pairs=5,
        )
        winner_examples = result["winners"]["examples"]
        aapl_wins = [e for e in winner_examples if e["ticker"] == "AAPL"]
        assert aapl_wins, "AAPL take-profit missing from winner examples"
        assert all(e["pnl_pct"] == 30.0 for e in aapl_wins), aapl_wins

        loser_examples = result["losers"]["examples"]
        aapl_losses = [e for e in loser_examples if e["ticker"] == "AAPL"]
        # The loss side must hold ONLY the -30% AAPL pair, never the +30%.
        assert all(e["pnl_pct"] == -30.0 for e in aapl_losses), aapl_losses
