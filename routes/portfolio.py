"""Portfolio routes: positions CRUD, buy/sell, capital, analytics."""
import json
import logging
import threading
from datetime import datetime, timezone
from functools import wraps
from flask import Blueprint, current_app, request, jsonify, make_response
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Position, SignalCache, TradeHistory
from security import trade_rate_limit
from services import fx_service, cache_service
from services.error_responses import api_error
from services.name_resolver import resolve_stock_name, canonical_display_name
from services.container import engine, fetcher, realtime
from services.price_overlay import overlay_prices, parse_price_display
from services.ticker_normalizer import normalize_ticker
from .decorators import api_auth, legal_scrub_response

logger = logging.getLogger(__name__)

portfolio_bp = Blueprint("portfolio", __name__, url_prefix="/api/portfolio")


# ── Deprecation marker for legacy singular `/position` endpoints ─────────────
# 2026-05-02: frontend (endpoints.ts) was migrated to the plural
# `/positions[/<id>]` aliases. The singular handlers remain so existing
# pytest coverage and any out-of-tree callers keep working, but every call
# emits a warning log + RFC 8594 Deprecation/Sunset response headers so
# operators can monitor real-world usage before final removal.
_SINGULAR_POSITION_SUNSET = "Sun, 01 Nov 2026 00:00:00 GMT"


