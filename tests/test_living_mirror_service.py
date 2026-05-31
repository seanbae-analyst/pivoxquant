"""tests/test_living_mirror_service.py — Living Mirror persona capstone.

Coverage contract (matches the build prompt):
  • 3-stage branch — new (intentional blanks) / observed (overlay) /
    trajectory (drift narration + sparkline).
  • 3-라벨만 — surfaced labels ∈ {성장형, 균형형, 수익형}; no
    speculator/daytrader/8-granular label, no score/grade/percentile/rank
    key or string anywhere in the context OR rendered HTML.
  • Determinism — same inputs (fixed ``now``) → identical context.
  • Empty-data safety — 0-trade user renders the ``new`` stage without
    raising, with non-empty declared radar geometry.

Runs entirely against the test SQLite DB via conftest fixtures. No
external API calls. WeasyPrint is optional — the render assertions stop
at HTML (Jinja) and skip the PDF byte path when WeasyPrint is absent.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from services.artifacts.living_mirror_service import (
    LivingMirrorService,
    MIN_TRADES_FOR_LIVING_MIRROR,
)
from services.profile.persona_analytics import SURFACE_LABELS


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

_FIXED_NOW = datetime(2026, 5, 31, 12, 0, 0)

# The 3 disclosed surface labels — the ONLY persona naming allowed to
# reach the user.
_ALLOWED_LABELS = set(SURFACE_LABELS.values())  # {성장형, 균형형, 수익형}

# Strings that must NEVER appear in a surfaced context value or HTML.
_FORBIDDEN_SUBSTRINGS = (
    "speculator", "daytrader", "투기", "단타",
    "Speculator", "Daytrader",
)

# Keys that must never exist anywhere in the context tree (점수화 폐기).
_FORBIDDEN_KEYS = ("score", "grade", "percentile", "rank", "ranking", "confidence")


def _make_profile(app, user_id: int, profile_type: str, risk: int = 7) -> None:
    from extensions import db
    from models import InvestmentProfile
    with app.app_context():
        p = InvestmentProfile.query.filter_by(user_id=user_id).first()
        if p is None:
            p = InvestmentProfile(user_id=user_id)
            db.session.add(p)
        p.profile_type = profile_type
        p.risk_tolerance = risk
        p.apply_preset()
        db.session.commit()


def _add_trades(app, user_id: int, n: int, *, span_days: int = 20) -> None:
    """Insert ``n`` recent trades spread across ``span_days``."""
    from extensions import db
    from models import TradeHistory
    with app.app_context():
        for i in range(n):
            action = "BUY" if i % 2 == 0 else "SELL"
            db.session.add(TradeHistory(
                user_id=user_id,
                ticker=("AAPL" if i % 3 else "MSFT"),
                action=action,
                shares=10.0,
                price_per_share=100.0,
                total_value=1000.0,
                pnl=0.0,
                traded_at=_FIXED_NOW - timedelta(days=(i % span_days) + 1),
            ))
        db.session.commit()


def _add_snapshots(app, user_id: int, specs: list[dict]) -> None:
    """Seed PersonaSnapshot rows for the trajectory stage."""
    from extensions import db
    from models import PersonaSnapshot
    base_features = {k: 0.5 for k in (
        "holding_period", "turnover", "sector_diversity", "ticker_diversity",
        "hold_variance", "loss_cut_discipline", "declared_risk",
        "conviction_stability", "feedback_engagement",
    )}
    with app.app_context():
        for s in specs:
            db.session.add(PersonaSnapshot(
                user_id=user_id,
                computed_at=s["at"],
                persona=s["persona"],
                confidence=int(s.get("confidence", 60)),
                features=json.dumps({**base_features, **s.get("features", {})}),
                present_mask=json.dumps({k: 1 for k in base_features}),
                ranking=json.dumps([{"persona": s["persona"], "similarity": 0.9}]),
                breakdown=json.dumps([]),
                declared_persona=s.get("declared", s["persona"]),
                trade_count=int(s.get("trade_count", 12)),
                window_days=90,
            ))
        db.session.commit()


def _walk_strings(node):
    """Yield every string + key in a nested dict/list context tree."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield ("key", k)
            yield from _walk_strings(v)
    elif isinstance(node, (list, tuple)):
        for v in node:
            yield from _walk_strings(v)
    elif isinstance(node, str):
        yield ("value", node)


