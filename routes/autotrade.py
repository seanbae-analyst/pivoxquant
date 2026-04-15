"""AutoTrader routes."""
from flask import Blueprint, jsonify
from flask_login import current_user

from security import trade_rate_limit
from services.container import trader
from .decorators import api_auth

autotrade_bp = Blueprint("autotrade", __name__, url_prefix="/api/autotrade")


@autotrade_bp.route("/status")
@api_auth
def status():
    return jsonify(trader.get_status())


@autotrade_bp.route("/start", methods=["POST"])
@trade_rate_limit
@api_auth
def start():
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
    """Get pending trade proposals awaiting user confirmation."""
    return jsonify({"ok": True, "pending": trader.get_pending_trades()})


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