def _deprecated_singular(plural_hint: str):
    """Decorator that wraps a Flask view to emit deprecation telemetry.

    - logger.warning on every call (one-line, with user_id + path)
    - adds `Deprecation: true`, `Sunset: <date>`, and a `Link` header
      pointing at the recommended plural endpoint
    - response body is unchanged so existing clients are unaffected
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                uid = getattr(current_user, "id", None)
            except Exception:
                uid = None
            logger.warning(
                "deprecated_singular_position_endpoint path=%s user_id=%s use_instead=%s",
                request.path, uid, plural_hint,
            )
            rv = fn(*args, **kwargs)
            try:
                resp = make_response(rv)
                resp.headers.setdefault("Deprecation", "true")
                resp.headers.setdefault("Sunset", _SINGULAR_POSITION_SUNSET)
                resp.headers.setdefault(
                    "Link", f'<{plural_hint}>; rel="successor-version"',
                )
                return resp
            except Exception:
                # Defensive: never break the response just to attach a header.
                return rv
        return wrapper
    return decorator


def _cache_ticker_async(app, ticker: str, capital: float):
    """Warm the SignalCache for a newly-added ticker without blocking the
    HTTP response. engine.analyze() can take 10-30s when FMP/Alpaca are
    slow (e.g. FMP 402 fallbacks), which would exceed the frontend
    apiFetch timeout and surface as a false 'add failed' error even
    though the Position row was already committed. Running it in a
    background thread keeps add_position snappy and idempotent —
    the cache miss on the next GET /portfolio call will simply fall
    back to stored avg_cost defaults, exactly as cache_service already
    handles."""
    def _run():
        with app.app_context():
            try:
                cache_service.cache_ticker(ticker, capital, engine)
            except Exception as e:
                logger.error("Background cache_ticker failed %s: %s", ticker, e)

    threading.Thread(target=_run, daemon=True).start()


# ── avg_cost plausibility guard (Bug #4, 2026-05-14) ────────────────────────
# A test/typo position (AAPL avg_cost=$30 — AAPL last traded at $30 in 2013)
# drove the portfolio equity curve to +593,259%. The position-write paths
# had no sanity check on avg_cost against a realistic price floor.
#
# Guard policy: reject avg_cost that is below 50% of the ticker's trailing
# 52-week low. This catches stale/typo cost-basis entries (an order of
# magnitude off) while still allowing legitimate deep-discount holdings —
# a real long-term holder who bought near a multi-year low is still well
# within 50% of the *52-week* low.
#
# FAIL-OPEN: if the 52-week low cannot be fetched (FMP plan-gated symbol,
# provider outage, KR ticker without FMP coverage), the guard returns None
# and the write proceeds. A data outage must never block a legitimate add.
_AVG_COST_FLOOR_RATIO = 0.5


def _avg_cost_implausible(ticker: str, avg_cost: float) -> str | None:
    """Return a human error string if ``avg_cost`` is implausibly low for
    ``ticker``, else None. Fails open on any data-fetch failure."""
    try:
        if avg_cost <= 0:
            return None  # zero/negative already rejected upstream
        from services.data import fmp as _fmp
        quote = _fmp.get_quote(ticker)
        if not quote:
            return None  # fail-open: no quote → cannot validate
        raw_low = quote.get("yearLow")
        if raw_low in (None, ""):
            return None  # fail-open: provider omitted the field
        year_low = float(raw_low)
        if year_low <= 0:
            return None  # fail-open: unusable field
        floor = year_low * _AVG_COST_FLOOR_RATIO
        if avg_cost < floor:
            logger.warning(
                "avg_cost guard: %s avg_cost=%.2f below floor=%.2f "
                "(52w low=%.2f x %.2f) — rejecting",
                ticker, avg_cost, floor, year_low, _AVG_COST_FLOOR_RATIO,
            )
            return (
                f"Average cost {avg_cost:,.2f} is implausibly low for "
                f"{ticker} (below 50% of its 52-week low of "
                f"{year_low:,.2f}). Please re-check the cost basis."
            )
        return None
    except Exception as e:  # pragma: no cover - defensive, always fail-open
        logger.debug("avg_cost guard fail-open for %s: %s", ticker, e)
        return None


@portfolio_bp.route("")
@api_auth
@legal_scrub_response
def get_portfolio():
    # Refresh FX rate in background so a slow/unavailable upstream (FMP 402,
    # exchangerate-api timeout) does not add 5-15s to every portfolio load.
    # The stale cached rate (default 1380.0) is accurate enough for display;
    # the scheduler refreshes it every 5 minutes via APScheduler.
    threading.Thread(target=fx_service.refresh, daemon=True).start()
    positions = Position.query.filter_by(user_id=current_user.id).all()

    # Batch-load all SignalCache rows in a single query to avoid N+1.
    tickers = [p.ticker for p in positions]
    cache_map = {
        c.ticker: c
        for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
    } if tickers else {}
    # Freshness overlay — never let this endpoint emit a stale "current price".
    overlay = overlay_prices(tickers)

    out = []
    for p in positions:
        cached = cache_map.get(p.ticker)
        sd = json.loads(cached.data_json) if cached and cached.data_json else {}
        is_kr = p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ")
        o = overlay.get(p.ticker) or {}
        # Bug C (2026-04-24): add price_display parse as last-resort before
        # avg_cost fallback. Matches the new behavior of overlay_prices
        # tier-3 but also covers rows whose cache blob is so old that
        # SignalCache.query returned no row at all.
        cur_px_raw = o.get("price") or sd.get("price")
        if not cur_px_raw:
            cur_px_raw = parse_price_display(sd.get("price_display"))
        cur_px = float(cur_px_raw or p.avg_cost or 0)
        observed_at = o.get("observed_at")
        if o.get("source"):
            price_source = o["source"]
        elif sd.get("price"):
            price_source = "stale"
        elif cur_px_raw:
            price_source = "stale_display"
        else:
            price_source = "avg_cost"
        pnl = (cur_px - p.avg_cost) / p.avg_cost * 100 if p.avg_cost else 0

        # 2026-05-09 abnormal-return guard (CEO live sanity flagged AAPL +877%):
        # An absolute pnl beyond ±500% is almost certainly stale FMP data
        # or a split-mismatched price (the same FMP /quote bug guarded by
        # `_quote_price_sane` upstream — but a self-consistent stale snapshot
        # can still slip the marketCap cross-check). Demote price_source to
        # "abnormal_pnl_guard" and clamp pnl to None so the UI shows "—"
        # instead of a garbage number. The avg_cost stays untouched — only
        # the display effect of cur_px is suppressed.
        if p.avg_cost and abs(pnl) > 500:
            logger.warning(
                "portfolio.get %s pnl=%.2f%% (cur=%.4f vs avg=%.4f) exceeds "
                "±500%% — likely stale price; demoting to avg_cost fallback",
                p.ticker, pnl, cur_px, p.avg_cost,
            )
            cur_px = float(p.avg_cost)
            pnl = 0
            price_source = "abnormal_pnl_guard"
        cur = sd.get("currency", "KRW" if is_kr else "USD")

        buy_fx = getattr(p, 'buy_fx_rate', 0) or 0
        krw_pnl_pct = krw_cost = krw_value = None
        if is_kr:
            krw_cost = round(p.avg_cost * p.shares)
            krw_value = round(cur_px * p.shares)
            krw_pnl_pct = round((krw_value - krw_cost) / krw_cost * 100, 2) if krw_cost else 0
        elif buy_fx > 0:
            krw_cost = p.avg_cost * buy_fx * p.shares
            krw_value = cur_px * fx_service.get_rate() * p.shares
            krw_pnl_pct = round((krw_value - krw_cost) / krw_cost * 100, 2) if krw_cost else 0

        # Prefer cache name only when it differs from the raw ticker.
        # If SignalCache stored the ticker itself as name (fetcher fallback
        # when KIS/FMP returned no name), ignore it and re-resolve via
        # kr_stock_registry/pyKRX (KR) or us_stock_registry (US).
        # Option B: skip stale name == ticker entries.
        cached_name = sd.get("name")
        if cached_name and cached_name.upper() != p.ticker.upper():
            display_name = cached_name
        else:
            display_name = resolve_stock_name(p.ticker) or p.ticker

        out.append({
            "id": p.id, "ticker": p.ticker, "shares": p.shares,
            "avg_cost": p.avg_cost, "price": cur_px, "current_price": cur_px,
            "price_display": sd.get("price_display", f"${cur_px:.2f}"),
            "observed_at": observed_at,
            "price_source": price_source,
            "pnl_pct": round(pnl, 2), "pnl_krw_pct": krw_pnl_pct,
            "buy_fx_rate": buy_fx,
            "cur_fx_rate": fx_service.get_rate() if not is_kr else 0,
            "krw_cost": round(krw_cost) if krw_cost else None,
            "krw_value": round(krw_value) if krw_value else None,
            "market_value": round(cur_px * p.shares, 2),
            "signal": sd.get("signal", "—"), "score": sd.get("score", 0),
            "rec_shares": sd.get("rec_shares", 0),
            "rec_investment": sd.get("rec_investment", 0),
            "rec_timing": sd.get("rec_timing", ""),
            "name": display_name,
            "sector": sd.get("sector", "Unknown"),
            "currency": cur, "is_korean": sd.get("is_korean", is_kr),
            "sell_pct": sd.get("sell_pct", 0),
            "sell_timing": sd.get("sell_timing", ""),
            "capital_needed": sd.get("capital_needed"),
            "capital_gap": sd.get("capital_gap"),
            "take_profit": sd.get("take_profit"),
            "stop_loss": sd.get("stop_loss"),
            "tp_pct": sd.get("tp_pct", 0), "sl_pct": sd.get("sl_pct", 0),
            "regime_profile": sd.get("regime_profile", ""),
            "regime_label": sd.get("regime_label", ""),
            "regime_label_kr": sd.get("regime_label_kr", ""),
            "priority": sd.get("priority", 0),
        })

    total_usd = sum(p["market_value"] for p in out if p["currency"] == "USD")
    total_krw = sum(p["market_value"] for p in out if p["currency"] == "KRW")
    total_all_krw = round(total_usd * fx_service.get_rate() + total_krw)
    cap_krw = getattr(current_user, "available_capital_krw", 0.0) or 0.0

    return jsonify({
        "positions": out,
        "available_capital": current_user.available_capital,
        "available_capital_krw": cap_krw,
        "total_value_usd": round(total_usd, 2),
        "total_value_krw": round(total_krw, 0),
        "total_value_all_krw": total_all_krw,
        "fx_rate": fx_service.get_rate(),
    })


@portfolio_bp.route("/position", methods=["POST"])
@api_auth
@trade_rate_limit
@_deprecated_singular("/api/portfolio/positions")
def add_position():
    # Tier check: Free users limited to 3 positions
    # Use effective_tier so DEV_PREMIUM_EMAILS can bypass the free-plan cap.
    if getattr(current_user, "effective_tier", None) in (None, "free"):
        position_count = Position.query.filter_by(user_id=current_user.id).count()
        if position_count >= 3:
            return jsonify({
                "error": "Free plan limited to 3 positions. Upgrade to Pro for unlimited.",
                "code": "TIER_LIMIT",
                "current_count": position_count,
                "limit": 3,
            }), 403

    d = request.get_json() or {}
    raw_ticker = (d.get("ticker") or "").strip().upper()
    # Bug #1 fix (2026-05-13): route through normalize_ticker so bare
    # 6-digit KRX codes (e.g. "005930") auto-resolve to "005930.KS" /
    # "035760.KQ". Without this every KR user's portfolio rows were
    # stored as bare digits → name_resolver never matched → currency
    # fell through to USD → "$54,000" instead of "₩54,000".
    ticker = normalize_ticker(raw_ticker)
    thesis = (d.get("thesis") or "").strip()[:500] or None
    try:
        shares = float(d.get("shares") or 0)
        cost = float(d.get("avg_cost") or 0)
    except (TypeError, ValueError):
        return api_error(
            en="Shares and average cost must be numbers", kr="주식 수와 평균가는 숫자여야 합니다.",
            code="POSITION_NUMERIC_REQUIRED", status=400,
        )
    # SEC-004: Position.ticker is db.String(20). Reject before SQL so the DB
    # never raises DataError (which would have bubbled up via the leaky
    # f-string error response).
    if not ticker or len(ticker) > 20:
        return api_error(
            en="Invalid ticker", kr="유효하지 않은 종목입니다.",
            code="INVALID_TICKER", status=400,
        )
    if shares <= 0 or cost <= 0:
        return api_error(
            en="Shares and average cost required", kr="주식 수와 평균가가 필요합니다.",
            code="POSITION_FIELDS_REQUIRED", status=400,
        )
    # Bug #4 guard: reject implausibly-low cost basis (test/typo data).
    _implausible = _avg_cost_implausible(ticker, cost)
    if _implausible:
        return api_error(
            en=_implausible,
            kr="평균 매입가가 비현실적입니다. 다시 확인해 주세요.",
            code="AVG_COST_IMPLAUSIBLE", status=400,
        )
    is_kr = ticker.endswith(".KS") or ticker.endswith(".KQ")
    fx_rate = fx_service.get_rate() if not is_kr else 0.0
    # NEW-D (2026-05-09): two-phase race-safe upsert.
    # Phase 1 (cheap path): SELECT + merge if row exists, else INSERT new.
    # Phase 2 (race recovery): if a concurrent request inserted between our
    # SELECT and INSERT, the new uq_positions_user_ticker constraint will
    # raise IntegrityError on commit. We rollback, re-fetch, and retry the
    # merge path — making concurrent add_position calls idempotent (the
    # second one folds into the first).
    def _merge_into(ex_row):
        total = ex_row.shares * ex_row.avg_cost + shares * cost
        if not is_kr and ex_row.buy_fx_rate and fx_rate:
            ex_row.buy_fx_rate = (
                ex_row.buy_fx_rate * ex_row.shares * ex_row.avg_cost
                + fx_rate * shares * cost
            ) / total
        ex_row.shares += shares
        ex_row.avg_cost = total / ex_row.shares
        if thesis and not ex_row.thesis:
            ex_row.thesis = thesis
            ex_row.thesis_created_at = datetime.now(timezone.utc).replace(tzinfo=None)
            ex_row.thesis_status = "pending"

    try:
        ex = Position.query.filter_by(user_id=current_user.id, ticker=ticker).first()
        if ex:
            _merge_into(ex)
        else:
            db.session.add(Position(
                user_id=current_user.id, ticker=ticker,
                shares=shares, avg_cost=cost, buy_fx_rate=fx_rate,
                thesis=thesis,
                thesis_created_at=datetime.now(timezone.utc).replace(tzinfo=None) if thesis else None,
                thesis_status="pending" if thesis else "pending",
            ))
        db.session.commit()
    except IntegrityError:
        # Concurrent insert collided on uq_positions_user_ticker — recover
        # by re-fetching the now-committed row and merging into it.
        db.session.rollback()
        logger.info("add_position race recovery for user=%s ticker=%s",
                    current_user.id, ticker)
        try:
            ex = Position.query.filter_by(
                user_id=current_user.id, ticker=ticker,
            ).first()
            if ex is None:
                # Extremely unlikely: constraint hit but row vanished. Surface
                # a 409 so the client can retry rather than masking as 500.
                return jsonify({
                    "error": "Position add raced; please retry.",
                    "code": "POSITION_RACE",
                }), 409
            _merge_into(ex)
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception("add_position race recovery failed")
            return api_error(
            en="Failed to save position", kr="포지션 저장에 실패했습니다.",
            code="POSITION_SAVE_FAILED", status=500,
        )
    except Exception:
        db.session.rollback()
        logger.exception("add_position DB commit failed")
        return api_error(
            en="Failed to save position", kr="포지션 저장에 실패했습니다.",
            code="POSITION_SAVE_FAILED", status=500,
        )

    # Warm the signal cache in the background — see _cache_ticker_async.
    _cache_ticker_async(
        current_app._get_current_object(),
        ticker,
        current_user.available_capital,
    )

    # Resolve display name synchronously so the client can show 회사명
    # immediately, before the background cache warm finishes.
    # Uses name_resolver (pyKRX for KR, us_stock_registry for US) so every
    # long-tail KRX listing resolves even on first add.
    from services.name_resolver import resolve_stock_name
    resolved_name = resolve_stock_name(ticker)
    return jsonify({
        "ok": True,
        "ticker": ticker,
        "name": resolved_name or ticker,
        "is_korean": is_kr,
    })


@portfolio_bp.route("/position/<int:pid>", methods=["PUT"])
@api_auth
@trade_rate_limit
@_deprecated_singular("/api/portfolio/positions/<id>")
def edit_position(pid):
    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p:
        return api_error(
            en="Position not found", kr="포지션을 찾을 수 없습니다.",
            code="POSITION_NOT_FOUND", status=404,
        )
    d = request.get_json() or {}
    try:
        shares = float(d.get("shares") or 0)
        cost = float(d.get("avg_cost") or 0)
    except (TypeError, ValueError):
        return api_error(
            en="Shares and average cost must be numbers", kr="주식 수와 평균가는 숫자여야 합니다.",
            code="POSITION_NUMERIC_REQUIRED", status=400,
        )
    if shares <= 0 or cost <= 0:
        return api_error(
            en="Shares and average cost must be positive", kr="주식 수와 평균가는 양수여야 합니다.",
            code="POSITION_POSITIVE_REQUIRED", status=400,
        )
    # Bug #4 guard: reject implausibly-low cost basis (test/typo data).
    _implausible = _avg_cost_implausible(p.ticker, cost)
    if _implausible:
        return api_error(
            en=_implausible,
            kr="평균 매입가가 비현실적입니다. 다시 확인해 주세요.",
            code="AVG_COST_IMPLAUSIBLE", status=400,
        )
    p.shares = shares
    p.avg_cost = cost
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("edit_position commit failed")
        return api_error(
            en="Failed to update position", kr="포지션 업데이트에 실패했습니다.",
            code="POSITION_UPDATE_FAILED", status=500,
        )
    cache_service.cache_ticker(p.ticker, current_user.available_capital, engine)
    return jsonify({"ok": True})


@portfolio_bp.route("/position/<int:pid>", methods=["DELETE"])
@api_auth
@trade_rate_limit
@_deprecated_singular("/api/portfolio/positions/<id>")
def del_position(pid):
    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p:
        return api_error(
            en="Position not found", kr="포지션을 찾을 수 없습니다.",
            code="POSITION_NOT_FOUND", status=404,
        )
    try:
        db.session.delete(p)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("del_position failed")
        return api_error(
            en="Failed to delete position", kr="포지션 삭제에 실패했습니다.",
            code="POSITION_DELETE_FAILED", status=500,
        )
    return jsonify({"ok": True})


@portfolio_bp.route("/position/<int:pid>/buy", methods=["POST"])
@api_auth
@trade_rate_limit
@_deprecated_singular("/api/portfolio/trades")
def buy_more(pid):
    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p:
        return api_error(
            en="Position not found", kr="포지션을 찾을 수 없습니다.",
            code="POSITION_NOT_FOUND", status=404,
        )
    d = request.get_json() or {}
    try:
        buy_shares = float(d.get("shares") or 0)
        buy_price = float(d.get("price") or 0)
    except (TypeError, ValueError):
        return api_error(
            en="Shares and price must be numbers", kr="주식 수와 가격은 숫자여야 합니다.",
            code="TRADE_NUMERIC_REQUIRED", status=400,
        )
    if buy_shares <= 0 or buy_price <= 0:
        return api_error(
            en="Shares and price required", kr="주식 수와 가격이 필요합니다.",
            code="TRADE_FIELDS_REQUIRED", status=400,
        )

    cost = buy_shares * buy_price
    # Use TTL-aware cache accessor for consistency with the rest of the codebase.
    # get_signal() returns None if the row is stale, so callers fall back to
    # safe defaults below instead of rendering stale name/currency values.
    cached = cache_service.get_signal(p.ticker)
    sd = json.loads(cached.data_json) if cached and cached.data_json else {}
    is_kr = sd.get("is_korean", False)
    name = canonical_display_name(sd.get("name"), p.ticker)
    currency = sd.get("currency", "USD")

    if is_kr:
        avail = getattr(current_user, "available_capital_krw", 0) or 0
        if avail < cost:
            return api_error(
                en=f"Insufficient KRW capital (need ₩{cost:,.0f}, have ₩{avail:,.0f})",
                kr=f"KRW 시드머니 부족 (필요 ₩{cost:,.0f}, 보유 ₩{avail:,.0f}).",
                code="INSUFFICIENT_CAPITAL_KRW", status=400,
            )
        current_user.available_capital_krw = avail - cost
    else:
        avail = current_user.available_capital or 0
        if avail < cost:
            return api_error(
                en=f"Insufficient capital (need ${cost:,.2f}, have ${avail:,.2f})",
                kr=f"USD 시드머니 부족 (필요 ${cost:,.2f}, 보유 ${avail:,.2f}).",
                code="INSUFFICIENT_CAPITAL_USD", status=400,
            )
        current_user.available_capital = avail - cost

    total_cost = p.shares * p.avg_cost + buy_shares * buy_price
    p.shares += buy_shares
    p.avg_cost = total_cost / p.shares

    db.session.add(TradeHistory(
        user_id=current_user.id, ticker=p.ticker, name=name,
        action="BUY", shares=buy_shares, price_per_share=round(buy_price, 2),
        total_value=round(cost, 2), pnl=0, pnl_pct=0, currency=currency,
    ))
    db.session.commit()
    return jsonify({
        "ok": True,
        "new_shares": round(p.shares, 4),
        "new_avg_cost": round(p.avg_cost, 2),
        "new_capital_usd": current_user.available_capital,
        "new_capital_krw": getattr(current_user, "available_capital_krw", 0) or 0,
    })


@portfolio_bp.route("/position/buy-new", methods=["POST"])
@api_auth
@trade_rate_limit
@_deprecated_singular("/api/portfolio/trades")
def buy_new_position():
    # Free-tier cap: same 3-position guard as add_position. Without this,
    # POST /position/buy-new bypasses the tier limit and lets free users
    # accumulate unlimited positions (revenue/tier-enforcement bypass).
    if getattr(current_user, "effective_tier", None) in (None, "free"):
        position_count = Position.query.filter_by(user_id=current_user.id).count()
        if position_count >= 3:
            return jsonify({
                "error": "Free plan limited to 3 positions. Upgrade to Pro for unlimited.",
                "code": "TIER_LIMIT",
                "current_count": position_count,
                "limit": 3,
            }), 403

    d = request.get_json() or {}
    raw_ticker = (d.get("ticker") or "").strip().upper()
    # Bug #1 fix (2026-05-13): normalize before any downstream usage so
    # "005930" routes to "005930.KS" / "035760.KQ" via the registry. See
    # add_position for the full rationale.
    ticker = normalize_ticker(raw_ticker)
    try:
        shares = float(d.get("shares") or 0)
        price = float(d.get("price") or 0)
    except (TypeError, ValueError):
        return api_error(
            en="Shares and price must be numbers", kr="주식 수와 가격은 숫자여야 합니다.",
            code="TRADE_NUMERIC_REQUIRED", status=400,
        )
    # SEC-004: Position.ticker is db.String(20); validate before persisting.
    if not ticker or len(ticker) > 20:
        return api_error(
            en="Invalid ticker", kr="유효하지 않은 종목입니다.",
            code="INVALID_TICKER", status=400,
        )
    if shares <= 0 or price <= 0:
        return api_error(
            en="Ticker, shares, and price required", kr="종목, 주식 수, 가격이 필요합니다.",
            code="TRADE_FIELDS_REQUIRED", status=400,
        )

    cost = shares * price
    currency = fetcher.currency(ticker)
    is_kr = currency == "KRW"

    cap = (getattr(current_user, "available_capital_krw", 0) or 0) if is_kr else (current_user.available_capital or 0)
    if cap < cost:
        sym = "₩" if is_kr else "$"
        return api_error(
            en=f"Insufficient capital (need {sym}{cost:,.0f}, have {sym}{cap:,.0f})",
            kr=f"시드머니 부족 (필요 {sym}{cost:,.0f}, 보유 {sym}{cap:,.0f}).",
            code="INSUFFICIENT_CAPITAL", status=400,
        )

    # NEW-D (2026-05-09): race-safe upsert against uq_positions_user_ticker.
    def _merge_buy_new(ex_row):
        total = ex_row.shares * ex_row.avg_cost + shares * price
        ex_row.shares += shares
        ex_row.avg_cost = total / ex_row.shares

    p = Position.query.filter_by(ticker=ticker, user_id=current_user.id).first()
    if p:
        _merge_buy_new(p)
    else:
        p = Position(user_id=current_user.id, ticker=ticker, shares=shares, avg_cost=price)
        db.session.add(p)

    if is_kr:
        current_user.available_capital_krw = cap - cost
    else:
        current_user.available_capital = cap - cost

    cached = cache_service.get_signal(ticker)
    sd = json.loads(cached.data_json) if cached and cached.data_json else {}
    name = canonical_display_name(sd.get("name"), ticker)
    db.session.add(TradeHistory(
        user_id=current_user.id, ticker=ticker, name=name,
        action="BUY", shares=shares, price_per_share=round(price, 2),
        total_value=round(cost, 2), pnl=0, pnl_pct=0, currency=currency,
    ))
    try:
        db.session.commit()
    except IntegrityError:
        # Concurrent add_position / create_position_alias / buy_new_position
        # raced ahead. Roll back, re-fetch, and merge into the surviving row
        # so capital + trade history still apply correctly.
        db.session.rollback()
        logger.info("buy_new_position race recovery user=%s ticker=%s",
                    current_user.id, ticker)
        try:
            ex = Position.query.filter_by(
                user_id=current_user.id, ticker=ticker,
            ).first()
            if ex is None:
                return jsonify({
                    "error": "Buy raced; please retry.",
                    "code": "POSITION_RACE",
                }), 409
            _merge_buy_new(ex)
            if is_kr:
                current_user.available_capital_krw = (cap - cost)
            else:
                current_user.available_capital = (cap - cost)
            db.session.add(TradeHistory(
                user_id=current_user.id, ticker=ticker, name=name,
                action="BUY", shares=shares, price_per_share=round(price, 2),
                total_value=round(cost, 2), pnl=0, pnl_pct=0, currency=currency,
            ))
            db.session.commit()
            p = ex
        except Exception:
            db.session.rollback()
            logger.exception("buy_new_position race recovery failed")
            return api_error(
            en="Failed to record trade", kr="거래 기록에 실패했습니다.",
            code="TRADE_RECORD_FAILED", status=500,
        )
    return jsonify({
        "ok": True,
        "new_shares": round(p.shares, 4),
        "new_avg_cost": round(p.avg_cost, 2),
        "new_capital_usd": current_user.available_capital,
        "new_capital_krw": getattr(current_user, "available_capital_krw", 0) or 0,
    })


@portfolio_bp.route("/position/<int:pid>/sell", methods=["POST"])
@api_auth
@trade_rate_limit
@_deprecated_singular("/api/portfolio/trades")
def sell_position(pid):
    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p:
        return api_error(
            en="Position not found", kr="포지션을 찾을 수 없습니다.",
            code="POSITION_NOT_FOUND", status=404,
        )
    d = request.get_json() or {}
    try:
        sell_shares = float(d.get("shares") or p.shares)
        sell_price = float(d.get("price") or 0)
    except (TypeError, ValueError):
        return api_error(
            en="Shares and price must be numbers", kr="주식 수와 가격은 숫자여야 합니다.",
            code="TRADE_NUMERIC_REQUIRED", status=400,
        )

    # SEC-001: reject non-positive share counts. `float(d.get("shares") or p.shares)`
    # passes negative numbers through (negative is truthy), which would invert the
    # sign of proceeds/PnL and could be abused to credit the user.
    if sell_shares <= 0:
        return api_error(
            en="Shares must be positive", kr="주식 수는 양수여야 합니다.",
            code="TRADE_SHARES_POSITIVE", status=400,
        )

    cached = cache_service.get_signal(p.ticker)
    sd = json.loads(cached.data_json) if cached and cached.data_json else {}
    if sell_price <= 0:
        sell_price = sd.get("price", p.avg_cost) if sd else p.avg_cost

    # Detect oversell: requested more shares than available
    if sell_shares > p.shares:
        adjusted = True
        requested_shares = sell_shares
        actual_sell = p.shares
    else:
        adjusted = False
        requested_shares = sell_shares
        actual_sell = sell_shares

    proceeds = actual_sell * sell_price
    cost_basis = actual_sell * p.avg_cost
    pnl = proceeds - cost_basis
    pnl_pct = pnl / cost_basis * 100 if cost_basis > 0 else 0
    name = canonical_display_name(sd.get("name"), p.ticker)
    currency = sd.get("currency", "USD")
    is_kr = sd.get("is_korean", False)

    if actual_sell >= p.shares - 0.0001:
        db.session.delete(p)
    else:
        p.shares = round(p.shares - actual_sell, 6)

    if is_kr:
        current_user.available_capital_krw = (getattr(current_user, "available_capital_krw", 0) or 0) + proceeds
    else:
        current_user.available_capital = (current_user.available_capital or 0) + proceeds

    db.session.add(TradeHistory(
        user_id=current_user.id, ticker=p.ticker, name=name,
        action="SELL", shares=actual_sell, price_per_share=round(sell_price, 2),
        total_value=round(proceeds, 2), pnl=round(pnl, 2), pnl_pct=round(pnl_pct, 2),
        currency=currency,
    ))
    db.session.commit()
    response = {
        "ok": True,
        "proceeds": round(proceeds, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "currency": currency,
        "new_capital_usd": current_user.available_capital,
        "new_capital_krw": getattr(current_user, "available_capital_krw", 0) or 0,
        "adjusted": adjusted,
    }
    if adjusted:
        response["warning"] = (
            f"Requested {requested_shares} shares but only "
            f"{actual_sell} available. Sold all {actual_sell} shares."
        )
        response["requested_shares"] = requested_shares
        response["actual_shares"] = actual_sell
    return jsonify(response)


@portfolio_bp.route("/capital", methods=["PUT"])
@api_auth
@trade_rate_limit
def set_capital():
    d = request.get_json() or {}
    try:
        cap_usd = float(d.get("capital_usd") or d.get("capital") or 0)
        cap_krw = float(d.get("capital_krw") or 0)
    except (TypeError, ValueError):
        return api_error(
            en="Capital must be numbers", kr="자본은 숫자여야 합니다.",
            code="CAPITAL_NUMERIC_REQUIRED", status=400,
        )
    if cap_usd < 0 or cap_krw < 0:
        return api_error(
            en="Capital must be ≥ 0", kr="자본은 0 이상이어야 합니다.",
            code="CAPITAL_NON_NEGATIVE", status=400,
        )
    current_user.available_capital = cap_usd
    current_user.available_capital_krw = cap_krw
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("set_capital commit failed")
        return api_error(
            en="Failed to update capital", kr="자본 업데이트에 실패했습니다.",
            code="CAPITAL_UPDATE_FAILED", status=500,
        )
    return jsonify({"ok": True, "capital_usd": cap_usd, "capital_krw": cap_krw})


@portfolio_bp.route("/analytics")
@api_auth
@legal_scrub_response
def portfolio_analytics():
    positions = Position.query.filter_by(user_id=current_user.id).all()

    # Batch-load all SignalCache rows in a single query to avoid N+1.
    tickers = [p.ticker for p in positions]
    cache_map = {
        c.ticker: c
        for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
    } if tickers else {}

    pl = []
    for p in positions:
        cached = cache_map.get(p.ticker)
        sd = json.loads(cached.data_json) if cached and cached.data_json else {}
        pl.append({
            "ticker": p.ticker,
            "name": canonical_display_name(sd.get("name"), p.ticker),
            "shares": p.shares,
            "market_value": sd.get("price", p.avg_cost) * p.shares,
            "sector": sd.get("sector", "Unknown"),
        })
    return jsonify(engine.portfolio_analytics(pl, current_user.available_capital))


# ── Frontend-friendly aliases (added 2026-04-22) ──────────────────────────────
# These endpoints expose a simpler schema for the new /portfolio page + modals
# while leaving the richer legacy endpoints (/api/portfolio, /position/...)
# intact for existing callers. No behavioral changes to legacy paths.


def _sector_for(sd):
    return sd.get("sector") or "Other"


def _position_display_name(p, sd):
    cached_name = sd.get("name")
    if cached_name and cached_name.upper() != p.ticker.upper():
        return cached_name
    return resolve_stock_name(p.ticker) or p.ticker


def _build_positions_list():
    threading.Thread(target=fx_service.refresh, daemon=True).start()
    positions = Position.query.filter_by(user_id=current_user.id).all()
    tickers = [p.ticker for p in positions]
    cache_map = {
        c.ticker: c
        for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
    } if tickers else {}
    # Freshness overlay: realtime (Alpaca/KIS) first, then non-stale cache.
    # Ensures "current" never shows a price older than the SignalCache TTL.
    overlay = overlay_prices(tickers)

    out = []
    for p in positions:
        cached = cache_map.get(p.ticker)
        sd = json.loads(cached.data_json) if cached and cached.data_json else {}
        is_kr = p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ")
        o = overlay.get(p.ticker) or {}
        if o.get("price"):
            cur_px = float(o["price"])
            price_source = o.get("source") or "realtime"
            observed_at = o.get("observed_at")
            change_pct = float(o.get("change_pct") or 0)
        else:
            # Bug C (2026-04-24): before falling back to avg_cost, attempt a
            # price_display parse. /api/portfolio/positions used to emit
            # LAST=avg_cost (rendered as "•-" stale chip) whenever the overlay
            # was empty, even when SignalCache had a legible "$402.91".
            parsed_fallback = parse_price_display(sd.get("price_display"))
            if parsed_fallback:
                cur_px = parsed_fallback
                price_source = "stale_display"
                observed_at = None
                change_pct = 0.0
            else:
                # Overlay has no fresh price — fall back to avg_cost (never stale cache).
                cur_px = float(p.avg_cost or 0)
                price_source = "stale"
                observed_at = None
                change_pct = 0.0
        currency = sd.get("currency", "KRW" if is_kr else "USD")
        name = _position_display_name(p, sd)
        opened_at = p.added_at.isoformat() if p.added_at else None

        out.append({
            "id": str(p.id),
            # 2026-05-02: emit both `symbol` (frontend-shape rename used
            # by /portfolio v2) and `ticker` (legacy key still read by
            # /detail access guard, /home v1 holding tables, /signals
            # widgets, /risk concentration aggregator). Single source of
            # truth on the backend, all consumers keep working.
            "symbol": p.ticker,
            "ticker": p.ticker,
            "name": name,
            "side": "Long",  # short positions not represented in DB
            "shares": p.shares,
            "avgCost": round(p.avg_cost, 4),
            "current": round(cur_px, 4),
            "change_pct": round(change_pct, 4),
            "observed_at": observed_at,
            "price_source": price_source,
            "sector": _sector_for(sd),
            "purchaseDate": opened_at[:10] if opened_at else "",
            "notes": p.thesis or "",
            "currency": currency,
            # 2026-05-08 (isKorean sweep): emit BOTH camelCase (v2 page-v2)
            # AND snake_case (lib/hooks.ts RawPosition, signal-card,
            # detail/[ticker], search-command, …). The frontend snake_case
            # is_korean is used in 10+ places — emitting both keeps every
            # consumer working without coordinated frontend rewrites.
            "isKorean":  is_kr,
            "is_korean": is_kr,
        })
    return out


@portfolio_bp.route("/positions", methods=["GET"])
@api_auth
def list_positions_alias():
    """Simpler positions list tailored to the new frontend shape."""
    try:
        return jsonify({"positions": _build_positions_list()})
    except Exception:
        logger.exception("list_positions_alias failed")
        return api_error(
            en="Failed to load positions", kr="포지션 목록을 불러오지 못했습니다.",
            code="POSITIONS_LOAD_FAILED", status=500,
        )


@portfolio_bp.route("/summary", methods=["GET"])
@api_auth
def portfolio_summary_alias():
    """KPI summary: NAV, today's P&L, unrealized, realized YTD."""
    try:
        threading.Thread(target=fx_service.refresh, daemon=True).start()
        rate = fx_service.get_rate() or 0
        positions = Position.query.filter_by(user_id=current_user.id).all()
        tickers = [p.ticker for p in positions]
        cache_map = {
            c.ticker: c
            for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
        } if tickers else {}

        # Freshness overlay — ensures NAV/P&L use the latest price, not stale cache.
        overlay = overlay_prices([p.ticker for p in positions])

        total_nav_usd = 0.0
        unrealized_usd = 0.0
        today_pnl_usd = 0.0

        for p in positions:
            cached = cache_map.get(p.ticker)
            sd = json.loads(cached.data_json) if cached and cached.data_json else {}
            is_kr = p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ")
            o = overlay.get(p.ticker) or {}
            cur_px = float(o.get("price") or p.avg_cost or 0)
            mv = cur_px * p.shares
            cost = p.avg_cost * p.shares

            # Convert KRW positions to USD for a unified NAV figure.
            if is_kr and rate:
                mv_usd = mv / rate
                cost_usd = cost / rate
            else:
                mv_usd = mv
                cost_usd = cost

            total_nav_usd += mv_usd
            unrealized_usd += mv_usd - cost_usd

            # Today's P&L: prefer fresh overlay change_pct, fall back to cache blob.
            chg_pct = (
                o.get("change_pct")
                if o.get("change_pct") is not None
                else (sd.get("change_pct") or sd.get("changePct") or 0)
            )
            try:
                today_pnl_usd += mv_usd * (float(chg_pct) / 100.0)
            except (TypeError, ValueError):
                logger.debug("silent-fallback: portfolio_summary_alias", exc_info=True)
                pass

        today_pnl_pct = (today_pnl_usd / total_nav_usd * 100) if total_nav_usd else 0

        # Realized YTD from TradeHistory (SELL rows only).
        from datetime import datetime
        ytd_start = datetime(datetime.now(timezone.utc).year, 1, 1)
        sells = (TradeHistory.query
                 .filter(TradeHistory.user_id == current_user.id,
                         TradeHistory.action == "SELL",
                         TradeHistory.traded_at >= ytd_start)
                 .all())
        realized_ytd_usd = 0.0
        for t in sells:
            pnl = t.pnl or 0
            if t.currency == "KRW" and rate:
                pnl = pnl / rate
            realized_ytd_usd += pnl

        # 2026-05-08 (observed_at sweep): the v2 portfolio page
        # (frontend/src/app/(dashboard)/portfolio/_v2/page-v2.tsx:158)
        # consumes `sumData?.observed_at ?? null` to render the "last
        # reconciled" timestamp chip. Emit it explicitly so the chip
        # stops showing "—" forever. The response IS what we observed.
        observed_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 2026-05-09 (bug-hunter Bug #5): the PORTFOLIO header renders
        # "Cash buffer at —." forever because this endpoint never emitted
        # the cash percent. Compute it as the idle-cash share of total
        # equity (cash + holdings), unified to USD via the same FX path as
        # totalNav. Defensive: returns 0.0 when capital and NAV are both
        # zero, never a negative or non-finite number.
        cap_usd = float(getattr(current_user, "available_capital", 0.0) or 0.0)
        cap_krw = float(getattr(current_user, "available_capital_krw", 0.0) or 0.0)
        cash_usd_total = cap_usd + (cap_krw / rate if (cap_krw and rate) else 0.0)
        equity_usd = total_nav_usd + cash_usd_total
        if equity_usd > 0:
            cash_pct = max(0.0, min(100.0, (cash_usd_total / equity_usd) * 100.0))
        else:
            cash_pct = 0.0

        return jsonify({
            "totalNav": round(total_nav_usd, 2),
            "todayPnl": round(today_pnl_usd, 2),
            "todayPnlPct": round(today_pnl_pct, 2),
            "unrealized": round(unrealized_usd, 2),
            "realizedYtd": round(realized_ytd_usd, 2),
            "currency": "USD",
            "fxRate": rate,
            "positionCount": len(positions),
            "observed_at": observed_iso,
            # Cash buffer percent of total equity (cash + holdings).
            # Frontend reads `sumData?.cashPct` in
            # frontend/src/app/(dashboard)/portfolio/_v2/page-v2.tsx and
            # renders "Cash buffer at {cashText}." in
            # frontend/src/components/portfolio/v2/portfolio-hero-v2.tsx.
            "cashPct": round(cash_pct, 2),
        })
    except Exception:
        logger.exception("portfolio_summary_alias failed")
        return api_error(
            en="Failed to load summary", kr="요약을 불러오지 못했습니다.",
            code="PORTFOLIO_SUMMARY_FAILED", status=500,
        )


@portfolio_bp.route("/trades", methods=["GET"])
@api_auth
def list_trades_alias():
    """Recent trades, mapped to the frontend Trade shape."""
    try:
        try:
            limit = int(request.args.get("limit", "20"))
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(limit, 100))

        rows = (TradeHistory.query
                .filter_by(user_id=current_user.id)
                .order_by(TradeHistory.traded_at.desc())
                .limit(limit).all())
        trades = []
        for t in rows:
            trades.append({
                "id": str(t.id),
                "date": t.traded_at.strftime("%Y-%m-%d") if t.traded_at else "",
                "symbol": t.ticker,
                "name": t.name or t.ticker,
                "side": "Bought" if (t.action or "").upper() == "BUY" else "Sold",
                "qty": t.shares or 0,
                "price": t.price_per_share or 0,
                "total": t.total_value or 0,
                "pnl": t.pnl or 0,
                "pnlPct": t.pnl_pct or 0,
                "currency": t.currency or "USD",
            })
        return jsonify({"trades": trades})
    except Exception:
        logger.exception("list_trades_alias failed")
        return api_error(
            en="Failed to load trades", kr="거래 내역을 불러오지 못했습니다.",
            code="TRADES_LOAD_FAILED", status=500,
        )


