"""Broker sync routes — manual sync trigger, status, connections."""
from flask import Blueprint, jsonify, request
from flask_login import current_user

from services.container import broker_sync
from .decorators import api_auth

broker_sync_bp = Blueprint("broker_sync", __name__, url_prefix="/api/broker")


@broker_sync_bp.route("/sync", methods=["POST"])
@api_auth
def trigger_sync():
    """POST /api/broker/sync — trigger manual position + balance sync."""
    body = request.get_json(silent=True) or {}
    broker = body.get("broker", "alpaca")
    result = broker_sync.sync_all(current_user.id, broker=broker)
    status_code = 200 if result.get("ok") else 502
    return jsonify(result), status_code


@broker_sync_bp.route("/sync-status", methods=["GET"])
@api_auth
def sync_status():
    """GET /api/broker/sync-status — last sync time and status."""
    return jsonify(broker_sync.get_sync_status(current_user.id))


@broker_sync_bp.route("/connections", methods=["GET"])
@api_auth
def connections():
    """GET /api/broker/connections — list connected brokers."""
    return jsonify(broker_sync.get_connections(current_user.id))
