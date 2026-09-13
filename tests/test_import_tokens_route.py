"""tests/test_import_tokens_route.py — Import Inbox Phase 2 v3-A: PAT + webhook.

Design: docs/product/IMPORT_INBOX_DESIGN.md §Phase 2 v3-A.

What must hold:
  - the raw token is returned exactly once (issuance) and stored only as sha256
  - listing never leaks the raw token
  - at most 5 active tokens per user; revoke is idempotent and user-scoped
  - the webhook authenticates by Bearer only (no session, no CSRF), all auth
    failures share one code, revoked tokens stop working
  - text / rows / text-plain bodies all land in the same pending inbox and the
    session user can approve them
  - the daily batch cap returns 429
  - the raw token never reaches the log
"""
from __future__ import annotations

import hashlib
import logging

import pytest

TOKENS = "/api/portfolio/imports/tokens"
WEBHOOK = "/api/portfolio/imports/webhook"
PENDING = "/api/portfolio/imports/pending"


@pytest.fixture
def webhook_client(app):
    """Bearer-only caller for the webhook.

    Deliberately NOT ``with app.test_client()``: the ``with`` form keeps each
    request context pushed until exit, and interleaving two such clients in one
    test pops the wrong context. A plain client carries no session cookie, so it
    also proves the webhook works without a login.
    """
    return app.test_client()


def _issue(client, name="폰 자동화", consent=True):
    body = {"name": name}
    if consent:
        body["consent"] = True
    return client.post(TOKENS, json=body)


def _bearer(raw):
    return {"Authorization": f"Bearer {raw}"}


class TestIssueAndList:
    def test_issue_returns_raw_once_and_stores_only_hash(self, client, auth_user, app):
        r = _issue(client)
        assert r.status_code == 201, r.get_json()
        body = r.get_json()
        raw = body["token"]
        assert raw.startswith("pvx_") and len(raw) > 20
        assert body["prefix"] == raw[:12]
        assert body["name"] == "폰 자동화"

        from models import ImportToken
        with app.app_context():
            row = ImportToken.query.get(body["id"])
            assert row.token_hash == hashlib.sha256(raw.encode()).hexdigest()
            assert row.consent_at is not None
            assert row.revoked_at is None

        # Listing must never carry the raw token (prefix only).
        lst = client.get(TOKENS)
        assert lst.status_code == 200
        text = lst.get_data(as_text=True)
        assert raw not in text
        tokens = lst.get_json()["tokens"]
        assert len(tokens) == 1
        assert tokens[0]["prefix"] == raw[:12]
        assert "token" not in tokens[0] and "token_hash" not in tokens[0]
        assert tokens[0]["batches_today"] == 0
        assert lst.get_json()["active_limit"] == 5

    def test_issue_requires_consent(self, client, auth_user):
        r = _issue(client, consent=False)
        assert r.status_code == 400
        assert r.get_json()["code"] == "IMPORT_CONSENT_REQUIRED"

    @pytest.mark.parametrize("name", ["", "   ", "x" * 61])
    def test_issue_name_invalid(self, client, auth_user, name):
        r = _issue(client, name=name)
        assert r.status_code == 400
        assert r.get_json()["code"] == "IMPORT_TOKEN_NAME_INVALID"

    def test_active_limit_is_five_and_revoke_frees_a_slot(self, client, auth_user):
        ids = []
        for i in range(5):
            r = _issue(client, name=f"t{i}")
            assert r.status_code == 201, r.get_json()
            ids.append(r.get_json()["id"])
        r = _issue(client, name="t6")
        assert r.status_code == 400
        assert r.get_json()["code"] == "IMPORT_TOKEN_LIMIT"

        assert client.delete(f"{TOKENS}/{ids[0]}").status_code == 200
        r = _issue(client, name="t6")
        assert r.status_code == 201, r.get_json()

        lst = client.get(TOKENS).get_json()["tokens"]
        assert len(lst) == 6
        revoked = [t for t in lst if t["revoked_at"]]
        assert len(revoked) == 1 and revoked[0]["id"] == ids[0]


