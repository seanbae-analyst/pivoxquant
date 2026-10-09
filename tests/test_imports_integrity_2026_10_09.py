"""tests/test_imports_integrity_2026_10_09.py — Import Inbox regressions.

1. An account pending deletion (``users.deletion_requested_at``) is refused
   by the webhook like a revoked token and gets no "방금 체결" push; the token
   is not revoked, so cancelling the deletion makes it work again.
2. A webhook row with no ``traded_at`` is stamped with the arrival time, so a
   retry a minute later used to land as a second pending row. It is now a
   duplicate inside ``dedupe.UNTIMED_RETRY_WINDOW`` (no second push), and
   approval re-checks the ledger so a duplicate that slipped through never
   doubles the position.
3. A date-only fill (stored as its KST date at 00:00) matches a pause written
   earlier on the same KST day.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from tests.test_import_tokens_route import (  # noqa: F401  (fixture)
    PENDING,
    WEBHOOK,
    _bearer,
    _issue,
    webhook_client,
)

ROWS = {"rows": [{"ticker": "AAPL", "action": "buy", "shares": 3, "price": 150}]}


@pytest.fixture(autouse=True)
def _fixed_fx(monkeypatch):
    monkeypatch.setattr("services.fx_service.get_rate", lambda: 1300.0)


@pytest.fixture
def token(client, auth_user):
    r = _issue(client)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["token"]


@pytest.fixture
def clock(monkeypatch):
    """A settable naive-UTC clock for the import path (both bindings)."""
    import routes.imports as routes_imports
    import services.imports as services_imports

    state = {"now": services_imports.utcnow_naive().replace(microsecond=0)}
    for module in (services_imports, routes_imports):
        monkeypatch.setattr(module, "utcnow_naive", lambda: state["now"])
    return state


def _post(webhook_client, token, body=ROWS):  # noqa: F811
    return webhook_client.post(WEBHOOK, json=body, headers=_bearer(token))


def _set_deletion(app, user_id, when):
    from extensions import db
    from models import User
    with app.app_context():
        u = db.session.get(User, user_id)
        u.deletion_requested_at = when
        db.session.commit()


# ── 1. deletion-pending account ──────────────────────────────────────

class TestDeletionPending:
    def test_token_refused_and_no_push_then_restored_on_cancel(
        self, app, webhook_client, token, auth_user,  # noqa: F811
    ):
        from models.import_token import ImportToken
        _set_deletion(app, auth_user["id"], datetime(2026, 10, 1))
        with patch("services.push_service.send_push_to_user") as send:
            r = _post(webhook_client, token)
        assert r.status_code == 401
        assert r.get_json()["code"] == "IMPORT_TOKEN_INVALID"
        assert send.call_count == 0
        with app.app_context():
            assert ImportToken.query.filter_by(user_id=auth_user["id"]).one().revoked_at is None

        _set_deletion(app, auth_user["id"], None)  # deletion cancelled
        with patch("services.push_service.send_push_to_user") as send:
            r = _post(webhook_client, token)
        assert r.status_code == 201, r.get_json()
        assert send.call_count == 1

    def test_fill_memo_never_pushes_to_a_deletion_pending_account(self, app, auth_user):
        from services import fill_memo
        _set_deletion(app, auth_user["id"], datetime(2026, 10, 1))
        rows = [{"id": 1, "status": "pending", "name": "AAPL", "shares": 3}]
        with app.app_context(), patch("services.push_service.send_push_to_user") as send:
            assert fill_memo.notify_fill_memo(auth_user["id"], rows) is False
        assert send.call_count == 0


# ── 2. time-less retries / approval re-check ─────────────────────────

class TestUntimedRetry:
    def test_retry_two_minutes_later_is_one_pending_and_one_push(
        self, client, webhook_client, token, clock,  # noqa: F811
    ):
        with patch("services.push_service.send_push_to_user") as send:
            first = _post(webhook_client, token)
            clock["now"] += timedelta(minutes=2)
            retry = _post(webhook_client, token)
        assert first.status_code == 201 and retry.status_code == 201
        assert first.get_json()["pending"][0]["status"] == "pending"
        assert retry.get_json()["pending"][0]["status"] == "duplicate"
        assert retry.get_json()["batch"]["duplicate_count"] == 1
        assert retry.get_json()["memo_url"] is None
        assert send.call_count == 1
        assert client.get(PENDING).get_json()["count"] == 1

    def test_same_fill_outside_the_window_is_a_new_pending(
        self, client, webhook_client, token, clock,  # noqa: F811
    ):
        from services.imports.dedupe import UNTIMED_RETRY_WINDOW
        _post(webhook_client, token)
        clock["now"] += UNTIMED_RETRY_WINDOW + timedelta(minutes=1)
        later = _post(webhook_client, token)
        assert later.get_json()["pending"][0]["status"] == "pending"
        assert client.get(PENDING).get_json()["count"] == 2

    def test_different_amounts_inside_the_window_are_not_duplicates(
        self, webhook_client, token, clock,  # noqa: F811
    ):
        _post(webhook_client, token)
        clock["now"] += timedelta(minutes=2)
        other = _post(webhook_client, token, {"rows": [
            {"ticker": "AAPL", "action": "buy", "shares": 4, "price": 150},
        ]})
        assert other.get_json()["pending"][0]["status"] == "pending"

    def test_approving_a_duplicate_does_not_double_shares(
        self, app, client, webhook_client, token, auth_user, clock,  # noqa: F811
    ):
        """A retry row that slipped through intake (pre-fix data) is refused
        at approval instead of writing the fill twice."""
        from extensions import db
        from models import Position, TradeHistory
        from models.import_batch import PendingTrade
        from services.imports.dedupe import make_key

        pid_a = _post(webhook_client, token).get_json()["pending"][0]["id"]
        with app.app_context():
            a = db.session.get(PendingTrade, pid_a)
            stamp = a.created_at + timedelta(minutes=2)
            b = PendingTrade(
                batch_id=a.batch_id, user_id=a.user_id, ticker=a.ticker, name=a.name,
                action=a.action, shares=a.shares, price=a.price, currency=a.currency,
                currency_stated=a.currency_stated, traded_at=stamp, created_at=stamp,
                dedupe_key=make_key(a.user_id, a.ticker, a.action, a.shares, a.price, stamp),
                status="pending",
            )
            db.session.add(b)
            db.session.commit()
            pid_b = b.id

        ok = client.post(f"{PENDING}/{pid_a}/approve", json={"thesis": "실적 기대감에 샀다"})
        assert ok.status_code == 200, ok.get_json()
        dup = client.post(f"{PENDING}/{pid_b}/approve", json={"thesis": "실적 기대감에 샀다"})
        assert dup.status_code == 409, dup.get_json()
        assert dup.get_json()["code"] == "IMPORT_DUPLICATE"
        with app.app_context():
            assert Position.query.filter_by(user_id=auth_user["id"], ticker="AAPL").one().shares == 3.0
            assert TradeHistory.query.filter_by(user_id=auth_user["id"]).count() == 1
            assert db.session.get(PendingTrade, pid_b).status == "duplicate"
        assert client.get(PENDING).get_json()["count"] == 0

    def test_manual_entry_after_intake_blocks_approval(
        self, app, client, webhook_client, token, auth_user,  # noqa: F811
    ):
        from extensions import db
        from models import TradeHistory
        from models.import_batch import PendingTrade

        pid = _post(webhook_client, token).get_json()["pending"][0]["id"]
        with app.app_context():
            row = db.session.get(PendingTrade, pid)
            db.session.add(TradeHistory(
                user_id=auth_user["id"], ticker="AAPL", name="AAPL", action="BUY",  # // legal-ok
                shares=3.0, price_per_share=150.0, total_value=450.0, pnl=0.0, pnl_pct=0.0,
                currency="USD", traded_at=row.traded_at,
            ))
            db.session.commit()
        r = client.post(f"{PENDING}/{pid}/approve", json={"thesis": "실적 기대감에 샀다"})
        assert r.status_code == 409 and r.get_json()["code"] == "IMPORT_DUPLICATE"
        with app.app_context():
            assert TradeHistory.query.filter_by(user_id=auth_user["id"]).count() == 1


# ── 3. date-only fill ↔ same-day pause ───────────────────────────────

def _reflection(app, user_id, created_at, ticker="005930.KS"):
    from extensions import db
    from models import PreTradeReflection
    with app.app_context():
        r = PreTradeReflection(
            user_id=user_id, intended_ticker=ticker, intended_side="BUY",
            rationale="같은 날 멈춤", cooldown_started_at=created_at,
            cooldown_ends_at=created_at, created_at=created_at,
        )
        db.session.add(r)
        db.session.commit()
        return r.id


class TestDateOnlyMatch:
    def test_date_only_paste_matches_a_pause_from_the_same_kst_day(self, app, client, auth_user):
        # 2026-09-01 14:00 KST = 05:00 UTC; the fill is "2026-09-01" (no time).
        rid = _reflection(app, auth_user["id"], datetime(2026, 9, 1, 5, 0))
        r = client.post("/api/portfolio/imports/", json={
            "text": "삼성전자 10주 매수 체결 71,200원 2026-09-01", "consent": True,
        })
        assert r.status_code == 201, r.get_json()
        row = r.get_json()["pending"][0]
        assert row["traded_at"].startswith("2026-09-01T00:00")
        assert row["pre_trade_reflection_id"] == rid

    def test_pause_on_the_next_kst_day_does_not_match(self, app, client, auth_user):
        # 2026-09-01 16:00 UTC = 2026-09-02 01:00 KST — after the fill's day.
        _reflection(app, auth_user["id"], datetime(2026, 9, 1, 16, 0))
        r = client.post("/api/portfolio/imports/", json={
            "text": "삼성전자 10주 매수 체결 71,200원 2026-09-01", "consent": True,
        })
        assert r.get_json()["pending"][0]["pre_trade_reflection_id"] is None

    def test_match_pre_trade_patch_path(self, app, auth_user):
        from services.imports.ledger import match_pre_trade
        same_day = _reflection(app, auth_user["id"], datetime(2026, 9, 1, 14, 59))  # 23:59 KST
        _reflection(app, auth_user["id"], datetime(2026, 9, 1, 15, 0))  # 09-02 00:00 KST
        with app.app_context():
            assert match_pre_trade(auth_user["id"], "005930.KS", datetime(2026, 9, 1)) == same_day

    def test_timed_fill_still_ignores_a_later_pause(self, app, auth_user):
        from services.imports.ledger import match_pre_trade
        _reflection(app, auth_user["id"], datetime(2026, 9, 1, 5, 0))
        with app.app_context():
            # 10:32 KST = 01:32 UTC, before the 14:00 KST pause
            assert match_pre_trade(auth_user["id"], "005930.KS", datetime(2026, 9, 1, 1, 32)) is None
