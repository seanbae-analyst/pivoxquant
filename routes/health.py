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

import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify
from sqlalchemy import text

from extensions import db

logger = logging.getLogger(__name__)

health_bp = Blueprint("health", __name__)

# Health version surfaces the deployed commit SHA so probes can correlate
# with the host's deploy log. 2026-05-12 bug-hunter found the hardcoded value
# masked a real 3-week stale value (still showed 2026-04-19 even after
# many deploys). 2026-09-17: the backend has run on Render since 09-04
# (CLAUDE.md §지금 상태) but this chain still read only the Railway and
# Vercel names, so prod answered the "v37+" fallback on every deploy and
# nobody could tell which commit was live. Render injects RENDER_GIT_COMMIT
# (https://render.com/docs/environment-variables); it goes first.
import os as _os
HEALTH_VERSION = (
    _os.environ.get("RENDER_GIT_COMMIT", "")[:12]
    or _os.environ.get("RAILWAY_GIT_COMMIT_SHA", "")[:12]
    or _os.environ.get("VERCEL_GIT_COMMIT_SHA", "")[:12]
    or _os.environ.get("GIT_COMMIT_SHA", "")[:12]
    or "v37+"
)


@health_bp.route("/api/health", methods=["GET"])
def health():
    """Lightweight health probe — intentionally no auth, no DB writes.

    2026-05-15 (launch prep): also surfaces a compact env_health
    summary so external monitoring can alert on missing recommended
    keys without needing to scrape Railway logs. The summary excludes
    full per-var purpose strings (those live in the boot-time log).
    """
    payload: dict = {
        "status":    "ok",
        "version":   HEALTH_VERSION,
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
    }

    # env_health summary (cheap — pure env read, no DB / network).
    try:
        from services.launch_prep import env_health_summary
        payload["env"] = env_health_summary()
    except Exception as exc:
        payload["env"] = {"error": str(exc)[:120]}

    # Best-effort DB ping. SQLAlchemy 2.x requires an explicit `text()`
    # around raw SQL, so we wrap the trivial SELECT here.
    #
    # 2026-05-20 bug-hunter (P0): run the probe on a *short-lived raw
    # connection* checked out from the engine pool rather than the shared
    # scoped `db.session`. On a Railway PG connection blip / pool blip the
    # OperationalError used to leave the request-scoped session in a failed
    # state; the next request on the same gevent worker then entered with a
    # poisoned session and 500/503'd too (observed ~30% 503 windows). A
    # standalone connection (a) isolates the failure from the request session
    # and (b) is auto-returned/closed by the `with` block. We still defensively
    # `rollback()` the scoped session in the except path in case any prior
    # work on this request left it dirty.
    try:
        with db.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        payload["db"] = "ok"
        return jsonify(payload), 200
    except Exception as exc:  # pragma: no cover — only fires on infra fault
        # Clean up the request-scoped session so a subsequent request on this
        # worker doesn't inherit a failed transaction. rollback() is a no-op if
        # the session is already clean, so this is always safe.
        try:
            db.session.rollback()
        except Exception:
            logger.debug("health: session rollback after DB ping failure also failed", exc_info=True)
        payload["status"] = "degraded"
        payload["db"] = f"error: {exc.__class__.__name__}"
        return jsonify(payload), 503
