"""Tests for /api/mirror-home — the composed 거울 home read.

Covers: auth gate, the declared-only "new" stage for a fresh user, the
legal invariant that no 8-code engine persona ever surfaces, and twin
report surfacing.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal


def test_requires_auth(raw_client):
    assert raw_client.get("/api/mirror-home").status_code == 401


def test_new_stage_for_fresh_user(client, auth_user):
    r = client.get("/api/mirror-home")
    assert r.status_code == 200
    data = r.get_json()

    assert data["ok"] is True
    # Fresh user has no closed trades → declared-only "new" stage.
    assert data["stage"] == "new"
    assert data["observed"]["label"] is None
    assert data["gap"] == []
    assert data["twin"] is None

    # Declared label is always one of the 3 disclosed buckets.
    assert data["declared"]["label"] in {"성장형", "균형형", "수익형"}

    # Radar always carries the 9-axis declared shape; observed blank in "new".
    assert len(data["radar"]["keys"]) == 9
    assert len(data["radar"]["labels"]) == 9
    assert len(data["radar"]["declared"]) == 9
    assert data["radar"]["observed"] is None


def test_no_eight_code_persona_leaks(client, auth_user):
    """Legal invariant: short-horizon / non-disclosed personas never surface."""
    blob = json.dumps(client.get("/api/mirror-home").get_json(), ensure_ascii=False).lower()
    for code in ("speculator", "daytrader", "value", "quant", "beginner"):
        assert code not in blob, f"8-code persona '{code}' leaked into mirror-home"


def test_twin_report_surfaces(client, auth_user, app):
    from extensions import db
    from models import AITwinWeeklyReport

    # Seed inside a context that CLOSES before the request — mirrors the
    # add_position fixture. Holding a db_session context open across
    # client.get() trips Flask's "popped wrong app context" assertion.
    with app.app_context():
        db.session.add(AITwinWeeklyReport(
            user_id=auth_user["id"],
            week_ending=date(2026, 6, 14),
            user_return_pct=Decimal("1.10"),
            twin_return_pct=Decimal("3.30"),
            diff_pct=Decimal("2.20"),
            user_trades_count=2,
            twin_trades_count=3,
        ))
        db.session.commit()

    twin = client.get("/api/mirror-home").get_json()["twin"]
    assert twin is not None
    assert twin["user_return_pct"] == 1.1
    assert twin["twin_return_pct"] == 3.3
    assert twin["diff_pct"] == 2.2
    assert twin["user_trades_count"] == 2
    assert twin["twin_trades_count"] == 3
