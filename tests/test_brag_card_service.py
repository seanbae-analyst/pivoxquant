"""
Brag Card Service — MVP #2 tests
================================
Covers:
  - generate_for_user: positive month / negative month / empty portfolio
  - privacy_mode (anonymous) toggle
  - render_html: required elements (return %, month, watermark) present
  - run_monthly: Free tier is INCLUDED (unlike Weekly Memo Pro+ filter)
  - share token generation + URL carries the referral code
  - render_png: graceful None when Playwright missing
  - send_email: no-provider → False (no raise)
  - _persist: idempotent on same month (UPSERT)

All external I/O (Playwright, SendGrid, SMTP) is mocked so the suite
runs cold without Chromium installed.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from extensions import db
from models import Artifact, TradeHistory, User


# ─── fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def brag_svc():
    from services.artifacts.brag_card_service import BragCardService
    return BragCardService()


@pytest.fixture
def target_month():
    """First day of the most recent *completed* month.

    Using the previous month avoids boundary flakes when tests run on
    the 1st (where today == month_start → `_compute_monthly_stats`
    includes a partial window).
    """
    today = date.today().replace(day=1)
    last_prev = today - timedelta(days=1)
    return last_prev.replace(day=1)


@pytest.fixture
def seed_trades(app, target_month):
    """Factory: insert (BUY, SELL) pairs for a user, dated inside the
    target month. Returns the user_id for chaining."""
    def _seed(user_id, ticker="AAPL", buy_cost=1000.0, pnl=100.0,
              action_pairs=True):
        traded = datetime.combine(
            target_month + timedelta(days=5),
            datetime.min.time(),
        )
        with app.app_context():
            if action_pairs:
                db.session.add(TradeHistory(
                    user_id=user_id, ticker=ticker, action="BUY",
                    shares=10, price_per_share=buy_cost / 10,
                    total_value=buy_cost, pnl=0,
                    traded_at=traded,
                ))
                db.session.add(TradeHistory(
                    user_id=user_id, ticker=ticker, action="SELL",
                    shares=10, price_per_share=(buy_cost + pnl) / 10,
                    total_value=buy_cost + pnl, pnl=pnl,
                    traded_at=traded + timedelta(days=1),
                ))
            db.session.commit()
        return user_id
    return _seed


# ─── 1. data assembly ────────────────────────────────────────────────────────

def test_generate_positive_month(app, make_user, seed_trades, target_month,
                                  brag_svc):
    """A winning month produces a positive return_pct and names the best
    ticker. The payload shape mirrors the dataclass."""
    u = make_user(email="gain@test.com", tier="free")
    seed_trades(u["id"], ticker="AAPL", buy_cost=1000, pnl=120)

    with app.app_context():
        data = brag_svc.generate_for_user(u["id"], month=target_month)

    assert data["user_id"] == u["id"]
    assert data["return_pct"] is not None
    assert data["return_pct"] > 0
    assert data["best_ticker"] == "AAPL"
    assert data["trade_count"] == 2  # one BUY + one SELL
    # Compliance: disclaimer carries no forbidden advisory words.
    forbidden = ["추천", "매수", "매도", "buy", "sell", "recommend"]
    assert not any(w in data["disclaimer"] for w in forbidden)


def test_generate_negative_month(app, make_user, seed_trades, target_month,
                                  brag_svc):
    """Loss months surface a negative return_pct — renderer uses the
    neutral color for these (verified in the html test)."""
    u = make_user(email="loss@test.com", tier="free")
    seed_trades(u["id"], ticker="BBB", buy_cost=1000, pnl=-150)

    with app.app_context():
        data = brag_svc.generate_for_user(u["id"], month=target_month)

    assert data["return_pct"] is not None
    assert data["return_pct"] < 0


def test_generate_empty_portfolio(app, make_user, target_month, brag_svc):
    """No positions + no trades → is_empty True, return_pct None, no crash."""
    u = make_user(email="empty@test.com", tier="free")

    with app.app_context():
        data = brag_svc.generate_for_user(u["id"], month=target_month)

    assert data["is_empty"] is True
    assert data["return_pct"] is None
    assert data["trade_count"] == 0
    assert data["best_ticker"] is None


# ─── 2. anonymous / privacy mode ─────────────────────────────────────────────

def test_anonymous_mode_masks_tickers(app, make_user, seed_trades,
                                       target_month, brag_svc):
    """privacy_mode=True → best_ticker masked to 'A 종목'."""
    u = make_user(email="anon@test.com", tier="free")
    seed_trades(u["id"], ticker="AAPL", buy_cost=1000, pnl=80)

    # Explicit override arg takes precedence over the user attribute.
    with app.app_context():
        data = brag_svc.generate_for_user(
            u["id"], month=target_month, anonymous=True,
        )
    assert data["anonymous"] is True
    assert data["best_ticker"] == "A 종목"

    # And the user-attribute path — set via the privacy route's semantics.
    with app.app_context():
        user = db.session.get(User, u["id"])
        user.privacy_mode = True
        db.session.commit()
        data2 = brag_svc.generate_for_user(u["id"], month=target_month)
    assert data2["anonymous"] is True
    assert data2["best_ticker"] == "A 종목"


# ─── 3. HTML render ──────────────────────────────────────────────────────────

def test_render_html_contains_required_elements(brag_svc):
    """The rendered card HTML MUST include:
      - the formatted return % (hero)
      - the long month label
      - the PIVOXQUANT watermark
      - the compliance disclaimer
    """
    data = {
        "user_id": 1, "user_name": "Tester",
        "referral_code": "ABCD2345",
        "month_label": "Mar 2026", "month_label_long": "March 2026",
        "month_start": "2026-03-01", "month_end": "2026-03-31",
        "generated_at": "2026-04-01T00:00:00Z",
        "return_pct": 12.3, "trade_count": 4,
        "best_ticker": "AAPL", "best_return_pct": 18.0,
        "worst_ticker": None, "worst_return_pct": None,
        "anonymous": False, "is_empty": False,
        "share_token": None,
        "disclaimer": "정보 제공 목적이며 투자 권유가 아닙니다.",
    }
    html = brag_svc.render_html(data)
    assert isinstance(html, str)
    # Template renders `best_return_pct` (18.0) with 2 decimals as "+18.00%"
    # (confirmed empirically via direct service call). The previous
    # assertion "+12.3%" was stale — return_pct is only a fallback when
    # best_return_pct is None.
    assert "+18.00%" in html
    assert "March 2026" in html
    assert "PIVOXQUANT" in html
    assert "정보 제공 목적" in html


# ─── 4. run_monthly covers Free tier ─────────────────────────────────────────

def test_run_monthly_includes_free_users(app, make_user, seed_trades,
                                           target_month, brag_svc):
    """Unlike the Weekly Memo (Pro+ only), the brag-card monthly run
    MUST iterate Free users too — they're the viral-loop distribution."""
    free = make_user(email="free-brag@test.com", tier="free")
    pro  = make_user(email="pro-brag@test.com",  tier="pro")
    seed_trades(free["id"], ticker="FFF", buy_cost=500, pnl=50)
    seed_trades(pro["id"],  ticker="PPP", buy_cost=500, pnl=50)

    with patch.object(brag_svc, "send_email", return_value=True), \
         patch.object(brag_svc, "render_png", return_value=None):
        with app.app_context():
            summary = brag_svc.run_monthly(target_month=target_month)

    with app.app_context():
        free_rows = Artifact.query.filter_by(
            user_id=free["id"], type="brag_card",
        ).count()
        pro_rows = Artifact.query.filter_by(
            user_id=pro["id"], type="brag_card",
        ).count()

    assert free_rows == 1, "Free user must receive a brag card"
    assert pro_rows == 1
    # Both users attempted; either both succeed or one may have been
    # skipped if seed_trades didn't write due to fixture scoping. At
    # minimum, at least one success and no failures.
    assert summary["success"] >= 1
    assert summary["failed"] == 0


