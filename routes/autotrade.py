"""AutoTrader routes.

Security (2026-04-24, C1):
    The AutoTrader singleton carries a `_user_id` attribute used by the
    background thread for DB sync of paper trades. Mutating this attribute
    from concurrent requests (User A → User B mid-flight) would silently
    attribute User A's orders to User B — a自본시장법/개인정보보호법
    violation even in paper mode, because TradeHistory rows tie to the
    wrong user.

    Hardening applied here:
      1) `_guarded_claim_trader()` — atomic claim under `trader._lock`;
         refuses the claim if the trader is already running under a
         different user. Only after the claim succeeds do we call `.start()`.
      2) Every non-status route validates ownership before delegating so
         User B cannot manipulate User A's active session (stop/sell-all/
         approve/reject/emergency-halt/pending).
      3) When no session is active (idle trader), user-scoped state
         (_user_id) gets set at claim time and cleared on stop/halt.

    Until autotrader.py is refactored to a per-user instance, this
    ownership guard is the correct mitigation. Procfile is pinned to
    `--workers 1` as a second layer of defence.
"""
from flask import Blueprint, jsonify
from flask_login import current_user

from security import trade_rate_limit
from services import container as _svc
from services.name_resolver import (
    lookup_name_from_signal_cache,
    resolve_stock_name,
)
from .decorators import api_auth, legal_scrub_response

autotrade_bp = Blueprint("autotrade", __name__, url_prefix="/api/autotrade")


def _trader():
    """Return the current AutoTrader singleton, or raise 503 payload.

    Late-binding lookup (via `services.container`) so test harnesses that
    initialise the trader AFTER importing this module see the same
    instance as production. A direct `from services.container import trader`
    binds None at import time and never refreshes.
    """
    return _svc.trader


def _trader_unavailable():
    return (
        jsonify({
            "ok": False,
            "error": "AutoTrader is not initialised on this deployment.",
            "code": "TRADER_UNAVAILABLE",
        }),
        503,
    )


def _enrich_pending_trade(t: dict) -> dict:
    """Return a copy of `t` with `name` guaranteed (falls back to ticker).

    Korean proposals already carry a `name` (see autotrader._propose_trade);
    US proposals don't. We resolve once here so every client gets a
    uniform shape without touching autotrader.py (frozen file).
    """
    if not isinstance(t, dict):
        return t
    enriched = dict(t)
    ticker = enriched.get("ticker") or ""
    if not enriched.get("name"):
        name = lookup_name_from_signal_cache(ticker) or resolve_stock_name(
            ticker
        )
        enriched["name"] = name or ticker
    return enriched


def _current_user_owns_trader(trader) -> bool:
    """True iff the singleton trader is idle OR claimed by current_user."""
    owner = getattr(trader, "_user_id", None)
    if owner is None:
        return True
    return int(owner) == int(current_user.id)


def _ownership_error():
    """Standard 409 response when another user owns the trader session."""
    return (
        jsonify({
            "ok": False,
            "error": "AutoTrader is currently in use by another session. "
                     "Please wait until it completes or contact support.",
            "code": "TRADER_BUSY",
        }),
        409,
    )


def _guarded_claim_trader(trader, user_id: int) -> tuple[bool, dict | None]:
    """Atomic: claim the trader for `user_id` under its internal lock.

    Refuses the claim if the trader is currently running under a
    different user (C1 multi-user leak prevention). If the trader is
    already running under the SAME user, claim succeeds as a no-op.

    Returns (claimed: bool, error_payload: dict|None).
    """
    lock = getattr(trader, "_lock", None)
    if lock is None:
        # Defensive: no lock attribute (shouldn't happen). Fall through to
        # a best-effort check.
        if getattr(trader, "running", False) and getattr(trader, "_user_id", None) not in (None, user_id):
            return False, {"error": "AutoTrader busy", "code": "TRADER_BUSY"}
        trader._user_id = user_id
        return True, None

    with lock:
        owner = getattr(trader, "_user_id", None)
        is_running = bool(getattr(trader, "running", False))
        if is_running and owner is not None and int(owner) != int(user_id):
            return False, {
                "ok": False,
                "error": "AutoTrader is currently in use by another session.",
                "code": "TRADER_BUSY",
            }
        # Safe to (re)claim: either idle, or same user.
        trader._user_id = int(user_id)
        return True, None


@autotrade_bp.route("/status")
@api_auth
@legal_scrub_response
def status():
    trader = _trader()
    if trader is None:
        return _trader_unavailable()
    return jsonify(trader.get_status())


