"""Signal analysis routes."""
import json
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from flask_login import current_user

from extensions import db
from models import Position, SignalCache, InvestmentProfile
from services import fx_service, cache_service, alert_service
from services.container import engine
from services.name_resolver import resolve_stock_name
from services.access_guard import is_user_allowed_ticker, access_denied_response
from .decorators import api_auth, legal_scrub_response
from security import general_rate_limit
import logging

logger = logging.getLogger(__name__)


def _get_profile_params():
    """Get current user's investment profile engine params, or None."""
    profile = InvestmentProfile.query.filter_by(user_id=current_user.id).first()
    return profile.to_engine_params() if profile else None


_VALID_LABELS = {"POSITIVE", "NEGATIVE", "NEUTRAL"}
_VALID_WINDOWS = {"today", "7d", "30d", "all"}


def _parse_signals_filters() -> dict:
    """W6-2 (2026-05-09): parse the frontend filter contract from query params.

    Hook source of truth: ``frontend/src/lib/hooks.ts::useSignals``.
    Wire format must stay 1:1 — every key the hook may emit is read here.
    Invalid values are dropped silently (defensive; frontend validates first).
    """
    raw_labels = (request.args.get("labels") or "").strip()
    labels: set[str] = set()
    if raw_labels:
        for part in raw_labels.split(","):
            tok = part.strip().upper()
            if tok in _VALID_LABELS:
                labels.add(tok)

    def _bounded_float(name: str, default: float, lo: float, hi: float) -> float:
        try:
            v = float(request.args.get(name, default))
        except (TypeError, ValueError):
            return default
        if v != v:  # NaN
            return default
        return max(lo, min(hi, v))

    strength_min = _bounded_float("strength_min", 0.0, 0.0, 1.0)
    strength_max = _bounded_float("strength_max", 1.0, 0.0, 1.0)
    if strength_min > strength_max:
        strength_min, strength_max = 0.0, 1.0

    symbol = (request.args.get("symbol") or "").strip().upper() or None

    window = (request.args.get("window") or "all").lower()
    if window not in _VALID_WINDOWS:
        window = "all"

    return {
        "labels": labels,
        "strength_min": strength_min,
        "strength_max": strength_max,
        "symbol": symbol,
        "window": window,
    }


def _strength_of(d: dict) -> float:
    """Mirror of frontend ``strengthOf`` (lib/hooks helpers)."""
    s = d.get("strength")
    if isinstance(s, (int, float)):
        return max(0.0, min(1.0, float(s)))
    score = d.get("score")
    if isinstance(score, (int, float)):
        return max(0.0, min(1.0, float(score) / 100.0))
    return 0.0


def _label_of(d: dict) -> str:
    """Mirror of frontend ``labelOf``."""
    raw = (d.get("label") or d.get("signal") or "").upper()
    if raw == "POSITIVE":
        return "POSITIVE"
    if raw == "NEGATIVE":
        return "NEGATIVE"
    return "NEUTRAL"


