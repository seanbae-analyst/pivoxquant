"""
PivoxQuant — Per-user KIS (Korea Investment & Securities) service.

Week 1 scope (2026-04-18): user-scoped OAuth token management + balance sync.
This module is INTENTIONALLY separate from the legacy `kis_service.py`
(global singleton keyed off env vars) — it must not be modified per project
constraints.

Each `UserKISService(user_id)` instance:
  - Loads the user's BrokerConnection row for broker='kis'
  - Decrypts app_key / app_secret / account_no via services.crypto_service
  - Calls KIS `/oauth2/tokenP` to mint a 24-hour access_token (cached on row)
  - Fetches balance via VTTC8434R (mock) or TTTC8434R (real)
  - Upserts DB `positions` table (CASCADE-safe, only user's rows)

Environment toggle:
  - KIS_USE_REAL=1 -> real endpoint (openapi.koreainvestment.com:9443, TTTC8434R)
  - otherwise       -> mock (openapivts.koreainvestment.com:29443, VTTC8434R)

If `requests` / network is unavailable, `authenticate()` returns a descriptive
error dict rather than raising — callers surface a friendly message to the
user and log details.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from extensions import db
from models.broker_connection import BrokerConnection
from models.position import Position
from services.crypto_service import decrypt, encrypt

logger = logging.getLogger(__name__)

_USE_REAL = os.environ.get("KIS_USE_REAL", "").strip() in ("1", "true", "True")
_BASE_URL = (
    "https://openapi.koreainvestment.com:9443"
    if _USE_REAL
    else "https://openapivts.koreainvestment.com:29443"
)
_TR_ID_BALANCE = "TTTC8434R" if _USE_REAL else "VTTC8434R"
_TR_ID_OVERSEAS_BALANCE = "TTTS3012R" if _USE_REAL else "VTTS3012R"
_REQUEST_TIMEOUT = 10

# 해외거래소 — 미국 커버 (NASDAQ + NYSE + AMEX)
_US_EXCHANGES = ("NASD", "NYSE", "AMEX")


# ── Sensitive-data masking (H3/H4, 2026-04-24) ─────────────────────────────
# Keys that may appear in JSON error responses or raw text from KIS. When we
# snapshot response text for a log line we must redact these so app_key /
# app_secret / account_no / tokens don't leak to stdout / log aggregators.
_SENSITIVE_KEY_PATTERNS = re.compile(
    r'("(?:appkey|appsecret|app_key|app_secret|access_token|approval_key|'
    r'authorization|CANO|ACNT_PRDT_CD|ACNT_NO|account_no|token|secret)"\s*:\s*")'
    r'([^"]*)(")',
    re.IGNORECASE,
)
# Bare 6-20 digit account-number-like runs (KIS 계좌번호 = 8 digits + 2-digit prod).
_BARE_ACCOUNT_RE = re.compile(r"\b(\d{6,20})\b")


def _mask_token(val: str) -> str:
    """Return a length-preserving redacted form: first 4 + '***' + last 2, or '***' if short."""
    if not val:
        return "***"
    if len(val) <= 6:
        return "***"
    return f"{val[:4]}***{val[-2:]}"


def _redact_response_snippet(text: str, max_len: int = 200) -> str:
    """Redact sensitive JSON values + bare account numbers, then truncate.

    Safe to log. Preserves error_code / msg1 / non-secret fields so operators
    can still diagnose. Returns '' for empty input.
    """
    if not text:
        return ""
    # Redact JSON string values for known sensitive keys.
    redacted = _SENSITIVE_KEY_PATTERNS.sub(
        lambda m: f'{m.group(1)}{_mask_token(m.group(2))}{m.group(3)}',
        text,
    )
    # Redact any bare long digit runs that might be a 계좌번호 echoed in an
    # error message. Keep 4-5 digit codes (HTTP status / error codes) alone.
    redacted = _BARE_ACCOUNT_RE.sub(lambda m: _mask_token(m.group(1)), redacted)
    return redacted[:max_len]


def _mask_account_no(account_no: str) -> str:
    """Mask a KIS account number for logs: show only last 4 digits."""
    if not account_no:
        return "***"
    s = str(account_no)
    if len(s) <= 4:
        return "***"
    return f"***{s[-4:]}"


class UserKISError(Exception):
    """Raised for broker errors that should be surfaced to callers."""

    def __init__(self, code: str, message: str, http_status: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


class UserKISService:
    """Per-user KIS client backed by encrypted credentials in `broker_connections`."""

    BROKER = "kis"

    def __init__(self, user_id: int, connection: Optional[BrokerConnection] = None):
        self.user_id = int(user_id)
        self._conn = connection or self._load_connection()
        if self._conn is None:
            raise UserKISError("NO_CONNECTION", "KIS 계정이 연결되지 않았습니다.", 404)
        if not self._conn.is_active:
            raise UserKISError("INACTIVE", "KIS 연결이 비활성화 상태입니다.", 410)

        self.base_url = _BASE_URL
        # Decrypt lazily and cache on the instance only (never logged).
        try:
            self.app_key = decrypt(self._conn.encrypted_app_key)
            self.app_secret = decrypt(self._conn.encrypted_app_secret)
            self.account_no = decrypt(self._conn.encrypted_account_no)
        except Exception as exc:
            logger.error("UserKIS decrypt failed user_id=%s: %s", user_id, exc)
            raise UserKISError(
                "DECRYPT_FAILED",
                "KIS 자격 증명을 복호화할 수 없습니다. 재연결이 필요합니다.",
                500,
            ) from exc
        self.account_prod = (self._conn.account_prod or "01").strip()
        self._access_token: Optional[str] = None

    # ── Helpers ───────────────────────────────────────────────────────────

    def _load_connection(self) -> Optional[BrokerConnection]:
        return BrokerConnection.query.filter_by(
            user_id=self.user_id, broker=self.BROKER, is_active=True
        ).first()

    def _save_token(self, token: str, expires_in: int) -> None:
        self._conn.encrypted_access_token = encrypt(token)
        self._conn.token_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            seconds=max(0, int(expires_in) - 60)
        )
        db.session.commit()
        self._access_token = token

    def _cached_token(self) -> Optional[str]:
        if self._access_token:
            return self._access_token
        if (
            self._conn.encrypted_access_token
            and self._conn.token_expires_at
            and self._conn.token_expires_at > datetime.now(timezone.utc).replace(tzinfo=None)
        ):
            try:
                self._access_token = decrypt(self._conn.encrypted_access_token)
                return self._access_token
            except Exception as exc:
                logger.warning(
                    f"UserKIS cached token decrypt failed (user_id={self.user_id}): {exc}"
                )
                return None
        return None

    def _record_failure(self, status: str, error: str) -> None:
        # Redact any incidentally-captured secrets before persisting the error
        # string to the DB (where it surfaces via /api/broker/kis/status).
        self._conn.last_sync_status = status
        self._conn.last_sync_error = (
            _redact_response_snippet(error, max_len=500) if error else None
        )
        self._conn.consecutive_failures = (self._conn.consecutive_failures or 0) + 1
        if self._conn.consecutive_failures >= 3:
            self._conn.is_active = False
        db.session.commit()

    def _record_success(self, status: str = "ok") -> None:
        self._conn.last_sync_status = status
        self._conn.last_sync_error = None
        self._conn.consecutive_failures = 0
        self._conn.last_synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()

    # ── Public: authenticate ──────────────────────────────────────────────

    def authenticate(self, force: bool = False) -> dict:
        """Mint (or reuse) a KIS access_token.

        Returns `{"ok": True, "token_cached": bool}` on success, or
        `{"ok": False, "code": ..., "error": ...}` on failure (never raises
        for network errors — caller decides).
        """
        if not force:
            cached = self._cached_token()
            if cached:
                return {"ok": True, "token_cached": True}

        try:
            resp = requests.post(
                f"{self.base_url}/oauth2/tokenP",
                headers={"Content-Type": "application/json"},
                data=json.dumps(
                    {
                        "grant_type": "client_credentials",
                        "appkey": self.app_key,
                        "appsecret": self.app_secret,
                    }
                ),
                timeout=_REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.warning("UserKIS token HTTP error user_id=%s: %s", self.user_id, exc)
            self._record_failure("broker_down", f"network: {exc}")
            return {
                "ok": False,
                "code": "BROKER_DOWN",
                "error": "증권사 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
            }

        if not resp.ok:
            raw_snippet = resp.text or ""
            # Safe-to-log redacted snippet (H3): removes appkey/appsecret/token
            # if KIS ever echoes the request body back in an error response.
            safe_snippet = _redact_response_snippet(raw_snippet, max_len=200)
            logger.warning(
                f"UserKIS token HTTP {resp.status_code} user_id={self.user_id}: {safe_snippet}"
            )
            # KIS "EGW00133" = 1분 1회 제한. Match against the *raw* snippet so
            # the error-code detection is unaffected by redaction.
            if "EGW00133" in raw_snippet:
                return {
                    "ok": False,
                    "code": "RATE_LIMITED",
                    "error": "KIS 토큰 발급은 1분에 1회만 가능합니다. 잠시 후 다시 시도해 주세요.",
                }
            self._record_failure("token_expired", f"http_{resp.status_code}")
            return {
                "ok": False,
                "code": "INVALID_CREDENTIALS",
                "error": "KIS 인증에 실패했습니다. APP KEY/SECRET을 확인해 주세요.",
            }

        data = resp.json()
        token = data.get("access_token")
        expires_in = int(data.get("expires_in") or 86400)
        if not token:
            self._record_failure("token_expired", "no access_token in response")
            return {
                "ok": False,
                "code": "INVALID_CREDENTIALS",
                "error": "KIS 응답에 access_token이 없습니다.",
            }
        self._save_token(token, expires_in)
        return {"ok": True, "token_cached": False, "expires_in": expires_in}

    # ── Public: balance ──────────────────────────────────────────────────

    def _auth_headers(self) -> Optional[dict]:
        token = self._cached_token()
        if not token:
            result = self.authenticate()
            if not result.get("ok"):
                return None
            token = self._access_token
        return {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }

    def _inquire_domestic_balance(self) -> dict:
        """국내주식 잔고 조회 — inquire-balance endpoint.

        Returns the same shape as the previous monolithic `get_balance()`:
        `{"ok": True, "available_cash", "total_value", "positions": [...]}`
        or `{"ok": False, "code", "error"}`.
        """
        headers = self._auth_headers()
        if headers is None:
            return {
                "ok": False,
                "code": "TOKEN_EXPIRED",
                "error": "KIS 토큰이 만료되었습니다. 재연결해 주세요.",
            }
        headers["tr_id"] = _TR_ID_BALANCE

        params = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": self.account_prod,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        try:
            resp = requests.get(
                f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance",
                headers=headers,
                params=params,
                timeout=_REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.warning("UserKIS balance HTTP error user_id=%s: %s", self.user_id, exc)
            self._record_failure("broker_down", f"network: {exc}")
            return {"ok": False, "code": "BROKER_DOWN", "error": "증권사 연결 실패."}

        if not resp.ok:
            logger.warning(
                f"UserKIS balance HTTP {resp.status_code} user_id={self.user_id}"
            )
            self._record_failure("broker_down", f"http_{resp.status_code}")
            return {
                "ok": False,
                "code": "BROKER_DOWN",
                "error": f"KIS API 오류 ({resp.status_code})",
            }

        body = resp.json()
        if body.get("rt_cd") != "0":
            msg = body.get("msg1", "Unknown KIS error")
            self._record_failure("broker_down", msg[:120])
            return {"ok": False, "code": "BROKER_DOWN", "error": msg}

        positions = []
        for item in body.get("output1", []) or []:
            qty = int(item.get("hldg_qty", 0) or 0)
            if qty <= 0:
                continue
            positions.append(
                {
                    "ticker": item.get("pdno", ""),
                    "name": item.get("prdt_name", ""),
                    "shares": qty,
                    "avg_cost": float(item.get("pchs_avg_pric", 0) or 0),
                    "current_price": float(item.get("prpr", 0) or 0),
                    "pnl": float(item.get("evlu_pfls_amt", 0) or 0),
                    "pnl_pct": float(item.get("evlu_pfls_rt", 0) or 0),
                    "currency": "KRW",
                    "market": "KR",
                }
            )
        output2 = body.get("output2") or [{}]
        balance_info = output2[0] if isinstance(output2, list) and output2 else output2
        return {
            "ok": True,
            "available_cash": float(balance_info.get("dnca_tot_amt", 0) or 0),
            "total_value": float(balance_info.get("tot_evlu_amt", 0) or 0),
            "positions": positions,
        }

    def _inquire_overseas_balance(self, exchange_code: str) -> dict:
        """단일 해외거래소 잔고 조회 (NASD/NYSE/AMEX 등).

        Returns `{"ok": True, "positions": [...], "summary": {...}}` or
        `{"ok": False, "code", "error"}`. Empty holdings → positions=[].
        """
        headers = self._auth_headers()
        if headers is None:
            return {
                "ok": False,
                "code": "TOKEN_EXPIRED",
                "error": "KIS 토큰이 만료되었습니다. 재연결해 주세요.",
            }
        headers["tr_id"] = _TR_ID_OVERSEAS_BALANCE

        params = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": self.account_prod,
            "OVRS_EXCG_CD": exchange_code,
            "TR_CRCY_CD": "USD",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": "",
        }
        try:
            resp = requests.get(
                f"{self.base_url}/uapi/overseas-stock/v1/trading/inquire-balance",
                headers=headers,
                params=params,
                timeout=_REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.warning(
                f"UserKIS overseas balance HTTP error user_id={self.user_id} "
                f"exch={exchange_code}: {exc}"
            )
            return {
                "ok": False,
                "code": "BROKER_DOWN",
                "error": f"해외 증권사 연결 실패 ({exchange_code}).",
            }

        if not resp.ok:
            logger.warning(
                f"UserKIS overseas balance HTTP {resp.status_code} "
                f"user_id={self.user_id} exch={exchange_code}"
            )
            return {
                "ok": False,
                "code": "BROKER_DOWN",
                "error": f"KIS 해외 API 오류 ({resp.status_code})",
            }

        body = resp.json()
        if body.get("rt_cd") != "0":
            msg = body.get("msg1", "Unknown KIS overseas error")
            # 해외 계좌 미개설 케이스는 에러가 아닌 빈 결과로 처리
            return {
                "ok": False,
                "code": "BROKER_DOWN",
                "error": msg,
            }

        positions = []
        for item in body.get("output1", []) or []:
            try:
                qty = float(item.get("ovrs_cblc_qty", 0) or 0)
            except (TypeError, ValueError):
                qty = 0.0
            if qty <= 0:
                continue
            ticker = (item.get("ovrs_pdno") or "").strip()
            if not ticker:
                continue
            positions.append(
                {
                    "ticker": ticker,
                    "name": item.get("ovrs_item_name", ""),
                    "shares": qty,
                    "avg_cost": float(item.get("pchs_avg_pric", 0) or 0),
                    "current_price": float(item.get("now_pric2", 0) or 0),
                    "pnl": float(item.get("evlu_pfls_amt", 0) or 0),
                    "pnl_pct": float(item.get("evlu_pfls_rt", 0) or 0),
                    "currency": (item.get("tr_crcy_cd") or "USD").upper(),
                    "market": "US",
                    "exchange": (item.get("ovrs_excg_cd") or exchange_code).upper(),
                    "evlu_amt_usd": float(item.get("evlu_amt", 0) or 0),
                    "frcr_pchs_amt_usd": float(item.get("frcr_pchs_amt1", 0) or 0),
                }
            )

        output2 = body.get("output2") or {}
        if isinstance(output2, list):
            output2 = output2[0] if output2 else {}
        summary = {
            "frcr_pchs_amt1": float(output2.get("frcr_pchs_amt1", 0) or 0),
            "tot_evlu_pfls_amt": float(output2.get("tot_evlu_pfls_amt", 0) or 0),
        }
        return {"ok": True, "positions": positions, "summary": summary}

    def _inquire_all_overseas_balances(self) -> dict:
        """NASD + NYSE + AMEX 3개 거래소 잔고를 병합.

        Returns `{"ok": True, "positions": [...], "total_purchase_usd", "total_pnl_usd"}`.
        개별 거래소 실패는 warning-log 후 skip (부분 성공 허용).
        모두 실패하면 `ok=False`. 해외 계좌 자체가 없으면 빈 리스트 반환.
        """
        merged: list[dict] = []
        total_purchase_usd = 0.0
        total_pnl_usd = 0.0
        successes = 0
        failures = 0
        last_error = None

        for exch in _US_EXCHANGES:
            result = self._inquire_overseas_balance(exch)
            if not result.get("ok"):
                failures += 1
                last_error = result.get("error")
                logger.info(
                    f"UserKIS overseas {exch} skipped user_id={self.user_id}: "
                    f"{result.get('error')}"
                )
                continue
            successes += 1
            merged.extend(result.get("positions", []))
            summary = result.get("summary") or {}
            total_purchase_usd += float(summary.get("frcr_pchs_amt1", 0) or 0)
            total_pnl_usd += float(summary.get("tot_evlu_pfls_amt", 0) or 0)

        if successes == 0:
            return {
                "ok": False,
                "code": "BROKER_DOWN",
                "error": last_error or "해외주식 잔고 조회 실패",
                "positions": [],
            }
        return {
            "ok": True,
            "positions": merged,
            "total_purchase_usd": total_purchase_usd,
            "total_pnl_usd": total_pnl_usd,
        }

    def get_balance(self) -> dict:
        """한투 계좌 잔고 — 국내 + 해외 통합.

        Returns:
            {
                "ok": True,
                "available_cash": KRW 예수금,
                "total_value": KRW 평가액 (국내 원화 기준; 해외는 USD→KRW 환산 합산),
                "positions": [국내 + 해외 통합 리스트],
                "overseas_total_usd": 해외 매입액 USD,
                "fx_rate": 환산에 사용된 환율 (USD/KRW),
                "currency_breakdown": {"KRW": ..., "USD": ...},
            }
            or `{"ok": False, "code", "error"}`.

        국내 조회 실패 → 전체 실패. 해외만 부분 실패는 partial 결과 반환.
        """
        domestic = self._inquire_domestic_balance()
        if not domestic.get("ok"):
            # 국내 실패 시 해외도 인증 토큰을 공유하므로 전체 실패로 처리.
            return domestic

        overseas = self._inquire_all_overseas_balances()
        overseas_positions = overseas.get("positions", []) if overseas.get("ok") else []

        # 환율 (USD→KRW). fx_service 재활용, 실패 시 기본값.
        try:
            from services import fx_service
            fx_rate = float(fx_service.get_rate() or 0) or 1380.0
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("fx_service.get_rate failed: %s", exc)
            fx_rate = 1380.0

        overseas_value_usd = sum(
            float(p.get("evlu_amt_usd", 0) or 0) for p in overseas_positions
        )
        overseas_value_krw = overseas_value_usd * fx_rate

        merged_positions = list(domestic.get("positions", [])) + list(overseas_positions)

        return {
            "ok": True,
            "available_cash": domestic["available_cash"],
            "total_value": domestic["total_value"] + overseas_value_krw,
            "total_value_krw": domestic["total_value"] + overseas_value_krw,
            "positions": merged_positions,
            "overseas_total_usd": overseas_value_usd,
            "overseas_purchase_usd": overseas.get("total_purchase_usd", 0.0) if overseas.get("ok") else 0.0,
            "fx_rate": fx_rate,
            "currency_breakdown": {
                "KRW": domestic["total_value"],
                "USD": overseas_value_usd,
            },
            "overseas_partial_failure": not overseas.get("ok"),
        }

    def get_positions(self) -> list[dict]:
        """Convenience — returns just the positions list. Empty on error."""
        data = self.get_balance()
        return data.get("positions", []) if data.get("ok") else []

    # ── Public: sync to DB ────────────────────────────────────────────────

    def sync_to_db(self, max_new_positions: Optional[int] = None) -> dict:
        """Fetch balance (국내 + 해외) and upsert into `positions` table.

        Normalization rules:
          - KR 6-digit codes → append `.KS` suffix (기존 컨벤션)
          - US tickers (해외 — NASD/NYSE/AMEX) → suffix 없음 (`AAPL`, `SPY`, ...)

        KIS를 소스 of truth로 간주 — shares/avg_cost는 매 sync마다 덮어씀.
        매입 환율(`buy_fx_rate`)은 KIS가 제공하지 않으므로, 신규 생성 시만 현재 환율을 저장하고
        기존 포지션은 그대로 유지한다.

        Tier cap (2026-05-22): `max_new_positions` limits how many *brand-new*
        rows may be inserted (free 티어 3-position cap). Existing positions are
        always upserted (shares/avg_cost refresh) regardless of the cap — the
        cap only governs NEW inserts so a free user cannot bypass the 3-position
        limit via broker reconcile. `None` means unlimited (paid tiers). The
        number of new inserts skipped is reported as `capped`.
        """
        balance = self.get_balance()
        if not balance.get("ok"):
            return balance  # propagate error

        fx_rate = float(balance.get("fx_rate") or 0) or 0.0

        existing = Position.query.filter_by(user_id=self.user_id).all()
        existing_map = {p.ticker: p for p in existing}

        # Remaining budget for NEW inserts. `None` → unlimited.
        new_budget = max_new_positions
        capped_tickers: list[str] = []

        added, updated, synced = [], [], []
        overseas_synced = set()
        for pos in balance["positions"]:
            raw = (pos.get("ticker") or "").strip()
            if not raw:
                continue
            market = pos.get("market")
            is_overseas = market == "US" or pos.get("currency") == "USD"

            if is_overseas:
                # US 티커는 suffix 없이 그대로 (AAPL, SPY, JPM, ...)
                ticker = raw.upper()
            else:
                ticker = (
                    raw if raw.endswith(".KS") or raw.endswith(".KQ") else f"{raw}.KS"
                )

            if ticker in existing_map:
                # Existing position → always upsert (tier cap never blocks an
                # update; it only governs brand-new inserts).
                db_pos = existing_map[ticker]
                if db_pos.shares != pos["shares"] or db_pos.avg_cost != pos["avg_cost"]:
                    db_pos.shares = pos["shares"]
                    db_pos.avg_cost = pos["avg_cost"]
                    # 해외이고 기존 buy_fx_rate가 비어있으면 현재 환율로 임시 저장
                    if is_overseas and fx_rate > 0 and (
                        not db_pos.buy_fx_rate or db_pos.buy_fx_rate <= 0
                    ):
                        db_pos.buy_fx_rate = fx_rate
                    updated.append(ticker)
                synced.append(ticker)
                if is_overseas:
                    overseas_synced.add(ticker)
            else:
                # Brand-new position. Enforce the tier cap on inserts only.
                if new_budget is not None and new_budget <= 0:
                    capped_tickers.append(ticker)
                    # Skip insert; do NOT mark as synced so zero-out logic and
                    # the response treat it as not-imported.
                    continue
                new_pos = Position(
                    user_id=self.user_id,
                    ticker=ticker,
                    shares=pos["shares"],
                    avg_cost=pos["avg_cost"],
                    buy_fx_rate=fx_rate if is_overseas else 0.0,
                )
                db.session.add(new_pos)
                added.append(ticker)
                synced.append(ticker)
                if is_overseas:
                    overseas_synced.add(ticker)
                if new_budget is not None:
                    new_budget -= 1

        # Zero-out Korean positions that disappeared from the broker side.
        synced_set = set(synced)
        for ticker, db_pos in existing_map.items():
            is_kr = (
                ticker.endswith(".KS")
                or ticker.endswith(".KQ")
                or (ticker.isdigit() and len(ticker) == 6)
            )
            if is_kr and ticker not in synced_set and db_pos.shares > 0:
                db_pos.shares = 0

        # Zero-out overseas (US) positions that disappeared — only if overseas
        # fetch succeeded. On overseas partial failure we keep existing rows
        # untouched to avoid data loss.
        if not balance.get("overseas_partial_failure"):
            for ticker, db_pos in existing_map.items():
                # US ticker heuristic: suffix 없음 + 알파벳 대문자 1~6자리 (dot/hyphen 허용)
                is_us = (
                    not ticker.endswith(".KS")
                    and not ticker.endswith(".KQ")
                    and not (ticker.isdigit() and len(ticker) == 6)
                    and any(c.isalpha() for c in ticker)
                )
                if is_us and ticker not in overseas_synced and db_pos.shares > 0:
                    db_pos.shares = 0

        db.session.commit()
        self._record_success()

        return {
            "ok": True,
            "added": added,
            "updated": updated,
            "synced": synced,
            "capped": capped_tickers,
            "available_cash": balance["available_cash"],
            "total_value": balance["total_value"],
            "fx_rate": fx_rate,
            "overseas_total_usd": balance.get("overseas_total_usd", 0.0),
            "overseas_partial_failure": balance.get("overseas_partial_failure", False),
        }


# ── Helpers for the OAuth routes ─────────────────────────────────────────


def upsert_kis_connection(
    user_id: int,
    *,
    app_key: str,
    app_secret: str,
    account_no: str,
    account_prod: str = "01",
    display_name: Optional[str] = None,
    is_paper: Optional[bool] = None,
) -> BrokerConnection:
    """Insert or update a user's KIS BrokerConnection with encrypted creds."""
    conn = BrokerConnection.query.filter_by(
        user_id=user_id, broker=UserKISService.BROKER
    ).first()
    if conn is None:
        conn = BrokerConnection(user_id=user_id, broker=UserKISService.BROKER)
        db.session.add(conn)

    conn.encrypted_app_key = encrypt(app_key.strip())
    conn.encrypted_app_secret = encrypt(app_secret.strip())
    conn.encrypted_account_no = encrypt(account_no.strip())
    conn.account_prod = (account_prod or "01").strip()
    conn.display_name = display_name or "내 한국투자증권 계좌"
    conn.is_paper = (not _USE_REAL) if is_paper is None else bool(is_paper)
    conn.is_active = True
    conn.account_id = f"***{account_no[-4:]}" if len(account_no) >= 4 else None
    # 2026-05-18 Wave G-2 P1 Bug #1 (partial admit): encryption_key_version
    # column is currently schema theater — every row is hardcoded to 1.
    # A real multi-version key ring (decrypt_versioned + per-version env vars
    # PIVOX_BROKER_ENCRYPTION_KEY_V{n} loaded into a dict) is a separate wave.
    # As-is, rotating PIVOX_BROKER_ENCRYPTION_KEY makes ALL broker_connections
    # rows permanently unreadable on next decrypt. Operators must run a
    # re-encrypt migration script BEFORE rotating the key (external action
    # carry-over). We set the column explicitly here (not via default) so the
    # write site is greppable when the ring is implemented.
    conn.encryption_key_version = 1
    conn.consecutive_failures = 0
    conn.last_sync_status = None
    conn.last_sync_error = None
    conn.encrypted_access_token = None
    conn.token_expires_at = None
    db.session.commit()
    return conn


