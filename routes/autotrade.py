"""AutoTrader routes."""
from flask import Blueprint, jsonify
from flask_login import current_user

from security import trade_rate_limit
from services.container import trader
from services.name_resolver import (
    lookup_name_from_signal_cache,
    resolve_stock_name,
)
from .decorators import api_auth

autotrade_bp = Blueprint("autotrade", __name__, url_prefix="/api/autotrade")


def _enrich_pending_trade(t: dict) -> dict:
    """Return a copy of `t` with `name` guaranteed (falls back to ticker).

    Korean proposals already carry a `name` (see autotrader._propose_trade);
    US proposals don't. We resolve once here so every client gets a
    uniform shape without touching autotrader.py (frozen file).
    """
    if not isinstance(t, dict):
        return t
    enriched = dict(t)
    ticker = enriched.get("ticker") or ""
    if not enriched.get("name"):
        name = lookup_name_from_signal_cache(ticker) or resolve_stock_name(
            ticker
        )
        enriched["name"] = name or ticker
    return enriched


@autotrade_bp.route("/status")
@api_auth
def status():
    return jsonify(trader.get_status())


@autotrade_bp.route("/start", methods=["POST"])
@trade_rate_limit
@api_auth
def start():
    # TODO(multi-user): mutating the singleton trader is unsafe under
    # concurrent requests (one user's id can leak into another user's order).
    # Beta mitigation: Procfile pinned to --workers 1 so only one request
    # runs at a time. Post-launch: remove singleton, pass user_id explicitly,
    # or instantiate a per-user AutoTrader (requires autotrader.py changes).
    trader._user_id = current_user.id
    return jsonify(trader.start())


@autotrade_bp.route("/stop", methods=["POST"])
@api_auth
def stop():
    return jsonify(trader.stop())


@autotrade_bp.route("/sell-all", methods=["POST"])
@trade_rate_limit
@api_auth
def sell_all():
    us_results = trader.force_sell_all()
    kr_results = trader.force_sell_all_kr()
    all_results = us_results.get("results", []) + kr_results
    return jsonify({"results": all_results})


@autotrade_bp.route("/pending", methods=["GET"])
@api_auth
def get_pending():
    """Get pending trade proposals awaiting user confirmation.

    Each proposal is enriched with a `name` field (company display name)
    so the frontend can render name-large / ticker-small. Falls back to
    ticker when unresolvable.
    """
    pending = [
        _enrich_pending_trade(t) for t in (trader.get_pending_trades() or [])
    ]
    return jsonify({"ok": True, "pending": pending})


@autotrade_bp.route("/approve/<trade_id>", methods=["POST"])
@api_auth
@trade_rate_limit
def approve(trade_id):
    """User approves a pending trade for execution."""
    result = trader.approve_trade(trade_id)
    if not result.get("ok"):
        return jsonify(result), 400
    return jsonify(result)


@autotrade_bp.route("/reject/<trade_id>", methods=["POST"])
@api_auth
def reject(trade_id):
    """User rejects a pending trade."""
    result = trader.reject_trade(trade_id)
    if not result.get("ok"):
        return jsonify(result), 400
    return jsonify(result)


@autotrade_bp.route("/emergency-halt", methods=["POST"])
@trade_rate_limit
@api_auth
def emergency_halt():
    """Kill switch: stop trading, close all positions, lock out for 1 hour."""
    result = trader.emergency_halt()
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)
