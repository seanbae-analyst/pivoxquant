"""Tests for the (dormant) Weekly Behavioural Score kernels.

Covers the 5 sub-score kernels, the weighted overall, persona-avg
floor, observational note's legal cleanliness, and the cron handler —
all still exercised so the dormant scorer (kept for export/persona
benchmark/mirror compatibility) stays correct.

The score-consuming HTTP endpoints were removed 2026-05-30 per the "AI
점수화 폐기" decision (DECISIONS.md); ``test_score_endpoints_removed``
is the regression gate.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from extensions import db
from models import (
    BehavioralScore,
    InvestmentProfile,
    Position,
    PreTradeReflection,
    SUB_SCORE_KEYS,
    TradeHistory,
)
from services.behavior.scorer import (
    WEIGHTS,
    _fomo_resistance_subscore,
    _holding_discipline_subscore,
    _last_sunday,
    _loss_cut_subscore,
    _observational_note,
    _overall_weighted_average,
    _position_sizing_subscore,
    _reflection_rate_subscore,
    compute_weekly_score,
    run_weekly_for_all_users,
)
from services.legal.forbidden_terms import contains_forbidden_term


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _trade(user_id, ticker, action, shares, price, pnl=0.0, pnl_pct=0.0,
           when=None):
    """Insert a TradeHistory row and return it."""
    t = TradeHistory(
        user_id=user_id, ticker=ticker, action=action,
        shares=shares, price_per_share=price,
        total_value=shares * price,
        pnl=pnl, pnl_pct=pnl_pct,
        traded_at=when or _now(),
    )
    db.session.add(t)
    db.session.commit()
    return t


def _make_user_with_persona(app, make_user, persona, email):
    user = make_user(email=email)
    with app.app_context():
        prof = InvestmentProfile(user_id=user["id"], profile_type=persona)
        db.session.add(prof)
        db.session.commit()
    return user


# ─────────────────────────────────────────────────────────────────────
# Sub-score kernels
# ─────────────────────────────────────────────────────────────────────

def test_compute_weekly_score_basic(app, make_user):
    """Empty trade week ⇒ all sub-scores resolve and overall is in [0, 100]."""
    user = make_user(email="bs-basic@test.com")
    with app.app_context():
        out = compute_weekly_score(user["id"], persist=False)
        assert set(out["sub_scores"].keys()) == set(SUB_SCORE_KEYS)
        assert 0.0 <= out["overall_score"] <= 100.0
        assert out["trade_count"] == 0


def test_holding_discipline_subscore(app, make_user):
    """Persona = balanced (target 60d). 65d held ⇒ score = 100 (≥ target)."""
    user = _make_user_with_persona(app, make_user, "balanced", "bs-hold@test.com")
    now = _now()
    with app.app_context():
        # BUY 65 days ago, SELL today — avg hold 65 days vs. 60d target.
        _trade(user["id"], "AAPL", "BUY", 10, 100, when=now - timedelta(days=65))
        _trade(user["id"], "AAPL", "SELL", 10, 110, pnl=100, when=now)
        trades = TradeHistory.query.filter_by(user_id=user["id"]).all()
        score = _holding_discipline_subscore(trades, "balanced")
        assert score == 100.0


def test_loss_cut_subscore_quick_cutter_high(app, make_user):
    """Cut a loss in 1 day ⇒ score 100; hold a loss 30+ days ⇒ score 0."""
    user_fast = make_user(email="bs-fast@test.com")
    user_slow = make_user(email="bs-slow@test.com")
    now = _now()
    with app.app_context():
        # Fast cutter: open + lose + close in 1 day.
        _trade(user_fast["id"], "AAPL", "BUY", 10, 100, when=now - timedelta(days=1))
        _trade(user_fast["id"], "AAPL", "SELL", 10, 90, pnl=-100, when=now)
        # Slow cutter: 35 days under water.
        _trade(user_slow["id"], "MSFT", "BUY", 10, 200, when=now - timedelta(days=35))
        _trade(user_slow["id"], "MSFT", "SELL", 10, 180, pnl=-200, when=now)

        fast = _loss_cut_subscore(
            TradeHistory.query.filter_by(user_id=user_fast["id"]).all()
        )
        slow = _loss_cut_subscore(
            TradeHistory.query.filter_by(user_id=user_slow["id"]).all()
        )
        assert fast >= 90.0
        assert slow <= 10.0


def test_position_sizing_concentrated_low_score(app, make_user):
    """One huge position vs. tiny others ⇒ sizing score < 30."""
    user = make_user(email="bs-size@test.com")
    with app.app_context():
        # 90% in AAPL, 10% spread elsewhere → share ~0.90, expect low score.
        db.session.add(Position(user_id=user["id"], ticker="AAPL",
                                 shares=900, avg_cost=100))
        db.session.add(Position(user_id=user["id"], ticker="MSFT",
                                 shares=100, avg_cost=100))
        db.session.commit()
        score = _position_sizing_subscore(user["id"])
        # 90% concentration ⇒ deep below the 10% target.
        assert score < 30.0


def test_position_sizing_balanced_high_score(app, make_user):
    """Even split across 10 names (10% each) ⇒ score 100."""
    user = make_user(email="bs-even@test.com")
    with app.app_context():
        for i in range(10):
            db.session.add(Position(
                user_id=user["id"], ticker=f"T{i}",
                shares=10, avg_cost=100,
            ))
        db.session.commit()
        score = _position_sizing_subscore(user["id"])
        assert score == 100.0


def test_fomo_resistance_metric(app, make_user):
    """A buy on a day with another trade carrying ≥5% pnl_pct ⇒ FOMO flagged."""
    user = make_user(email="bs-fomo@test.com")
    today = _now()
    with app.app_context():
        # SELL row registers a 6% intraday move on AAPL same day.
        _trade(user["id"], "AAPL", "SELL", 5, 106, pnl=30, pnl_pct=6.0, when=today)
        # BUY on same day, same ticker → FOMO.
        _trade(user["id"], "AAPL", "BUY", 1, 106, when=today)
        score = _fomo_resistance_subscore(
            TradeHistory.query.filter_by(user_id=user["id"]).all()
        )
        # 1 of 1 buys was FOMO ⇒ score 0.
        assert score == 0.0


def test_reflection_rate_uses_pre_trade_table(app, make_user):
    """A user with one reflection / one trade and a long rationale gets a
    reflection_rate score > 0; a user with no reflections gets 0."""
    user = make_user(email="bs-refl@test.com")
    week_end = _last_sunday(date.today())
    end_dt = datetime.combine(week_end, datetime.min.time())
    start_dt = end_dt - timedelta(days=6)
    with app.app_context():
        # 1 trade in window.
        _trade(user["id"], "AAPL", "BUY", 1, 100, when=start_dt + timedelta(days=2))
        trades = TradeHistory.query.filter_by(user_id=user["id"]).all()
        zero = _reflection_rate_subscore(user["id"], start_dt, end_dt, trades)
        assert zero == 0.0

        # Add a 200-char rationale reflection.
        rationale = "사전 reasoning. " * 20
        ref = PreTradeReflection(
            user_id=user["id"],
            intended_ticker="AAPL",
            intended_side="BUY",
            intended_shares=1,
            rationale=rationale,
            cooldown_started_at=start_dt + timedelta(days=2),
            cooldown_ends_at=start_dt + timedelta(days=2, seconds=120),
        )
        db.session.add(ref)
        db.session.commit()
        nonzero = _reflection_rate_subscore(user["id"], start_dt, end_dt, trades)
        assert nonzero > 0.0


def test_overall_weighted_average():
    """Equal-weight average of (50, 50, 50, 50, 50) = 50."""
    sub = {k: 50.0 for k in SUB_SCORE_KEYS}
    assert _overall_weighted_average(sub) == 50.0
    # Sanity: weights still sum to 1.0
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_persona_avg_suppressed_when_under_20(app, make_user):
    """When PersonaGroupStats is suppressed (n<20), persona_avg is None."""
    user = _make_user_with_persona(app, make_user, "balanced", "bs-supp@test.com")
    with app.app_context(), patch(
        "services.profile.group_benchmark.get_persona_stats",
        return_value=None,
    ):
        out = compute_weekly_score(user["id"], persist=False)
        assert out["persona_avg"] is None


def test_observational_note_no_advice_words(app, make_user):
    """The generated note must not contain any forbidden directive term."""
    user = _make_user_with_persona(app, make_user, "growth", "bs-note@test.com")
    with app.app_context():
        sub = {k: 75.0 for k in SUB_SCORE_KEYS}
        sub["holding_discipline"] = 95.0  # Make it the top one.
        note = _observational_note(sub, "growth", None)
        assert isinstance(note, str)
        # Either it's empty (filter dropped it) or it contains no
        # forbidden term.
        if note:
            assert contains_forbidden_term(note) is None, (
                f"forbidden term in observational note: {note!r}"
            )


# ─────────────────────────────────────────────────────────────────────
# Cron handler
# ─────────────────────────────────────────────────────────────────────

def test_cron_handler_runs_for_active_users(app, make_user):
    """Cron walks every user with a trade in the week and produces a score row."""
    user = make_user(email="bs-cron@test.com")
    week_end = _last_sunday(date.today())
    start_dt = datetime.combine(week_end - timedelta(days=6), datetime.min.time())
    with app.app_context():
        _trade(user["id"], "AAPL", "BUY", 1, 100, when=start_dt + timedelta(days=2))
        result = run_weekly_for_all_users(week_end)
        assert result["processed"] >= 1
        assert result["errors"] == 0
        row = (
            BehavioralScore.query
            .filter_by(user_id=user["id"], week_ending=week_end)
            .first()
        )
        assert row is not None
        assert 0.0 <= float(row.overall_score) <= 100.0


def test_cron_handler_idempotent(app, make_user):
    """A second run for the same week overwrites instead of duplicating."""
    user = make_user(email="bs-idem@test.com")
    week_end = _last_sunday(date.today())
    start_dt = datetime.combine(week_end - timedelta(days=6), datetime.min.time())
    with app.app_context():
        _trade(user["id"], "AAPL", "BUY", 1, 100, when=start_dt + timedelta(days=2))
        run_weekly_for_all_users(week_end)
        run_weekly_for_all_users(week_end)
        rows = (
            BehavioralScore.query
            .filter_by(user_id=user["id"], week_ending=week_end)
            .all()
        )
        assert len(rows) == 1


# ─────────────────────────────────────────────────────────────────────
# Route surface
# ─────────────────────────────────────────────────────────────────────

def test_score_endpoints_removed(client, auth_user):
    """AI 점수화 폐기 (DECISIONS, 2026-05-30): the score-consuming
    endpoints are gone. Regression gate so they can't be re-added.

    The scorer/model are dormant (still importable for export/persona
    benchmark/mirror compatibility) but no score surface is reachable.
    """
    for path in (
        "/api/behavior/score",
        "/api/behavior/score?weeks=4",
        "/api/behavior/breakdown",
        "/api/behavior/persona-comparison",
    ):
        resp = client.get(path)
        assert resp.status_code == 404, f"{path} should be removed, got {resp.status_code}"


def test_mirror_routes_csrf_required_on_no_writes_is_no_op(client, auth_user):
    """Surviving behavior mirror routes are GET-only; no CSRF header needed.

    Pinning this so a future write route (e.g. ``POST``) surfaces here first.
    """
    resp = client.get("/api/behavior/holding-mirror")
    assert resp.status_code == 200
