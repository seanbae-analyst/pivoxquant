"""Signal analysis routes."""
import json
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from flask_login import current_user

from extensions import db
from models import Position, SignalCache, InvestmentProfile
from services import fx_service, cache_service, alert_service
from services.container import engine
from services.name_resolver import canonical_display_name
from services.access_guard import is_user_allowed_ticker, access_denied_response
from .decorators import api_auth, legal_scrub_response
from security import general_rate_limit
import logging

logger = logging.getLogger(__name__)


# 2026-05-17 wave 12 P2: bounded background-refresh pool. The previous
# pattern spawned a fresh `Thread(daemon=True)` per stale ticker per
# request — a single user with N stale tickers minted N threads, each
# opening an app_context + DB session. Under cache cold-start that
# scales to thousands of threads. Pinning a small module-level pool
# so the worst case is `_REFRESH_WORKERS` concurrent refreshes
# regardless of how many requests pile in.
_REFRESH_WORKERS = int(os.environ.get("SIGNAL_REFRESH_WORKERS", "4"))
_refresh_executor = ThreadPoolExecutor(
    max_workers=_REFRESH_WORKERS, thread_name_prefix="signal-refresh"
)


def _get_profile_params():
    """Get current user's investment profile engine params, or None."""
    profile = InvestmentProfile.query.filter_by(user_id=current_user.id).first()
    return profile.to_engine_params() if profile else None


_VALID_LABELS = {"POSITIVE", "NEGATIVE", "NEUTRAL"}
_VALID_WINDOWS = {"today", "7d", "30d", "all"}


def _canonical_name(payload: dict, ticker: str) -> str:
    """Wrapper around ``canonical_display_name`` (BUG-01 follow-up,
    2026-05-10). Overrides legacy English KR names from SignalCache
    rows that were written before PR #227 fixed the source."""
    return canonical_display_name((payload or {}).get("name"), ticker)


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
            # Canonical name (BUG-01 follow-up): KR tickers always
            # Korean, US keeps cached/resolved English. Old SignalCache
            # rows (pre-PR-#227) still carry English KR names — overwrite
            # them so the detail H1 always renders the Korean name.
            d["name"] = _canonical_name(d, t)
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

                    # 2026-05-17 wave 12 P2: submit to the bounded pool
                    # instead of spawning a fresh Thread per ticker.
                    # ThreadPoolExecutor queues over-capacity tasks and
                    # reuses workers, bounding the concurrent app_context +
                    # DB session count regardless of request burst size.
                    _refresh_executor.submit(_refresh)
                except Exception:
                    logger.warning(
                        "failed to submit background refresh ticker=%s",
                        t,
                        exc_info=True,
                    )
        else:
            # No row at all — surface as stale so the client can show "—" / skeleton.
            placeholder = {
                "ticker": t,
                "name": _canonical_name({}, t),
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

    # 2026-05-15 (bug-hunter P0): /detail/<ticker> for AAPL was rendering
    # an indefinite skeleton because `engine.analyze('AAPL')` blocked the
    # Flask thread with no timeout — the FMP / data fetcher path hung
    # specifically for this ticker (Samsung 005930.KS returned 200 in
    # the same session, confirming the hang is ticker-specific, not
    # systemic). SWR stayed in `loadingSignal=true` forever because the
    # response never resolved. The cache-fallback branch below never
    # executed because it only fires when `analyze` returns falsy — a
    # hanging call returns neither.
    #
    # Fix: run engine.analyze in a worker thread with a hard timeout.
    # On timeout we treat it as a soft failure and fall through to the
    # SignalCache fallback (same path as if analyze had returned None).
    # The hung worker is detached — Flask's gunicorn worker keeps
    # serving, and the runaway thread either completes in the
    # background (its result is discarded) or eventually crashes its
    # own thread. Worst case = leaked thread for the gunicorn worker's
    # lifetime; gunicorn's --keep-alive 5 + restart-on-failure policy
    # bounds the leak.
    timeout_s = float(os.environ.get("SIGNAL_DETAIL_TIMEOUT_S", "15"))
    r = None
    timed_out = False
    try:
        with ThreadPoolExecutor(max_workers=1) as _ex:
            future = _ex.submit(
                engine.analyze,
                t_up,
                current_user.available_capital,
                getattr(current_user, "available_capital_krw", 0.0) or 0.0,
                fx_rate=fx_service.get_rate(),
                profile_params=_get_profile_params(),
            )
            try:
                r = future.result(timeout=timeout_s)
            except FuturesTimeoutError:
                timed_out = True
                logger.warning(
                    "signal_detail %s: engine.analyze timed out after %.1fs — "
                    "falling through to SignalCache. user_id=%s",
                    t_up, timeout_s, current_user.id,
                )
                # Note: do NOT cancel the worker; ThreadPoolExecutor's
                # cancel() is best-effort on running tasks. Let the
                # worker complete in the background; gunicorn worker
                # recycling will reclaim if it leaks.
    except Exception as exc:
        # ThreadPoolExecutor setup or pool shutdown error — extremely
        # rare. Log and fall through to cache path.
        logger.exception(
            "signal_detail %s: ThreadPoolExecutor failure: %s", t_up, exc
        )

    if not r:
        cached = db.session.get(SignalCache, t_up)
        if cached and cached.data_json:
            d = json.loads(cached.data_json)
            d["name"] = _canonical_name(d, t_up)
            # Tell the client this is a stale cache hit, not a fresh
            # analyze result. The frontend can render an "approximate"
            # / "last observed" annotation. Honest disclosure beats a
            # silent stale value.
            if timed_out:
                d["is_stale"] = True
                d["stale_reason"] = "analyze_timeout"
            return jsonify(d)
        # Cache empty AND analyze failed — return a structured error
        # the frontend can render as a real error state instead of an
        # indefinite skeleton.
        return jsonify({
            "error": f"Analysis unavailable for '{ticker}'.",
            "code": "ANALYZE_TIMEOUT" if timed_out else "ANALYZE_FAILED",
        }), 504 if timed_out else 404
    cache_service.save_signal(t_up, r)
    r["name"] = _canonical_name(r, t_up)
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
            d["name"] = _canonical_name(d, ticker)
            return jsonify(d)
        return jsonify({"error": f"Analysis failed for '{ticker}'"}), 404
    r["name"] = _canonical_name(r, ticker)
    return jsonify(r)
