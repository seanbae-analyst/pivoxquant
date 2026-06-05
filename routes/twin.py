"""AI Trader Twin routes — Feature 5 (paper-only).

LEGAL POSTURE
-------------
Every response from this blueprint includes a fixed ``disclaimer``
field stating the Twin is paper / not advice. ``portfolio`` adds
``paper_label: "PAPER PORTFOLIO"`` and ``trades`` rows carry
``is_paper: true`` per row. No endpoint exposes prospective
decisions — only entries with ``executed_at <= now`` are shown.

URL prefix: ``/api/twin``
Authentication: every endpoint requires a logged-in user (api_auth).
Authorization: a user can only ever read or mutate their OWN twin.
"""

# legal-exempt: disclaimer language only — section101-check detector FP
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request
from flask_login import current_user

from models import (
    AITwinPortfolio,
    AITwinTrade,
    AITwinWeeklyReport,
    TradeHistory,
)
from services import container as svc
from services.twin import initialize_twin, generate_weekly_report

from .decorators import api_auth, legal_scrub_response
from security import ai_rate_limit

logger = logging.getLogger(__name__)

twin_bp = Blueprint("twin", __name__, url_prefix="/api/twin")


# Fixed disclaimer attached to every response.
DISCLAIMER = (
    "AI Twin은 가상의 paper 포트폴리오이며 실제 자금이 투입되지 않습니다. "
    "본 정보는 정보제공 목적이며 투자 권유, 추천, 자문이 아닙니다. "
    "AI Twin is a paper-only simulation; no real money is at risk. "
    "This information is for self-analysis only and does not constitute "
    "investment advice, recommendation, or solicitation."
)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _envelope(data: dict | list, status: int = 200):
    """Wrap any payload with the legally-required disclaimer."""
    body = {
        "ok": status < 400,
        "data": data,
        "disclaimer": DISCLAIMER,
    }
    return jsonify(body), status


# ─────────────────────────────────────────────────────────────────────
# POST /api/twin/initialize
# ─────────────────────────────────────────────────────────────────────


@twin_bp.route("/initialize", methods=["POST"])
@api_auth
@legal_scrub_response
@ai_rate_limit
def init_twin_endpoint():
    """Idempotent. Creates the user's $10K paper Twin if absent."""
    try:
        twin = initialize_twin(int(current_user.id))
    except Exception as exc:
        logger.exception("Twin initialize failed for user=%s: %s", current_user.id, exc)
        return _envelope({"error": "initialize_failed"}, status=500)
    return _envelope(twin.to_dict(), status=200)


# ─────────────────────────────────────────────────────────────────────
# GET /api/twin/portfolio
# ─────────────────────────────────────────────────────────────────────


@twin_bp.route("/portfolio", methods=["GET"])
@api_auth
@legal_scrub_response
def twin_portfolio():
    twin = AITwinPortfolio.query.filter_by(user_id=current_user.id).first()
    if twin is None:
        return _envelope({"initialized": False, "paper_label": "PAPER PORTFOLIO"}, status=200)

    # Mark to current price (best-effort). Failures degrade to cost basis
    # so the UI always renders something sensible. Single batch call avoids
    # per-position external API round-trips (N+1 → 1).
    tickers = [pos.ticker for pos in twin.positions]
    try:
        price_map = svc.fetcher.get_prices_batch(tickers) if tickers else {}
    except Exception:
        logger.exception("twin_portfolio: get_prices_batch failed user=%s", current_user.id)
        price_map = {}

    positions_payload: list[dict] = []
    market_value = 0.0
    for pos in twin.positions:
        row = pos.to_dict()
        snap = price_map.get(pos.ticker)
        price_now = float(snap["price"]) if snap and snap.get("price") else float(pos.avg_cost or 0)
        row["price_now"] = price_now
        row["market_value"] = float(pos.shares or 0) * price_now
        market_value += row["market_value"]
        positions_payload.append(row)

    cash = float(twin.current_cash or 0)
    total_value = cash + market_value
    starting = float(twin.starting_cash or 0)
    total_return_pct = ((total_value - starting) / starting * 100.0) if starting > 0 else None

    payload = twin.to_dict()
    payload.update({
        "positions": positions_payload,
        "market_value": round(market_value, 4),
        "total_value": round(total_value, 4),
        "total_return_pct": round(total_return_pct, 4) if total_return_pct is not None else None,
        # Echoed once more at the top level so the UI never needs to
        # walk into the nested object to know this is paper.
        "paper_label": "PAPER PORTFOLIO",
        "initialized": True,
    })
    return _envelope(payload, status=200)