class TestRevoke:
    def test_revoke_is_idempotent_and_user_scoped(self, client, auth_user, make_user, app):
        tid = _issue(client).get_json()["id"]
        assert client.delete(f"{TOKENS}/{tid}").get_json() == {"ok": True}
        assert client.delete(f"{TOKENS}/{tid}").get_json() == {"ok": True}

        # Another user cannot see or revoke it — 404, not 403 (no existence leak).
        other = make_user(email="other@test.com")
        client.post("/api/auth/logout")
        r = client.post("/api/auth/login", json={"email": other["email"], "password": other["password"]})
        assert r.status_code == 200
        assert client.delete(f"{TOKENS}/{tid}").status_code == 404
        assert client.get(TOKENS).get_json()["tokens"] == []


class TestWebhookAuth:
    def test_missing_malformed_unknown_and_revoked_share_one_code(self, client, webhook_client, auth_user):
        raw = _issue(client).get_json()["token"]
        cases = [
            {},
            {"Authorization": "Basic abc"},
            {"Authorization": "Bearer"},
            {"Authorization": "Bearer not-a-token"},
            {"Authorization": "Bearer pvx_" + "a" * 32},
        ]
        for headers in cases:
            r = webhook_client.post(WEBHOOK, json={"text": "삼성전자 1주 매수 체결 70,000원"}, headers=headers)
            assert r.status_code == 401, headers
            assert r.get_json()["code"] == "IMPORT_TOKEN_INVALID"

        # Works before revoke, fails after with the same code.
        ok = webhook_client.post(WEBHOOK, json={"text": "삼성전자 1주 매수 체결 70,000원"}, headers=_bearer(raw))
        assert ok.status_code == 201, ok.get_json()
        tid = client.get(TOKENS).get_json()["tokens"][0]["id"]
        client.delete(f"{TOKENS}/{tid}")
        r = webhook_client.post(WEBHOOK, json={"text": "삼성전자 1주 매수 체결 70,000원"}, headers=_bearer(raw))
        assert r.status_code == 401
        assert r.get_json()["code"] == "IMPORT_TOKEN_INVALID"

    def test_raw_token_never_reaches_the_log(self, client, webhook_client, auth_user, caplog):
        raw = _issue(client).get_json()["token"]
        with caplog.at_level(logging.DEBUG):
            webhook_client.post(WEBHOOK, json={"text": "삼성전자 2주 매수 체결 70,000원"}, headers=_bearer(raw))
            webhook_client.post(WEBHOOK, json={}, headers=_bearer(raw))
            webhook_client.post(WEBHOOK, json={"text": "x"}, headers={"Authorization": "Bearer pvx_" + "b" * 32})
        assert raw not in caplog.text
        assert "pvx_" + "b" * 32 not in caplog.text


