"""Discover route — scans a pool of tickers for opportunities."""
import logging
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Blueprint, request, jsonify
from flask_login import current_user

from models import Position
from services import fx_service, cache_service
from services.container import engine
from .decorators import api_auth

logger = logging.getLogger(__name__)

discover_bp = Blueprint("discover", __name__, url_prefix="/api")


@discover_bp.route("/discover")
@api_auth
def discover():
    now = time.time()
    uid = current_user.id
    force = request.args.get("force") == "1"
    uc = cache_service.discover_cache.get(uid, {"data": None, "ts": 0})
    if not force and uc["data"] and now - uc["ts"] < cache_service.DISCOVER_TTL:
        return jsonify({"results": uc["data"], "cached": True,
                        "cached_at": datetime.fromtimestamp(uc["ts"]).isoformat()})

    cap_usd = current_user.available_capital or 0.0
    cap_krw = getattr(current_user, "available_capital_krw", 0.0) or 0.0
    owned = {p.ticker for p in Position.query.filter_by(user_id=current_user.id).all()}
    pool = engine.DISCOVER_POOL

    def _analyze_one(ticker):
        try:
            r = engine.analyze(ticker, cap_usd, cap_krw, fx_rate=fx_service.get_rate())
            if r:
                r["already_owned"] = ticker in owned
            return r
        except Exception as e:
            logger.warning(f"Discover skip {ticker}: {e}")
            return None

    results = []
    with ThreadPoolExecutor(max_workers=15) as ex:
        futures = {ex.submit(_analyze_one, t): t for t in pool}
        for f in as_completed(futures):
            r = f.result()
            if r:
                results.append(r)

    order = {"POSITIVE": 0, "NEUTRAL": 1, "NEGATIVE": 2}
    results.sort(key=lambda x: (order.get(x.get("signal", ""), 9), -x.get("priority", 0)))
    cache_service.discover_cache[uid] = {"data": results, "ts": now}
    return jsonify({"results": results, "cached": False})