@portfolio_bp.route("/positions", methods=["POST"])
@api_auth
@trade_rate_limit
def create_position_alias():
    """Accepts the new frontend shape {symbol, side, quantity, price,
    purchase_date, note} and funnels into the existing add_position flow.
    """
    d = request.get_json() or {}
    raw_symbol = (d.get("symbol") or d.get("ticker") or "").strip().upper()
    # Bug #1 fix (2026-05-13): this is the *production* endpoint hit by
    # the new frontend (POST /api/portfolio/positions). Previously stored
    # bare "005930" → portfolio surfaces rendered "$54,000" / raw ticker /
    # missing name. Funnel every input through normalize_ticker so KR
    # codes always land as canonical .KS / .KQ.
    symbol = normalize_ticker(raw_symbol)
    try:
        quantity = float(d.get("quantity") or d.get("shares") or 0)
        price = float(d.get("price") or d.get("avg_cost") or 0)
    except (TypeError, ValueError):
        return api_error(
            en="Quantity and price must be numbers", kr="수량과 가격은 숫자여야 합니다.",
            code="TRADE_NUMERIC_REQUIRED", status=400,
        )
    if not symbol or quantity <= 0 or price <= 0:
        return api_error(
            en="Symbol, quantity, and price required", kr="종목, 수량, 가격이 필요합니다.",
            code="TRADE_FIELDS_REQUIRED", status=400,
        )
    # SEC-004 parity with add_position: Position.ticker is db.String(20).
    if len(symbol) > 20:
        return api_error(
            en="Invalid ticker", kr="유효하지 않은 종목입니다.",
            code="INVALID_TICKER", status=400,
        )
    # Bug #4 guard: reject implausibly-low cost basis (test/typo data).
    _implausible = _avg_cost_implausible(symbol, price)
    if _implausible:
        return api_error(
            en=_implausible,
            kr="평균 매입가가 비현실적입니다. 다시 확인해 주세요.",
            code="AVG_COST_IMPLAUSIBLE", status=400,
        )

    # Proxy to legacy add_position logic by rewriting request body.
    # Reuse free-plan cap check.
    if getattr(current_user, "effective_tier", None) in (None, "free"):
        pos_count = Position.query.filter_by(user_id=current_user.id).count()
        if pos_count >= 3:
            return jsonify({
                "error": "Free plan limited to 3 positions. Upgrade to Pro for unlimited.",
                "code": "TIER_LIMIT",
            }), 403

    note = (d.get("note") or d.get("notes") or d.get("thesis") or "").strip()[:500] or None
    is_kr = symbol.endswith(".KS") or symbol.endswith(".KQ")
    fx_rate = fx_service.get_rate() if not is_kr else 0.0

    # NEW-D (2026-05-09): mirror add_position race-safe upsert. See the
    # uq_positions_user_ticker rationale on Position.__table_args__.
    def _merge_into_alias(ex_row):
        total = ex_row.shares * ex_row.avg_cost + quantity * price
        if not is_kr and ex_row.buy_fx_rate and fx_rate:
            ex_row.buy_fx_rate = (
                ex_row.buy_fx_rate * ex_row.shares * ex_row.avg_cost
                + fx_rate * quantity * price
            ) / total
        ex_row.shares += quantity
        ex_row.avg_cost = total / ex_row.shares
        if note and not ex_row.thesis:
            ex_row.thesis = note
            ex_row.thesis_created_at = datetime.now(timezone.utc).replace(tzinfo=None)
            ex_row.thesis_status = "pending"

    try:
        ex = Position.query.filter_by(user_id=current_user.id, ticker=symbol).first()
        if ex:
            _merge_into_alias(ex)
            new_pos = ex
        else:
            new_pos = Position(
                user_id=current_user.id, ticker=symbol,
                shares=quantity, avg_cost=price, buy_fx_rate=fx_rate,
                thesis=note,
                thesis_created_at=datetime.now(timezone.utc).replace(tzinfo=None) if note else None,
                thesis_status="pending",
            )
            db.session.add(new_pos)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        logger.info("create_position_alias race recovery user=%s ticker=%s",
                    current_user.id, symbol)
        try:
            ex = Position.query.filter_by(
                user_id=current_user.id, ticker=symbol,
            ).first()
            if ex is None:
                return jsonify({
                    "error": "Position add raced; please retry.",
                    "code": "POSITION_RACE",
                }), 409
            _merge_into_alias(ex)
            db.session.commit()
            new_pos = ex
        except Exception:
            db.session.rollback()
            logger.exception("create_position_alias race recovery failed")
            return api_error(
            en="Failed to save position", kr="포지션 저장에 실패했습니다.",
            code="POSITION_SAVE_FAILED", status=500,
        )
    except Exception:
        db.session.rollback()
        logger.exception("create_position_alias commit failed")
        return api_error(
            en="Failed to save position", kr="포지션 저장에 실패했습니다.",
            code="POSITION_SAVE_FAILED", status=500,
        )

    _cache_ticker_async(
        current_app._get_current_object(),
        symbol,
        current_user.available_capital,
    )
    resolved_name = resolve_stock_name(symbol)
    return jsonify({
        "ok": True,
        "id": str(new_pos.id),
        "symbol": symbol,
        "name": resolved_name or symbol,
        # 2026-05-08 (isKorean sweep): dual-emit camelCase + snake_case;
        # see _build_positions_list comment for rationale.
        "isKorean":  is_kr,
        "is_korean": is_kr,
    })


