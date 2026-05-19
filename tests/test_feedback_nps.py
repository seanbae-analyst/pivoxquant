"""NPS 1-click endpoint tests (Wave G C-AC2).

Covers ``POST /api/feedback/nps``:

  * 401 when unauthenticated.
  * 200 + row persisted for valid integer scores in [1, 10].
  * 400 for out-of-range / non-integer / boolean / missing scores.
  * user_id auto-filled from current_user; clients cannot spoof it.
  * weekly_memo_id is optional and stored as-typed when present.
"""
from __future__ import annotations

from sqlalchemy import inspect


def test_nps_feedback_table_exists(app):
    """Migration 039 must have created the nps_feedback table."""
    with app.app_context():
        from extensions import db
        tables = set(inspect(db.engine).get_table_names())
    assert "nps_feedback" in tables


def test_submit_nps_unauthenticated_returns_401(client):
    resp = client.post("/api/feedback/nps", json={"score": 9})
    assert resp.status_code == 401


def test_submit_nps_valid_score_persists(app, client, auth_user):
    resp = client.post(
        "/api/feedback/nps",
        json={"score": 9, "weekly_memo_id": "memo-abc-123"},
    )
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["ok"] is True
    assert body["feedback"]["score"] == 9
    assert body["feedback"]["weekly_memo_id"] == "memo-abc-123"
    assert body["feedback"]["created_at"] is not None

    # DB-level verification — user_id must come from current_user, not
    # the request body (clients cannot spoof identity).
    with app.app_context():
        from extensions import db
        from models import NpsFeedback
        rows = db.session.query(NpsFeedback).all()
        assert len(rows) == 1
        assert rows[0].user_id == auth_user["id"]
        assert rows[0].score == 9
        assert rows[0].weekly_memo_id == "memo-abc-123"


def test_submit_nps_without_memo_id(app, client, auth_user):
    resp = client.post("/api/feedback/nps", json={"score": 5})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["feedback"]["weekly_memo_id"] is None


def test_submit_nps_boundary_scores_accepted(client, auth_user):
    for score in (1, 10):
        resp = client.post("/api/feedback/nps", json={"score": score})
        assert resp.status_code == 200, f"score={score} rejected"
        assert resp.get_json()["feedback"]["score"] == score


def test_submit_nps_rejects_score_zero(client, auth_user):
    resp = client.post("/api/feedback/nps", json={"score": 0})
    assert resp.status_code == 400


def test_submit_nps_rejects_score_eleven(client, auth_user):
    resp = client.post("/api/feedback/nps", json={"score": 11})
    assert resp.status_code == 400


def test_submit_nps_rejects_negative_score(client, auth_user):
    resp = client.post("/api/feedback/nps", json={"score": -3})
    assert resp.status_code == 400


def test_submit_nps_rejects_non_integer_score(client, auth_user):
    # Float must be rejected — silent coercion to int would let a buggy
    # client poison aggregates with values like 9.7 → 9.
    resp = client.post("/api/feedback/nps", json={"score": 7.5})
    assert resp.status_code == 400


def test_submit_nps_rejects_string_score(client, auth_user):
    resp = client.post("/api/feedback/nps", json={"score": "9"})
    assert resp.status_code == 400


def test_submit_nps_rejects_boolean_score(client, auth_user):
    # bool is a subclass of int in Python — must be rejected explicitly.
    resp = client.post("/api/feedback/nps", json={"score": True})
    assert resp.status_code == 400


def test_submit_nps_rejects_missing_score(client, auth_user):
    resp = client.post("/api/feedback/nps", json={})
    assert resp.status_code == 400


def test_submit_nps_rejects_oversized_memo_id(client, auth_user):
    long_memo = "a" * 65
    resp = client.post(
        "/api/feedback/nps",
        json={"score": 8, "weekly_memo_id": long_memo},
    )
    assert resp.status_code == 400


def test_submit_nps_empty_memo_id_treated_as_null(app, client, auth_user):
    resp = client.post(
        "/api/feedback/nps",
        json={"score": 8, "weekly_memo_id": "   "},
    )
    assert resp.status_code == 200
    assert resp.get_json()["feedback"]["weekly_memo_id"] is None


def test_submit_nps_allows_duplicate_submissions(app, client, auth_user):
    """Frontend de-dupes; server lets users change their mind."""
    client.post("/api/feedback/nps", json={"score": 6, "weekly_memo_id": "m1"})
    resp = client.post("/api/feedback/nps", json={"score": 9, "weekly_memo_id": "m1"})
    assert resp.status_code == 200

    with app.app_context():
        from extensions import db
        from models import NpsFeedback
        rows = (
            db.session.query(NpsFeedback)
            .filter_by(user_id=auth_user["id"], weekly_memo_id="m1")
            .all()
        )
        assert len(rows) == 2
