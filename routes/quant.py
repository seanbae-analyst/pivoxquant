"""Quant strategy routes: VIX strategy, cross-asset momentum."""
import time as _time
from flask import Blueprint, jsonify
from .decorators import api_auth

quant_bp = Blueprint("quant", __name__, url_prefix="/api")

_ca_cache = {"data": None, "ts": 0}


@quant_bp.route("/vix-strategy")
@api_auth
def vix_strategy():
    from quant_models import VIXStrategy
    result = VIXStrategy.analyze()
    if result:
        return jsonify(result)
    return jsonify({"error": "VIX data unavailable"}), 500


@quant_bp.route("/cross-asset")
@api_auth
def cross_asset():
    now = _time.time()
    if _ca_cache["data"] and now - _ca_cache["ts"] < 300:
        return jsonify(_ca_cache["data"])
    from quant_models import CrossAssetMomentum
    result = CrossAssetMomentum.analyze()
    if result:
        _ca_cache["data"] = result
        _ca_cache["ts"] = now
        return jsonify(result)
    return jsonify({"error": "Insufficient data"}), 500