@portfolio_bp.route("/positions/<int:pid>", methods=["PATCH"])
@api_auth
@trade_rate_limit
def patch_position_alias(pid):
    """Partial update: note and/or avg_cost only. Shares untouched."""
    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p:
        return api_error(
            en="Position not found", kr="포지션을 찾을 수 없습니다.",
            code="POSITION_NOT_FOUND", status=404,
        )
    d = request.get_json() or {}

    if "avg_cost" in d or "avgCost" in d:
        try:
            new_cost = float(d.get("avg_cost") if "avg_cost" in d else d.get("avgCost"))
        except (TypeError, ValueError):
            return api_error(
            en="avg_cost must be a number", kr="avg_cost 는 숫자여야 합니다.",
            code="AVG_COST_NUMERIC", status=400,
        )
        if new_cost <= 0:
            return api_error(
            en="avg_cost must be positive", kr="avg_cost 는 양수여야 합니다.",
            code="AVG_COST_POSITIVE", status=400,
        )
        # Bug #4 guard: reject implausibly-low cost basis (test/typo data).
        _implausible = _avg_cost_implausible(p.ticker, new_cost)
        if _implausible:
            return api_error(
            en=_implausible,
            kr="평균 매입가가 비현실적입니다. 다시 확인해 주세요.",
            code="AVG_COST_IMPLAUSIBLE", status=400,
        )
        p.avg_cost = new_cost

    if "note" in d or "notes" in d or "thesis" in d:
        note_val = d.get("note") or d.get("notes") or d.get("thesis") or ""
        note_val = (note_val or "").strip()[:500]
        p.thesis = note_val or None
        if note_val and not p.thesis_created_at:
            p.thesis_created_at = datetime.now(timezone.utc).replace(tzinfo=None)
            p.thesis_status = "pending"

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("patch_position_alias failed")
        return api_error(
            en="Failed to update", kr="업데이트에 실패했습니다.",
            code="POSITION_UPDATE_FAILED", status=500,
        )
    return jsonify({"ok": True, "id": str(p.id)})


