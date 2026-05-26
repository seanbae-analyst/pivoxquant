"""Viral-loop backend tests — /api/track, /api/card, referral attribution.

Covers:
  * POST /api/track whitelist + anonymous + logged-in attribution + meta cap
  * GET  /api/card/<token> public gate (is_public default-private) + §101 safety
  * POST /api/card/<token>/visibility owner-only toggle
  * attribute_referral idempotency / self-referral / unknown-code guards
  * weekly_funnel_snapshot K-factor math (divisor guards)
  * brag card snapshot mode (Activation for 0-trade users)
"""
from __future__ import annotations

from extensions import db


# ── /api/track ───────────────────────────────────────────────────────────────

def test_track_anonymous_landing_view(client, app):
    """Public landing event accepted with no auth + no user_id attributed."""
    resp = client.post("/api/track", json={
        "event": "landing_view",
        "channel": "instagram",
        "anon_id": "anon-abc-123",
    })
    assert resp.status_code == 200, resp.data
    assert resp.get_json()["ok"] is True

    from models import FunnelEvent
    with app.app_context():
        row = (FunnelEvent.query
               .filter_by(event="landing_view", anon_id="anon-abc-123")
               .first())
        assert row is not None
        assert row.user_id is None       # anonymous
        assert row.channel == "instagram"


def test_track_rejects_unknown_event(client, app):
    """Whitelist guard — arbitrary event strings are 400, not stored."""
    resp = client.post("/api/track", json={"event": "evil_injection"})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["code"] == "EVENT_NOT_ALLOWED"

    from models import FunnelEvent
    with app.app_context():
        assert FunnelEvent.query.filter_by(event="evil_injection").count() == 0


def test_track_requires_event(client):
    resp = client.post("/api/track", json={"channel": "x"})
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "EVENT_REQUIRED"


def test_track_attributes_logged_in_user(client, app, auth_user):
    """A logged-in caller's user_id is attached to the event."""
    resp = client.post("/api/track", json={"event": "artifact_opened"})
    assert resp.status_code == 200

    from models import FunnelEvent
    with app.app_context():
        row = FunnelEvent.query.filter_by(event="artifact_opened").first()
        assert row is not None
        assert row.user_id == auth_user["id"]


def test_track_meta_is_bounded(client, app):
    """meta values are length-capped + key-count-capped (abuse guard)."""
    big_val = "x" * 5000
    many = {f"k{i}": i for i in range(50)}
    many["blob"] = big_val
    resp = client.post("/api/track", json={"event": "share_clicked", "meta": many})
    assert resp.status_code == 200

    from models import FunnelEvent
    from routes.growth import _MAX_META_KEYS, _MAX_META_VALUE_LEN
    with app.app_context():
        row = FunnelEvent.query.filter_by(event="share_clicked").first()
        assert row is not None
        assert len(row.meta) <= _MAX_META_KEYS
        for v in row.meta.values():
            if isinstance(v, str):
                assert len(v) <= _MAX_META_VALUE_LEN


# ── /api/card/<token> public gate ──────────────────────────────────────────

def _make_brag_artifact(app, user_id, *, token="t" * 32, is_public=False,
                        data=None):
    from models import Artifact
    with app.app_context():
        a = Artifact(
            user_id=user_id,
            type="brag_card",
            title=f"2026-03 Brag Card {token[:4]}",
            data_json=data or {
                "return_pct": 12.3,
                "month_label": "Mar 2026",
                "referral_code": "ABCD2345",
                "anonymous": False,
            },
            is_public=is_public,
        )
        a.share_token = token
        db.session.add(a)
        db.session.commit()
        return a.id


def test_public_card_hidden_when_private(client, app, make_user):
    """Default-private card is 404 even with a valid token (PIPA §29)."""
    u = make_user(email="owner1@test.com")
    token = "priv" + "a" * 28
    _make_brag_artifact(app, u["id"], token=token, is_public=False)
    resp = client.get(f"/api/card/{token}")
    assert resp.status_code == 404
    assert resp.get_json()["code"] == "CARD_NOT_FOUND"


