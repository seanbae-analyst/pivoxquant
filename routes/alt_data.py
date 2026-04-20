"""
PivoxQuant — Alternative Data Routes (KR market)
================================================
pyKRX-powered endpoints that feed Foreign-Flow Predictor and Short-Squeeze
Radar models. No DB writes — everything is memory-cached for 24h.

Response envelope (success):
    {
        "ticker": "005930",   # or "market" for market-flow
        "data":   [...]|{...},
        "cached_at": "2026-04-18T00:00:00",
        "source": "pyKRX"
    }

Errors return {"error": "..."} with appropriate HTTP status.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify

from services.data.pykrx_service import pykrx_service, _normalize_ticker
from services.data.fred_service import FRED_SERIES, get_fred_service
from services.data.sec_edgar_service import SECEdgarService, SMART_MONEY_CIKS
from services.name_resolver import resolve_stock_name
from .decorators import api_auth

logger = logging.getLogger(__name__)

alt_data_bp = Blueprint("alt_data", __name__, url_prefix="/api/alt-data")


def _envelope(key: str, value, data, cached_at: str | None) -> dict:
    """Build the standard response envelope.

    When `key == "ticker"` we also emit a resolved `name` so the frontend can
    render 회사명 without re-querying /api/lookup. pyKRX ticker codes are
    6-digit KR listings — resolve_stock_name prepends .KS/.KQ internally.
    """
    out = {
        key: value,
        "data": data,
        "cached_at": cached_at or datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "source": "pyKRX",
    }
    if key == "ticker" and isinstance(value, str) and value:
        # pyKRX uses 6-digit codes; resolver wraps them in .KS/.KQ internally.
        v = value if value.upper().endswith((".KS", ".KQ")) else f"{value}.KS"
        out["name"] = resolve_stock_name(v) or resolve_stock_name(value) or value
    return out


@alt_data_bp.route("/kr/foreign-flow/<ticker>", methods=["GET"])
@api_auth
def foreign_flow(ticker: str):
    """Foreign + institutional + individual net-buying (억원), last N trading days."""
    code = _normalize_ticker(ticker)
    if not code:
        return jsonify({"error": "Invalid KR ticker — expected 6-digit code"}), 400

    try:
        days = int(request.args.get("days", 30))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid 'days' parameter"}), 400
    if days < 1 or days > 365:
        return jsonify({"error": "'days' must be between 1 and 365"}), 400

    data = pykrx_service.get_foreign_flow(code, days)
    cached_at = pykrx_service.cached_at(code, "foreign_flow", days=days)
    return jsonify(_envelope("ticker", code, data, cached_at))


@alt_data_bp.route("/kr/short-interest/<ticker>", methods=["GET"])
@api_auth
def short_interest(ticker: str):
    """Daily short-sale volume + outstanding short balance + latest ratio vs market cap."""
    code = _normalize_ticker(ticker)
    if not code:
        return jsonify({"error": "Invalid KR ticker — expected 6-digit code"}), 400

    try:
        days = int(request.args.get("days", 30))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid 'days' parameter"}), 400
    if days < 1 or days > 365:
        return jsonify({"error": "'days' must be between 1 and 365"}), 400

    series = pykrx_service.get_short_interest(code, days)
    ratio = pykrx_service.get_short_balance_ratio(code)
    payload = {"series": series, "latest_ratio": ratio}
    cached_at = pykrx_service.cached_at(code, "short_interest", days=days)
    return jsonify(_envelope("ticker", code, payload, cached_at))


@alt_data_bp.route("/kr/market-flow", methods=["GET"])
@api_auth
def market_flow():
    """Whole-market investor-type net-buying summary (KOSPI | KOSDAQ)."""
    market = (request.args.get("market") or "KOSPI").upper()
    if market not in ("KOSPI", "KOSDAQ"):
        return jsonify({"error": "'market' must be KOSPI or KOSDAQ"}), 400

    date = request.args.get("date")  # YYYYMMDD, optional
    data = pykrx_service.get_market_flow_summary(market=market, date=date)
    cached_at = pykrx_service.cached_at(market, "market_flow", date=date or (data.get("date") if data else None))
    return jsonify(_envelope("market", market, data, cached_at))


# ─────────────────────────────────────────────────────────────────────────────
# US market — SEC EDGAR alt-data (Smart Money 13F + Form 4 insider trades)
# ─────────────────────────────────────────────────────────────────────────────
_SRC_SEC = "SEC EDGAR"


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sec_envelope(key: str, value, data, *, extra: dict | None = None) -> dict:
    """Build SEC EDGAR response envelope (mirrors pyKRX shape but source=SEC).

    When `key == "ticker"` we also emit a resolved `name` so frontends can
    render 회사명 immediately without a second round-trip.
    """
    payload = {
        key: value,
        "data": data,
        "cached_at": _now_iso_utc(),
        "source": _SRC_SEC,
    }
    if key == "ticker" and isinstance(value, str) and value:
        payload["name"] = resolve_stock_name(value) or value
    if extra:
        payload.update(extra)
    return payload


@alt_data_bp.route("/us/13f/<cik>", methods=["GET"])
@api_auth
def us_13f(cik: str):
    """Latest 13F-HR institutional holdings for a CIK.

    Accepts either a raw numeric CIK (auto-padded to 10 digits) or a curated
    smart-money key (e.g. ``berkshire``, ``ark``).
    """
    resolved = SMART_MONEY_CIKS.get((cik or "").lower(), cik)
    data = SECEdgarService.get_13f_holdings(resolved)
    return jsonify(_sec_envelope("cik", str(resolved).zfill(10), data))


@alt_data_bp.route("/us/smart-money/<ticker>", methods=["GET"])
@api_auth
def us_smart_money(ticker: str):
    """Which curated smart-money funds hold ``ticker`` (per latest 13F)."""
    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid 'limit' parameter"}), 400
    if limit < 1 or limit > 100:
        return jsonify({"error": "'limit' must be between 1 and 100"}), 400

    data = SECEdgarService.get_institutional_filers_by_ticker(ticker, limit=limit)
    return jsonify(_sec_envelope("ticker", (ticker or "").upper(), data))


@alt_data_bp.route("/us/insider-trades/<ticker>", methods=["GET"])
@api_auth
def us_insider_trades(ticker: str):
    """Form 4 insider transactions for ``ticker`` within the last N days."""
    try:
        days = int(request.args.get("days", 90))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid 'days' parameter"}), 400
    if days < 1 or days > 365:
        return jsonify({"error": "'days' must be between 1 and 365"}), 400

    data = SECEdgarService.get_form4_insider_trades(ticker, days=days)
    return jsonify(_sec_envelope(
        "ticker", (ticker or "").upper(), data, extra={"window_days": days}
    ))


@alt_data_bp.route("/us/cluster-buys/<ticker>", methods=["GET"])
@api_auth
def us_cluster_buys(ticker: str):
    """Detect ≥ ``min_insiders`` distinct insider purchases within ``days``."""
    try:
        days = int(request.args.get("days", 30))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid 'days' parameter"}), 400
    if days < 1 or days > 180:
        return jsonify({"error": "'days' must be between 1 and 180"}), 400

    try:
        min_insiders = int(request.args.get("min_insiders", 3))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid 'min_insiders' parameter"}), 400
    if min_insiders < 1 or min_insiders > 20:
        return jsonify({"error": "'min_insiders' must be between 1 and 20"}), 400

    result = SECEdgarService.detect_cluster_buys(
        ticker, days=days, min_insiders=min_insiders
    )
    return jsonify(_sec_envelope("ticker", (ticker or "").upper(), result))


# ══════════════════════════════════════════════════════════════════════════════
# FRED — Federal Reserve Economic Data (Macro Scenario Stress Test data layer)
# ══════════════════════════════════════════════════════════════════════════════
# Unlike the pyKRX endpoints above (always available because pyKRX is a bundled
# library) and SEC EDGAR (public, no key), FRED requires FRED_API_KEY. When
# absent, these endpoints return HTTP 503 with code=FRED_NOT_CONFIGURED rather
# than 500'ing.

def _fred_unavailable_response():
    """Shared 503 body for when FRED_API_KEY is missing."""
    return jsonify({
        "ok": False,
        "error": "FRED service unavailable",
        "reason": "FRED_API_KEY not configured",
        "code": "FRED_NOT_CONFIGURED",
    }), 503


@alt_data_bp.route("/macro/snapshot", methods=["GET"])
@api_auth
def macro_snapshot():
    """Dashboard-ready snapshot: latest value + delta for every FRED_SERIES entry."""
    svc = get_fred_service()
    if not svc.available:
        return _fred_unavailable_response()
    snapshot = svc.get_macro_snapshot()
    return jsonify({"ok": True, **snapshot}), 200


@alt_data_bp.route("/macro/series/<series_id>", methods=["GET"])
@api_auth
def macro_series(series_id: str):
    """Time series for a single FRED id.

    Query params:
        start — ISO date (YYYY-MM-DD) for observation_start (optional)
        limit — max points, 1..10000 (default 365)
    """
    svc = get_fred_service()
    if not svc.available:
        return _fred_unavailable_response()

    sid = (series_id or "").strip().upper()
    if not sid:
        return jsonify({"ok": False, "error": "series_id required"}), 400

    # Only allow curated catalog ids — prevents drive-by use of our auth'd
    # endpoint as a generic FRED proxy.
    if sid not in FRED_SERIES:
        return jsonify({
            "ok": False,
            "error": f"Unknown series_id: {sid}",
            "supported": sorted(FRED_SERIES.keys()),
        }), 404

    start = request.args.get("start")
    limit_raw = request.args.get("limit", "365")
    try:
        limit = int(limit_raw)
        if limit < 1:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "limit must be a positive integer"}), 400
    limit = min(limit, 10_000)

    data = svc.get_series(sid, start=start, limit=limit)
    if not data:
        return jsonify({
            "ok": False,
            "error": "No data returned from FRED",
            "series_id": sid,
        }), 502

    return jsonify({"ok": True, **data}), 200


@alt_data_bp.route("/macro/regime", methods=["GET"])
@api_auth
def macro_regime():
    """Lightweight recession/expansion classification from FRED signals."""
    svc = get_fred_service()
    if not svc.available:
        return _fred_unavailable_response()
    regime = svc.detect_regime()
    return jsonify({"ok": True, **regime}), 200


@alt_data_bp.route("/macro/catalog", methods=["GET"])
@api_auth
def macro_catalog():
    """List the supported FRED series_ids with their human labels + units."""
    return jsonify({
        "ok": True,
        "series": [{"series_id": sid, **meta} for sid, meta in FRED_SERIES.items()],
        "count": len(FRED_SERIES),
    }), 200
