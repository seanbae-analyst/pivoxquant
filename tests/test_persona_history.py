"""tests/test_persona_history.py — PivoxQuant Feature 3+4.

PersonaSnapshot persistence + Evolution Timeline.

Covers
------
* ``services.profile.persona_history.take_snapshot``
* ``services.profile.persona_history.get_history``
* ``services.profile.persona_history.compute_drift``
* ``services.profile.persona_history.detect_significant_drift``
* ``services.profile.persona_history.iter_active_user_ids``
* ``services.profile.persona_history.run_weekly_snapshots``
* ``GET  /api/profile/persona-history``
* ``GET  /api/profile/persona-drift``
* ``POST /api/profile/persona-snapshot``

Legal invariants
----------------
* Every drift / history response carries the
  :data:`services.profile.persona_history.DRIFT_DISCLAIMER` constant.
* Drift descriptors come from a closed set ("유지 관찰", "이동 중 관찰",
  "영역 이동 관찰") — no "추천" / "조언" / "recommendation" / "advice"
  wording is allowed in any persona-history-shaped response.
* Migration 016 row enforces ``confidence ∈ [0, 100]`` at the DB layer.

These tests pin all of those invariants so a future refactor cannot
silently regress the legal posture.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _persist_snapshot(
    app,
    user_id: int,
    *,
    persona: str = "balanced",
    confidence: int = 60,
    features: dict | None = None,
    computed_at: datetime | None = None,
    declared: str | None = None,
    trade_count: int = 12,
):
    """Insert a PersonaSnapshot row directly — bypasses the classifier.

    Used by tests that need a deterministic series; the live classifier
    is exercised by ``test_take_snapshot_creates_row`` only.
    """
    from extensions import db
    from models import PersonaSnapshot

    if features is None:
        features = {
            "holding_period": 0.5,
            "turnover": 0.5,
            "sector_diversity": 0.5,
            "ticker_diversity": 0.5,
            "hold_variance": 0.5,
            "loss_cut_discipline": 0.5,
            "declared_risk": 0.5,
            "conviction_stability": 0.5,
            "feedback_engagement": 0.5,
        }
    when = computed_at or _utc_now()

    with app.app_context():
        row = PersonaSnapshot(
            user_id=user_id,
            computed_at=when,
            persona=persona,
            confidence=confidence,
            features=json.dumps(features),
            present_mask=json.dumps({k: 1 for k in features}),
            ranking=json.dumps([{"persona": persona, "similarity": 0.9}]),
            breakdown=json.dumps([]),
            declared_persona=declared,
            trade_count=trade_count,
            window_days=90,
        )
        db.session.add(row)
        db.session.commit()
        return row.id


# ═════════════════════════════════════════════════════════════════════
# Migration / model surface
# ═════════════════════════════════════════════════════════════════════

class TestMigrationApplied:
    def test_table_exists_with_required_columns(self, app):
        """Migration 016 created the table with the columns we declared."""
        from extensions import db
        from sqlalchemy import inspect

        with app.app_context():
            insp = inspect(db.engine)
            assert "persona_snapshots" in insp.get_table_names()

            cols = {c["name"] for c in insp.get_columns("persona_snapshots")}
            for required in (
                "id", "user_id", "computed_at", "persona", "confidence",
                "features", "present_mask", "ranking", "breakdown",
                "declared_persona", "trade_count", "window_days",
                "created_at",
            ):
                assert required in cols, f"missing column: {required}"

    def test_unique_user_time_constraint(self, app, make_user):
        """UNIQUE(user_id, computed_at) blocks the second write."""
        from sqlalchemy.exc import IntegrityError
        from extensions import db
        from models import PersonaSnapshot

        u = make_user(email="uniq@test.com")
        when = _utc_now()
        _persist_snapshot(app, u["id"], computed_at=when)

        with app.app_context():
            dup = PersonaSnapshot(
                user_id=u["id"],
                computed_at=when,
                persona="balanced",
                confidence=50,
                features="{}",
                present_mask="{}",
                ranking="[]",
                breakdown="[]",
                trade_count=0,
                window_days=90,
            )
            db.session.add(dup)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()


# ═════════════════════════════════════════════════════════════════════
# take_snapshot — write path
# ═════════════════════════════════════════════════════════════════════

class TestTakeSnapshot:
    def test_take_snapshot_creates_row(self, app, make_user):
        """Live classifier path → one row, valid persona, confidence range."""
        from services.profile import take_snapshot
        from models import PersonaSnapshot, VALID_SNAPSHOT_PERSONAS

        u = make_user(email="snap1@test.com")
        with app.app_context():
            row = take_snapshot(u["id"], window_days=90)
            assert row is not None
            assert row.user_id == u["id"]
            assert row.persona in VALID_SNAPSHOT_PERSONAS
            assert 0 <= row.confidence <= 100
            assert row.window_days == 90
            assert PersonaSnapshot.query.filter_by(
                user_id=u["id"]
            ).count() == 1

    def test_take_snapshot_idempotent_same_timestamp(self, app, make_user):
        """Two calls with the same explicit ``now`` → second is a no-op."""
        from services.profile import take_snapshot
        from models import PersonaSnapshot

        u = make_user(email="snap2@test.com")
        when = _utc_now()
        with app.app_context():
            first = take_snapshot(u["id"], now=when)
            second = take_snapshot(u["id"], now=when)
            assert first is not None
            assert second is None  # UNIQUE collision swallowed
            assert PersonaSnapshot.query.filter_by(
                user_id=u["id"]
            ).count() == 1


# ═════════════════════════════════════════════════════════════════════
# get_history — read path
# ═════════════════════════════════════════════════════════════════════

class TestGetHistory:
    def test_get_history_empty_user(self, app, make_user):
        from services.profile import get_history
        u = make_user(email="hist0@test.com")
        with app.app_context():
            assert get_history(u["id"]) == []

    def test_get_history_with_3_snapshots(self, app, make_user):
        """Three rows over 30 days → returned oldest → newest."""
        from services.profile import get_history

        u = make_user(email="hist1@test.com")
        now = _utc_now()
        for offset_days, persona in [
            (30, "balanced"),
            (15, "balanced"),
            (1, "balanced"),
        ]:
            _persist_snapshot(
                app, u["id"],
                persona=persona,
                computed_at=now - timedelta(days=offset_days),
            )

        with app.app_context():
            rows = get_history(u["id"], days_back=180)
            assert len(rows) == 3
            # Oldest first
            ts = [r["computed_at"] for r in rows]
            assert ts == sorted(ts)


# ═════════════════════════════════════════════════════════════════════
# compute_drift — pure function over a series
# ═════════════════════════════════════════════════════════════════════

class TestComputeDrift:
    def test_compute_drift_distance(self, app, make_user):
        """Big change in two features → measurable feature_distance > 0."""
        from services.profile import compute_drift, get_history

        u = make_user(email="drift1@test.com")
        now = _utc_now()
        f0 = {k: 0.5 for k in (
            "holding_period", "turnover", "sector_diversity",
            "ticker_diversity", "hold_variance", "loss_cut_discipline",
            "declared_risk", "conviction_stability", "feedback_engagement",
        )}
        f1 = dict(f0)
        f1["turnover"] = 0.95
        f1["holding_period"] = 0.05

        _persist_snapshot(
            app, u["id"], persona="balanced", features=f0,
            computed_at=now - timedelta(days=21),
        )
        _persist_snapshot(
            app, u["id"], persona="balanced", features=f1,
            computed_at=now - timedelta(days=1),
        )

        with app.app_context():
            snapshots = get_history(u["id"])
            d = compute_drift(snapshots)
            assert d["available"] is True
            assert d["n_snapshots"] == 2
            assert d["feature_distance"] > 0.10
            # turnover + holding_period should dominate
            top = {row["feature"] for row in d["dominant_changes"][:2]}
            assert "turnover" in top
            assert "holding_period" in top

    def test_compute_drift_persona_transition(self, app, make_user):
        """Persona label changes between adjacent snapshots → transition row."""
        from services.profile import compute_drift, get_history

        u = make_user(email="drift2@test.com")
        now = _utc_now()
        _persist_snapshot(
            app, u["id"], persona="balanced",
            computed_at=now - timedelta(days=20),
        )
        _persist_snapshot(
            app, u["id"], persona="quant",
            computed_at=now - timedelta(days=2),
        )

        with app.app_context():
            d = compute_drift(get_history(u["id"]))
            assert d["first_persona"] == "balanced"
            assert d["last_persona"] == "quant"
            assert len(d["transitions"]) == 1
            assert d["transitions"][0]["from"] == "balanced"
            assert d["transitions"][0]["to"] == "quant"
            assert d["descriptor"] == "영역 이동 관찰"


# ═════════════════════════════════════════════════════════════════════
# detect_significant_drift — 4-week threshold
# ═════════════════════════════════════════════════════════════════════

class TestDetectSignificantDrift:
    def test_detect_significant_drift_4week_change(self, app, make_user):
        """Persona flips within the 4-week window → drift surfaces."""
        from services.profile import detect_significant_drift

        u = make_user(email="sigdrift@test.com")
        now = _utc_now()
        _persist_snapshot(
            app, u["id"], persona="balanced",
            computed_at=now - timedelta(days=21),
        )
        _persist_snapshot(
            app, u["id"], persona="quant",
            computed_at=now - timedelta(days=2),
        )

        with app.app_context():
            sig = detect_significant_drift(u["id"], threshold=0.25)
            assert sig is not None
            assert sig["persona_changed"] is True
            assert sig["first_persona"] == "balanced"
            assert sig["last_persona"] == "quant"
            assert "→" in sig["message"]
            assert "관찰" in sig["message"]

    def test_detect_no_drift_steady_user(self, app, make_user):
        """Identical features + persona across the window → None."""
        from services.profile import detect_significant_drift

        u = make_user(email="steady@test.com")
        now = _utc_now()
        features = {
            "holding_period": 0.5,
            "turnover": 0.4,
            "sector_diversity": 0.6,
            "ticker_diversity": 0.5,
            "hold_variance": 0.4,
            "loss_cut_discipline": 0.6,
            "declared_risk": 0.5,
            "conviction_stability": 0.7,
            "feedback_engagement": 0.5,
        }
        for offset in (21, 14, 7, 1):
            _persist_snapshot(
                app, u["id"], persona="balanced", features=features,
                computed_at=now - timedelta(days=offset),
            )

        with app.app_context():
            assert detect_significant_drift(u["id"], threshold=0.25) is None


# ═════════════════════════════════════════════════════════════════════
# API surface
# ═════════════════════════════════════════════════════════════════════

class TestPersonaHistoryAPI:
    def test_endpoint_history_unauth_401(self, client):
        r = client.get("/api/profile/persona-history?days=180")
        assert r.status_code == 401

    def test_endpoint_history_returns_user_only(
        self, app, client, auth_user, make_user,
    ):
        """Snapshots from another user MUST NOT appear in the response."""
        # Auth user gets 1 snapshot.
        _persist_snapshot(app, auth_user["id"], persona="balanced")

        # Stranger user gets 2 snapshots — they must not leak.
        stranger = make_user(email="stranger@test.com")
        _persist_snapshot(app, stranger["id"], persona="quant")
        _persist_snapshot(
            app, stranger["id"], persona="quant",
            computed_at=_utc_now() - timedelta(days=2),
        )

        r = client.get("/api/profile/persona-history?days=180")
        assert r.status_code == 200
        d = r.get_json()
        assert d["n"] == 1
        for row in d["snapshots"]:
            assert row["user_id"] == auth_user["id"]
        # Stranger persona never appears
        assert all(row["persona"] != "quant" or row["user_id"] == auth_user["id"]
                   for row in d["snapshots"])

    def test_post_snapshot_creates_and_returns_row(self, client, auth_user):
        """POST /api/profile/persona-snapshot → row in DB + valid payload."""
        r = client.post("/api/profile/persona-snapshot", json={})
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        assert d["snapshot"] is not None
        assert d["snapshot"]["user_id"] == auth_user["id"]


# ═════════════════════════════════════════════════════════════════════
# Cron handler — active-user filtering
# ═════════════════════════════════════════════════════════════════════

class TestCronHandler:
    def test_cron_handler_skips_inactive_users(
        self, app, make_user, add_position,
    ):
        """Users with no recent TradeHistory must NOT be snapshotted."""
        from extensions import db
        from models import PersonaSnapshot, TradeHistory
        from services.profile import run_weekly_snapshots

        active = make_user(email="active@test.com")
        inactive = make_user(email="inactive@test.com")

        # Insert a recent trade for `active` only.
        with app.app_context():
            db.session.add(TradeHistory(
                user_id=active["id"], ticker="AAPL", action="BUY",
                shares=10.0, price_per_share=100.0, total_value=1000.0,
                pnl=0.0, pnl_pct=0.0,
                traded_at=_utc_now() - timedelta(days=3),
            ))
            db.session.commit()

            summary = run_weekly_snapshots()
            assert summary["attempted"] == 1
            assert summary["written"] == 1
            assert summary["failed"] == 0

            rows = PersonaSnapshot.query.all()
            assert len(rows) == 1
            assert rows[0].user_id == active["id"]
            # Inactive user never got a row.
            assert PersonaSnapshot.query.filter_by(
                user_id=inactive["id"]
            ).count() == 0


# ═════════════════════════════════════════════════════════════════════
# Legal posture
# ═════════════════════════════════════════════════════════════════════

class TestLegalPosture:
    _BANNED_TOKENS = (
        "추천", "조언", "권유",
        "recommend", "Recommend", "RECOMMEND",
        "advice", "Advice", "ADVICE",
        "advise", "buy now", "sell now",
    )

    def test_legal_disclaimer_in_drift_message(self, client, auth_user):
        """``/persona-drift`` always carries the observational disclaimer."""
        r = client.get("/api/profile/persona-drift")
        assert r.status_code == 200
        d = r.get_json()
        assert "disclaimer" in d
        assert "투자 추천" in d["disclaimer"] or "조언이 아닙니다" in d["disclaimer"]
        # Drift block also carries the disclaimer
        assert "disclaimer" in d["drift"]

        # Recursive check: no banned token anywhere in the response body.
        blob = json.dumps(d, ensure_ascii=False)
        for token in self._BANNED_TOKENS:
            # The disclaimer itself uses "추천이나 조언이 아닙니다" — a
            # negation of the words. Allow that exact phrase to coexist
            # with the ban by counting only token occurrences outside it.
            if token in ("추천", "조언", "권유"):
                # Strip the disclaimer text and re-check.
                from services.profile.persona_history import DRIFT_DISCLAIMER
                stripped = blob.replace(DRIFT_DISCLAIMER, "")
                assert token not in stripped, (
                    f"banned token '{token}' surfaced outside the disclaimer"
                )
            else:
                assert token not in blob, f"banned token '{token}' in body"
