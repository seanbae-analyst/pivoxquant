"""
PivoxQuant — Broker Sync Service
Syncs positions and balance from Alpaca (paper trading) into the local DB.
"""

import os
import logging
from datetime import datetime

from extensions import db
from models.position import Position
from models.broker_connection import BrokerConnection
from models.user import User

logger = logging.getLogger(__name__)


class BrokerSyncService:
    """Fetches positions/balance from Alpaca and merges with the local database."""

    def __init__(self):
        self._trading_client = None
        self._last_sync = {}       # {user_id: {"time": datetime, "status": str, "detail": str}}

    # ── Alpaca client (lazy init) ────────────────────────────

    def _get_alpaca_client(self):
        """Return a cached TradingClient or create one from env vars."""
        if self._trading_client is not None:
            return self._trading_client
        api_key = os.environ.get("ALPACA_API_KEY", "").strip()
        secret = os.environ.get("ALPACA_SECRET_KEY", "").strip()
        if not api_key or not secret:
            return None
        try:
            from alpaca.trading.client import TradingClient
            self._trading_client = TradingClient(api_key, secret, paper=True)
            return self._trading_client
        except Exception as e:
            logger.error(f"BrokerSync: Alpaca client init failed: {e}")
            return None

    # ── Position sync ────────────────────────────────────────

    def sync_positions(self, user_id: int, broker: str = "alpaca") -> dict:
        """Fetch positions from Alpaca, merge with DB positions.

        Merge logic:
        - Match by ticker
        - Update shares / avg_cost for existing
        - Add new positions from broker
        - Flag (set shares=0) positions that no longer exist on broker side
        """
        if broker != "alpaca":
            return {"error": f"Unsupported broker: {broker}"}

        client = self._get_alpaca_client()
        if not client:
            self._record_sync(user_id, "error", "Alpaca not configured")
            return {"error": "Alpaca not configured (missing API keys)"}

        try:
            alpaca_positions = client.get_all_positions()
        except Exception as e:
            self._record_sync(user_id, "error", str(e))
            return {"error": f"Failed to fetch Alpaca positions: {e}"}

        # Build map of broker positions: {ticker: {shares, avg_cost, current_price}}
        broker_map = {}
        for p in alpaca_positions:
            broker_map[p.symbol] = {
                "shares": float(p.qty),
                "avg_cost": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
            }

        # Existing DB positions for this user
        db_positions = Position.query.filter_by(user_id=user_id).all()
        db_map = {pos.ticker: pos for pos in db_positions}

        added, updated, removed = [], [], []

        # Update or add positions from broker
        for ticker, bdata in broker_map.items():
            if ticker in db_map:
                pos = db_map[ticker]
                if pos.shares != bdata["shares"] or pos.avg_cost != bdata["avg_cost"]:
                    pos.shares = bdata["shares"]
                    pos.avg_cost = bdata["avg_cost"]
                    updated.append(ticker)
            else:
                new_pos = Position(
                    user_id=user_id,
                    ticker=ticker,
                    shares=bdata["shares"],
                    avg_cost=bdata["avg_cost"],
                    buy_fx_rate=0.0,
                )
                db.session.add(new_pos)
                added.append(ticker)

        # Flag positions that no longer exist on the broker (set shares=0)
        for ticker, pos in db_map.items():
            if ticker not in broker_map and pos.shares > 0:
                # Only flag US tickers (skip Korean positions which aren't on Alpaca)
                if not ticker.endswith(".KS") and not ticker.endswith(".KQ") and not (ticker.isdigit() and len(ticker) == 6):
                    pos.shares = 0
                    removed.append(ticker)

        # Update broker_connection record
        self._update_broker_connection(user_id, broker)

        db.session.commit()

        detail = f"+{len(added)} added, ~{len(updated)} updated, -{len(removed)} removed"
        self._record_sync(user_id, "success", detail)

        return {
            "ok": True,
            "added": added,
            "updated": updated,
            "removed": removed,
            "broker_positions": len(broker_map),
            "detail": detail,
        }

    # ── Balance sync ─────────────────────────────────────────

    def sync_balance(self, user_id: int, broker: str = "alpaca") -> dict:
        """Fetch account balance from Alpaca, update User.available_capital."""
        if broker != "alpaca":
            return {"error": f"Unsupported broker: {broker}"}

        client = self._get_alpaca_client()
        if not client:
            return {"error": "Alpaca not configured (missing API keys)"}

        try:
            account = client.get_account()
        except Exception as e:
            return {"error": f"Failed to fetch Alpaca account: {e}"}

        user = db.session.get(User, user_id)
        if not user:
            return {"error": "User not found"}

        equity = float(account.equity)
        cash = float(account.cash)
        buying_power = float(account.buying_power)

        user.available_capital = cash
        db.session.commit()

        return {
            "ok": True,
            "equity": equity,
            "cash": cash,
            "buying_power": buying_power,
            "updated_capital": cash,
        }

    # ── KIS (한국투자증권) sync ────────────────────────────────

    def sync_kis(self, user_id: int) -> dict:
        """Fetch KIS positions and merge with local DB.

        Returns: {"ok": True, "synced": [...], "cash": float} or {"error": ...}
        """
        try:
            from kis_service import KISService
        except ImportError:
            return {"error": "KIS service not available"}

        kis = KISService()
        if not kis.available:
            return {"error": "KIS not configured (missing KIS_APP_KEY / KIS_APP_SECRET)"}
        if not kis.account_no:
            return {"error": "KIS_ACCOUNT_NO not set in environment"}

        balance = kis.get_balance()
        if "error" in balance:
            self._record_sync(user_id, "error", balance["error"])
            return {"error": balance["error"]}

        # Existing DB positions for this user
        db_positions = Position.query.filter_by(user_id=user_id).all()
        db_map = {pos.ticker: pos for pos in db_positions}

        added, updated, synced = [], [], []

        for pos in balance.get("positions", []):
            raw_ticker = pos["ticker"]
            # Normalize: 6-digit Korean code -> append .KS suffix for DB consistency
            ticker = raw_ticker if raw_ticker.endswith(".KS") or raw_ticker.endswith(".KQ") else f"{raw_ticker}.KS"

            if ticker in db_map:
                db_pos = db_map[ticker]
                if db_pos.shares != pos["shares"] or db_pos.avg_cost != pos["avg_cost"]:
                    db_pos.shares = pos["shares"]
                    db_pos.avg_cost = pos["avg_cost"]
                    updated.append(ticker)
            else:
                new_pos = Position(
                    user_id=user_id,
                    ticker=ticker,
                    shares=pos["shares"],
                    avg_cost=pos["avg_cost"],
                    buy_fx_rate=0.0,
                )
                db.session.add(new_pos)
                added.append(ticker)
            synced.append(ticker)

        # Flag Korean positions no longer on KIS (set shares=0)
        for ticker, db_pos in db_map.items():
            is_korean = ticker.endswith(".KS") or ticker.endswith(".KQ") or (ticker.isdigit() and len(ticker) == 6)
            if is_korean and ticker not in synced and db_pos.shares > 0:
                db_pos.shares = 0

        self._update_broker_connection(user_id, "kis")
        db.session.commit()

        detail = f"KIS sync: +{len(added)} added, ~{len(updated)} updated, {len(synced)} total"
        self._record_sync(user_id, "success", detail)

        return {
            "ok": True,
            "synced": synced,
            "added": added,
            "updated": updated,
            "cash": balance.get("available_cash", 0),
            "total_value": balance.get("total_value", 0),
            "detail": detail,
        }

    # ── Full sync (positions + balance) ──────────────────────

    def sync_all(self, user_id: int, broker: str = "alpaca") -> dict:
        """Run both position and balance sync."""
        pos_result = self.sync_positions(user_id, broker)
        bal_result = self.sync_balance(user_id, broker)
        return {
            "ok": pos_result.get("ok", False) and bal_result.get("ok", False),
            "positions": pos_result,
            "balance": bal_result,
        }

    # ── Status / connections ─────────────────────────────────

    def get_sync_status(self, user_id: int) -> dict:
        """Return last sync info for a user."""
        info = self._last_sync.get(user_id)
        if not info:
            return {"last_synced_at": None, "status": "never"}
        return {
            "last_synced_at": info["time"].isoformat(),
            "status": info["status"],
            "detail": info.get("detail", ""),
        }

    def get_connections(self, user_id: int) -> list[dict]:
        """List broker connections for a user."""
        conns = BrokerConnection.query.filter_by(user_id=user_id).all()
        if conns:
            return [c.to_dict() for c in conns]

        # If no explicit connection records, detect from env vars
        env_conns = []
        client = self._get_alpaca_client()
        if client:
            env_conns.append({
                "broker": "alpaca",
                "account_id": None,
                "is_paper": True,
                "is_active": True,
                "last_synced_at": None,
                "source": "env",
            })
        kis_key = os.environ.get("KIS_APP_KEY", "").strip()
        kis_acct = os.environ.get("KIS_ACCOUNT_NO", "").strip()
        if kis_key:
            env_conns.append({
                "broker": "kis",
                "account_id": kis_acct or None,
                "is_paper": True,  # 모의투자
                "is_active": bool(kis_acct),
                "last_synced_at": None,
                "source": "env",
            })
        return env_conns

    # ── Internal helpers ─────────────────────────────────────

    def _record_sync(self, user_id: int, status: str, detail: str = ""):
        self._last_sync[user_id] = {
            "time": datetime.utcnow(),
            "status": status,
            "detail": detail,
        }

    def _update_broker_connection(self, user_id: int, broker: str):
        """Update or create BrokerConnection.last_synced_at."""
        conn = BrokerConnection.query.filter_by(user_id=user_id, broker=broker).first()
        if conn:
            conn.last_synced_at = datetime.utcnow()
            conn.is_active = True
        else:
            conn = BrokerConnection(
                user_id=user_id,
                broker=broker,
                is_paper=True,
                is_active=True,
                last_synced_at=datetime.utcnow(),
            )
            db.session.add(conn)
