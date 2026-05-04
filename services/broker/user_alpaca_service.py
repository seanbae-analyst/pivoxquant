"""
PivoxQuant — Per-user Alpaca (US equity paper) service.

2026-04-22: Adds per-user Alpaca paper account linking alongside the existing
per-user KIS flow. We intentionally do NOT modify `autotrader.py` (frozen); its
env-var-driven `paper=True` Alpaca client remains the automation path. This
service is read-only observation:

  - verify(): sanity-check credentials by minting an account snapshot
  - get_account(): returns equity/cash/buying_power for display
  - sync_positions(): (best-effort) refresh last_synced_at + account snapshot

Keys are stored encrypted in `broker_connections` reusing the existing
`encrypted_app_key` / `encrypted_app_secret` columns (bound to broker='alpaca').

We force `paper=True` unconditionally. The `env` field on connect accepts
"paper" only — any attempt to pass "live" is rejected upstream in the route
and here defensively.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from extensions import db
from models.broker_connection import BrokerConnection
from services.crypto_service import decrypt, encrypt

logger = logging.getLogger(__name__)

_PAPER_BASE_URL = "https://paper-api.alpaca.markets"


class UserAlpacaError(Exception):
    """Raised for Alpaca errors that should surface to HTTP callers."""

    def __init__(self, code: str, message: str, http_status: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


class UserAlpacaService:
    """Per-user Alpaca paper trading client backed by encrypted credentials."""

    BROKER = "alpaca"

    def __init__(self, user_id: int, connection: Optional[BrokerConnection] = None):
        self.user_id = int(user_id)
        self._conn = connection or self._load_connection()
        if self._conn is None:
            raise UserAlpacaError(
                "NO_CONNECTION", "Alpaca account not connected.", 404
            )
        if not self._conn.is_active:
            raise UserAlpacaError(
                "INACTIVE", "Alpaca connection is inactive.", 410
            )
        try:
            self.key_id = decrypt(self._conn.encrypted_app_key)
            self.secret_key = decrypt(self._conn.encrypted_app_secret)
        except Exception as exc:
            logger.error("UserAlpaca decrypt failed user_id=%s: %s", user_id, exc)
            raise UserAlpacaError(
                "DECRYPT_FAILED",
                "Could not decrypt stored Alpaca credentials. Please reconnect.",
                500,
            ) from exc

    # ── Helpers ───────────────────────────────────────────────────────────

    def _load_connection(self) -> Optional[BrokerConnection]:
        return BrokerConnection.query.filter_by(
            user_id=self.user_id, broker=self.BROKER, is_active=True
        ).first()

    def _record_failure(self, status: str, error: str) -> None:
        self._conn.last_sync_status = status
        self._conn.last_sync_error = (error or "")[:500] or None
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

    def _trading_client(self):
        """Instantiate an alpaca-py TradingClient in paper mode.

        Raises UserAlpacaError with BROKER_DOWN on import/connection errors.
        """
        try:
            from alpaca.trading.client import TradingClient  # type: ignore
        except Exception as exc:  # pragma: no cover — missing dep
            logger.error("alpaca-py not importable: %s", exc)
            raise UserAlpacaError(
                "BROKER_DOWN",
                "Alpaca SDK unavailable on the server.",
                503,
            ) from exc
        try:
            return TradingClient(self.key_id, self.secret_key, paper=True)
        except Exception as exc:  # pragma: no cover
            logger.warning("Alpaca TradingClient init failed: %s", exc)
            raise UserAlpacaError(
                "BROKER_DOWN",
                "Could not reach Alpaca paper API.",
                502,
            ) from exc

    # ── Public: verify ────────────────────────────────────────────────────

    def verify(self) -> dict:
        """Hit /v2/account once to confirm credentials are valid.

        Returns {"ok": True, "account": {...}} or {"ok": False, "code", "error"}.
        Never raises for network errors — caller decides.
        """
        try:
            client = self._trading_client()
            account = client.get_account()
        except UserAlpacaError as exc:
            self._record_failure(exc.code.lower(), exc.message)
            return {"ok": False, "code": exc.code, "error": exc.message}
        except Exception as exc:  # auth errors typically surface here
            msg = str(exc)
            logger.warning("Alpaca verify failed user_id=%s: %s", self.user_id, msg)
            code = "INVALID_CREDENTIALS" if "40" in msg else "BROKER_DOWN"
            self._record_failure(code.lower(), msg)
            return {
                "ok": False,
                "code": code,
                "error": "Alpaca rejected these keys. Check the key/secret and try again."
                if code == "INVALID_CREDENTIALS"
                else "Alpaca is unreachable. Please retry in a moment.",
            }

        snapshot = {
            "account_number": getattr(account, "account_number", None),
            "equity": _to_float(getattr(account, "equity", None)),
            "cash": _to_float(getattr(account, "cash", None)),
            "buying_power": _to_float(getattr(account, "buying_power", None)),
            "status": getattr(account, "status", None),
        }
        self._record_success("ok")
        return {"ok": True, "account": snapshot}

    # ── Public: sync ──────────────────────────────────────────────────────

    def sync_account(self) -> dict:
        """Light-touch sync: refresh account snapshot + touch last_synced_at.

        Position mirroring is out of scope for this release — Alpaca is
        observation-only here and `positions` table stays per-user KIS-only.
        """
        result = self.verify()
        if not result.get("ok"):
            return result
        return {
            "ok": True,
            "synced_at": self._conn.last_synced_at.isoformat()
            if self._conn.last_synced_at
            else None,
            "account": result["account"],
        }


# ── Module-level CRUD helpers ────────────────────────────────────────────


def upsert_alpaca_connection(
    *,
    user_id: int,
    key_id: str,
    secret_key: str,
    display_name: Optional[str] = None,
) -> BrokerConnection:
    """Create or update the user's Alpaca connection row (paper only)."""
    conn = BrokerConnection.query.filter_by(
        user_id=user_id, broker="alpaca"
    ).first()
    if conn is None:
        conn = BrokerConnection(user_id=user_id, broker="alpaca")
        db.session.add(conn)

    conn.encrypted_app_key = encrypt(key_id)
    conn.encrypted_app_secret = encrypt(secret_key)
    conn.is_paper = True
    conn.is_active = True
    conn.display_name = display_name or "Alpaca · Paper"
    conn.consecutive_failures = 0
    conn.last_sync_error = None
    conn.last_sync_status = None
    db.session.commit()
    return conn


def delete_alpaca_connection(user_id: int) -> bool:
    """Remove the user's Alpaca connection row. Returns True if one existed."""
    conn = BrokerConnection.query.filter_by(
        user_id=user_id, broker="alpaca"
    ).first()
    if conn is None:
        return False
    db.session.delete(conn)
    db.session.commit()
    return True


def _to_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        logger.debug("silent-fallback: _to_float", exc_info=True)
        return None
