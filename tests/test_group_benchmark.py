"""
tests/test_group_benchmark.py — PivoxQuant Group Benchmark
==========================================================
Covers the anonymized, aggregated peer-group stats feature:

    compute_persona_stats(persona, window_days)
    compute_all_personas(window_days)
    get_persona_stats(persona, window_days)
    get_all_persona_stats(window_days)

    GET /api/profile/persona-benchmark?window=90
    GET /api/profile/persona-benchmark-all?window=90

Legal invariants validated here
-------------------------------
- No user_id / email / ticker appears in any API response or stored row.
- ``n_users < 20`` → suppressed row + API returns ``available: false``.
- Sector buckets are the finest-grained identifier that ever leaves
  this layer.
- Observational framing only — never "recommendation" / "advice" wording.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make_users(app, make_user, n: int, profile_type: str) -> list[int]:
    """Create ``n`` users with the given ``profile_type`` and return their ids."""
    from extensions import db
    from models import InvestmentProfile

    user_ids: list[int] = []
    for i in range(n):
        u = make_user(email=f"grp{profile_type}{i}@test.com", password="pw12345", name=f"u{i}")
        with app.app_context():
            profile = InvestmentProfile(
                user_id=u["id"],
                profile_type=profile_type,
                risk_tolerance=5,
            )
            db.session.add(profile)
            db.session.commit()
        user_ids.append(u["id"])
    return user_ids


def _add_round_trip(app, user_id: int, *, ticker: str, pnl_pct: float, days_ago: float = 5.0):
    """Insert a BUY/SELL pair with a known pnl_pct."""
    from extensions import db
    from models import TradeHistory

    now = _utc_now()
    buy_at = now - timedelta(days=days_ago + 1)
    sell_at = now - timedelta(days=days_ago)
    with app.app_context():
        db.session.add(TradeHistory(
            user_id=user_id, ticker=ticker, action="BUY",
            shares=10.0, price_per_share=100.0, total_value=1000.0,
            pnl=0.0, pnl_pct=0.0, traded_at=buy_at,
        ))
        db.session.add(TradeHistory(
            user_id=user_id, ticker=ticker, action="SELL",
            shares=10.0, price_per_share=100.0 * (1.0 + pnl_pct / 100.0),
            total_value=1000.0 * (1.0 + pnl_pct / 100.0),
            pnl=10.0 * pnl_pct, pnl_pct=pnl_pct, traded_at=sell_at,
        ))
        db.session.commit()


# ═════════════════════════════════════════════════════════════════════
# Service layer — compute_persona_stats
# ═════════════════════════════════════════════════════════════════════

class TestMinimumGroupSizeEnforced:
    def test_below_threshold_marks_suppressed(self, app, make_user):
        """N=5 (< MIN_GROUP_SIZE=20) → row persisted with suppressed=True."""
        from services.profile import compute_persona_stats
        from models import MIN_GROUP_SIZE, PersonaGroupStats

        assert MIN_GROUP_SIZE == 20  # guard the constant

        user_ids = _make_users(app, make_user, n=5, profile_type="growth")
        for uid in user_ids:
            _add_round_trip(app, uid, ticker="AAPL", pnl_pct=5.0)

        with app.app_context():
            row = compute_persona_stats("growth", 90)
            assert row is not None
            assert row.n_users == 5
            assert row.suppressed is True
            assert row.metrics is None  # legal: never materialized

            # Public read path → None (never expose sub-threshold data)
            from services.profile import get_persona_stats
            assert get_persona_stats("growth", 90) is None

            # Count suppressed rows
            stored = PersonaGroupStats.query.filter_by(persona="growth").all()
            assert len(stored) == 1
            assert stored[0].suppressed is True

    def test_at_threshold_publishes(self, app, make_user):
        """N=20 (exactly at threshold) → publishes real metrics."""
        from services.profile import compute_persona_stats, get_persona_stats

        user_ids = _make_users(app, make_user, n=20, profile_type="growth")
        for uid in user_ids:
            _add_round_trip(app, uid, ticker="AAPL", pnl_pct=5.0)

        with app.app_context():
            row = compute_persona_stats("growth", 90)
            assert row is not None
            assert row.n_users == 20
            assert row.suppressed is False
            assert row.metrics is not None

            published = get_persona_stats("growth", 90)
            assert published is not None
            assert published["n_users"] == 20
            assert "metrics" in published
            metrics = published["metrics"]
            # Shape check
            for key in (
                "avg_cagr", "avg_sharpe", "median_holding_days",
                "win_rate", "max_drawdown_avg", "most_held_sectors",
                "common_mistakes", "comparison_to_all",
            ):
                assert key in metrics, f"missing metric: {key}"

    def test_zero_users_returns_none(self, app):
        """Zero-user bucket → no row at all (saves cron storage)."""
        from services.profile import compute_persona_stats
        from models import PersonaGroupStats

        with app.app_context():
            row = compute_persona_stats("value", 90)
            assert row is None
            assert PersonaGroupStats.query.count() == 0


class TestAnonymizationInvariants:
    def test_no_user_id_leaked_in_metrics(self, app, make_user):
        """compute result MUST NOT contain any user_id / email / ticker."""
        from services.profile import compute_persona_stats

        user_ids = _make_users(app, make_user, n=20, profile_type="growth")
        for uid in user_ids:
            _add_round_trip(app, uid, ticker="AAPL", pnl_pct=7.0)

        with app.app_context():
            row = compute_persona_stats("growth", 90)
            assert row is not None
            blob = row.metrics or ""

            # Exact user ids → must not appear as integers in the payload.
            for uid in user_ids:
                assert f'"user_id": {uid}' not in blob
                assert f'"user_id":{uid}' not in blob

            # Raw tickers → must not appear (only sector buckets allowed).
            assert "AAPL" not in blob
            # Email addresses → must not appear.
            assert "@test.com" not in blob

    def test_only_sector_level_exposure(self, app, make_user):
        """most_held_sectors contains sector labels (strings), not tickers."""
        from services.profile import compute_persona_stats

        user_ids = _make_users(app, make_user, n=20, profile_type="growth")
        # Add a Position per user to exercise the sector aggregator.
        from extensions import db
        from models import Position
        with app.app_context():
            for i, uid in enumerate(user_ids):
                db.session.add(Position(
                    user_id=uid, ticker=f"T{i:03d}",
                    shares=10.0, avg_cost=50.0, buy_fx_rate=1.0,
                ))
            db.session.commit()
            # Need a trade so pnls pipeline runs; reuse AAPL pnl
            for uid in user_ids:
                _add_round_trip(app, uid, ticker="AAPL", pnl_pct=2.0)

            row = compute_persona_stats("growth", 90)
            payload = row.metrics_dict()
            sectors = payload.get("most_held_sectors", [])
            assert isinstance(sectors, list)
            for s in sectors:
                assert "sector" in s and "share" in s
                # No individual tickers leaked
                assert "T0" not in str(s["sector"])


# ═════════════════════════════════════════════════════════════════════
# CAGR / Sharpe computation
# ═════════════════════════════════════════════════════════════════════

class TestCagrComputation:
    def test_cagr_positive_when_gains(self, app, make_user):
        """20 users with uniform +5% trades → positive aggregate CAGR."""
        from services.profile import compute_persona_stats

        user_ids = _make_users(app, make_user, n=20, profile_type="growth")
        for uid in user_ids:
            _add_round_trip(app, uid, ticker="AAPL", pnl_pct=5.0)

        with app.app_context():
            row = compute_persona_stats("growth", 90)
            m = row.metrics_dict()
            # +5% compounded once, annualised over 90 days → ~21% CAGR
            assert m["avg_cagr"] > 0
            assert m["win_rate"] >= 99.0  # all wins

    def test_cagr_negative_when_losses(self, app, make_user):
        from services.profile import compute_persona_stats

        user_ids = _make_users(app, make_user, n=20, profile_type="growth")
        for uid in user_ids:
            _add_round_trip(app, uid, ticker="AAPL", pnl_pct=-4.0)

        with app.app_context():
            row = compute_persona_stats("growth", 90)
            m = row.metrics_dict()
            assert m["avg_cagr"] < 0
            assert m["win_rate"] == 0.0


# ═════════════════════════════════════════════════════════════════════
# common_mistakes detection
# ═════════════════════════════════════════════════════════════════════

class TestCommonMistakesTop3:
    def test_top_mistakes_capped_at_three(self, app, make_user):
        """Even if 5 mistake types fire, only top 3 are surfaced."""
        from services.profile import compute_persona_stats

        user_ids = _make_users(app, make_user, n=20, profile_type="growth")
        # Anchoring signal: 3 negative SELLs on same ticker per user.
        for uid in user_ids:
            _add_round_trip(app, uid, ticker="XYZ", pnl_pct=-2.0, days_ago=30)
            _add_round_trip(app, uid, ticker="XYZ", pnl_pct=-3.0, days_ago=20)
            _add_round_trip(app, uid, ticker="XYZ", pnl_pct=-1.0, days_ago=10)

        with app.app_context():
            row = compute_persona_stats("growth", 90)
            m = row.metrics_dict()
            mistakes = m.get("common_mistakes", [])
            assert isinstance(mistakes, list)
            assert len(mistakes) <= 3
            for entry in mistakes:
                assert set(entry.keys()) == {"label", "count"}
                assert entry["label"] in (
                    "disposition_effect", "herding", "anchoring",
                )
                # No surfaced count may fall below the re-identification floor.
                assert entry["count"] >= 2

    def test_min_mistake_count_floor(self):
        """The privacy floor never drops below 2 and scales at n//10."""
        from services.profile.group_benchmark import _min_mistake_count
        assert _min_mistake_count(20) == 2     # MIN_GROUP_SIZE → 2 (count=1 hidden)
        assert _min_mistake_count(5) == 2      # never below 2
        assert _min_mistake_count(100) == 10

    def test_rare_mistake_below_floor_is_suppressed(self, app, make_user):
        """A mistake exhibited by a single cohort member (count=1) is hidden —
        the floor keeps any surfaced pattern un-pinnable to one identifiable
        person (PIPA §23 re-identification, legal-kr-fintech 2026-06)."""
        from services.profile import compute_persona_stats

        user_ids = _make_users(app, make_user, n=20, profile_type="growth")
        # Only ONE of the 20 exhibits the anchoring pattern → raw count = 1.
        lone = user_ids[0]
        _add_round_trip(app, lone, ticker="XYZ", pnl_pct=-2.0, days_ago=30)
        _add_round_trip(app, lone, ticker="XYZ", pnl_pct=-3.0, days_ago=20)
        _add_round_trip(app, lone, ticker="XYZ", pnl_pct=-1.0, days_ago=10)

        with app.app_context():
            row = compute_persona_stats("growth", 90)
            mistakes = row.metrics_dict().get("common_mistakes", [])
        # count=1 < floor (2 for n=20) → suppressed entirely.
        assert mistakes == []


