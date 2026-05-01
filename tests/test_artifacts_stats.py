"""Regression tests for GET /api/artifacts/stats.

The /reports v2 hero counter (countBragCards) consumes this endpoint.
Both `monthly_brag` (auto-generated digest) and `brag_card` (one-off
card) must be aggregated, otherwise /reports renders "0 brag cards"
while /home shows the same row in `total`.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from extensions import db
from models import Artifact


_counter = {"n": 0}


def _make_artifact(user_id: int, type_: str, sent_offset_days: int = 0) -> Artifact:
    """Persist a minimal Artifact row for stat-endpoint testing.

    `sent_at` is set to a stable past timestamp so YTD math stays
    deterministic across the calendar boundary. Titles are uniquified
    via a module-level counter because (user_id, type, title) carries a
    UNIQUE constraint.
    """
    sent = datetime(datetime.now(timezone.utc).year, 6, 15)
    _counter["n"] += 1
    a = Artifact(
        user_id=user_id,
        type=type_,
        title=f"{type_} fixture #{_counter['n']}",
        sent_at=sent,
    )
    db.session.add(a)
    db.session.commit()
    return a


@pytest.mark.parametrize("brag_type", ["monthly_brag", "brag_card"])
def test_brag_card_count_includes_both_types(app, client, auth_user, brag_type):
    """countBragCards must include both monthly_brag and brag_card rows.

    Regression for HANDOVER v19 P1 #5 — "/reports counter (0 brag cards)
    vs /home counter (1 brag card …) mismatch". The frontend computes the
    same number both ways via deriveArtifactStats, so the bug was the
    server contract, not the renderer.
    """
    with app.app_context():
        _make_artifact(auth_user["id"], brag_type)

    resp = client.get("/api/artifacts/stats")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["countBragCards"] == 1, (
        f"countBragCards should include {brag_type} rows but got {body}"
    )


def test_brag_card_count_sums_monthly_brag_and_brag_card(app, client, auth_user):
    """Mixed rows: 2 monthly_brag + 1 brag_card → countBragCards = 3."""
    with app.app_context():
        _make_artifact(auth_user["id"], "monthly_brag")
        _make_artifact(auth_user["id"], "monthly_brag")
        _make_artifact(auth_user["id"], "brag_card")

    resp = client.get("/api/artifacts/stats")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["countBragCards"] == 3
    # And the per-type breakdown is preserved so the frontend can split
    # them back out if it ever needs to.
    assert body["byType"]["monthly_brag"] == 2
    assert body["byType"]["brag_card"] == 1


def test_brag_card_count_zero_when_no_artifacts(client, auth_user):
    """No artifacts at all → all counters 0, no division-by-zero etc."""
    resp = client.get("/api/artifacts/stats")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total"] == 0
    assert body["countBragCards"] == 0
    assert body["countMemos"] == 0
    assert body["countBriefs"] == 0