# ─────────────────────────────────────────────────────────────────────
# GET /api/twin/trades?days=30
# ─────────────────────────────────────────────────────────────────────


@twin_bp.route("/trades", methods=["GET"])
@api_auth
@legal_scrub_response
def twin_trades():
    twin = AITwinPortfolio.query.filter_by(user_id=current_user.id).first()
    if twin is None:
        return _envelope({"trades": [], "initialized": False}, status=200)

    try:
        days = int(request.args.get("days", "30"))
    except (TypeError, ValueError):
        days = 30
    days = max(1, min(days, 365))  # clamp

    now = _utc_now_naive()
    since = now - timedelta(days=days)

    rows = (
        AITwinTrade.query
        .filter(AITwinTrade.twin_id == twin.id)
        .filter(AITwinTrade.executed_at >= since)
        # Hard cap at NOW — prospective rows could never be exposed.
        .filter(AITwinTrade.executed_at <= now)
        .order_by(AITwinTrade.executed_at.desc())
        .limit(500)
        .all()
    )

    return _envelope({
        "trades": [r.to_dict() for r in rows],
        "window_days": days,
        "as_of": now.isoformat(),
        "last_decision_at": twin.last_decision_at.isoformat() if twin.last_decision_at else None,
        "paper_label": "PAPER PORTFOLIO",
    }, status=200)


# ─────────────────────────────────────────────────────────────────────
# GET /api/twin/weekly-reports?n=12
# ─────────────────────────────────────────────────────────────────────


@twin_bp.route("/weekly-reports", methods=["GET"])
@api_auth
@legal_scrub_response
def twin_weekly_reports():
    try:
        n = int(request.args.get("n", "12"))
    except (TypeError, ValueError):
        n = 12
    n = max(1, min(n, 52))

    rows = (
        AITwinWeeklyReport.query
        .filter_by(user_id=current_user.id)
        .order_by(AITwinWeeklyReport.week_ending.desc())
        .limit(n)
        .all()
    )
    return _envelope({
        "reports": [r.to_dict() for r in rows],
        "paper_label": "PAPER PORTFOLIO",
    }, status=200)


# ─────────────────────────────────────────────────────────────────────
# GET /api/twin/comparison
# ─────────────────────────────────────────────────────────────────────