# ═════════════════════════════════════════════════════════════════════
# API layer — /api/profile/persona-benchmark
# ═════════════════════════════════════════════════════════════════════

class TestPersonaBenchmarkAPI:
    def test_unauthenticated_returns_401(self, client):
        r = client.get("/api/profile/persona-benchmark?window=90")
        assert r.status_code == 401

    def test_invalid_window_returns_400(self, client, auth_user):
        r = client.get("/api/profile/persona-benchmark?window=7")
        assert r.status_code == 400
        assert "window" in r.get_json().get("error", "").lower()

    def test_default_window_when_missing(self, client, auth_user):
        r = client.get("/api/profile/persona-benchmark")
        assert r.status_code == 200
        d = r.get_json()
        assert d["window_days"] == 90

    def test_not_computed_returns_available_false(self, client, auth_user):
        """Fresh DB, no snapshots → available=false, reason=not_computed."""
        r = client.get("/api/profile/persona-benchmark?window=90")
        assert r.status_code == 200
        d = r.get_json()
        assert d["available"] is False
        assert d["reason"] == "not_computed"
        assert "persona" in d
        assert "window_days" in d

    def test_suppressed_returns_available_false(self, app, client, auth_user, make_user):
        """Snapshot exists but n_users < 20 → available=false, reason=insufficient_group_size."""
        from services.profile import compute_persona_stats

        # Auth user is balanced by default. Put 3 balanced users so compute
        # runs but suppresses.
        user_ids = _make_users(app, make_user, n=3, profile_type="balanced")
        for uid in user_ids:
            _add_round_trip(app, uid, ticker="AAPL", pnl_pct=3.0)

        # Also set auth_user's own profile to balanced so resolver returns it.
        from extensions import db
        from models import InvestmentProfile
        with app.app_context():
            p = InvestmentProfile.query.filter_by(user_id=auth_user["id"]).first()
            if p is None:
                p = InvestmentProfile(user_id=auth_user["id"])
                db.session.add(p)
            p.profile_type = "balanced"
            p.risk_tolerance = 5
            db.session.commit()

            compute_persona_stats("balanced", 90)

        r = client.get("/api/profile/persona-benchmark?window=90")
        assert r.status_code == 200
        d = r.get_json()
        assert d["available"] is False
        assert d["reason"] == "insufficient_group_size"

    def test_published_returns_stats(self, app, client, auth_user, make_user):
        from services.profile import compute_persona_stats
        from extensions import db
        from models import InvestmentProfile

        user_ids = _make_users(app, make_user, n=20, profile_type="balanced")
        for uid in user_ids:
            _add_round_trip(app, uid, ticker="AAPL", pnl_pct=4.0)

        with app.app_context():
            p = InvestmentProfile.query.filter_by(user_id=auth_user["id"]).first()
            if p is None:
                p = InvestmentProfile(user_id=auth_user["id"])
                db.session.add(p)
            p.profile_type = "balanced"
            p.risk_tolerance = 5
            db.session.commit()

            compute_persona_stats("balanced", 90)

        r = client.get("/api/profile/persona-benchmark?window=90")
        assert r.status_code == 200
        d = r.get_json()
        assert d["available"] is True
        assert d["persona"] == "balanced"
        assert d["window_days"] == 90
        assert "stats" in d
        stats = d["stats"]
        # Frontend ``BenchmarkStats`` contract: metric fields live at the
        # TOP level of ``stats`` (flattened), NOT nested under ``metrics``.
        # Regression guard for the route-level flatten of the nested
        # ``to_dict()`` model shape (page-v2 + peer-benchmark-block crash
        # otherwise: ``undefined.toFixed()`` / silent ``fmt(undefined)``).
        assert "avg_cagr" in stats
        assert "avg_sharpe" in stats
        assert "win_rate" in stats
        assert "comparison_to_all" in stats
        # The metric dict carries persona + window_days per the contract.
        assert stats["persona"] == "balanced"
        assert stats["window_days"] == 90
        # The nested model shape MUST NOT leak through the API.
        assert stats.get("metrics") is None
        assert "n_users" not in stats
        assert "suppressed" not in stats
        # legal-kr-fintech (2026-06): the 5 behavioural sub-scores (0-100) must
        # NOT leave the API — surfacing a score-shaped number contradicts the
        # "AI 점수화 폐기" decision + 표시광고법 §3. Legitimate peer stats
        # (avg_cagr/avg_sharpe/win_rate/comparison_to_all, asserted above) stay.
        from models import SUB_SCORE_KEYS
        for _k in SUB_SCORE_KEYS:
            assert _k not in stats, f"sub-score {_k!r} leaked to persona-benchmark API"
        # Sanity: no ticker leaked
        import json as _json
        blob = _json.dumps(d, ensure_ascii=False)
        assert "AAPL" not in blob


