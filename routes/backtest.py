"""Backtest route."""
from flask import Blueprint, request, jsonify
from .decorators import api_auth, legal_scrub_response

backtest_bp = Blueprint("backtest", __name__, url_prefix="/api")


@backtest_bp.route("/backtest/<ticker>")
@api_auth
@legal_scrub_response
def run_backtest(ticker):
    from backtester import Backtester
    period = request.args.get("period", "1y")
    try:
        capital = float(request.args.get("capital", "10000"))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid capital value"}), 400
    capital = min(max(capital, 100), 10_000_000)

    try:
        limit = int(request.args.get("limit", "100"))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid limit value"}), 400
    limit = min(max(limit, 1), 1000)

    result = Backtester.run(ticker.upper(), period=period, initial_capital=capital)
    if result:
        return jsonify(result)
    return jsonify({"error": f"Backtest failed for {ticker}"}), 500
