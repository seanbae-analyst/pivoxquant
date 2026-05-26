"""Backtest route."""
from flask import Blueprint, request, jsonify

from security import general_rate_limit
from services.error_responses import api_error
from .decorators import api_auth, legal_scrub_response

backtest_bp = Blueprint("backtest", __name__, url_prefix="/api")

# Allowlist of lookback periods. An arbitrary `?period=` string flowed
# straight into the FMP price-history fetch — a caller could request
# exotic ranges and run up our metered FMP budget.
VALID_PERIODS = {"1mo", "3mo", "6mo", "1y", "2y", "5y"}


@backtest_bp.route("/backtest/<ticker>")
@api_auth
@general_rate_limit
@legal_scrub_response
def run_backtest(ticker):
    from services.quant.backtester import Backtester
    period = request.args.get("period", "1y")
    if period not in VALID_PERIODS:
        period = "1y"
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
    # Backtest failure is an unprocessable request (no data / too short
    # history for this ticker), not an internal server error — return the
    # canonical api_error envelope with 422 rather than a bare 500.
    return api_error(
        en=f"Backtest failed for {ticker}",
        kr=f"{ticker} 종목의 백테스트에 실패했습니다.",
        code="BACKTEST_FAILED",
        status=422,
    )