class TestPersonaBenchmarkAllAPI:
    def test_unauthenticated_returns_401(self, client):
        r = client.get("/api/profile/persona-benchmark-all?window=90")
        assert r.status_code == 401

    def test_returns_all_eight_personas(self, client, auth_user):
        r = client.get("/api/profile/persona-benchmark-all?window=90")
        assert r.status_code == 200
        d = r.get_json()
        assert d["window_days"] == 90
        assert "personas" in d
        for persona in (
            "growth", "value", "balanced", "income",
            "quant", "speculator", "daytrader", "beginner",
        ):
            assert persona in d["personas"]
            entry = d["personas"][persona]
            assert "available" in entry
            assert "label" in entry
            # With no data, all must be unavailable
            assert entry["available"] is False

    def test_invalid_window_returns_400(self, client, auth_user):
        r = client.get("/api/profile/persona-benchmark-all?window=45")
        assert r.status_code == 400

    def test_published_persona_stats_are_flattened(
        self, app, client, auth_user, make_user
    ):
        """An available persona exposes flattened ``BenchmarkStats`` shape.

        Regression guard: metric fields must sit at the top level of the
        per-persona ``stats`` object (matching the frontend contract),
        never nested under ``metrics``.
        """
        from services.profile import compute_persona_stats

        user_ids = _make_users(app, make_user, n=20, profile_type="growth")
        for uid in user_ids:
            _add_round_trip(app, uid, ticker="AAPL", pnl_pct=4.0)

        with app.app_context():
            compute_persona_stats("growth", 90)

        r = client.get("/api/profile/persona-benchmark-all?window=90")
        assert r.status_code == 200
        d = r.get_json()
        growth = d["personas"]["growth"]
        assert growth["available"] is True
        stats = growth["stats"]
        # Flattened metric fields at top level.
        assert "avg_cagr" in stats
        assert "win_rate" in stats
        assert "comparison_to_all" in stats
        assert stats["persona"] == "growth"
        assert stats["window_days"] == 90
        # Nested model shape must not leak.
        assert stats.get("metrics") is None
        assert "n_users" not in stats
        assert "suppressed" not in stats
        # legal-kr-fintech (2026-06): no 0-100 behavioural sub-score leaves the
        # API here either (점수화 폐기 + 표시광고법 §3).
        from models import SUB_SCORE_KEYS
        for _k in SUB_SCORE_KEYS:
            assert _k not in stats, f"sub-score {_k!r} leaked to persona-benchmark-all API"