@twin_bp.route("/comparison", methods=["GET"])
@api_auth
@legal_scrub_response
def twin_comparison():
    """Cumulative since-inception comparison (user vs twin)."""
    twin = AITwinPortfolio.query.filter_by(user_id=current_user.id).first()
    if twin is None:
        return _envelope({
            "initialized": False,
            "paper_label": "PAPER PORTFOLIO",
        }, status=200)

    # Twin lifetime return (paper). Batch price fetch avoids per-position
    # external API round-trips (N+1 → 1).
    starting = float(twin.starting_cash or 0)
    cash = float(twin.current_cash or 0)
    market_value = 0.0
    tickers = [pos.ticker for pos in twin.positions]
    try:
        price_map = svc.fetcher.get_prices_batch(tickers) if tickers else {}
    except Exception:
        logger.exception("twin_comparison: get_prices_batch failed user=%s", current_user.id)
        price_map = {}
    # Twin paper cash/starting_cash are USD (DEFAULT_STARTING_CASH = $10,000), so
    # normalise each position's value to USD before summing — a raw ₩+$ sum is the
    # Pattern-7 defect (cf. performance_quant F-1 + the user-side ratio below). A
    # KR (.KS/.KQ) holding is priced in ₩, so /fx it before adding to USD cash.
    from services import fx_service
    _fx = fx_service.get_rate()
    for pos in twin.positions:
        snap = price_map.get(pos.ticker)
        price_now = float(snap["price"]) if snap and snap.get("price") else float(pos.avg_cost or 0)
        mv_native = float(pos.shares or 0) * price_now
        is_kr = (pos.ticker or "").upper().endswith((".KS", ".KQ"))
        market_value += (mv_native / _fx) if (is_kr and _fx and _fx > 0) else mv_native
    twin_total = cash + market_value
    twin_lifetime_pct = ((twin_total - starting) / starting * 100.0) if starting > 0 else None

    # User lifetime return — sum of TradeHistory P&L since inception.
    user_trades = (
        TradeHistory.query
        .filter(
            TradeHistory.user_id == current_user.id,
            TradeHistory.traded_at >= twin.initialized_at,
        )
        .all()
    )
    # Denominator = capital deployed (BUY legs only). A SELL's ``total_value``
    # is the proceeds, NOT additional invested capital — including it inflated
    # the denominator and silently understated ``user_lifetime_pct`` (e.g. a
    # $1000 buy → $1100 sell read as 4.76% instead of the true 10%). Roundtrips
    # are now measured against the cost basis actually put to work.
    # Multi-currency ledgers (US + KR) must NOT raw-sum ₩ + $ — normalise both
    # legs of the ratio to KRW (same fix class as performance_quant F-1, CEO
    # 2026-06-05). The twin/paper side (twin_total above) is now normalised to
    # USD (its cash base) in the market_value loop, so both ratios are self-
    # consistent within their own currency (USD for twin, KRW for the user) — a %
    # comparison is valid regardless of base. ``_fx`` is computed above.
    user_invested = sum(
        fx_service.amount_to_krw(t.total_value, t.currency, t.ticker, _fx)
        for t in user_trades
        if (t.action or "").upper() == "BUY"
    ) or 0.0
    user_pnl = sum(
        fx_service.amount_to_krw(t.pnl, t.currency, t.ticker, _fx) for t in user_trades
    ) or 0.0
    user_lifetime_pct = (user_pnl / user_invested * 100.0) if user_invested > 0 else None

    payload = {
        "initialized": True,
        "paper_label": "PAPER PORTFOLIO",
        "since": twin.initialized_at.isoformat() if twin.initialized_at else None,
        "twin_lifetime_pct": round(twin_lifetime_pct, 4) if twin_lifetime_pct is not None else None,
        "user_lifetime_pct": round(user_lifetime_pct, 4) if user_lifetime_pct is not None else None,
        "twin_total_value": round(twin_total, 4),
        "user_trades_count": len(user_trades),
        "twin_trades_count": twin.trades.count(),
        "persona_at_init": twin.persona_at_init,
    }
    return _envelope(payload, status=200)


# ─────────────────────────────────────────────────────────────────────
# (Internal-only) trigger for tests / admin — generate this week's report
# ─────────────────────────────────────────────────────────────────────


@twin_bp.route("/weekly-reports/generate", methods=["POST"])
@api_auth
@legal_scrub_response
@ai_rate_limit
def twin_generate_weekly():
    """Compute (or fetch) the user's weekly comparison row.

    Allows the frontend to refresh the comparison without waiting on
    Sunday's cron. Idempotent (UNIQUE user_id + week_ending).
    """
    row = generate_weekly_report(int(current_user.id))
    return _envelope(row.to_dict(), status=200)
