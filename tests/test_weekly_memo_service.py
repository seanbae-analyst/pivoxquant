"""
Weekly Investor Memo — service + route tests
============================================
Covers:
  - generate_for_user: assembly with mocked Position + FRED + prices
  - render_html / render_pdf: fallback path when WeasyPrint missing
  - send_email: no-provider branch returns False gracefully
  - run_weekly: Pro+ filter, empty portfolio skip
  - _persist: idempotent upsert on (user, type, title)
  - Route: /weekly-memo/preview requires auth, returns ok
  - Route: /weekly-memo/history shape
  - Route: /weekly-memo/trigger 404s without DEV_LOGIN_SECRET

All external I/O (FRED, FMP, DataFetcher, email providers) is mocked.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from extensions import db
from models import Artifact, Position, User


# ─── fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def memo_svc():
    # Local import — avoids pulling optional deps at module-scope if the
    # suite is ever run with a skipped test file.
    from services.artifacts.weekly_memo_service import WeeklyMemoService
    return WeeklyMemoService()


@pytest.fixture
def pro_user(app, make_user):
    u = make_user(email="pro@test.com", tier="pro")
    return u


@pytest.fixture
def free_user(app, make_user):
    u = make_user(email="free@test.com", tier="free")
    return u


@pytest.fixture
def patched_fetcher():
    """Patch the price-history lookup used inside weekly_memo_service."""
    import pandas as pd

    def _fake_history(ticker, period="1mo"):
        # 10 closing prices trending up for "AAPL", flat for "FLAT",
        # down for "DOWN", missing for "NONE".
        if ticker == "NONE":
            return None
        if ticker == "AAPL":
            closes = [100, 101, 102, 103, 104, 105, 106]
        elif ticker == "DOWN":
            closes = [110, 108, 106, 104, 102, 100, 98]
        elif ticker in ("SPY", "^GSPC"):
            closes = [400, 401, 402, 403, 404, 405, 406]
        else:
            closes = [50, 50, 50, 50, 50, 50, 50]
        return pd.DataFrame({"Close": closes})

    fake_container = MagicMock()
    fake_container.fetcher.get_price_history.side_effect = _fake_history
    with patch("services.artifacts.weekly_memo_service._safe_fetch_price_history",
               side_effect=_fake_history):
        yield fake_container


# ─── 1. assembly ─────────────────────────────────────────────────────────────

def test_generate_for_user_assembles_basic_structure(
    app, pro_user, add_position, patched_fetcher, memo_svc,
):
    add_position(pro_user["id"], ticker="AAPL", shares=10, avg_cost=100)
    add_position(pro_user["id"], ticker="DOWN", shares=5, avg_cost=100)

    with app.app_context():
        data = memo_svc.generate_for_user(pro_user["id"])

    assert data["user_id"] == pro_user["id"]
    assert data["week_number"] >= 1
    # Both winners and losers surface
    up_tickers = [m["ticker"] for m in data["top_movers_up"]]
    down_tickers = [m["ticker"] for m in data["top_movers_down"]]
    assert "AAPL" in up_tickers
    assert "DOWN" in down_tickers
    assert data["disclaimer"]
    # Compliance: disclaimer must not contain forbidden advisory verbs
    forbidden = ["추천", "매수", "매도", "buy", "sell", "recommend"]
    assert not any(w in data["disclaimer"] for w in forbidden)


def test_generate_for_user_handles_missing_prices(
    app, pro_user, add_position, patched_fetcher, memo_svc,
):
    """Tickers whose price history returns None are dropped silently."""
    add_position(pro_user["id"], ticker="NONE", shares=5, avg_cost=50)
    with app.app_context():
        data = memo_svc.generate_for_user(pro_user["id"])
    # No movers, but the memo still assembles cleanly
    assert data["top_movers_up"] == []
    assert data["top_movers_down"] == []
    assert data["weekly_return_pct"] is None


# ─── 2. rendering ────────────────────────────────────────────────────────────

def test_render_html_returns_string_with_key_fields(memo_svc):
    data = {
        "user_id": 1, "user_name": "Tester", "week_number": 16,
        "period_start": "2026-04-11", "period_end": "2026-04-18",
        "generated_at": "2026-04-18T00:00:00Z",
        "weekly_return_pct": 1.23, "benchmark_pct": 0.5, "alpha_pct": 0.73,
        "sector_alloc": {"Tech": 100.0}, "sector_changes": [],
        "top_movers_up": [{"ticker": "AAPL", "weekly_return_pct": 3.4}],
        "top_movers_down": [],
        "earnings_calendar": [], "macro_checklist": [], "risk_notes": [],
        "disclaimer": "정보 제공 목적.",
    }
    html = memo_svc.render_html(data)
    assert isinstance(html, str)
    assert "Tester" in html
    assert "AAPL" in html
    # Week # should appear somewhere
    assert "16" in html


def test_render_pdf_returns_none_when_weasyprint_missing(memo_svc):
    """If WeasyPrint can't be imported we return None, not raise."""
    with patch("services.artifacts.weekly_memo_service._try_import_weasyprint",
               return_value=None):
        out = memo_svc.render_pdf({
            "user_id": 1, "user_name": "T", "week_number": 1,
            "period_start": "2026-04-11", "period_end": "2026-04-18",
            "generated_at": "2026-04-18T00:00:00Z",
            "weekly_return_pct": None, "benchmark_pct": None, "alpha_pct": None,
            "sector_alloc": {}, "sector_changes": [],
            "top_movers_up": [], "top_movers_down": [],
            "earnings_calendar": [], "macro_checklist": [], "risk_notes": [],
            "disclaimer": "정보 제공 목적.",
        })
    assert out is None