class TestWebhookIngest:
    def test_text_body_lands_in_pending_with_webhook_source(self, client, webhook_client, auth_user):
        raw = _issue(client).get_json()["token"]
        r = webhook_client.post(WEBHOOK, json={"text": "삼성전자 10주 매수 체결 71,200원"}, headers=_bearer(raw))
        assert r.status_code == 201, r.get_json()
        body = r.get_json()
        assert body["batch"]["source"] == "webhook"
        assert body["batch"]["parsed_count"] == 1
        assert body["mapping"] is None
        p = body["pending"][0]
        assert p["status"] == "pending"
        assert p["ticker"] == "005930.KS"
        assert p["action"] == "BUY"  # // legal-ok — data field restored through the scrub
        assert p["shares"] == 10.0 and p["price"] == 71200.0

        # Session sees it in the inbox; token shows one batch today + last_used_at.
        inbox = client.get(PENDING).get_json()
        assert inbox["count"] == 1
        tok = client.get(TOKENS).get_json()["tokens"][0]
        assert tok["batches_today"] == 1
        assert tok["last_used_at"] is not None

    def test_rows_body(self, client, webhook_client, auth_user):
        raw = _issue(client).get_json()["token"]
        rows = [
            {"ticker": "AAPL", "action": "BUY", "shares": 2, "price": 190.5, "traded_at": "2026-09-01"},
            {"name": "삼성전자", "action": "매도", "shares": 1, "price": 73000, "traded_at": "2026-09-02 10:30"},
        ]
        r = webhook_client.post(WEBHOOK, json={"rows": rows}, headers=_bearer(raw))
        assert r.status_code == 201, r.get_json()
        pend = {p["ticker"]: p for p in r.get_json()["pending"]}
        assert pend["AAPL"]["currency"] == "USD" and pend["AAPL"]["action"] == "BUY"  # // legal-ok
        assert pend["005930.KS"]["action"] == "SELL"  # // legal-ok
        assert pend["005930.KS"]["traded_at"].startswith("2026-09-02T10:30")

    def test_text_plain_body(self, client, webhook_client, auth_user):
        raw = _issue(client).get_json()["token"]
        r = webhook_client.post(
            WEBHOOK,
            data="Bought 3 NVDA @ $120.50\n삼성전자 4주 매수 체결 70,000원",
            content_type="text/plain",
            headers=_bearer(raw),
        )
        assert r.status_code == 201, r.get_json()
        assert r.get_json()["batch"]["parsed_count"] == 2

    def test_duplicate_send_is_marked(self, client, webhook_client, auth_user):
        raw = _issue(client).get_json()["token"]
        body = {"text": "삼성전자 10주 매수 체결 71,200원"}
        assert webhook_client.post(WEBHOOK, json=body, headers=_bearer(raw)).status_code == 201
        r = webhook_client.post(WEBHOOK, json=body, headers=_bearer(raw))
        assert r.status_code == 201
        assert r.get_json()["batch"]["duplicate_count"] == 1
        assert r.get_json()["pending"][0]["status"] == "duplicate"

    def test_empty_and_invalid_bodies(self, client, webhook_client, auth_user):
        raw = _issue(client).get_json()["token"]
        r = webhook_client.post(WEBHOOK, json={}, headers=_bearer(raw))
        assert r.status_code == 400 and r.get_json()["code"] == "IMPORT_NO_ROWS"
        r = webhook_client.post(WEBHOOK, json={"text": "   "}, headers=_bearer(raw))
        assert r.status_code == 400 and r.get_json()["code"] == "IMPORT_NO_ROWS"
        r = webhook_client.post(WEBHOOK, json={"rows": [{"ticker": "AAPL", "action": "BUY", "shares": "x", "price": 1}]},
                            headers=_bearer(raw))
        assert r.status_code == 400
        assert r.get_json()["code"] == "IMPORT_INVALID_FIELD"

    def test_daily_limit_returns_429(self, client, webhook_client, auth_user, monkeypatch):
        import routes.imports as mod
        monkeypatch.setattr(mod, "TOKEN_DAILY_BATCH_LIMIT", 2)
        raw = _issue(client).get_json()["token"]
        for i in range(2):
            r = webhook_client.post(WEBHOOK, json={"text": f"삼성전자 {i + 1}주 매수 체결 70,000원"}, headers=_bearer(raw))
            assert r.status_code == 201, r.get_json()
        r = webhook_client.post(WEBHOOK, json={"text": "삼성전자 9주 매수 체결 70,000원"}, headers=_bearer(raw))
        assert r.status_code == 429
        assert r.get_json()["code"] == "IMPORT_TOKEN_DAILY_LIMIT"

    def test_webhook_pending_is_approvable_by_the_session_user(self, client, webhook_client, auth_user, app):
        raw = _issue(client).get_json()["token"]
        r = webhook_client.post(WEBHOOK, json={"text": "삼성전자 10주 매수 체결 71,200원"}, headers=_bearer(raw))
        pid = r.get_json()["pending"][0]["id"]
        a = client.post(f"{PENDING}/{pid}/approve", json={"thesis": "반도체 업황 회복 기대"})
        assert a.status_code == 200, a.get_json()
        assert a.get_json()["ok"] is True

        from models import Position, TradeHistory
        with app.app_context():
            pos = Position.query.filter_by(user_id=auth_user["id"], ticker="005930.KS").one()
            assert pos.shares == 10.0 and pos.avg_cost == 71200.0
            assert TradeHistory.query.filter_by(user_id=auth_user["id"]).count() == 1

    def test_webhook_pending_is_isolated_to_token_owner(self, client, webhook_client, auth_user, make_user):
        raw = _issue(client).get_json()["token"]
        webhook_client.post(WEBHOOK, json={"text": "삼성전자 10주 매수 체결 71,200원"}, headers=_bearer(raw))
        other = make_user(email="other2@test.com")
        client.post("/api/auth/logout")
        client.post("/api/auth/login", json={"email": other["email"], "password": other["password"]})
        assert client.get(PENDING).get_json()["count"] == 0
