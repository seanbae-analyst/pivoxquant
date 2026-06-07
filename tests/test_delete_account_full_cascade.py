"""Regression — DELETE /api/auth/delete-account must purge EVERY user-FK table.

delete_account ran for the first time against prod only when self-service
deletion shipped (2026-06-07); the UI had been a mailto link. The first run
500'd because four user-referencing tables (checkout_expirations,
portfolio_nav_snapshots, user_agent_audit, companion_waitlist) were missing
from the explicit purge list, so a drifted prod FK without ON DELETE CASCADE
blocked the user-row delete.

This test exercises the ENDPOINT (the ORM db.session.delete(user) path) with
those four tables populated — the existing cascade test only issued a raw
DELETE FROM users and never covered them. It locks: (1) the endpoint returns
200, (2) the four tables are purged, (3) a non-FK analytics row (funnel_events,
deliberately a plain int snapshot) SURVIVES the deletion.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone, date


def test_delete_account_purges_all_user_fk_tables(app, client, make_user):
    from extensions import db
    from models import (
        Position, CheckoutExpiration, PortfolioNavSnapshot, UserAgentAudit,
        CompanionWaitlist, FunnelEvent, User,
    )
    from models.inquiry import Inquiry
    from sqlalchemy import text

    user = make_user(email="full_cascade@test.com")
    uid = user["id"]

    with app.app_context():
        pos = Position(user_id=uid, ticker="TEST", shares=10.0, avg_cost=100.0)
        db.session.add(pos)
        db.session.add_all([
            Inquiry(user_id=uid, category="other", subject="제목", body="본문 " * 20),
            CheckoutExpiration(
                user_id=uid, session_id=f"cs_{secrets.token_hex(6)}",
                expired_at=datetime.now(timezone.utc),
                scheduled_send_at=datetime.now(timezone.utc),
            ),
            PortfolioNavSnapshot(
                user_id=uid, as_of_date=date(2026, 6, 1),
                nav_total_usd=1000, nav_us_usd=1000, nav_kr_krw=0,
            ),
            UserAgentAudit(
                request_id=secrets.token_hex(5), user_id=uid, persona_code="balanced",
                user_message_hash="h" * 20, user_message_len=10, gate_verdict="pass",
            ),
            CompanionWaitlist(email_hash=secrets.token_hex(16), user_id=uid),
            # Non-FK analytics snapshot — MUST survive the deletion.
            FunnelEvent(user_id=uid, event="signup"),
        ])
        db.session.commit()

    login = client.post("/api/auth/login",
                        json={"email": user["email"], "password": user["password"]})
    assert login.status_code == 200, login.data

    resp = client.delete("/api/auth/delete-account")
    assert resp.status_code == 200, f"delete failed: {resp.get_json()}"

    with app.app_context():
        # User + the four formerly-missing tables are gone.
        assert db.session.get(User, uid) is None
        for tbl in ("checkout_expirations", "portfolio_nav_snapshots",
                    "user_agent_audit", "positions", "inquiries"):
            n = db.session.execute(
                text(f"SELECT COUNT(*) FROM {tbl} WHERE user_id = :u"), {"u": uid}
            ).scalar()
            assert n == 0, f"{tbl} not purged ({n} rows remain)"

        # companion_waitlist: row survives, user_id detached (SET NULL).
        cw = db.session.execute(
            text("SELECT COUNT(*) FROM companion_waitlist WHERE user_id = :u"),
            {"u": uid},
        ).scalar()
        assert cw == 0, "companion_waitlist user_id not detached"

        # funnel_events: deliberately NOT a FK — the analytics snapshot survives.
        fe = db.session.execute(
            text("SELECT COUNT(*) FROM funnel_events WHERE user_id = :u"),
            {"u": uid},
        ).scalar()
        assert fe == 1, "funnel_events analytics snapshot should survive deletion"