def test_render_pdf_invokes_weasyprint_when_available(memo_svc):
    """Happy path — PDF bytes returned from the mocked HTML class."""
    fake_html_cls = MagicMock()
    fake_instance = MagicMock()
    fake_instance.write_pdf.return_value = b"%PDF-1.4 fake"
    fake_html_cls.return_value = fake_instance

    with patch("services.artifacts.weekly_memo_service._try_import_weasyprint",
               return_value=fake_html_cls):
        out = memo_svc.render_pdf({
            "user_id": 1, "user_name": "T", "week_number": 1,
            "period_start": "2026-04-11", "period_end": "2026-04-18",
            "generated_at": "2026-04-18T00:00:00Z",
            "weekly_return_pct": 1.0, "benchmark_pct": 0.5, "alpha_pct": 0.5,
            "sector_alloc": {}, "sector_changes": [],
            "top_movers_up": [], "top_movers_down": [],
            "earnings_calendar": [], "macro_checklist": [], "risk_notes": [],
            "disclaimer": "정보 제공 목적.",
        })
    assert out == b"%PDF-1.4 fake"
    fake_html_cls.assert_called_once()
    fake_instance.write_pdf.assert_called_once()


# ─── 3. email dispatch ──────────────────────────────────────────────────────

def test_send_email_returns_false_with_no_provider(app, pro_user, memo_svc):
    """Unset SENDGRID_API_KEY + unset SMTP_HOST → skip (False), no raise."""
    for k in ("SENDGRID_API_KEY", "SMTP_HOST"):
        os.environ.pop(k, None)

    with app.app_context():
        u = db.session.get(User, pro_user["id"])
        sent = memo_svc.send_email(u, pdf_bytes=b"pdf", html_body="<p>hi</p>")
    assert sent is False


def test_send_email_skips_opted_out_user(app, pro_user, memo_svc):
    """email_opt_out=True → bail out before any provider call."""
    with app.app_context():
        u = db.session.get(User, pro_user["id"])
        # Dynamic attribute is fine — the service treats it as truthy check.
        u.email_opt_out = True
        db.session.commit()
        sent = memo_svc.send_email(u, pdf_bytes=None, html_body="<p>hi</p>")
    assert sent is False