def _assert_surface_clean(ctx: dict) -> None:
    """Assert no 8-granular label leaks into any surfaced string."""
    for kind, s in _walk_strings(ctx):
        if kind != "value":
            continue
        for bad in _FORBIDDEN_SUBSTRINGS:
            assert bad not in s, f"forbidden 8-label string leaked: {bad!r} in {s!r}"


# ═════════════════════════════════════════════════════════════════════
# Stage 1 — new (intentional blanks)
# ═════════════════════════════════════════════════════════════════════

class TestNewStage:
    def test_zero_trade_user_renders_new_stage(self, app, make_user):
        user = make_user(email="lm_new@test.com")
        _make_profile(app, user["id"], "growth")
        svc = LivingMirrorService()
        with app.app_context():
            ctx = svc.generate_for_user(user["id"], now=_FIXED_NOW)

        assert ctx["stage"] == "new"
        # declared radar must still be present + non-degenerate.
        assert ctx["radar"]["declared_points"]
        assert ctx["radar"]["observed_points"] is None
        assert ctx["has_observed"] is False
        # intentional-blank prompts present.
        assert ctx["blank_prompt"]
        assert ctx["trajectory_blank_prompt"]
        # surfaced label ∈ the 3 disclosed buckets.
        assert ctx["declared_label"] in _ALLOWED_LABELS
        _assert_surface_clean(ctx)

    def test_below_threshold_trades_still_new(self, app, make_user):
        user = make_user(email="lm_few@test.com")
        _make_profile(app, user["id"], "aggressive")  # → speculator engine code
        _add_trades(app, user["id"], MIN_TRADES_FOR_LIVING_MIRROR - 1)
        svc = LivingMirrorService()
        with app.app_context():
            ctx = svc.generate_for_user(user["id"], now=_FIXED_NOW)

        assert ctx["stage"] == "new"
        # 'aggressive' maps to the speculator engine code, which MUST
        # collapse to 성장형 on the surface — never named as speculator.
        assert ctx["declared_label"] == SURFACE_LABELS["growth"]
        _assert_surface_clean(ctx)


# ═════════════════════════════════════════════════════════════════════
# Stage 2 — observed (overlay)
# ═════════════════════════════════════════════════════════════════════

class TestObservedStage:
    def test_overlay_present_with_enough_trades(self, app, make_user):
        user = make_user(email="lm_obs@test.com")
        _make_profile(app, user["id"], "balanced")
        _add_trades(app, user["id"], MIN_TRADES_FOR_LIVING_MIRROR + 6)
        svc = LivingMirrorService()
        with app.app_context():
            ctx = svc.generate_for_user(user["id"], now=_FIXED_NOW)

        assert ctx["stage"] == "observed"
        assert ctx["has_observed"] is True
        assert ctx["radar"]["observed_points"]
        assert ctx["observed_label"] in _ALLOWED_LABELS
        # gap rows are descriptive direction only — no numeric judgement.
        assert isinstance(ctx["gap_dimensions"], list)
        assert len(ctx["gap_dimensions"]) <= 3
        for g in ctx["gap_dimensions"]:
            assert g["direction"] in (
                "관찰값이 더 큼", "관찰값이 더 작음", "선언과 일치",
            )
        # trajectory stays absent until snapshot history exists.
        assert ctx["trajectory"] is None
        _assert_surface_clean(ctx)


# ═════════════════════════════════════════════════════════════════════
# Stage 3 — trajectory (drift narration + sparkline)
# ═════════════════════════════════════════════════════════════════════

class TestTrajectoryStage:
    def test_trajectory_with_snapshot_history(self, app, make_user):
        user = make_user(email="lm_traj@test.com")
        _make_profile(app, user["id"], "growth")
        _add_trades(app, user["id"], MIN_TRADES_FOR_LIVING_MIRROR + 6)
        # Two snapshots across a surface-bucket move: speculator (성장형)
        # → income (수익형) so the surface narrative shows a real move.
        _add_snapshots(app, user["id"], [
            {"at": _FIXED_NOW - timedelta(days=120), "persona": "speculator"},
            {"at": _FIXED_NOW - timedelta(days=10), "persona": "income"},
        ])
        svc = LivingMirrorService()
        with app.app_context():
            ctx = svc.generate_for_user(user["id"], now=_FIXED_NOW)

        assert ctx["stage"] == "trajectory"
        traj = ctx["trajectory"]
        assert traj is not None
        assert traj["moved"] is True
        # both endpoints surfaced as 3-bucket labels, never 8-code.
        assert traj["first_label"] == SURFACE_LABELS["growth"]   # speculator→성장형
        assert traj["last_label"] == SURFACE_LABELS["income"]
        assert "성장형" in traj["narrative"] and "수익형" in traj["narrative"]
        _assert_surface_clean(ctx)

    def test_same_bucket_snapshots_read_as_stable(self, app, make_user):
        user = make_user(email="lm_stable@test.com")
        _make_profile(app, user["id"], "growth")
        _add_trades(app, user["id"], MIN_TRADES_FOR_LIVING_MIRROR + 6)
        # growth → value: distinct 8-codes that BOTH collapse to 성장형 →
        # surface must read "유지" not a fake move.
        _add_snapshots(app, user["id"], [
            {"at": _FIXED_NOW - timedelta(days=120), "persona": "growth"},
            {"at": _FIXED_NOW - timedelta(days=10), "persona": "value"},
        ])
        svc = LivingMirrorService()
        with app.app_context():
            ctx = svc.generate_for_user(user["id"], now=_FIXED_NOW)

        assert ctx["stage"] == "trajectory"
        assert ctx["trajectory"]["moved"] is False
        _assert_surface_clean(ctx)