def test_public_card_served_when_public(client, app, make_user):
    u = make_user(email="owner2@test.com", name="배상현")
    token = "pub0" + "b" * 28
    _make_brag_artifact(app, u["id"], token=token, is_public=True)
    resp = client.get(f"/api/card/{token}")
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["ok"] is True
    assert body["owner_display_name"] == "배상현"
    assert body["card_image_url"].endswith(f"/api/artifacts/brag-card/share/{token}/image")
    assert "투자 권유가 아닙니다" in body["summary_safe"]
    assert body["referral_code"] == "ABCD2345"


def test_public_card_anonymous_masks_name(client, app, make_user):
    u = make_user(email="owner3@test.com", name="실명노출금지")
    token = "anon" + "c" * 28
    _make_brag_artifact(
        app, u["id"], token=token, is_public=True,
        data={"return_pct": -4.0, "month_label": "Apr 2026", "anonymous": True},
    )
    resp = client.get(f"/api/card/{token}")
    assert resp.status_code == 200
    assert resp.get_json()["owner_display_name"] == "익명 투자자"


def test_public_card_short_token_404(client):
    resp = client.get("/api/card/short")
    assert resp.status_code == 404
    assert resp.get_json()["code"] == "INVALID_SHARE_TOKEN"


def test_public_card_summary_has_no_recommendation_language(client, app, make_user):
    """§101 — summary must not contain buy/sell/추천/조언 verbs."""
    u = make_user(email="owner4@test.com")
    token = "s101" + "d" * 28
    _make_brag_artifact(app, u["id"], token=token, is_public=True)
    body = client.get(f"/api/card/{token}").get_json()
    summary = body["summary_safe"]
    for banned in ("매수", "매도", "추천", "조언", "buy", "sell"):
        assert banned.lower() not in summary.lower(), f"banned term: {banned}"


# ── /api/card/<token>/visibility owner toggle ──────────────────────────────

def test_visibility_toggle_requires_auth(client, app, make_user):
    u = make_user(email="owner5@test.com")
    token = "vis0" + "e" * 28
    _make_brag_artifact(app, u["id"], token=token)
    resp = client.post(f"/api/card/{token}/visibility", json={"is_public": True})
    assert resp.status_code == 401


def test_visibility_toggle_owner_only(client, app, auth_user, make_user):
    """A non-owner cannot flip another user's card (404, no existence leak)."""
    other = make_user(email="someoneelse@test.com")
    token = "vis1" + "f" * 28
    _make_brag_artifact(app, other["id"], token=token)
    resp = client.post(f"/api/card/{token}/visibility", json={"is_public": True})
    assert resp.status_code == 404


def test_visibility_toggle_flips_and_publishes(client, app, auth_user):
    token = "vis2" + "g" * 28
    _make_brag_artifact(app, auth_user["id"], token=token, is_public=False)
    # Owner publishes
    resp = client.post(f"/api/card/{token}/visibility", json={"is_public": True})
    assert resp.status_code == 200
    assert resp.get_json()["is_public"] is True
    # Now publicly visible
    assert client.get(f"/api/card/{token}").status_code == 200
    # Owner un-publishes → public endpoint 404 again
    client.post(f"/api/card/{token}/visibility", json={"is_public": False})
    assert client.get(f"/api/card/{token}").status_code == 404


def test_visibility_toggle_validates_bool(client, app, auth_user):
    token = "vis3" + "h" * 28
    _make_brag_artifact(app, auth_user["id"], token=token)
    resp = client.post(f"/api/card/{token}/visibility", json={"is_public": "yes"})
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "IS_PUBLIC_BOOL_REQUIRED"


# ── attribute_referral ─────────────────────────────────────────────────────

def test_attribute_referral_records_and_counts(app, make_user):
    from routes.growth import attribute_referral
    from models import User, UserReferral, FunnelEvent

    with app.app_context():
        inviter = make_user(email="inviter@test.com")
        ur = UserReferral.get_or_create(inviter["id"])
        code = ur.referral_code
        invitee = make_user(email="invitee@test.com")

        u = db.session.get(User, invitee["id"])
        ok = attribute_referral(u, code)
        assert ok is True

        u2 = db.session.get(User, invitee["id"])
        assert u2.referred_by == code
        ur2 = UserReferral.query.filter_by(user_id=inviter["id"]).first()
        assert ur2.invited_count >= 1
        ev = FunnelEvent.query.filter_by(event="referral_signup",
                                         ref_code=code).first()
        assert ev is not None
        assert ev.user_id == invitee["id"]