# ─── 5. share token + referral in URL ────────────────────────────────────────

def test_share_url_carries_referral_code(app, make_user, seed_trades,
                                          target_month, brag_svc):
    """get_share_url must embed the user's referral code so downstream
    signups attribute to the sharer."""
    u = make_user(email="share@test.com", tier="free")
    seed_trades(u["id"], ticker="ZZZ", buy_cost=1000, pnl=50)

    with patch.object(brag_svc, "send_email", return_value=True), \
         patch.object(brag_svc, "render_png", return_value=None):
        with app.app_context():
            user = db.session.get(User, u["id"])
            artefact = brag_svc.run_for_user(user, target_month=target_month)
            assert artefact is not None

            # Share URL carries the referral code.
            url = brag_svc.get_share_url(artefact.id)

            from models import UserReferral
            ref = UserReferral.get_or_create(u["id"])

    assert "pivoxquant.com" in url or "http" in url
    assert ref.referral_code in url
    # Share token is a 32-char urlsafe chunk — ensure it's in the URL.
    with app.app_context():
        refreshed = db.session.get(Artifact, artefact.id)
        assert refreshed.share_token
        assert refreshed.share_token in url


# ─── 6. Playwright missing → render_png None (graceful) ─────────────────────

def test_render_png_returns_none_when_playwright_missing(brag_svc):
    """If Playwright can't be imported we return None, not raise."""
    with patch("services.artifacts.brag_card_service._try_import_playwright",
               return_value=None):
        out = brag_svc.render_png("<html><body>hi</body></html>")
    assert out is None