@autotrade_bp.route("/start", methods=["POST"])
@trade_rate_limit
@api_auth
def start():
    trader = _trader()
    if trader is None:
        return _trader_unavailable()
    # C1 fix (2026-04-24): atomic ownership claim under trader._lock
    # BEFORE delegating to start(). This prevents user_id leak between
    # concurrent requests (User A's orders attributed to User B's DB row).
    claimed, err = _guarded_claim_trader(trader, current_user.id)
    if not claimed:
        return jsonify(err), 409
    result = trader.start()
    # If start() failed (e.g. already running under a different user, or
    # broker unavailable), release the claim so the next user can try.
    if isinstance(result, dict) and result.get("error"):
        # Only release if we were the owner AND it didn't actually start.
        if (
            getattr(trader, "_user_id", None) == current_user.id
            and not getattr(trader, "running", False)
        ):
            trader._user_id = None
    return jsonify(result)


@autotrade_bp.route("/stop", methods=["POST"])
@api_auth
def stop():
    trader = _trader()
    if trader is None:
        return _trader_unavailable()
    # Ownership check: only the claiming user (or idle session) may stop.
    if not _current_user_owns_trader(trader):
        return _ownership_error()
    result = trader.stop()
    # Release the claim on successful stop so another user can use the trader.
    if isinstance(result, dict) and result.get("ok"):
        if getattr(trader, "_user_id", None) == current_user.id:
            trader._user_id = None
    return jsonify(result)


@autotrade_bp.route("/sell-all", methods=["POST"])
@trade_rate_limit
@api_auth
@legal_scrub_response
def sell_all():
    trader = _trader()
    if trader is None:
        return _trader_unavailable()
    # Ownership check: cannot sell another user's positions.
    if not _current_user_owns_trader(trader):
        return _ownership_error()
    us_results = trader.force_sell_all()
    kr_results = trader.force_sell_all_kr()
    all_results = us_results.get("results", []) + kr_results
    return jsonify({"results": all_results})


@autotrade_bp.route("/pending", methods=["GET"])
@api_auth
@legal_scrub_response
def get_pending():
    """Get pending trade proposals awaiting user confirmation.

    Each proposal is enriched with a `name` field (company display name)
    so the frontend can render name-large / ticker-small. Falls back to
    ticker when unresolvable.
    """
    trader = _trader()
    if trader is None:
        return jsonify({"ok": True, "pending": []})
    # Ownership check: another user's pending trades must not be visible.
    if not _current_user_owns_trader(trader):
        # Return an empty list rather than an error — matches frontend
        # expectation that idle / foreign sessions show no pending trades.
        return jsonify({"ok": True, "pending": []})
    pending = [
        _enrich_pending_trade(t) for t in (trader.get_pending_trades() or [])
    ]
    return jsonify({"ok": True, "pending": pending})


@autotrade_bp.route("/approve/<trade_id>", methods=["POST"])
@api_auth
@trade_rate_limit
@legal_scrub_response
def approve(trade_id):
    """User approves a pending trade for execution."""
    trader = _trader()
    if trader is None:
        return _trader_unavailable()
    if not _current_user_owns_trader(trader):
        return _ownership_error()
    result = trader.approve_trade(trade_id)
    if not result.get("ok"):
        return jsonify(result), 400
    return jsonify(result)


@autotrade_bp.route("/reject/<trade_id>", methods=["POST"])
@api_auth
@legal_scrub_response
def reject(trade_id):
    """User rejects a pending trade."""
    trader = _trader()
    if trader is None:
        return _trader_unavailable()
    if not _current_user_owns_trader(trader):
        return _ownership_error()
    result = trader.reject_trade(trade_id)
    if not result.get("ok"):
        return jsonify(result), 400
    return jsonify(result)


@autotrade_bp.route("/emergency-halt", methods=["POST"])
@trade_rate_limit
@api_auth
@legal_scrub_response
def emergency_halt():
    """Kill switch: stop trading, close all positions, lock out for 1 hour."""
    trader = _trader()
    if trader is None:
        return _trader_unavailable()
    if not _current_user_owns_trader(trader):
        return _ownership_error()
    result = trader.emergency_halt()
    if "error" in result:
        return jsonify(result), 400
    # Release the ownership claim after a successful halt.
    if getattr(trader, "_user_id", None) == current_user.id:
        trader._user_id = None
    return jsonify(result)
