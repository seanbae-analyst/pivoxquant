"""Bug sweep 2026-09-29 — regressions for three reproduced defects.

1. PATCH /api/portfolio/positions/<id> accepted avg_cost="1e400" (float → inf)
   and stored it; GET /positions then 500'd forever (round(sum(inf)) overflow).
2. check_52w_highs_lows() only had the MARKET_DATA_DISPLAY_ENABLED gate in its
   cron wrapper, so POST /api/alerts/admin/check?mode=price still fanned
   vendor-quote 52-week alerts out to every holder while the flag was off.
3. The bell (GET /api/alerts, /unread-count) kept serving 52-week rows written
   before the flag went off, for the whole 14-day TTL.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.parametrize("bad", ["1e400", "-1e400", "nan", "inf"])
def test_patch_avg_cost_rejects_non_finite(client, auth_user, add_position, bad):
    pid = add_position(auth_user["id"], ticker="AAPL", avg_cost=150.0)

    resp = client.patch(f"/api/portfolio/positions/{pid}", json={"avg_cost": bad})
    assert resp.status_code == 400, resp.data

    # The list stays loadable — the bad value never reached the row.
    assert client.get("/api/portfolio/positions").status_code == 200


def test_52w_sweep_itself_refuses_when_display_off(app, market_display_off):
    from services.alert import check_52w_highs_lows

    with app.app_context(), patch("services.container.fetcher") as fetcher:
        m = check_52w_highs_lows()
    assert m["alerts_created"] == 0
    assert m["skipped"] == "display_disabled"
    fetcher.assert_not_called()


def _insert_alert(app, user_id, kind):
    from extensions import db
    from models import Alert

    with app.app_context():
        db.session.add(Alert(user_id=user_id, kind=kind, title=kind,
                             message=kind, is_read=False))
        db.session.commit()


def test_bell_hides_52w_rows_when_display_off(app, client, auth_user,
                                              market_display_off):
    _insert_alert(app, auth_user["id"], "price_52w_high")
    _insert_alert(app, auth_user["id"], "concentration")

    body = client.get("/api/alerts").get_json()
    kinds = [a.get("kind") for a in body["alerts"]]
    assert "price_52w_high" not in kinds
    assert "concentration" in kinds
    assert body["unread"] == 1
    assert client.get("/api/alerts/unread-count").get_json()["count"] == 1


def test_bell_shows_52w_rows_when_display_on(app, client, auth_user,
                                             market_display_on):
    _insert_alert(app, auth_user["id"], "price_52w_high")

    body = client.get("/api/alerts").get_json()
    assert [a.get("kind") for a in body["alerts"]] == ["price_52w_high"]
    assert client.get("/api/alerts/unread-count").get_json()["count"] == 1