def _revoke_kis_token(app_key: str, app_secret: str, token: str) -> None:
    """POST KIS /oauth2/revokeP. Best-effort — never raises.

    KIS access_tokens have a 24-hour TTL and are NOT invalidated server-side
    when we delete our local copy. Without an explicit revoke, a stale token
    can still hit KIS APIs for up to 24h after the user "disconnects" — that
    is a security surface that contradicts user intent.

    We swallow all exceptions: a failed revoke must not block the local row
    deletion (sovereignty: user intent to disconnect wins over our cleanup).
    """
    url = f"{_BASE_URL}/oauth2/revokeP"
    try:
        r = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "appkey": app_key,
                "appsecret": app_secret,
                "token": token,
            }),
            timeout=5,
        )
        if r.status_code != 200:
            logger.warning(
                "KIS revoke non-200: status=%s body=%s",
                r.status_code,
                _redact_response_snippet(r.text or "", max_len=200),
            )
    except requests.RequestException as exc:
        logger.warning("KIS revoke network error: %s", exc)
    except Exception as exc:  # pragma: no cover — defensive (must not raise)
        logger.warning("KIS revoke unexpected error: %s", exc)


def delete_kis_connection(user_id: int) -> bool:
    """Hard-delete the user's KIS connection (and cascade-remove secrets).

    2026-05-18 Wave G-2 P1 Bug #2: before deleting the row we attempt to
    revoke the access_token at KIS. The token has a 24h TTL — without revoke
    a leaked/cached copy stays usable for up to 24h after disconnect. Revoke
    is best-effort: failures are logged but never block row deletion.
    """
    conn = BrokerConnection.query.filter_by(
        user_id=user_id, broker=UserKISService.BROKER
    ).first()
    if conn is None:
        return False

    # Best-effort token revoke. Decrypt failures or missing tokens just skip
    # the revoke step — the row deletion still proceeds.
    if conn.encrypted_access_token:
        try:
            access_token = decrypt(conn.encrypted_access_token)
            app_key = decrypt(conn.encrypted_app_key)
            app_secret = decrypt(conn.encrypted_app_secret)
            _revoke_kis_token(app_key, app_secret, access_token)
        except Exception as exc:
            logger.warning(
                "KIS pre-delete token decrypt failed (skipping revoke) "
                "user_id=%s: %s",
                user_id,
                exc,
            )

    db.session.delete(conn)
    db.session.commit()
    return True