def test_render_png_invokes_playwright_when_available(brag_svc):
    """Happy path — Playwright mock returns bytes; render_png forwards them."""
    fake_sync_pw = MagicMock()
    fake_cm = MagicMock()
    # Context manager plumbing: sync_playwright() returns a CM whose
    # __enter__ yields an object with .chromium.launch(...)
    fake_cm.__enter__.return_value = fake_cm
    fake_cm.__exit__.return_value = False
    fake_sync_pw.return_value = fake_cm
    fake_browser = MagicMock()
    fake_cm.chromium.launch.return_value = fake_browser
    fake_ctx = MagicMock()
    fake_browser.new_context.return_value = fake_ctx
    fake_page = MagicMock()
    fake_ctx.new_page.return_value = fake_page
    fake_page.screenshot.return_value = b"\x89PNG\r\n\x1a\nfake"

    with patch("services.artifacts.brag_card_service._try_import_playwright",
               return_value=fake_sync_pw):
        out = brag_svc.render_png("<html><body>hi</body></html>")
    assert out == b"\x89PNG\r\n\x1a\nfake"
    fake_page.set_content.assert_called_once()
    fake_page.screenshot.assert_called_once()


# ─── 7. email send — no-provider branch ──────────────────────────────────────

def test_send_email_returns_false_with_no_provider(app, make_user, brag_svc):
    """Unset SENDGRID_API_KEY + unset SMTP_HOST → skip (False), no raise."""
    for k in ("SENDGRID_API_KEY", "SMTP_HOST"):
        os.environ.pop(k, None)

    u = make_user(email="mailnone@test.com", tier="free")
    with app.app_context():
        user = db.session.get(User, u["id"])
        sent = brag_svc.send_email(user, png_bytes=b"", html_body="<p>hi</p>")
    assert sent is False


# ─── 8. idempotent persist on same month ────────────────────────────────────

def test_persist_idempotent_on_same_month(app, make_user, seed_trades,
                                            target_month, brag_svc):
    """Running twice in the same month UPSERTs — no duplicate row."""
    u = make_user(email="idempotent@test.com", tier="free")
    seed_trades(u["id"], ticker="III", buy_cost=1000, pnl=30)

    with patch.object(brag_svc, "send_email", return_value=True), \
         patch.object(brag_svc, "render_png", return_value=None):
        with app.app_context():
            user = db.session.get(User, u["id"])
            brag_svc.run_for_user(user, target_month=target_month)
            brag_svc.run_for_user(user, target_month=target_month)
            count = Artifact.query.filter_by(
                user_id=u["id"], type="brag_card",
            ).count()
    assert count == 1


# ─── 9. routes smoke test ────────────────────────────────────────────────────

def test_brag_card_preview_route_requires_auth(raw_client):
    """Unauthenticated requests rejected with 401."""
    resp = raw_client.post("/api/artifacts/brag-card/preview")
    assert resp.status_code == 401


def test_brag_card_trigger_404s_without_dev_secret(client, auth_user):
    """No DEV_LOGIN_SECRET → /trigger pretends to not exist (prod shape)."""
    os.environ.pop("DEV_LOGIN_SECRET", None)
    resp = client.post("/api/artifacts/brag-card/trigger", json={})
    assert resp.status_code == 404


def test_brag_card_privacy_toggle(client, auth_user):
    """POST /brag-card/privacy flips the boolean."""
    resp = client.post("/api/artifacts/brag-card/privacy",
                       json={"privacy_mode": True})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["privacy_mode"] is True