def _within_window(d: dict, window: str) -> bool:
    """Mirror of frontend ``isWithinWindow``."""
    if window == "all":
        return True
    obs = d.get("observed_at")
    if not obs:
        return True
    try:
        ts = datetime.fromisoformat(obs.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return True
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - ts
    if delta < timedelta(0):
        # Future timestamp from clock skew — treat as fresh, do not filter out.
        return True
    if window == "today":
        return delta <= timedelta(days=1)
    if window == "7d":
        return delta <= timedelta(days=7)
    if window == "30d":
        return delta <= timedelta(days=30)
    return True


signals_bp = Blueprint("signals", __name__, url_prefix="/api")


@signals_bp.route("/signals")
@api_auth
@legal_scrub_response
def get_signals():
    # W6-2 (2026-05-09): honor frontend filter contract so SWR cache keys
    # carrying the same effective query collapse to a single backend hit.
    # Without this, every filter toggle minted a new SWR key against the
    # same response payload — cache fragmentation + extra network traffic.
    # Frontend keeps its own client-side filter pass as a defensive layer.
    flt = _parse_signals_filters()
    user_positions = {p.ticker for p in Position.query.filter_by(user_id=current_user.id).all()}

    # Symbol filter narrows the source set so we don't load + filter signals
    # we'd discard anyway. ``access_guard`` semantics still apply (we never
    # surface a ticker outside the user's allowed set).
    if flt["symbol"]:
        if flt["symbol"] not in user_positions:
            return jsonify({"signals": []})
        tickers = {flt["symbol"]}
    else:
        tickers = user_positions

    # Batch-load SignalCache for all user positions in a single query (avoid N+1).
    cache_map = {
        c.ticker: c
        for c in SignalCache.query.filter(SignalCache.ticker.in_(list(tickers))).all()
    } if tickers else {}
    out = []
    for t in tickers:
        c = cache_map.get(t)
        if c and c.data_json:
            try:
                d = json.loads(c.data_json)
            except json.JSONDecodeError:
                d = {}
            stale = c.is_stale()
            d["cached_at"] = c.updated_at.isoformat()
            d["observed_at"] = c.updated_at.isoformat()
            d["is_stale"] = stale
            # Backfill name: SignalCache blobs are populated by engine.analyze()
            # which may emit bare ticker when the broker snapshot lacks a name.
            # resolve_stock_name guarantees 회사명 for every KRX/US listing.
            if not d.get("name") or d.get("name") == t:
                d["name"] = resolve_stock_name(t) or t
            d.setdefault("ticker", t)

            # Apply server-side filter — drops signals outside the contract.
            if flt["labels"] and _label_of(d) not in flt["labels"]:
                continue
            s = _strength_of(d)
            if s < flt["strength_min"] or s > flt["strength_max"]:
                continue
            if not _within_window(d, flt["window"]):
                continue

            out.append(d)

            # Best-effort background refresh when stale so subsequent reads
            # see fresh data. Never blocks the current response.
            if stale:
                try:
                    from threading import Thread
                    from flask import current_app
                    app_obj = current_app._get_current_object()
                    capital = current_user.available_capital

                    def _refresh(ticker=t, cap=capital, app=app_obj):
                        with app.app_context():
                            try:
                                cache_service.cache_ticker(ticker, cap, engine)
                            except Exception:
                                logger.warning(
                                    "background cache_ticker failed ticker=%s",
                                    ticker,
                                    exc_info=True,
                                )

                    Thread(target=_refresh, daemon=True).start()
                except Exception:
                    logger.warning(
                        "failed to spawn background refresh ticker=%s",
                        t,
                        exc_info=True,
                    )
        else:
            # No row at all — surface as stale so the client can show "—" / skeleton.
            placeholder = {
                "ticker": t,
                "name": resolve_stock_name(t) or t,
                "observed_at": None,
                "is_stale": True,
                "label": "NEUTRAL",  # placeholder rows are NEUTRAL by design
            }
            # Honor label filter — placeholder is NEUTRAL.
            if flt["labels"] and "NEUTRAL" not in flt["labels"]:
                continue
            # Strength filter — placeholders score 0, drop if min > 0.
            if flt["strength_min"] > 0.0:
                continue
            # Window: observed_at None → treated as visible (matches frontend).
            out.append(placeholder)
    return jsonify({"signals": out})


@signals_bp.route("/signals/<ticker>")
@api_auth
@legal_scrub_response
def signal_detail(ticker):
    t_up = ticker.upper()
    # §101 회피 — 보유/watchlist 종목만 분석 허용.
    if not is_user_allowed_ticker(current_user.id, t_up):
        body, status = access_denied_response()
        return jsonify(body), status
    r = engine.analyze(t_up, current_user.available_capital,
                       getattr(current_user, "available_capital_krw", 0.0) or 0.0,
                       fx_rate=fx_service.get_rate(),
                       profile_params=_get_profile_params())
    if not r:
        cached = db.session.get(SignalCache, t_up)
        if cached and cached.data_json:
            d = json.loads(cached.data_json)
            if not d.get("name") or d.get("name") == t_up:
                d["name"] = resolve_stock_name(t_up) or t_up
            return jsonify(d)
        return jsonify({"error": f"Analysis failed for '{ticker}'. Check the ticker symbol."}), 404
    cache_service.save_signal(t_up, r)
    if not r.get("name") or r.get("name") == t_up:
        r["name"] = resolve_stock_name(t_up) or t_up
    return jsonify(r)


@signals_bp.route("/signals/refresh", methods=["POST"])
@api_auth
@legal_scrub_response
@general_rate_limit
def refresh():
    positions = Position.query.filter_by(user_id=current_user.id).all()
    pos_map = {p.ticker: p for p in positions}
    # Batch-load SignalCache for all user positions in a single query (avoid N+1).
    cache_map = {
        c.ticker: c
        for c in SignalCache.query.filter(SignalCache.ticker.in_(list(pos_map.keys()))).all()
    } if pos_map else {}
    done = []
    for t, p in pos_map.items():
        cached = cache_map.get(t)
        cur_price = json.loads(cached.data_json).get("price", p.avg_cost) if cached and cached.data_json else p.avg_cost
        pnl_pct = (cur_price - p.avg_cost) / p.avg_cost * 100 if p.avg_cost > 0 else 0
        r = engine.analyze(t, current_user.available_capital,
                           getattr(current_user, "available_capital_krw", 0.0) or 0.0,
                           fx_rate=fx_service.get_rate(), current_pnl_pct=pnl_pct,
                           profile_params=_get_profile_params())
        if r:
            cache_service.save_signal(t, r)
            alert_service.maybe_generate(current_user.id, r)
            done.append(t)
    return jsonify({"ok": True, "refreshed": done})


@signals_bp.route("/scan", methods=["POST"])
@api_auth
@legal_scrub_response
@general_rate_limit
def scan():
    ticker = ((request.get_json() or {}).get("ticker") or "").strip().upper()
    if not ticker:
        return jsonify({"error": "Ticker required"}), 400
    # §101 회피 — 보유/watchlist 종목만 스캔 허용.
    if not is_user_allowed_ticker(current_user.id, ticker):
        body, status = access_denied_response()
        return jsonify(body), status
    r = engine.analyze(ticker, current_user.available_capital,
                       getattr(current_user, "available_capital_krw", 0.0) or 0.0,
                       fx_rate=fx_service.get_rate(),
                       profile_params=_get_profile_params())
    if not r:
        cached = db.session.get(SignalCache, ticker)
        if cached and cached.data_json:
            d = json.loads(cached.data_json)
            if not d.get("name") or d.get("name") == ticker:
                d["name"] = resolve_stock_name(ticker) or ticker
            return jsonify(d)
        return jsonify({"error": f"Analysis failed for '{ticker}'"}), 404
    if not r.get("name") or r.get("name") == ticker:
        r["name"] = resolve_stock_name(ticker) or ticker
    return jsonify(r)