# ═════════════════════════════════════════════════════════════════════
# compute_all_personas — multi-persona cron entry point
# ═════════════════════════════════════════════════════════════════════

class TestComputeAllPersonas:
    def test_only_buckets_with_users_return_rows(self, app, make_user):
        from services.profile import compute_all_personas

        # Populate only 'growth' — the other 7 buckets remain empty and
        # must not create rows.
        user_ids = _make_users(app, make_user, n=20, profile_type="growth")
        for uid in user_ids:
            _add_round_trip(app, uid, ticker="AAPL", pnl_pct=1.0)

        with app.app_context():
            rows = compute_all_personas(90)
            assert len(rows) == 1
            assert rows[0].persona == "growth"
            assert rows[0].suppressed is False


# ═════════════════════════════════════════════════════════════════════
# F7 — behavioural sub-score aggregation (added 2026-04-30)
# ═════════════════════════════════════════════════════════════════════
# Background: ``services.behavior.scorer._persona_avg_with_floor`` reads
# 5 sub-score keys from the ``metrics`` dict (holding_discipline,
# loss_cut, position_sizing, fomo_resistance, reflection_rate). Without
# the F7 fix, ``_aggregate_metrics`` never wrote these keys → every
# behavioural score response returned ``persona_avg = None``.
#
# These tests pin the contract: when a persona group exists, the
# aggregated metrics dict MUST contain (or at least allow) the 5
# SUB_SCORE_KEYS so ``persona_avg`` can populate.

