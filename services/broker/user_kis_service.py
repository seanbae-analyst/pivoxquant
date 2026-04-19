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
from datetime import datetime, timedelta
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
_REQUEST_TIMEOUT = 10


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
            logger.error(f"UserKIS decrypt failed user_id={user_id}: {exc}")
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
        self._conn.token_expires_at = datetime.utcnow() + timedelta(
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
            and self._conn.token_expires_at > datetime.utcnow()
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
        self._conn.last_sync_status = status
        self._conn.last_sync_error = error[:500] if error else None
        self._conn.consecutive_failures = (self._conn.consecutive_failures or 0) + 1
        if self._conn.consecutive_failures >= 3:
            self._conn.is_active = False
        db.session.commit()

    def _record_success(self, status: str = "ok") -> None:
        self._conn.last_sync_status = status
        self._conn.last_sync_error = None
        self._conn.consecutive_failures = 0
        self._conn.last_synced_at = datetime.utcnow()
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
            logger.warning(f"UserKIS token HTTP error user_id={self.user_id}: {exc}")
            self._record_failure("broker_down", f"network: {exc}")
            return {
                "ok": False,
                "code": "BROKER_DOWN",
                "error": "증권사 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
            }

        if not resp.ok:
            snippet = resp.text[:200] if resp.text else ""
            logger.warning(
                f"UserKIS token HTTP {resp.status_code} user_id={self.user_id}: {snippet}"
            )
            # KIS "EGW00133" = 1분 1회 제한
            if "EGW00133" in snippet:
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

    def get_balance(self) -> dict:
        """한투 계좌 잔고 조회 — 예수금 + 보유종목.

        Returns dict: `{"ok": True, "available_cash", "total_value", "positions": [...]}`
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
            logger.warning(f"UserKIS balance HTTP error user_id={self.user_id}: {exc}")
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

    def get_positions(self) -> list[dict]:
        """Convenience — returns just the positions list. Empty on error."""
        data = self.get_balance()
        return data.get("positions", []) if data.get("ok") else []

    # ── Public: sync to DB ────────────────────────────────────────────────

    def sync_to_db(self) -> dict:
        """Fetch balance and upsert into `positions` table for this user.

        Normalization: Korean 6-digit codes are stored with '.KS' suffix to match
        the convention used by the rest of PivoxQuant.
        """
        balance = self.get_balance()
        if not balance.get("ok"):
            return balance  # propagate error

        existing = Position.query.filter_by(user_id=self.user_id).all()
        existing_map = {p.ticker: p for p in existing}

        added, updated, synced = [], [], []
        for pos in balance["positions"]:
            raw = pos["ticker"]
            ticker = (
                raw if raw.endswith(".KS") or raw.endswith(".KQ") else f"{raw}.KS"
            )
            synced.append(ticker)

            if ticker in existing_map:
                db_pos = existing_map[ticker]
                if db_pos.shares != pos["shares"] or db_pos.avg_cost != pos["avg_cost"]:
                    db_pos.shares = pos["shares"]
                    db_pos.avg_cost = pos["avg_cost"]
                    updated.append(ticker)
            else:
                new_pos = Position(
                    user_id=self.user_id,
                    ticker=ticker,
                    shares=pos["shares"],
                    avg_cost=pos["avg_cost"],
                    buy_fx_rate=0.0,
                )
                db.session.add(new_pos)
                added.append(ticker)

        # Zero-out Korean positions that disappeared from the broker side.
        for ticker, db_pos in existing_map.items():
            is_kr = (
                ticker.endswith(".KS")
                or ticker.endswith(".KQ")
                or (ticker.isdigit() and len(ticker) == 6)
            )
            if is_kr and ticker not in synced and db_pos.shares > 0:
                db_pos.shares = 0

        db.session.commit()
        self._record_success()

        return {
            "ok": True,
            "added": added,
            "updated": updated,
            "synced": synced,
            "available_cash": balance["available_cash"],
            "total_value": balance["total_value"],
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
    conn.encryption_key_version = 1
    conn.consecutive_failures = 0
    conn.last_sync_status = None
    conn.last_sync_error = None
    conn.encrypted_access_token = None
    conn.token_expires_at = None
    db.session.commit()
    return conn


def delete_kis_connection(user_id: int) -> bool:
    """Hard-delete the user's KIS connection (and cascade-remove secrets)."""
    conn = BrokerConnection.query.filter_by(
        user_id=user_id, broker=UserKISService.BROKER
    ).first()
    if conn is None:
        return False
    db.session.delete(conn)
    db.session.commit()
    return True
