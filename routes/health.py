"""Health check endpoint for Railway / load-balancer probes.

Unauthenticated on purpose — the Railway health checker cannot carry session
cookies, so we expose a dedicated endpoint instead of reusing `/api/auth/me`
(which returns 401 for anonymous callers and trips the probe).

Response contract (stable; platform probes depend on it):

    200  {"status": "ok",       "version": "...", "timestamp": "...", "db": "ok"}
    503  {"status": "degraded", "version": "...", "timestamp": "...", "db": "<error>"}

The DB branch is best-effort — a failing `SELECT 1` degrades the response
but doesn't take the process down, so the probe can distinguish "process
dead" (TCP refused) from "DB dead" (200/503 with `db != ok`).
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify
from sqlalchemy import text

from extensions import db

health_bp = Blueprint("health", __name__)

# Bump whenever the /api/health response shape or a material platform
# invariant changes — makes it trivial to correlate probe telemetry with
# deploys from the Railway logs.
HEALTH_VERSION = "2026-04-19"


@health_bp.route("/api/health", methods=["GET"])
def health():
    """Lightweight health probe — intentionally no auth, no DB writes."""
    payload: dict = {
        "status":    "ok",
        "version":   HEALTH_VERSION,
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
    }

    # Best-effort DB ping. SQLAlchemy 2.x requires an explicit `text()`
    # around raw SQL, so we wrap the trivial SELECT here.
    try:
        db.session.execute(text("SELECT 1"))
        payload["db"] = "ok"
        return jsonify(payload), 200
    except Exception as exc:  # pragma: no cover — only fires on infra fault
        payload["status"] = "degraded"
        payload["db"] = f"error: {exc.__class__.__name__}"
        return jsonify(payload), 503
