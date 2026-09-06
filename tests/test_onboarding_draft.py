"""tests/test_onboarding_draft.py — onboarding partial-save endpoint.

Wave 12 UX P0 — onboarding wizard server-side draft slot so progress
survives device handoff + ITP / private browsing localStorage eviction.

Contract pinned here:
- ``GET  /api/profile/onboarding/draft`` — auth required; returns
  ``{"draft": <object> | null}``. Missing / corrupt blob → null
  (wizard restarts cleanly rather than crash).
- ``PUT  /api/profile/onboarding/draft`` — auth required + rate limited;
  body ``{"answers": {...}}``. Empty dict resets. Payload > 32KB → 413.
- ``POST /api/profile/onboarding`` — on successful submit, the draft
  column is cleared so a future device session doesn't resurrect a
  stale wizard for an already-onboarded user.
"""
from __future__ import annotations


# ── GET draft ───────────────────────────────────────────────────────────────


def test_get_draft_unauthenticated_returns_401(client):
    r = client.get("/api/profile/onboarding/draft")
    assert r.status_code == 401


def test_get_draft_returns_null_when_none_saved(client, auth_user):
    r = client.get("/api/profile/onboarding/draft")
    assert r.status_code == 200
    assert r.get_json() == {"draft": None}


def test_get_draft_returns_saved_object(client, auth_user):
    payload = {"answers": {"risk_tolerance": 6, "preferred_markets": "both"}}
    r1 = client.put("/api/profile/onboarding/draft", json=payload)
    assert r1.status_code == 200

    r2 = client.get("/api/profile/onboarding/draft")
    assert r2.status_code == 200
    assert r2.get_json()["draft"] == payload["answers"]


def test_get_draft_returns_null_when_blob_is_corrupt(app, client, auth_user):
    """Manual DB edit / partial write should not 500 the GET — the
    wizard restarts from scratch rather than crashing on parse."""
    from extensions import db
    from models import User

    with app.app_context():
        u = db.session.get(User, auth_user["id"])
        u.onboarding_draft_json = "{not valid json"
        db.session.commit()

    r = client.get("/api/profile/onboarding/draft")
    assert r.status_code == 200
    assert r.get_json() == {"draft": None}


# ── PUT draft ───────────────────────────────────────────────────────────────


def test_put_draft_unauthenticated_returns_401(client):
    r = client.put(
        "/api/profile/onboarding/draft",
        json={"answers": {"risk_tolerance": 5}},
    )
    assert r.status_code == 401


def test_put_draft_rejects_missing_answers_field(client, auth_user):
    r = client.put("/api/profile/onboarding/draft", json={})
    assert r.status_code == 400
    assert "answers" in r.get_json()["error"].lower()


def test_put_draft_rejects_non_object_answers(client, auth_user):
    r = client.put(
        "/api/profile/onboarding/draft",
        json={"answers": "not an object"},
    )
    assert r.status_code == 400


def test_put_draft_accepts_empty_object_as_reset(client, auth_user):
    r1 = client.put(
        "/api/profile/onboarding/draft",
        json={"answers": {"risk_tolerance": 6}},
    )
    assert r1.status_code == 200

    r2 = client.put("/api/profile/onboarding/draft", json={"answers": {}})
    assert r2.status_code == 200

    r3 = client.get("/api/profile/onboarding/draft")
    assert r3.get_json()["draft"] == {}


def test_put_draft_payload_size_limit_413(client, auth_user):
    """Anything over the 32KB ceiling must 413 — guards against
    pathological clients trying to use the column as scratch storage."""
    huge = {"k": "x" * (33 * 1024)}
    r = client.put("/api/profile/onboarding/draft", json={"answers": huge})
    assert r.status_code == 413


def test_put_draft_round_trips_korean_text(client, auth_user):
    """ensure_ascii=False on the server keeps Korean answer text legible
    in the DB and on the round-trip."""
    answers = {"investment_goal": "장기 성장", "preferred_sectors": ["반도체", "헬스케어"]}
    r = client.put("/api/profile/onboarding/draft", json={"answers": answers})
    assert r.status_code == 200

    r2 = client.get("/api/profile/onboarding/draft")
    assert r2.get_json()["draft"] == answers


# ── Submit clears draft ─────────────────────────────────────────────────────


def test_submit_onboarding_clears_draft(app, client, auth_user):
    """After POST /api/profile/onboarding the draft column must be NULL
    so a future session doesn't resurrect a stale wizard for an
    already-onboarded user."""
    from extensions import db
    from models import User

    # Seed a draft.
    r1 = client.put(
        "/api/profile/onboarding/draft",
        json={"answers": {"risk_tolerance": 5}},
    )
    assert r1.status_code == 200

    # Submit full onboarding (questionnaire V3, 2026-09-06). A non-empty
    # submission must carry the legal_confirmations block; the real frontend
    # always sends it on a non-empty submit.
    r2 = client.post(
        "/api/profile/onboarding",
        json={"answers": {
            "declared_holding": "months",
            "declared_frequency": "few",
            "declared_positions": "focused",
            "declared_drawdown_response": "hold",
            "record_habit": "sometimes",
            "legal_confirmations": [
                "age_18", "experience_acknowledged", "risk_acknowledged",
                "past_performance", "ai_advisory",
            ],
        }},
    )
    assert r2.status_code == 200, r2.get_data(as_text=True)

    # DB column should be NULL again.
    with app.app_context():
        u = db.session.get(User, auth_user["id"])
        assert u.onboarding_draft_json is None
