"""Regression: risk_score must not double-count leverage / concentration.

Before the 2026-05-26 fix, ``concentration_preference`` and
``leverage_appetite`` were folded BOTH into ``risk_raw`` (→ normalised
psychology component, weighted 40%) AND added again as explicit 10% composite
terms. That double-counted them: two profiles identical except for leverage
diverged by far more than the intended single 10% term, pushing users into
different ``investor_type`` buckets on the strength of one over-weighted answer.

The fix removes conc/leverage from ``risk_raw`` (which is now pure C-block risk
*psychology*) and keeps only the explicit composite terms, so each contributes
exactly once. These tests pin that property so it can't silently regress.
"""

from services.profile.questionnaire import calculate_profile_v2


def _base():
    return dict(
        holding_period="weeks",
        rebalance_preference="monthly",
        concentration_preference="moderate",
        leverage_appetite="never",
        scenario_portfolio_drop="hold",
        scenario_single_stock_crash="hold",
        scenario_market_crash_relative="acceptable",
        expected_annual_return="10to20",
        return_vs_stability="mostly_steady",
        min_acceptable_return="beat_spy",
        knowledge_concepts=["pe_ratio"],
        knowledge_self_rating=3,
        trading_frequency="weekly",
        years_investing="1to3",
    )


def _score(**overrides):
    a = _base()
    a.update(overrides)
    return calculate_profile_v2(a)["risk_score"]


def test_leverage_contributes_exactly_its_explicit_term():
    """never(lev=0) → full(lev=10) must move risk_score by exactly 10.

    leverage_score * 10 / 10 == leverage_score, so a 0→10 swing == 10 points.
    A larger delta would mean leverage is still amplified through risk_raw
    (the double-count bug).
    """
    delta = _score(leverage_appetite="full") - _score(leverage_appetite="never")
    assert delta == 10, f"leverage swing should be exactly 10 (explicit term), got {delta}"


def test_concentration_contributes_exactly_its_explicit_term():
    """broad(conc=1) → ultra_focused(conc=10) must move risk_score by exactly 9."""
    delta = _score(concentration_preference="ultra_focused") - _score(
        concentration_preference="broad"
    )
    assert delta == 9, f"concentration swing should be exactly 9 (explicit term), got {delta}"


def test_risk_score_stays_in_range():
    """Composite stays within 0..100 at both extremes after the divisor change."""
    lo = _score(
        leverage_appetite="never",
        concentration_preference="broad",
        scenario_portfolio_drop="sell_all",
        scenario_single_stock_crash="cut_loss",
        scenario_market_crash_relative="too_much",
    )
    hi = _score(
        leverage_appetite="full",
        concentration_preference="ultra_focused",
        scenario_portfolio_drop="buy_heavy",
        scenario_single_stock_crash="double_down",
        scenario_market_crash_relative="regret_upside",
    )
    assert 0 <= lo <= 100 and 0 <= hi <= 100
    assert hi > lo  # higher-risk answers → higher score