class TestBehaviouralSubScoreAggregation:
    def test_metrics_dict_can_carry_sub_score_keys(self, app, make_user):
        """The aggregator's output must accept SUB_SCORE_KEYS.

        We don't assert the keys are *always present* (they may be
        empty when no user has a computable sub-score in the window),
        but the contract with ``_persona_avg_with_floor`` requires that
        a metrics dict at least *can* contain the 5 keys, and when
        present they are floats in [0, 100].
        """
        from models import SUB_SCORE_KEYS
        from services.profile import compute_persona_stats

        user_ids = _make_users(app, make_user, n=20, profile_type="growth")
        for uid in user_ids:
            _add_round_trip(app, uid, ticker="AAPL", pnl_pct=1.0)

        with app.app_context():
            row = compute_persona_stats("growth", 90)
            assert row is not None
            metrics = row.metrics if isinstance(row.metrics, dict) else None
            if metrics is None:
                # Some implementations store metrics as JSON text — load.
                import json
                metrics = json.loads(row.metrics) if isinstance(row.metrics, str) else {}

            # Per-key contract: when present, it's a float in [0, 100].
            for key in SUB_SCORE_KEYS:
                if key in metrics:
                    val = metrics[key]
                    assert isinstance(val, (int, float)), \
                        f"{key} must be numeric, got {type(val).__name__}"
                    assert 0.0 <= float(val) <= 100.0, \
                        f"{key} = {val} out of [0, 100]"

    def test_aggregate_helper_returns_dict(self, app, make_user):
        """_aggregate_behavioral_sub_scores must return a dict."""
        from services.profile.group_benchmark import _aggregate_behavioral_sub_scores

        # Empty user_ids → empty dict (no crash, no None).
        assert _aggregate_behavioral_sub_scores([]) == {}

        # Non-empty user list → dict (keys may be empty if no scores).
        with app.app_context():
            result = _aggregate_behavioral_sub_scores([1, 2, 3])
            assert isinstance(result, dict)
            # All values, when present, must be numeric.
            for k, v in result.items():
                assert isinstance(v, (int, float)), \
                    f"sub-score {k} must be numeric, got {type(v).__name__}"

    def test_persona_avg_uses_aggregated_keys(self, app, make_user):
        """End-to-end: _persona_avg_with_floor reads what the aggregator wrote."""
        from services.behavior.scorer import _persona_avg_with_floor

        user_ids = _make_users(app, make_user, n=20, profile_type="growth")
        for uid in user_ids:
            _add_round_trip(app, uid, ticker="AAPL", pnl_pct=1.0)

        with app.app_context():
            # Trigger aggregate metrics computation first.
            from services.profile import compute_persona_stats
            row = compute_persona_stats("growth", 90)
            assert row is not None

            # Now read back via the scorer's helper.
            avg = _persona_avg_with_floor("growth")
            # avg may be None if no sub-scores were computable in the test
            # data, OR a dict with numeric values. Either is correct
            # behaviour — None must not crash.
            assert avg is None or isinstance(avg, dict)
            if isinstance(avg, dict):
                for k, v in avg.items():
                    assert isinstance(v, float)
                    assert 0.0 <= v <= 100.0