# ─── 4. weekly run orchestration ─────────────────────────────────────────────

def test_run_weekly_filters_to_paid_tiers(
    app, make_user, add_position, patched_fetcher, memo_svc,
):
    """Free user is not attempted; Pro user is."""
    free = make_user(email="free2@test.com", tier="free")
    pro  = make_user(email="pro2@test.com",  tier="pro")
    add_position(free["id"], ticker="AAPL", shares=1, avg_cost=100)
    add_position(pro["id"],  ticker="AAPL", shares=1, avg_cost=100)

    # send_email → no-op True (simulate success); don't actually render PDF.
    with patch.object(memo_svc, "send_email", return_value=True), \
         patch.object(memo_svc, "render_pdf", return_value=None):
        with app.app_context():
            summary = memo_svc.run_weekly()

    # Free user's row never exists; Pro user's does.
    with app.app_context():
        pro_rows = Artifact.query.filter_by(user_id=pro["id"],
                                            type="weekly_memo").count()
        free_rows = Artifact.query.filter_by(user_id=free["id"],
                                              type="weekly_memo").count()
    assert pro_rows == 1
    assert free_rows == 0
    assert summary["success"] >= 1
    # attempted counts ONLY paid users — free isn't even in the loop
    assert summary["attempted"] == 1


def test_run_weekly_skips_empty_portfolio_user(
    app, make_user, patched_fetcher, memo_svc,
):
    """Pro user with no positions → counted as skipped, no Artifact row."""
    pro  = make_user(email="pro-empty@test.com", tier="pro")

    with patch.object(memo_svc, "send_email", return_value=True), \
         patch.object(memo_svc, "render_pdf", return_value=None):
        with app.app_context():
            summary = memo_svc.run_weekly()

    with app.app_context():
        rows = Artifact.query.filter_by(user_id=pro["id"]).count()
    assert rows == 0
    assert summary["skipped"] >= 1
    assert summary["success"] == 0


# ─── 5. persistence: idempotent upsert ───────────────────────────────────────

def test_persist_is_idempotent_on_same_week(
    app, pro_user, add_position, patched_fetcher, memo_svc,
):
    """Running twice in the same week updates, not duplicates."""
    add_position(pro_user["id"], ticker="AAPL", shares=1, avg_cost=100)

    with patch.object(memo_svc, "send_email", return_value=True), \
         patch.object(memo_svc, "render_pdf", return_value=None):
        with app.app_context():
            u = db.session.get(User, pro_user["id"])
            memo_svc.run_for_user(u)
            memo_svc.run_for_user(u)  # second run — same week
            count = Artifact.query.filter_by(
                user_id=pro_user["id"], type="weekly_memo"
            ).count()
    assert count == 1


# ─── 6. routes ───────────────────────────────────────────────────────────────

def test_preview_route_requires_auth(raw_client):
    """Unauthenticated requests are rejected with 401."""
    resp = raw_client.post("/api/artifacts/weekly-memo/preview")
    assert resp.status_code == 401


def test_preview_route_returns_ok_for_authed_user(
    client, auth_user, patched_fetcher,
):
    resp = client.post("/api/artifacts/weekly-memo/preview")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert "data" in body
    assert "html" in body
    assert "week_number" in body["data"]


def test_history_route_empty_shape(client, auth_user):
    """New user → zero memos, ok=True."""
    resp = client.get("/api/artifacts/weekly-memo/history")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["count"] == 0
    assert body["memos"] == []


def test_trigger_route_404s_without_dev_secret(client, auth_user):
    """No DEV_LOGIN_SECRET → /trigger pretends to not exist."""
    os.environ.pop("DEV_LOGIN_SECRET", None)
    resp = client.post("/api/artifacts/weekly-memo/trigger", json={})
    assert resp.status_code == 404


def test_download_route_404_for_missing_memo(client, auth_user):
    """Unknown id returns 404 (same code as "not yours")."""
    resp = client.get("/api/artifacts/weekly-memo/download/99999")
    assert resp.status_code == 404
