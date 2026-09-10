"""TossReadOnlyClient — the guard is the point, so the guard gets the tests.

No network. A fake session records every call and answers from canned bodies
built on the OpenAPI v1.2.15 examples.
"""
from __future__ import annotations

import json

import pytest

from services.toss.client import (
    READ_ONLY_PATHS,
    TossApiError,
    TossReadOnlyClient,
    TossReadOnlyViolation,
    redact,
)


class _Resp:
    def __init__(self, status: int, body, headers=None):
        self.status_code = status
        self._body = body
        self.headers = headers or {}
        self.text = json.dumps(body, ensure_ascii=False)

    def json(self):
        return self._body


class _FakeSession:
    def __init__(self, routes):
        self.routes = routes  # (method, path) -> list[_Resp] or _Resp
        self.calls = []

    def request(self, method, url, **kw):
        path = url.split("openapi.tossinvest.com", 1)[1].split("?", 1)[0]
        self.calls.append((method, path, kw))
        r = self.routes.get((method, path))
        if r is None:
            raise AssertionError(f"unexpected {method} {path}")
        if isinstance(r, list):
            return r.pop(0)
        return r


TOKEN = _Resp(200, {"access_token": "tok-1", "token_type": "Bearer", "expires_in": 86400})


def _client(routes, **kw):
    sess = _FakeSession({("POST", "/oauth2/token"): TOKEN, **routes})
    return TossReadOnlyClient("cid", "csecret", session=sess, sleep=lambda s: None, **kw), sess


# ── the guard ────────────────────────────────────────────────────────────────
def test_allowlist_contains_no_order_capable_path():
    for p in READ_ONLY_PATHS:
        assert "modify" not in p and "cancel" not in p and "conditional" not in p
        assert p != "/api/v1/buying-power"


@pytest.mark.parametrize("path", [
    "/api/v1/orders/abc/cancel",
    "/api/v1/orders/abc/modify",
    "/api/v1/conditional-orders",
    "/api/v1/buying-power",
    "/api/v1/sellable-quantity",
    "/api/v1/commissions",
    "/api/v1/stocks/all",
    "/api/v1/stocks/005930/warnings",
])
def test_get_outside_allowlist_raises_before_any_request(path):
    c, sess = _client({})
    with pytest.raises(TossReadOnlyViolation):
        c._get(path)
    assert sess.calls == [], "nothing may leave the process for a denied path"


def test_generic_request_verb_is_refused():
    c, sess = _client({})
    with pytest.raises(TossReadOnlyViolation):
        c.request("POST", "/api/v1/orders", json={"side": "x"})
    assert sess.calls == []


def test_only_the_token_endpoint_is_ever_posted():
    c, sess = _client({("GET", "/api/v1/accounts"): _Resp(200, {"result": []})})
    c.accounts()
    posts = [(m, p) for m, p, _ in sess.calls if m != "GET"]
    assert posts == [("POST", "/oauth2/token")]


