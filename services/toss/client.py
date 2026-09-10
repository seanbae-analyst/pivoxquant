"""Read-only HTTP client for the Toss Securities Open API.

Source of truth for paths and payloads: the server-owned OpenAPI document
``https://openapi.tossinvest.com/openapi-docs/latest/openapi.json``
(v1.2.15 at the time of writing, 2026-09-10). Key facts that shaped this file:

* Auth is OAuth 2.0 **Client Credentials**, form-encoded ``POST /oauth2/token``.
  No refresh token; ``expires_in`` seconds (example: 86400). **One valid token
  per client** — re-issuing invalidates the previous one, so two processes
  sharing one client id will keep revoking each other. Run one at a time.
* ``scopes: {}`` — there is no read-only grant. See package docstring.
* Account / asset / order-history calls need ``X-Tossinvest-Account: {accountSeq}``
  where ``accountSeq`` comes from ``GET /api/v1/accounts``.
* Rate limits are per client × group; ``AUTH`` 5/s, ``ACCOUNT`` 1/s. 429 carries
  ``Retry-After``. We retry 429 once after honouring it.
* The REST allowed-IP list also applies: a 403 ``edge-blocked`` usually means
  the caller's public IP is not registered under WTS 설정 → Open API.
* All numeric fields are **strings**. They are returned as-is here; the report
  layer converts with :class:`decimal.Decimal`.
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Iterator

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://openapi.tossinvest.com"
TOKEN_PATH = "/oauth2/token"

# The complete set of paths this client may request, and the only verb it may
# use for them. Anything else raises before a socket is opened. Order-capable
# paths (POST /api/v1/orders, */modify, */cancel, /conditional-orders …) are
# absent on purpose; do not add them.
READ_ONLY_PATHS: frozenset[str] = frozenset({
    "/api/v1/accounts",
    "/api/v1/holdings",
    "/api/v1/orders",              # GET only — list of past orders
    "/api/v1/orders/{orderId}",    # GET only — one past order
    "/api/v1/exchange-rate",
    "/api/v1/prices",
    "/api/v1/market-calendar/KR",
    "/api/v1/market-calendar/US",
})
_ORDER_ID_RE = re.compile(r"^/api/v1/orders/[A-Za-z0-9_\-]+$")

_SECRET_KEYS_RE = re.compile(
    r'("(?:access_token|client_secret|client_id|accountNo|authorization)"\s*:\s*")([^"]*)(")',
    re.IGNORECASE,
)


class TossReadOnlyViolation(RuntimeError):
    """Raised when code tries to use this client for anything but the allowlist."""


class TossApiError(RuntimeError):
    def __init__(self, status: int, code: str | None, message: str, request_id: str | None = None):
        super().__init__(f"Toss API {status} {code or '?'}: {message}")
        self.status = status
        self.code = code
        self.message = message
        self.request_id = request_id


def _mask(val: str | None) -> str:
    if not val:
        return "***"
    return "***" if len(val) <= 6 else f"{val[:3]}***{val[-2:]}"


def redact(text: str, max_len: int = 300) -> str:
    """Strip anything secret-shaped from a response body before it hits a log."""
    if not text:
        return ""
    out = _SECRET_KEYS_RE.sub(lambda m: f"{m.group(1)}{_mask(m.group(2))}{m.group(3)}", text)
    return out[:max_len]


def _normalise_path(path: str) -> str:
    """Collapse ``/api/v1/orders/<id>`` onto its allowlist template."""
    if _ORDER_ID_RE.match(path):
        return "/api/v1/orders/{orderId}"
    return path


class TossReadOnlyClient:
    """GET-only client. Construct with explicit credentials or from env.

    ``session`` may be any object with ``requests.Session.request`` semantics;
    tests inject a fake. ``sleep`` is injectable for the same reason.
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        *,
        base_url: str | None = None,
        session: Any | None = None,
        timeout: float = 15.0,
        sleep=time.sleep,
    ):
        self.client_id = client_id or os.environ.get("TOSS_CLIENT_ID", "").strip()
        self.client_secret = client_secret or os.environ.get("TOSS_CLIENT_SECRET", "").strip()
        self.base_url = (base_url or os.environ.get("TOSS_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout
        self._sleep = sleep
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    # ── auth ────────────────────────────────────────────────────────────────
    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _fetch_token(self) -> str:
        if not self.configured:
            raise TossApiError(0, "not-configured", "TOSS_CLIENT_ID / TOSS_CLIENT_SECRET not set")
        resp = self.session.request(
            "POST",
            f"{self.base_url}{TOKEN_PATH}",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise self._error_from(resp)
        body = resp.json()
        token = body.get("access_token")
        if not token:
            raise TossApiError(resp.status_code, "no-token", "token response had no access_token")
        expires_in = int(body.get("expires_in") or 0)
        # Refresh a minute early so a long report run never straddles expiry.
        self._token = token
        self._token_expires_at = time.time() + max(expires_in - 60, 30)
        logger.info("Toss token issued (client=%s, expires_in=%ss)", _mask(self.client_id), expires_in)
        return token

    def _bearer(self) -> str:
        if self._token and time.time() < self._token_expires_at:
            return self._token
        return self._fetch_token()

    # ── transport ────────────────────────────────────────────────────────────
    def _error_from(self, resp) -> TossApiError:
        code = msg = rid = None
        try:
            body = resp.json()
            err = body.get("error")
            if isinstance(err, dict):
                # BFF envelope: {"error": {"requestId", "code", "message", "data"}}
                code, msg, rid = err.get("code"), err.get("message"), err.get("requestId")
            elif isinstance(err, str):
                # /oauth2/token uses the OAuth2 shape: {"error": "invalid_client", "error_description": "..."}
                code, msg = err, body.get("error_description")
        except Exception:  # noqa: BLE001 — body may not be JSON
            pass
        if resp.status_code == 403:
            # Both shapes mean the same thing here: this IP is not on the client's allowlist.
            msg = (msg or "forbidden") + " — register this machine's public IP under WTS 설정 → Open API → 허용 IP 관리"
        return TossApiError(resp.status_code, code, msg or redact(getattr(resp, "text", "") or ""), rid)

    def _get(self, path: str, *, params: dict | None = None, account_seq: int | None = None) -> dict:
        """The only way out of this class. GET + allowlist, or raise."""
        if _normalise_path(path) not in READ_ONLY_PATHS:
            raise TossReadOnlyViolation(
                f"{path} is not on the read-only allowlist; this client never places, modifies or cancels orders"
            )
        url = f"{self.base_url}{path}"
        for attempt in (1, 2):
            # Fresh dict per attempt: the bearer may change between attempts.
            headers = {"Authorization": f"Bearer {self._bearer()}", "Accept": "application/json"}
            if account_seq is not None:
                headers["X-Tossinvest-Account"] = str(account_seq)
            resp = self.session.request("GET", url, params=params, headers=headers, timeout=self.timeout)
            if resp.status_code == 429 and attempt == 1:
                wait = float(resp.headers.get("Retry-After") or 1.0)
                logger.warning("Toss 429 on %s — waiting %.1fs", path, wait)
                self._sleep(wait)
                continue
            if resp.status_code == 401 and attempt == 1:
                # expired-token / token-revoked: drop the cached token so the
                # next attempt re-issues one.
                self._token = None
                continue
            break
        if resp.status_code != 200:
            raise self._error_from(resp)
        body = resp.json()
        if "result" not in body:
            raise TossApiError(200, "bad-envelope", f"missing result: {redact(str(body))}")
        return body["result"]

    def request(self, method: str, path: str, **_: Any):  # pragma: no cover - guard only
        """Explicitly unsupported: exists so a caller reaching for a generic
        verb gets a loud error rather than a silent ``AttributeError``."""
        raise TossReadOnlyViolation(f"{method.upper()} {path}: TossReadOnlyClient exposes GET helpers only")

    # ── read-only endpoints ──────────────────────────────────────────────────
    def accounts(self) -> list[dict]:
        """``GET /api/v1/accounts`` — only BROKERAGE accounts are returned today."""
        return self._get("/api/v1/accounts")

    def holdings(self, account_seq: int, symbol: str | None = None) -> dict:
        """``GET /api/v1/holdings`` — KR + US equities only (no options/bonds)."""
        params = {"symbol": symbol} if symbol else None
        return self._get("/api/v1/holdings", params=params, account_seq=account_seq)

    def orders_page(
        self,
        account_seq: int,
        *,
        status: str,
        date_from: str | None = None,
        date_to: str | None = None,
        cursor: str | None = None,
        limit: int = 100,
        symbol: str | None = None,
    ) -> dict:
        if status not in ("OPEN", "CLOSED"):
            raise ValueError("status must be OPEN or CLOSED")
        params: dict[str, Any] = {"status": status, "limit": min(max(limit, 1), 100)}
        if date_from:
            params["from"] = date_from
        if date_to:
            params["to"] = date_to
        if cursor:
            params["cursor"] = cursor
        if symbol:
            params["symbol"] = symbol
        return self._get("/api/v1/orders", params=params, account_seq=account_seq)

    def iter_closed_orders(
        self,
        account_seq: int,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        max_pages: int = 50,
    ) -> Iterator[dict]:
        """Walk ``status=CLOSED`` pages by cursor. Newest first, as the API returns them."""
        cursor = None
        for _ in range(max_pages):
            page = self.orders_page(account_seq, status="CLOSED", date_from=date_from, date_to=date_to, cursor=cursor)
            yield from page.get("orders", [])
            if not page.get("hasNext") or not page.get("nextCursor"):
                return
            cursor = page["nextCursor"]
        logger.warning("Toss closed-orders: stopped after %d pages (max_pages)", max_pages)

    def open_orders(self, account_seq: int) -> list[dict]:
        return self.orders_page(account_seq, status="OPEN").get("orders", [])

    def exchange_rate(self, base: str = "USD", quote: str = "KRW") -> dict:
        """Display rate, refreshed every minute. Not the execution rate."""
        return self._get("/api/v1/exchange-rate", params={"baseCurrency": base, "quoteCurrency": quote})

    def prices(self, symbols: list[str]) -> list[dict]:
        if not symbols:
            return []
        return self._get("/api/v1/prices", params={"symbols": ",".join(symbols[:200])})
