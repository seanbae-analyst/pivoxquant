"""Backtest route."""
from flask import Blueprint, request, jsonify
from .decorators import api_auth

backtest_bp = Blueprint("backtest", __name__, url_prefix="/api")


@backtest_bp.route("/backtest/<ticker>")
@api_auth
def run_backtest(ticker):
    from backtester import Backtester
    period = request.args.get("period", "1y")
    capital = float(request.args.get("capital", "10000"))
    result = Backtester.run(ticker.upper(), period=period, initial_capital=capital)
    if result:
        return jsonify(result)
    return jsonify({"error": f"Backtest failed for {ticker}"}), 500
