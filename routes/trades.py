"""Trade history routes."""
from flask import Blueprint, jsonify
from flask_login import current_user

from models import TradeHistory
from services.serializers import serialize_trade
from .decorators import api_auth

trades_bp = Blueprint("trades", __name__, url_prefix="/api")


@trades_bp.route("/trades")
@api_auth
def get_trades():
    trades = (TradeHistory.query
              .filter_by(user_id=current_user.id)
              .order_by(TradeHistory.traded_at.desc())
              .limit(60).all())
    return jsonify({"trades": [serialize_trade(t) for t in trades]})