# ═════════════════════════════════════════════════════════════════════
# Legal — no score / rank / 8-label keys anywhere
# ═════════════════════════════════════════════════════════════════════

class TestNoScoreNoRank:
    @pytest.mark.parametrize("profile_type,n_trades", [
        ("growth", 0),
        ("aggressive", MIN_TRADES_FOR_LIVING_MIRROR + 6),
        ("conservative", MIN_TRADES_FOR_LIVING_MIRROR + 6),
    ])
    def test_no_forbidden_keys_in_context(self, app, make_user,
                                          profile_type, n_trades):
        user = make_user(email=f"lm_keys_{profile_type}@test.com")
        _make_profile(app, user["id"], profile_type)
        if n_trades:
            _add_trades(app, user["id"], n_trades)
        svc = LivingMirrorService()
        with app.app_context():
            ctx = svc.generate_for_user(user["id"], now=_FIXED_NOW)

        for kind, name in _walk_strings(ctx):
            if kind == "key":
                assert name not in _FORBIDDEN_KEYS, (
                    f"forbidden score/rank key present in context: {name!r}"
                )
        _assert_surface_clean(ctx)

    def test_rendered_html_has_no_forbidden_strings(self, app, make_user):
        user = make_user(email="lm_html@test.com")
        _make_profile(app, user["id"], "aggressive")
        _add_trades(app, user["id"], MIN_TRADES_FOR_LIVING_MIRROR + 6)
        svc = LivingMirrorService()
        with app.app_context():
            ctx = svc.generate_for_user(user["id"], now=_FIXED_NOW)
            html = svc.render_html(ctx)

        assert html and "<html" in html.lower()
        for bad in _FORBIDDEN_SUBSTRINGS:
            assert bad not in html, f"forbidden 8-label string in HTML: {bad!r}"
        # disclaimer partial must render (legal footer present).
        assert "투자자문업" in html or "investment advisor" in html.lower()
        # AI-content label (regulatory ③) present via shared partial.
        assert "AI 생성" in html or "AI-generated" in html


# ═════════════════════════════════════════════════════════════════════
# Determinism + empty-data safety
# ═════════════════════════════════════════════════════════════════════

class TestDeterminismAndSafety:
    def test_deterministic_context(self, app, make_user):
        user = make_user(email="lm_det@test.com")
        _make_profile(app, user["id"], "balanced")
        _add_trades(app, user["id"], MIN_TRADES_FOR_LIVING_MIRROR + 6)
        svc = LivingMirrorService()
        with app.app_context():
            a = svc.generate_for_user(user["id"], now=_FIXED_NOW)
            b = svc.generate_for_user(user["id"], now=_FIXED_NOW)

        # Drop the wall-clock field, compare the rest verbatim.
        a.pop("generated_at", None)
        b.pop("generated_at", None)
        assert a == b

    def test_missing_profile_does_not_raise(self, app, make_user):
        user = make_user(email="lm_noprofile@test.com")
        # No InvestmentProfile row at all.
        svc = LivingMirrorService()
        with app.app_context():
            ctx = svc.generate_for_user(user["id"], now=_FIXED_NOW)
        # Falls back to the neutral 균형형 bucket, new stage, no crash.
        assert ctx["stage"] == "new"
        assert ctx["declared_label"] in _ALLOWED_LABELS

    def test_unknown_user_raises_valueerror(self, app):
        svc = LivingMirrorService()
        with app.app_context():
            with pytest.raises(ValueError):
                svc.generate_for_user(999_999_999, now=_FIXED_NOW)