# ── auth + headers ───────────────────────────────────────────────────────────
def test_token_is_form_encoded_and_cached_across_calls():
    c, sess = _client({("GET", "/api/v1/accounts"): _Resp(200, {"result": []})})
    c.accounts()
    c.accounts()
    tok_calls = [kw for m, p, kw in sess.calls if p == "/oauth2/token"]
    assert len(tok_calls) == 1
    assert tok_calls[0]["data"]["grant_type"] == "client_credentials"
    assert tok_calls[0]["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
    gets = [kw for m, p, kw in sess.calls if p == "/api/v1/accounts"]
    assert all(kw["headers"]["Authorization"] == "Bearer tok-1" for kw in gets)


def test_account_header_is_sent_for_account_scoped_calls_only():
    c, sess = _client({
        ("GET", "/api/v1/accounts"): _Resp(200, {"result": [{"accountSeq": 7, "accountNo": "1", "accountType": "BROKERAGE"}]}),
        ("GET", "/api/v1/holdings"): _Resp(200, {"result": {"items": []}}),
        ("GET", "/api/v1/exchange-rate"): _Resp(200, {"result": {"rate": "1380.5"}}),
    })
    c.accounts()
    c.holdings(7)
    c.exchange_rate()
    by_path = {p: kw["headers"] for m, p, kw in sess.calls if m == "GET"}
    assert by_path["/api/v1/holdings"]["X-Tossinvest-Account"] == "7"
    assert "X-Tossinvest-Account" not in by_path["/api/v1/accounts"]
    assert "X-Tossinvest-Account" not in by_path["/api/v1/exchange-rate"]


def test_401_reissues_token_once_and_retries():
    sess = _FakeSession({
        ("POST", "/oauth2/token"): [TOKEN, _Resp(200, {"access_token": "tok-2", "token_type": "Bearer", "expires_in": 100})],
        ("GET", "/api/v1/accounts"): [
            _Resp(401, {"error": {"code": "expired-token", "message": "x"}}),
            _Resp(200, {"result": []}),
        ],
    })
    c = TossReadOnlyClient("cid", "cs", session=sess, sleep=lambda s: None)
    assert c.accounts() == []
    auths = [kw["headers"]["Authorization"] for m, p, kw in sess.calls if p == "/api/v1/accounts"]
    assert auths == ["Bearer tok-1", "Bearer tok-2"]


def test_429_honours_retry_after_then_retries_once():
    waited = []
    sess = _FakeSession({
        ("POST", "/oauth2/token"): TOKEN,
        ("GET", "/api/v1/accounts"): [
            _Resp(429, {"error": {"code": "rate-limit-exceeded", "message": "slow"}}, {"Retry-After": "2"}),
            _Resp(200, {"result": []}),
        ],
    })
    c = TossReadOnlyClient("cid", "cs", session=sess, sleep=waited.append)
    assert c.accounts() == []
    assert waited == [2.0]


def test_api_error_carries_code_and_hints_ip_allowlist_on_403():
    c, _ = _client({("GET", "/api/v1/accounts"): _Resp(403, {"error": {"code": "edge-blocked", "message": ""}})})
    with pytest.raises(TossApiError) as ei:
        c.accounts()
    assert ei.value.status == 403 and ei.value.code == "edge-blocked"
    assert "허용 IP" in str(ei.value)


def test_unconfigured_client_fails_closed():
    c = TossReadOnlyClient("", "", session=_FakeSession({}))
    assert not c.configured
    with pytest.raises(TossApiError):
        c.accounts()


# ── pagination ───────────────────────────────────────────────────────────────
def test_closed_orders_follow_cursor_until_hasnext_false():
    c, sess = _client({("GET", "/api/v1/orders"): [
        _Resp(200, {"result": {"orders": [{"orderId": "a"}], "nextCursor": "c1", "hasNext": True}}),
        _Resp(200, {"result": {"orders": [{"orderId": "b"}], "nextCursor": None, "hasNext": False}}),
    ]})
    got = [o["orderId"] for o in c.iter_closed_orders(1, date_from="2026-01-01", date_to="2026-03-30")]
    assert got == ["a", "b"]
    params = [kw["params"] for m, p, kw in sess.calls if p == "/api/v1/orders"]
    assert params[0]["status"] == "CLOSED" and "cursor" not in params[0]
    assert params[1]["cursor"] == "c1"
    assert params[0]["from"] == "2026-01-01" and params[0]["to"] == "2026-03-30"


def test_order_detail_path_normalises_onto_allowlist():
    c, _ = _client({("GET", "/api/v1/orders/abc-123_X"): _Resp(200, {"result": {"orderId": "abc-123_X"}})})
    assert c._get("/api/v1/orders/abc-123_X", account_seq=1)["orderId"] == "abc-123_X"


# ── redaction ────────────────────────────────────────────────────────────────
def test_redact_masks_secret_shaped_keys():
    body = '{"access_token": "eyJabcdefghijklmnop", "accountNo": "12345678901", "rate": "1380"}'
    out = redact(body)
    assert "eyJabcdefghijklmnop" not in out and "12345678901" not in out
    assert '"rate": "1380"' in out


def test_token_endpoint_errors_use_the_oauth2_shape():
    sess = _FakeSession({("POST", "/oauth2/token"): _Resp(401, {"error": "invalid_client", "error_description": "Client authentication failed."})})
    c = TossReadOnlyClient("cid", "wrong", session=sess)
    with pytest.raises(TossApiError) as ei:
        c.accounts()
    assert ei.value.code == "invalid_client" and "Client authentication failed" in str(ei.value)


def test_token_endpoint_403_names_the_ip_allowlist():
    sess = _FakeSession({("POST", "/oauth2/token"): _Resp(403, {"error": "access_denied", "error_description": "IP address not allowed"})})
    c = TossReadOnlyClient("cid", "cs", session=sess)
    with pytest.raises(TossApiError) as ei:
        c.accounts()
    assert ei.value.code == "access_denied" and "허용 IP" in str(ei.value)