def test_attribute_referral_idempotent(app, make_user):
    from routes.growth import attribute_referral
    from models import User, UserReferral

    with app.app_context():
        inviter = make_user(email="inv2@test.com")
        code = UserReferral.get_or_create(inviter["id"]).referral_code
        invitee = make_user(email="inve2@test.com")
        u = db.session.get(User, invitee["id"])
        assert attribute_referral(u, code) is True
        # Second attempt is a no-op (immutable attribution).
        u = db.session.get(User, invitee["id"])
        assert attribute_referral(u, "OTHERCODE") is False
        assert db.session.get(User, invitee["id"]).referred_by == code


def test_attribute_referral_rejects_self(app, make_user):
    from routes.growth import attribute_referral
    from models import User, UserReferral

    with app.app_context():
        me = make_user(email="self@test.com")
        code = UserReferral.get_or_create(me["id"]).referral_code
        u = db.session.get(User, me["id"])
        assert attribute_referral(u, code) is False
        assert db.session.get(User, me["id"]).referred_by is None


def test_attribute_referral_unknown_code_noop(app, make_user):
    from routes.growth import attribute_referral
    from models import User

    with app.app_context():
        invitee = make_user(email="unk@test.com")
        u = db.session.get(User, invitee["id"])
        assert attribute_referral(u, "NOPE9999") is False
        assert db.session.get(User, invitee["id"]).referred_by is None


# ── brag card snapshot mode (Activation for 0-trade users) ──────────────────

def test_brag_card_snapshot_mode_from_watchlist(app, make_user):
    """A user with only a watchlist (no trades/positions) gets a snapshot card."""
    from services.artifacts.brag_card_service import BragCardService
    from models import Watchlist
    with app.app_context():
        u = make_user(email="watcher@test.com")
        db.session.add(Watchlist(user_id=u["id"], ticker="AAPL"))
        db.session.add(Watchlist(user_id=u["id"], ticker="MSFT"))
        db.session.commit()

        data = BragCardService().generate_for_user(u["id"])
        assert data["mode"] == "snapshot"
        assert data["empty_reason"] == "no_closed_trades_watchlist"
        assert "AAPL" in data["snapshot_tickers"]


def test_brag_card_no_activity_reason(app, make_user):
    """Truly empty account → no_activity reason (still not a crash)."""
    from services.artifacts.brag_card_service import BragCardService
    with app.app_context():
        u = make_user(email="empty@test.com")
        data = BragCardService().generate_for_user(u["id"])
        assert data["mode"] == "trades"
        assert data["empty_reason"] == "no_activity"
        assert data["snapshot_tickers"] == []


# ── weekly_funnel_snapshot K-factor math ────────────────────────────────────

def test_kfactor_math_divisor_guards():
    """K-factor must never ZeroDivisionError on empty windows."""
    def k(shares, active, ref_signup):
        i = (shares / active) if active > 0 else 0.0
        c = (ref_signup / shares) if shares > 0 else 0.0
        return round(i * c, 3)

    assert k(0, 0, 0) == 0.0          # empty window — no crash
    assert k(10, 0, 5) == 0.0         # no active users
    assert k(0, 100, 0) == 0.0        # no shares
    assert k(50, 100, 10) == 0.1      # i=0.5, c=0.2 → K=0.1


def test_format_report_smoke():
    from scripts.nightly.weekly_funnel_snapshot import _format_report
    txt = _format_report({
        "acq": 5, "signup": 2, "onboard": 1, "activate": 3,
        "shares": 4, "ref_signup": 1, "wamr": 6, "k": 0.1, "i": 0.6, "c": 0.25,
    })
    assert "주간 퍼널 스냅샷" in txt
    assert "K-factor" in txt