@portfolio_bp.route("/positions/<int:pid>", methods=["DELETE"])
@api_auth
@trade_rate_limit
def delete_position_alias(pid):
    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p:
        return api_error(
            en="Position not found", kr="포지션을 찾을 수 없습니다.",
            code="POSITION_NOT_FOUND", status=404,
        )
    try:
        db.session.delete(p)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("delete_position_alias failed")
        return api_error(
            en="Failed to delete", kr="삭제에 실패했습니다.",
            code="POSITION_DELETE_FAILED", status=500,
        )
    return jsonify({"ok": True})


@portfolio_bp.route("/trades", methods=["POST"])
@api_auth
@trade_rate_limit
def create_trade_alias():
    """Unified buy/sell endpoint accepting {position_id, action, quantity,
    price, date, note}. Delegates to the existing buy_more / sell_position
    business logic.
    """
    d = request.get_json() or {}
    try:
        pid = int(d.get("position_id") or d.get("positionId") or 0)
        quantity = float(d.get("quantity") or d.get("shares") or 0)
        price = float(d.get("price") or 0)
    except (TypeError, ValueError):
        return api_error(
            en="position_id/quantity/price must be numeric", kr="position_id / quantity / price 는 숫자여야 합니다.",
            code="TRADE_NUMERIC_REQUIRED", status=400,
        )
    action = (d.get("action") or "").lower()

    if action not in ("buy", "sell"):
        return api_error(
            en="action must be 'buy' or 'sell'", kr="action 은 'buy' 또는 'sell' 이어야 합니다.",
            code="TRADE_ACTION_INVALID", status=400,
        )
    if pid <= 0 or quantity <= 0 or price <= 0:
        return api_error(
            en="position_id, quantity, and price required", kr="position_id, quantity, price 가 필요합니다.",
            code="TRADE_FIELDS_REQUIRED", status=400,
        )

    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p:
        return api_error(
            en="Position not found", kr="포지션을 찾을 수 없습니다.",
            code="POSITION_NOT_FOUND", status=404,
        )

    cached = cache_service.get_signal(p.ticker)
    sd = json.loads(cached.data_json) if cached and cached.data_json else {}
    is_kr = sd.get("is_korean", p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ"))
    name = canonical_display_name(sd.get("name"), p.ticker)
    currency = sd.get("currency", "KRW" if is_kr else "USD")

    if action == "buy":
        cost = quantity * price
        if is_kr:
            avail = getattr(current_user, "available_capital_krw", 0) or 0
            if avail < cost:
                return jsonify({
                    "error": f"Insufficient KRW capital (need ₩{cost:,.0f}, have ₩{avail:,.0f})"
                }), 400
            current_user.available_capital_krw = avail - cost
        else:
            avail = current_user.available_capital or 0
            if avail < cost:
                return jsonify({
                    "error": f"Insufficient capital (need ${cost:,.2f}, have ${avail:,.2f})"
                }), 400
            current_user.available_capital = avail - cost
        total_cost = p.shares * p.avg_cost + quantity * price
        p.shares += quantity
        p.avg_cost = total_cost / p.shares
        db.session.add(TradeHistory(
            user_id=current_user.id, ticker=p.ticker, name=name,
            action="BUY", shares=quantity, price_per_share=round(price, 4),
            total_value=round(cost, 2), pnl=0, pnl_pct=0, currency=currency,
        ))
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception("create_trade_alias buy failed")
            return api_error(
            en="Failed to record trade", kr="거래 기록에 실패했습니다.",
            code="TRADE_RECORD_FAILED", status=500,
        )
        return jsonify({
            "ok": True,
            "action": "buy",
            "positionId": str(p.id),
            "newShares": round(p.shares, 6),
            "newAvgCost": round(p.avg_cost, 4),
        })

    # sell
    if quantity > p.shares:
        return jsonify({
            "error": f"Cannot sell {quantity}; only {p.shares} shares held."
        }), 400
    proceeds = quantity * price
    cost_basis = quantity * p.avg_cost
    pnl = proceeds - cost_basis
    pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0
    closed = quantity >= p.shares - 0.0001
    if closed:
        db.session.delete(p)
    else:
        p.shares = round(p.shares - quantity, 6)
    if is_kr:
        current_user.available_capital_krw = (
            getattr(current_user, "available_capital_krw", 0) or 0
        ) + proceeds
    else:
        current_user.available_capital = (
            current_user.available_capital or 0
        ) + proceeds
    db.session.add(TradeHistory(
        user_id=current_user.id, ticker=p.ticker, name=name,
        action="SELL", shares=quantity, price_per_share=round(price, 4),
        total_value=round(proceeds, 2), pnl=round(pnl, 2),
        pnl_pct=round(pnl_pct, 2), currency=currency,
    ))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("create_trade_alias sell failed")
        return api_error(
            en="Failed to record trade", kr="거래 기록에 실패했습니다.",
            code="TRADE_RECORD_FAILED", status=500,
        )
    return jsonify({
        "ok": True,
        "action": "sell",
        "positionId": str(pid),
        "proceeds": round(proceeds, 2),
        "pnl": round(pnl, 2),
        "pnlPct": round(pnl_pct, 2),
        "closed": closed,
    })


@portfolio_bp.route("/history")
@api_auth
def portfolio_history():
    from datetime import datetime, timezone
    positions = Position.query.filter_by(user_id=current_user.id).all()
    if not positions:
        return jsonify({"data": []})
    from services.data import fmp as fmp

    period = request.args.get("period", "5d")
    if period not in ("5d", "1mo", "3mo", "6mo", "1y"):
        period = "5d"

    # PERF-004: Parallelize history fetches across positions. Previous serial
    # loop was O(n) FMP RTTs (often 800ms+ each). ThreadPoolExecutor with a
    # small pool keeps the upstream rate manageable while cutting wall time
    # to roughly the slowest single fetch.
    from concurrent.futures import ThreadPoolExecutor

    def _fetch_one(p):
        try:
            return p, fmp.get_history(p.ticker, period=period)
        except Exception:
            logger.debug("silent-fallback: portfolio_history", exc_info=True)
            return p, None

    all_values = {}
    with ThreadPoolExecutor(max_workers=5) as ex:
        for p, h in ex.map(_fetch_one, positions):
            if h is None or h.empty:
                continue
            try:
                for date, row in h.iterrows():
                    ds = date.strftime("%Y-%m-%d")
                    if ds not in all_values:
                        all_values[ds] = 0
                    all_values[ds] += float(row["Close"]) * p.shares
            except Exception:
                logger.debug("silent-fallback: portfolio_history", exc_info=True)
                pass

    if not all_values:
        return jsonify({"data": []})

    try:
        today = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d")
        rt_prices = realtime.get_prices_batch([p.ticker for p in positions])
        today_val = 0
        for p in positions:
            if p.ticker in rt_prices:
                today_val += rt_prices[p.ticker]["price"] * p.shares
        if today_val > 0:
            all_values[today] = today_val
    except Exception:
        logger.debug("silent-fallback: portfolio_history", exc_info=True)
        pass

    sorted_dates = sorted(all_values.keys())
    data = [{"date": k, "value": round(all_values[k], 2)} for k in sorted_dates]

    # ── Benchmark overlay (EQUITY CURVE 비교선) ──────────────────────────────
    # Frontend (`EquityPoint.benchmark`) renders an optional comparison line
    # whenever each point carries a `benchmark` field. We emit raw close
    # prices — the frontend handles normalisation so backend changes stay
    # backwards compatible (omit field == old behaviour, no benchmark line).
    #
    # Source policy (메모리 룰: 공식 라이선스만 — yfinance/pykrx 영구 금지):
    #   • KR portfolio (any .KS/.KQ position) → KOSPI 200 via KIS
    #     (`get_index_history("2001")`), with `0001` (KOSPI) as graceful
    #     fallback. KIS already powers `routes/market.py` indices tile via
    #     the same endpoint — same code path, same auth.
    #   • US portfolio → S&P 500 via FMP `SPY` ETF (proven Starter-plan
    #     coverage; `^GSPC` 402-gates on the same plan — see
    #     services/data/fetcher.py:703 fallback table).
    #
    # Graceful degradation: any fetch failure / empty response → benchmark
    # field omitted entirely. Existing equity-curve rendering preserved.
    try:
        is_kr_portfolio = any(
            isinstance(p.ticker, str)
            and (p.ticker.endswith(".KS") or p.ticker.endswith(".KQ"))
            for p in positions
        )
        bench_map: dict[str, float] = {}

        if is_kr_portfolio:
            # KIS index daily history (FHPUP02120000). 2001 = KOSPI 200,
            # 0001 = KOSPI (broad). Mirror the market.py fallback chain
            # so a degraded 2001 plan still yields a comparison line.
            try:
                from services.kis.service import KISService
                _svc = KISService()
                for _idx_code in ("2001", "0001"):
                    rows = _svc.get_index_history(_idx_code, period=period)
                    if rows:
                        for row in rows:
                            ds = (row.get("date") or "").strip()
                            close = row.get("close")
                            if not ds or len(ds) != 8 or not ds.isdigit():
                                continue
                            try:
                                iso = f"{ds[0:4]}-{ds[4:6]}-{ds[6:8]}"
                                bench_map[iso] = float(close)
                            except (TypeError, ValueError):
                                continue
                        if bench_map:
                            break
            except Exception:
                logger.debug("silent-fallback: portfolio_history KIS bench",
                             exc_info=True)
        else:
            # S&P 500 via SPY ETF (FMP Starter plan covers this; ^GSPC
            # raw index 402-gates — see services/data/fetcher.py:703).
            try:
                bh = fmp.get_history("SPY", period=period)
                if bh is not None and not bh.empty and "Close" in bh.columns:
                    for date, row in bh.iterrows():
                        ds = date.strftime("%Y-%m-%d")
                        try:
                            bench_map[ds] = float(row["Close"])
                        except (TypeError, ValueError):
                            continue
            except Exception:
                logger.debug("silent-fallback: portfolio_history SPY bench",
                             exc_info=True)

        if bench_map:
            # Per-point match by ISO date. Trading-day misalignment
            # (KIS holiday vs FMP holiday vs portfolio compute) means
            # some points may legitimately lack benchmark — frontend
            # tolerates omission per `EquityPoint.benchmark?`.
            for point in data:
                bv = bench_map.get(point["date"])
                if bv is not None:
                    point["benchmark"] = round(bv, 2)
    except Exception:
        # Belt-and-suspenders: never let benchmark logic break the
        # primary equity-curve response. 메모리 룰 [기능 100% 보존].
        logger.debug("silent-fallback: portfolio_history bench wrap",
                     exc_info=True)

    return jsonify({"data": data})
