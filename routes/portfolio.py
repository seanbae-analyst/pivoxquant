"""Portfolio routes: positions CRUD, buy/sell, capital, analytics."""
import logging
import math
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
from services.container import fetcher, realtime
from services.price_overlay import overlay_prices, parse_price_display
from services.ticker_normalizer import normalize_ticker
from .decorators import api_auth, legal_scrub_response

logger = logging.getLogger(__name__)

portfolio_bp = Blueprint("portfolio", __name__, url_prefix="/api/portfolio")

# Bug API#5 (2026-05-26): upper bound for any user-supplied shares/price/quantity
# amount. Without a finite + bounded guard, a value like 1e308 (or inf/nan from a
# crafted payload) flows into ``shares * price`` → Infinity → JSON Infinity →
# frontend JSON.parse crash. 1e9 is well above any plausible real trade
# (₩1B shares or $1B price per unit) while keeping every product of two amounts
# safely below float64's ~1.8e308 ceiling.
_MAX_AMOUNT = 1e9


def _validate_amount(v):
    """Return True iff ``v`` is a finite, positive, in-range trade amount.

    Used for shares/price/quantity after float() conversion. Rejects nan, inf,
    -inf, <= 0, and anything above _MAX_AMOUNT (which would risk Infinity
    products downstream).
    """
    return math.isfinite(v) and 0 < v <= _MAX_AMOUNT


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
    HTTP response. The warm is a quote lookup rather than the old
    engine.analyze() run, so it is fast now, but it still hits FMP/KIS and
    can stall on a 402 fallback. Running it in a background thread keeps
    add_position snappy and idempotent — the cache miss on the next
    GET /portfolio call will simply fall back to stored avg_cost defaults,
    exactly as cache_service already handles."""
    def _run():
        with app.app_context():
            try:
                cache_service.cache_ticker(ticker)
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
    # NAV totals are accumulated on the suffix-derived `is_kr` (authoritative),
    # NOT the cache-blob `currency` string echoed per-row. A cross-contaminated
    # or stale SignalCache row can carry the wrong currency; bucketing a native
    # USD market_value into the KRW bucket (or vice versa) skews
    # total_value_all_krw by ~1380x for that position (Pattern-7 FX class).
    # The sibling endpoints (_build_positions_list, summary) already bucket on
    # the suffix — this brings get_portfolio in line. The per-row "currency"
    # field is untouched (display only).
    total_usd = 0.0
    total_krw = 0.0
    for p in positions:
        cached = cache_map.get(p.ticker)
        sd = cache_service.safe_cache_blob(cached)
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

        market_value = round(cur_px * p.shares, 2)
        if is_kr:
            total_krw += market_value
        else:
            total_usd += market_value

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
            "market_value": market_value,
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
    # Tier check (Free users limited to 3 positions) is performed below under
    # a User-row lock — see Bug C#2 TOCTOU note before the upsert.
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
    # Bug API#5 (2026-05-26): reject non-finite / out-of-range amounts so a
    # value like 1e308 can't produce shares*price=Infinity → JSON Infinity →
    # frontend crash. Applied after the >0 guard for both shares and cost.
    if not _validate_amount(shares) or not _validate_amount(cost):
        return api_error(
            en="Shares and average cost out of range", kr="주식 수 또는 평균가가 허용 범위를 벗어났습니다.",
            code="INVALID_AMOUNT", status=400,
        )
    # Bug #4 guard: reject implausibly-low cost basis (test/typo data).
    _implausible = _avg_cost_implausible(ticker, cost)
    if _implausible:
        return api_error(
            en=_implausible,
            kr="평균 매입가가 비현실적입니다. 다시 확인해 주세요.",
            code="AVG_COST_IMPLAUSIBLE", status=400,
        )
    # Optional user-supplied open date ("YYYY-MM-DD"). Parity with the
    # production alias endpoint. None → default now().
    opened_dt = _parse_purchase_date(d.get("purchase_date"))
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
        elif not is_kr and not ex_row.buy_fx_rate and fx_rate:
            # Existing USD row had null/zero rate (e.g. KIS overseas sync
            # without FX). Initialize it so KRW P&L isn't permanently blank.
            ex_row.buy_fx_rate = fx_rate
        ex_row.shares += shares
        ex_row.avg_cost = total / ex_row.shares
        if thesis and not ex_row.thesis:
            ex_row.thesis = thesis
            ex_row.thesis_created_at = datetime.now(timezone.utc).replace(tzinfo=None)
            ex_row.thesis_status = "pending"

    # Bug C#2 (2026-05-26): free-tier 3-position cap had a TOCTOU window — two
    # concurrent adds of *different* tickers both COUNT 2 (< 3), both insert,
    # and the user ends with 4. Lock the User row FIRST (lock order User→
    # Position is enforced across every buy/sell/add path to avoid deadlock),
    # then COUNT under that lock so per-user adds serialize. effective_tier
    # gate logic + the response message are unchanged. SQLite no-ops the lock.
    from models import User as _U
    locked_user = (
        db.session.query(_U)
        .filter(_U.id == current_user.id)
        .with_for_update()
        .one()
    )
    if getattr(current_user, "effective_tier", None) in (None, "free"):
        position_count = Position.query.filter_by(user_id=current_user.id).filter(
            Position.shares > 0
        ).count()
        if position_count >= 3:
            db.session.rollback()
            return jsonify({
                "error": "Free plan limited to 3 positions. Upgrade to Pro for unlimited.",
                "code": "TIER_LIMIT",
                "current_count": position_count,
                "limit": 3,
            }), 403

    try:
        ex = Position.query.filter_by(user_id=current_user.id, ticker=ticker).first()
        if ex:
            _merge_into(ex)
        else:
            new_pos = Position(
                user_id=current_user.id, ticker=ticker,
                shares=shares, avg_cost=cost, buy_fx_rate=fx_rate,
                thesis=thesis,
                thesis_created_at=datetime.now(timezone.utc).replace(tzinfo=None) if thesis else None,
                thesis_status="pending" if thesis else "pending",
            )
            if opened_dt is not None:
                new_pos.added_at = opened_dt
            db.session.add(new_pos)
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
    cache_service.cache_ticker(p.ticker)
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
    # Bug API#5 (2026-05-26): reject non-finite / out-of-range amounts so
    # buy_shares*buy_price can't overflow to Infinity → JSON crash downstream.
    if not _validate_amount(buy_shares) or not _validate_amount(buy_price):
        return api_error(
            en="Shares and price out of range", kr="주식 수 또는 가격이 허용 범위를 벗어났습니다.",
            code="INVALID_AMOUNT", status=400,
        )

    cost = buy_shares * buy_price
    # Use TTL-aware cache accessor for consistency with the rest of the codebase.
    # get_signal() returns None if the row is stale, so callers fall back to
    # safe defaults below instead of rendering stale name/currency values.
    cached = cache_service.get_signal(p.ticker)
    sd = cache_service.safe_cache_blob(cached)
    # When the SignalCache row is stale (TTL expired → sd == {}), a plain
    # ``.get("is_korean", False)`` mis-classifies .KS/.KQ tickers as USD and
    # routes their capital into the wrong bucket. Fall back to the ticker
    # suffix so KR positions stay KR even with no cache (matches
    # create_trade_alias' pattern).
    is_kr = sd.get("is_korean", p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ"))
    name = canonical_display_name(sd.get("name"), p.ticker)
    # Data-integrity fix (2026-05-22): a flat "USD" fallback mis-stamps .KS/.KQ
    # trades as USD whenever the SignalCache row is stale (sd == {}), poisoning
    # TradeHistory.currency so realizedYtd sums KRW pnl into the USD bucket
    # (thousands-fold inflation). Use the ticker-suffix-aware is_kr as the
    # default currency — parity with create_trade_alias (:1520).
    currency = sd.get("currency", "KRW" if is_kr else "USD")

    # 2026-05-17 wave 14 P1 (PR #449): capital double-spend race fix.
    # Pre-fix two concurrent buy_more (gevent greenlets, same user) both
    # read ``current_user.available_capital_krw`` (or USD), both pass the
    # ``avail < cost`` check, both subtract cost, both commit — last
    # writer wins and one of the two deductions silently disappears.
    # User effectively bought 2x for the price of 1x. Locking the User
    # row with SELECT FOR UPDATE serializes the read-modify-write so
    # the second greenlet sees the post-deduction balance and rejects.
    # SQLite (dev) treats with_for_update() as a no-op without erroring.
    from models import User as _U
    locked_user = (
        db.session.query(_U)
        .filter(_U.id == current_user.id)
        .with_for_update()
        .one()
    )
    # Bug C#1 (2026-05-26): the initial ``p`` was loaded WITHOUT a row lock, so
    # two concurrent buy/sell on the same position interleaved their
    # read-modify-write on p.shares/p.avg_cost (last writer wins → data loss).
    # Re-load the Position under SELECT FOR UPDATE *after* the User lock — lock
    # order is always User→Position across every buy/sell/add path so no two
    # greenlets can acquire them in opposite order (deadlock-free). The pre-lock
    # first() above still serves the 404 fast-path. SQLite no-ops the lock.
    p = (
        db.session.query(Position)
        .filter_by(id=pid, user_id=current_user.id)
        .with_for_update()
        .one_or_none()
    )
    if p is None:
        db.session.rollback()
        return api_error(
            en="Position not found", kr="포지션을 찾을 수 없습니다.",
            code="POSITION_NOT_FOUND", status=404,
        )

    if is_kr:
        avail = getattr(locked_user, "available_capital_krw", 0) or 0
        if avail < cost:
            db.session.rollback()
            return api_error(
                en=f"Insufficient KRW capital (need ₩{cost:,.0f}, have ₩{avail:,.0f})",
                kr=f"KRW 시드머니 부족 (필요 ₩{cost:,.0f}, 보유 ₩{avail:,.0f}).",
                code="INSUFFICIENT_CAPITAL_KRW", status=400,
            )
        locked_user.available_capital_krw = avail - cost
    else:
        avail = locked_user.available_capital or 0
        if avail < cost:
            db.session.rollback()
            return api_error(
                en=f"Insufficient capital (need ${cost:,.2f}, have ${avail:,.2f})",
                kr=f"USD 시드머니 부족 (필요 ${cost:,.2f}, 보유 ${avail:,.2f}).",
                code="INSUFFICIENT_CAPITAL_USD", status=400,
            )
        locked_user.available_capital = avail - cost

    total_cost = p.shares * p.avg_cost + buy_shares * buy_price
    # Trade-accuracy fix (2026-05-22): cost-weight buy_fx_rate on add-buy
    # (USD only) so KRW cost-basis / P&L% reflect blended purchase FX rather
    # than the first lot's rate. Mirrors add_position._merge_into (:345-349).
    # KR positions keep buy_fx_rate 0. Must use pre-update p.shares/avg_cost.
    if not is_kr:
        new_fx = fx_service.get_rate() or 0
        if p.buy_fx_rate and new_fx and total_cost:
            p.buy_fx_rate = (
                p.buy_fx_rate * p.shares * p.avg_cost
                + new_fx * buy_shares * buy_price
            ) / total_cost
        elif not p.buy_fx_rate and new_fx:
            p.buy_fx_rate = new_fx
    p.shares += buy_shares
    p.avg_cost = total_cost / p.shares

    db.session.add(TradeHistory(
        user_id=current_user.id, ticker=p.ticker, name=name,
        action="BUY", shares=buy_shares, price_per_share=round(buy_price, 2),
        total_value=round(cost, 2), pnl=0, pnl_pct=0, currency=currency,
    ))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("buy_more commit failed pid=%s", pid)
        return api_error(
            en="Failed to record trade", kr="거래 기록에 실패했습니다.",
            code="TRADE_RECORD_FAILED", status=500,
        )
    return jsonify({
        "ok": True,
        "new_shares": round(p.shares, 4),
        "new_avg_cost": round(p.avg_cost, 2),
        "new_capital_usd": locked_user.available_capital,
        "new_capital_krw": getattr(locked_user, "available_capital_krw", 0) or 0,
    })


@portfolio_bp.route("/position/buy-new", methods=["POST"])
@api_auth
@trade_rate_limit
@_deprecated_singular("/api/portfolio/trades")
def buy_new_position():
    # Free-tier cap is enforced below under a User-row lock — see Bug C#2 note
    # before the upsert. Without the lock the 3-position cap had a TOCTOU race
    # (two concurrent /buy-new of different tickers both COUNT < 3 → cap bypass).
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
    # Bug API#5 (2026-05-26): reject non-finite / out-of-range amounts.
    if not _validate_amount(shares) or not _validate_amount(price):
        return api_error(
            en="Shares and price out of range", kr="주식 수 또는 가격이 허용 범위를 벗어났습니다.",
            code="INVALID_AMOUNT", status=400,
        )

    cost = shares * price
    currency = fetcher.currency(ticker)
    is_kr = currency == "KRW"

    # Wave G-5 P1 G5-03 (2026-05-18): SELECT FOR UPDATE on User row to
    # serialize capital read-modify-write across concurrent gevent greenlets.
    # Mirrors buy_more (PR #449). Without this, two simultaneous /buy-new
    # calls (same user) can both pass `cap < cost`, both deduct, and one
    # deduction silently disappears. SQLite (dev) no-ops with_for_update().
    from models import User as _U
    locked_user = (
        db.session.query(_U)
        .filter(_U.id == current_user.id)
        .with_for_update()
        .one()
    )
    # Bug C#2 (2026-05-26): free-tier cap COUNT now runs under the User lock so
    # concurrent /buy-new of distinct tickers can't both pass the cap and
    # bypass the limit. Lock order User→Position preserved (User locked here,
    # any Position merge below). Gate logic / message unchanged.
    if getattr(current_user, "effective_tier", None) in (None, "free"):
        position_count = Position.query.filter_by(user_id=current_user.id).filter(
            Position.shares > 0
        ).count()
        if position_count >= 3:
            db.session.rollback()
            return jsonify({
                "error": "Free plan limited to 3 positions. Upgrade to Pro for unlimited.",
                "code": "TIER_LIMIT",
                "current_count": position_count,
                "limit": 3,
            }), 403
    cap = (getattr(locked_user, "available_capital_krw", 0) or 0) if is_kr else (locked_user.available_capital or 0)
    if cap < cost:
        db.session.rollback()
        sym = "₩" if is_kr else "$"
        return api_error(
            en=f"Insufficient capital (need {sym}{cost:,.0f}, have {sym}{cap:,.0f})",
            kr=f"시드머니 부족 (필요 {sym}{cost:,.0f}, 보유 {sym}{cap:,.0f}).",
            code="INSUFFICIENT_CAPITAL", status=400,
        )

    # Trade-accuracy fix (2026-05-22): capture buy FX once for both the new-row
    # and merge paths. KR positions keep buy_fx_rate 0 (matches add_position).
    new_fx = fx_service.get_rate() if not is_kr else 0.0

    # NEW-D (2026-05-09): race-safe upsert against uq_positions_user_ticker.
    def _merge_buy_new(ex_row):
        total = ex_row.shares * ex_row.avg_cost + shares * price
        # Cost-weight buy_fx_rate on add-buy (USD only) so KRW cost-basis /
        # P&L% reflect blended purchase FX. Mirrors add_position._merge_into.
        if not is_kr and new_fx:
            if ex_row.buy_fx_rate and total:
                ex_row.buy_fx_rate = (
                    ex_row.buy_fx_rate * ex_row.shares * ex_row.avg_cost
                    + new_fx * shares * price
                ) / total
            elif not ex_row.buy_fx_rate:
                ex_row.buy_fx_rate = new_fx
        ex_row.shares += shares
        ex_row.avg_cost = total / ex_row.shares

    p = Position.query.filter_by(ticker=ticker, user_id=current_user.id).first()
    if p:
        _merge_buy_new(p)
    else:
        p = Position(user_id=current_user.id, ticker=ticker, shares=shares,
                     avg_cost=price, buy_fx_rate=new_fx)
        db.session.add(p)

    if is_kr:
        locked_user.available_capital_krw = cap - cost
    else:
        locked_user.available_capital = cap - cost

    cached = cache_service.get_signal(ticker)
    sd = cache_service.safe_cache_blob(cached)
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
            # Wave G-5 G5-03 (2026-05-18): re-acquire User lock after
            # rollback (locked_user detached). Re-check cap to avoid
            # double-spending if a parallel writer committed in the gap.
            relocked = (
                db.session.query(_U)
                .filter(_U.id == current_user.id)
                .with_for_update()
                .one()
            )
            cap2 = (getattr(relocked, "available_capital_krw", 0) or 0) if is_kr else (relocked.available_capital or 0)
            if cap2 < cost:
                db.session.rollback()
                sym = "₩" if is_kr else "$"
                return api_error(
                    en=f"Insufficient capital (need {sym}{cost:,.0f}, have {sym}{cap2:,.0f})",
                    kr=f"시드머니 부족 (필요 {sym}{cost:,.0f}, 보유 {sym}{cap2:,.0f}).",
                    code="INSUFFICIENT_CAPITAL", status=400,
                )
            if is_kr:
                relocked.available_capital_krw = cap2 - cost
            else:
                relocked.available_capital = cap2 - cost
            db.session.add(TradeHistory(
                user_id=current_user.id, ticker=ticker, name=name,
                action="BUY", shares=shares, price_per_share=round(price, 2),
                total_value=round(cost, 2), pnl=0, pnl_pct=0, currency=currency,
            ))
            db.session.commit()
            p = ex
            # Race-recovery applied the deduction to ``relocked`` (the
            # original ``locked_user`` was detached on rollback). Point the
            # response at the row that actually holds the post-deduction
            # balance.
            locked_user = relocked
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
        "new_capital_usd": locked_user.available_capital,
        "new_capital_krw": getattr(locked_user, "available_capital_krw", 0) or 0,
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

    # Bug C#1 (2026-05-26): acquire the User row lock FIRST, then re-load the
    # Position under SELECT FOR UPDATE — lock order User→Position across every
    # buy/sell/add path (deadlock-free). All subsequent reads of p.shares (the
    # "sell entire position" default + oversell clamp) and the delete/decrement
    # mutation now run on the locked instance, so concurrent buy/sell on the
    # same position can no longer interleave their read-modify-write. The
    # pre-lock first() above still serves the 404 fast-path. SQLite no-ops the
    # lock. (The User row was previously locked far below, after the mutation —
    # too late to protect p; that ordering is corrected here.)
    from models import User as _U
    locked_user = (
        db.session.query(_U)
        .filter(_U.id == current_user.id)
        .with_for_update()
        .one()
    )
    p = (
        db.session.query(Position)
        .filter_by(id=pid, user_id=current_user.id)
        .with_for_update()
        .one_or_none()
    )
    if p is None:
        db.session.rollback()
        return api_error(
            en="Position not found", kr="포지션을 찾을 수 없습니다.",
            code="POSITION_NOT_FOUND", status=404,
        )

    # Trade-accuracy fix (2026-05-22): `float(d.get("shares") or p.shares)`
    # treats an explicit shares=0 as falsy and silently falls back to the full
    # position → an unintended full-close. Preserve the documented "shares
    # omitted → sell entire position" behavior (raw is None) but reject an
    # explicit 0 / negative via the <=0 guard below.
    raw_shares = d.get("shares")
    try:
        sell_shares = float(raw_shares) if raw_shares is not None else float(p.shares)
        sell_price = float(d.get("price") or 0)
    except (TypeError, ValueError):
        db.session.rollback()
        return api_error(
            en="Shares and price must be numbers", kr="주식 수와 가격은 숫자여야 합니다.",
            code="TRADE_NUMERIC_REQUIRED", status=400,
        )

    # SEC-001: reject non-positive share counts. An explicit shares=0 (or a
    # negative) now reaches this guard instead of full-closing the position;
    # negatives are truthy and would otherwise invert proceeds/PnL.
    if sell_shares <= 0:
        db.session.rollback()
        return api_error(
            en="Shares must be positive", kr="주식 수는 양수여야 합니다.",
            code="TRADE_SHARES_POSITIVE", status=400,
        )
    # Bug API#5 (2026-05-26): reject non-finite / out-of-range sell amounts so
    # actual_sell*sell_price can't overflow to Infinity. sell_price may legitly
    # default from cache below when omitted (<=0), so validate it there; here we
    # bound the explicit shares (and any explicit price already parsed).
    if not _validate_amount(sell_shares):
        db.session.rollback()
        return api_error(
            en="Shares out of range", kr="주식 수가 허용 범위를 벗어났습니다.",
            code="INVALID_AMOUNT", status=400,
        )
    if sell_price > 0 and not _validate_amount(sell_price):
        db.session.rollback()
        return api_error(
            en="Price out of range", kr="가격이 허용 범위를 벗어났습니다.",
            code="INVALID_AMOUNT", status=400,
        )

    cached = cache_service.get_signal(p.ticker)
    sd = cache_service.safe_cache_blob(cached)
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
    # Stale-cache safety: a False fallback would credit .KS/.KQ sell proceeds
    # to the USD bucket once the SignalCache TTL expires. Use the ticker
    # suffix as the authoritative fallback (matches create_trade_alias).
    is_kr = sd.get("is_korean", p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ"))
    # Data-integrity fix (2026-05-22): same stale-cache currency poisoning as
    # buy_more — a flat "USD" fallback stamps KR sells as USD, corrupting
    # TradeHistory.currency / realizedYtd. Default off is_kr (computed above).
    currency = sd.get("currency", "KRW" if is_kr else "USD")

    if actual_sell >= p.shares - 0.0001:
        db.session.delete(p)
    else:
        p.shares = round(p.shares - actual_sell, 6)

    # 2026-05-17 wave 14 P1 (PR #449): the sell-side proceeds credit shares the
    # same TOCTOU window as the buy-side debit. The User row was already locked
    # at the top of this handler (Bug C#1 reorder, 2026-05-26) so the
    # read-modify-write below is serialized — no separate lock acquisition here.
    if is_kr:
        locked_user.available_capital_krw = (
            getattr(locked_user, "available_capital_krw", 0) or 0
        ) + proceeds
    else:
        locked_user.available_capital = (
            locked_user.available_capital or 0
        ) + proceeds

    db.session.add(TradeHistory(
        user_id=current_user.id, ticker=p.ticker, name=name,
        action="SELL", shares=actual_sell, price_per_share=round(sell_price, 2),
        total_value=round(proceeds, 2), pnl=round(pnl, 2), pnl_pct=round(pnl_pct, 2),
        currency=currency,
    ))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("sell_position commit failed pid=%s", pid)
        return api_error(
            en="Failed to record trade", kr="거래 기록에 실패했습니다.",
            code="TRADE_RECORD_FAILED", status=500,
        )
    response = {
        "ok": True,
        "proceeds": round(proceeds, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "currency": currency,
        "new_capital_usd": locked_user.available_capital,
        "new_capital_krw": getattr(locked_user, "available_capital_krw", 0) or 0,
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
        sd = cache_service.safe_cache_blob(cached)
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
            # Native-currency market value — required by the /risk weight
            # aggregators (useConcentration / useSectorExposure). Its absence
            # made every concentration weight render 0% (CEO 2026-05-24).
            "market_value": round(cur_px * p.shares, 2),
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
        positions = _build_positions_list()
        # Portfolio totals — the /risk weight aggregators divide each holding's
        # market value by these. Omitting them made `denom = 0` → every
        # concentration/sector weight rendered 0% (CEO 2026-05-24).
        #
        # 2026-06-10 (wave-3 P1): bucket on the suffix-derived `is_korean`
        # flag, NOT the cache-blob `currency` string — the same Pattern-7
        # poisoned-cache bug fixed in get_portfolio (2610c824) lived on here,
        # and THIS is the endpoint the v2 frontend actually polls (feeds
        # useConcentration/useSectorExposure weights). `is_korean` is computed
        # from the .KS/.KQ suffix in _build_positions_list; the per-row
        # `currency` display field stays cache-echoed (unchanged).
        rate = fx_service.get_rate() or 0
        total_usd = sum(
            p["market_value"] for p in positions if not p.get("is_korean")
        )
        total_krw = sum(
            p["market_value"] for p in positions if p.get("is_korean")
        )
        total_all_krw = round(total_usd * rate + total_krw)
        return jsonify({
            "positions": positions,
            "total_value_usd": round(total_usd, 2),
            "total_value_krw": round(total_krw, 0),
            "total_value_all_krw": total_all_krw,
            "fx_rate": rate,
        })
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
        # Native-currency subtotals so /home can show US holdings in USD and
        # KR holdings in KRW separately (CEO: don't unify everything to USD).
        nav_us_usd = 0.0   # US positions, native USD market value
        nav_kr_krw = 0.0   # KR positions, native KRW market value
        # Per-currency P&L (native) so the hero KPIs (Today / Unrealized /
        # Realized) show KR figures in KRW, not only a USD-unified number
        # (CEO 2026-05-24: "today 부분은 여전히 usd만").
        today_pnl_us_usd = 0.0
        today_pnl_kr_krw = 0.0
        unrealized_us_usd = 0.0
        unrealized_kr_krw = 0.0

        for p in positions:
            cached = cache_map.get(p.ticker)
            sd = cache_service.safe_cache_blob(cached)
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
            if is_kr:
                nav_kr_krw += mv      # native KRW
                unrealized_kr_krw += (mv - cost)
            else:
                nav_us_usd += mv      # native USD
                unrealized_us_usd += (mv - cost)

            # Today's P&L: prefer fresh overlay change_pct, fall back to cache blob.
            chg_pct = (
                o.get("change_pct")
                if o.get("change_pct") is not None
                else (sd.get("change_pct") or sd.get("changePct") or 0)
            )
            try:
                _pct = float(chg_pct) / 100.0
                today_pnl_usd += mv_usd * _pct
                if is_kr:
                    today_pnl_kr_krw += mv * _pct
                else:
                    today_pnl_us_usd += mv * _pct
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
        realized_us_usd = 0.0
        realized_kr_krw = 0.0
        for t in sells:
            raw = t.pnl or 0
            if t.currency == "KRW":
                realized_kr_krw += raw
                realized_ytd_usd += (raw / rate) if rate else 0
            else:
                realized_us_usd += raw
                realized_ytd_usd += raw

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
            # Native-currency stock subtotals (no FX unification). /home shows
            # US holdings in USD and KR holdings in KRW separately.
            "navUsd": round(nav_us_usd, 2),
            "navKrw": round(nav_kr_krw, 0),
            "todayPnl": round(today_pnl_usd, 2),
            "todayPnlPct": round(today_pnl_pct, 2),
            "unrealized": round(unrealized_usd, 2),
            "realizedYtd": round(realized_ytd_usd, 2),
            # Per-currency P&L (native) — hero KPIs show KR figures in KRW.
            "todayPnlUsd": round(today_pnl_us_usd, 2),
            "todayPnlKrw": round(today_pnl_kr_krw, 0),
            "unrealizedUsd": round(unrealized_us_usd, 2),
            "unrealizedKrw": round(unrealized_kr_krw, 0),
            "realizedUsd": round(realized_us_usd, 2),
            "realizedKrw": round(realized_kr_krw, 0),
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


def _parse_purchase_date(raw):
    """Parse a user-supplied "YYYY-MM-DD" purchase (open) date.

    Returns a naive-UTC ``datetime`` (midnight) on success, or ``None`` to
    signal "fall back to default now()". Validation is lenient on purpose —
    a malformed value must never 400 / break the add-asset flow (UX), it
    just falls through to the server clock.

    Guards:
      * empty / non-string / unparseable  → None (default now)
      * future date (after today)         → None (default now); a user
        cannot have opened a position in the future
      * implausibly old (before 1900)     → None (default now)
    """
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    try:
        parsed = datetime.strptime(s, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    parsed = parsed.replace(tzinfo=None)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Future date: reject → default now (cannot open a position in the future).
    if parsed.date() > now.date():
        return None
    # Implausibly old: guard against typos / sentinel dates.
    if parsed.year < 1900:
        return None
    return parsed


@portfolio_bp.route("/positions", methods=["POST"])
@api_auth
@trade_rate_limit
def create_position_alias():
    """Accepts the new frontend shape {symbol, side, quantity, price,
    purchase_date, note} and funnels into the existing add_position flow.

    ``purchase_date`` (optional, "YYYY-MM-DD") is the date the user opened
    the position. When valid it is stored as ``Position.added_at`` (the
    position open date, serialised as ``opened_at``). Invalid / missing /
    future values fall back to the default server clock — see
    :func:`_parse_purchase_date`. On a merge into an existing position the
    original ``added_at`` is preserved (earliest open date wins).
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
    # Bug API#5 (2026-05-26): reject non-finite / out-of-range amounts so
    # quantity*price can't overflow to Infinity → JSON crash. This is the
    # production add endpoint hit by the frontend (POST /api/portfolio/positions).
    if not _validate_amount(quantity) or not _validate_amount(price):
        return api_error(
            en="Quantity and price out of range", kr="수량 또는 가격이 허용 범위를 벗어났습니다.",
            code="INVALID_AMOUNT", status=400,
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
    # Bug C#2 (2026-05-26): lock the User row FIRST (lock order User→Position,
    # consistent with every buy/sell/add path → deadlock-free), then run the
    # free-plan cap COUNT under that lock so concurrent adds of distinct tickers
    # can't both pass the cap and bypass the limit. Gate logic / message
    # unchanged. SQLite no-ops the lock.
    from models import User as _U
    locked_user = (
        db.session.query(_U)
        .filter(_U.id == current_user.id)
        .with_for_update()
        .one()
    )
    if getattr(current_user, "effective_tier", None) in (None, "free"):
        pos_count = Position.query.filter_by(user_id=current_user.id).filter(
            Position.shares > 0
        ).count()
        if pos_count >= 3:
            db.session.rollback()
            return jsonify({
                "error": "Free plan limited to 3 positions. Upgrade to Pro for unlimited.",
                "code": "TIER_LIMIT",
            }), 403

    note = (d.get("note") or d.get("notes") or d.get("thesis") or "").strip()[:500] or None
    # Optional user-supplied open date ("YYYY-MM-DD"). None → default now().
    opened_dt = _parse_purchase_date(d.get("purchase_date"))
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
        elif not is_kr and not ex_row.buy_fx_rate and fx_rate:
            # Initialize FX on a null/zero existing USD row (see _merge_into).
            ex_row.buy_fx_rate = fx_rate
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
            # When the user supplied a valid open date, override the model
            # default (now()). Invalid/missing → leave default. Merge path
            # never reaches here, so an existing position keeps its earliest
            # added_at.
            if opened_dt is not None:
                new_pos.added_at = opened_dt
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
    # Bug API#5 (2026-05-26): reject non-finite / out-of-range amounts so
    # quantity*price can't overflow to Infinity → JSON crash.
    if not _validate_amount(quantity) or not _validate_amount(price):
        return api_error(
            en="Quantity and price out of range", kr="수량 또는 가격이 허용 범위를 벗어났습니다.",
            code="INVALID_AMOUNT", status=400,
        )

    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p:
        return api_error(
            en="Position not found", kr="포지션을 찾을 수 없습니다.",
            code="POSITION_NOT_FOUND", status=404,
        )

    cached = cache_service.get_signal(p.ticker)
    sd = cache_service.safe_cache_blob(cached)
    is_kr = sd.get("is_korean", p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ"))
    name = canonical_display_name(sd.get("name"), p.ticker)
    currency = sd.get("currency", "KRW" if is_kr else "USD")

    # Trade-accuracy fix (2026-05-22): the TradeModalV2 record-mode sends an
    # explicit trade date ("YYYY-MM-DD") for already-executed past trades, but
    # this handler ignored it — TradeHistory.traded_at fell to default now(),
    # so a 2020 trade was stamped today. Parse the optional date and stamp
    # traded_at when valid; None (missing / malformed / future / pre-1900)
    # falls back to the server clock via the column default.
    traded_at_dt = _parse_purchase_date(d.get("date"))

    # Wave G-5 P1 G5-02 (2026-05-18): SELECT FOR UPDATE on User row to
    # serialize capital read-modify-write across concurrent gevent greenlets.
    # Without this, two simultaneous TradeModalV2 entries (same user) can
    # both read `avail`, both pass `avail < cost`, both deduct, and one
    # deduction silently disappears — user buys 2x for 1x cost. Mirrors
    # buy_more (PR #449) and buy_new_position fixes. SQLite (dev) treats
    # with_for_update() as a no-op without erroring.
    from models import User as _U
    locked_user = (
        db.session.query(_U)
        .filter(_U.id == current_user.id)
        .with_for_update()
        .one()
    )
    # Bug C#1 (2026-05-26): the initial ``p`` (first() above) was unlocked, so
    # concurrent buy/sell on the same position interleaved their
    # read-modify-write on p.shares/p.avg_cost. Re-load under SELECT FOR UPDATE
    # *after* the User lock — lock order User→Position across all paths
    # (deadlock-free). The pre-lock first() still serves the 404 + the
    # display-name lookup above. SQLite no-ops the lock.
    p = (
        db.session.query(Position)
        .filter_by(id=pid, user_id=current_user.id)
        .with_for_update()
        .one_or_none()
    )
    if p is None:
        db.session.rollback()
        return api_error(
            en="Position not found", kr="포지션을 찾을 수 없습니다.",
            code="POSITION_NOT_FOUND", status=404,
        )

    if action == "buy":
        cost = quantity * price
        if is_kr:
            avail = getattr(locked_user, "available_capital_krw", 0) or 0
            if avail < cost:
                db.session.rollback()
                return jsonify({
                    "error": f"Insufficient KRW capital (need ₩{cost:,.0f}, have ₩{avail:,.0f})"
                }), 400
            locked_user.available_capital_krw = avail - cost
        else:
            avail = locked_user.available_capital or 0
            if avail < cost:
                db.session.rollback()
                return jsonify({
                    "error": f"Insufficient capital (need ${cost:,.2f}, have ${avail:,.2f})"
                }), 400
            locked_user.available_capital = avail - cost
        total_cost = p.shares * p.avg_cost + quantity * price
        # Trade-accuracy fix (2026-05-22): cost-weight buy_fx_rate on add-buy
        # (USD only) so the KRW cost-basis / KRW P&L% reflect the blended
        # purchase FX, not just the first lot's rate. Mirrors
        # add_position._merge_into (:345-349). KR positions keep buy_fx_rate 0.
        if not is_kr:
            new_fx = fx_service.get_rate() or 0
            if p.buy_fx_rate and new_fx and total_cost:
                p.buy_fx_rate = (
                    p.buy_fx_rate * p.shares * p.avg_cost
                    + new_fx * quantity * price
                ) / total_cost
            elif not p.buy_fx_rate and new_fx:
                p.buy_fx_rate = new_fx
        p.shares += quantity
        p.avg_cost = total_cost / p.shares
        _buy_th = TradeHistory(
            user_id=current_user.id, ticker=p.ticker, name=name,
            action="BUY", shares=quantity, price_per_share=round(price, 4),
            total_value=round(cost, 2), pnl=0, pnl_pct=0, currency=currency,
        )
        if traded_at_dt is not None:
            _buy_th.traded_at = traded_at_dt
        db.session.add(_buy_th)
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
        locked_user.available_capital_krw = (
            getattr(locked_user, "available_capital_krw", 0) or 0
        ) + proceeds
    else:
        locked_user.available_capital = (
            locked_user.available_capital or 0
        ) + proceeds
    _sell_th = TradeHistory(
        user_id=current_user.id, ticker=p.ticker, name=name,
        action="SELL", shares=quantity, price_per_share=round(price, 4),
        total_value=round(proceeds, 2), pnl=round(pnl, 2),
        pnl_pct=round(pnl_pct, 2), currency=currency,
    )
    if traded_at_dt is not None:
        _sell_th.traded_at = traded_at_dt
    db.session.add(_sell_th)
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
    if period not in ("5d", "1mo", "2mo", "3mo", "6mo", "1y"):
        period = "5d"

    # ── Honest equity curve: plot REAL recorded NAV, never reconstruct. ──────
    # This curve used to apply the CURRENT share count to historical prices,
    # fabricating portfolio value for dates the user never actually held that
    # book (CEO flagged repeatedly as fake data; 표시광고법 fabrication risk).
    # The previous `added_at` clamp was only a band-aid — it moved the start
    # date but still drew a counterfactual "if you'd held today's book back
    # then" line, and for KIS-synced positions `added_at` is our sync time, not
    # the real purchase date. We now plot ONLY NAV we actually observed and
    # stored (services/portfolio/nav_snapshot.py). No backfill — a new account
    # shows a short/empty curve, which is the truth.
    from datetime import date as _d, timedelta as _td

    # Opportunistically record today's NAV on every load, so the curve keeps
    # accumulating from real usage even without the daily cron. Best-effort —
    # must never break the read.
    try:
        from services.portfolio.nav_snapshot import record_today_snapshot
        record_today_snapshot(current_user.id)
    except Exception:
        logger.debug("silent-fallback: nav snapshot record", exc_info=True)

    _win_days = {"5d": 8, "1mo": 35, "2mo": 60, "3mo": 100, "6mo": 200, "1y": 370}.get(period, 8)
    _since = _d.today() - _td(days=_win_days)

    all_values: dict[str, float] = {}
    try:
        from models import PortfolioNavSnapshot
        snap_rows = (
            PortfolioNavSnapshot.query
            .filter(
                PortfolioNavSnapshot.user_id == current_user.id,
                PortfolioNavSnapshot.as_of_date >= _since,
            )
            .order_by(PortfolioNavSnapshot.as_of_date.asc())
            .all()
        )
        for _r in snap_rows:
            all_values[_r.as_of_date.strftime("%Y-%m-%d")] = round(
                float(_r.nav_total_usd), 2
            )
    except Exception:
        # Table may be absent on a lagging deploy — degrade to today-only
        # rather than 500. db.create_all() at boot makes this transient.
        logger.debug("silent-fallback: nav snapshot read", exc_info=True)
        all_values = {}

    try:
        today = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d")
        rt_prices = realtime.get_prices_batch([p.ticker for p in positions])
        today_val = 0
        # Today's realtime values: use today's spot rate (get_rate_at(today) →
        # get_rate() for same-day dates — consistent with fx_service design).
        fx_today = fx_service.get_rate() or fx_service.FALLBACK_USDKRW
        for p in positions:
            if p.ticker in rt_prices:
                is_kr = p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ")
                mv = rt_prices[p.ticker]["price"] * p.shares
                if is_kr:
                    mv = mv / fx_today
                today_val += mv
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
        benchmark_label: str | None = (
            "KOSPI 200" if is_kr_portfolio else "S&P 500"
        )

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
        benchmark_label = None

    payload: dict = {"data": data}
    if benchmark_label is not None and any("benchmark" in pt for pt in data):
        # Frontend `hooks-v2.ts` BackendEquityResponse already expects
        # `benchmark?: { name?: string }` — emit the label there so the
        # equity-curve legend can render "KOSPI 200" / "S&P 500" dynamically
        # instead of the prior hardcoded "Benchmark · KOSPI200".
        payload["benchmark"] = {"name": benchmark_label}
    return jsonify(payload)


# ── Reconcile (broker sync) — REMOVED 2026-08-31 ───────────────────────────
#
# `POST /api/portfolio/reconcile` used to live here and was deleted with the
# rest of the broker surface in the prune (47a5e8f3). Its ~20-line design note
# was left behind describing the endpoint in the present tense — legal posture,
# response shape, mockup reference — which reads as if the route still exists.
# Removed 2026-09-06; recover the implementation with
#     git show 47a5e8f3^:routes/portfolio.py
#
# The frontend still names the path (`portfolio/page.tsx`), and that is not a
# live 404: the CTA is gated on `reconcileAvailable = brokerData?.kis_connected`
# and `useBrokerConnections()` passes SWR the key `false && ...`, so the request
# never fires. It is dormant, like the rest of `API.broker.*` (CLAUDE.md 함정
# §12) — KIS does not partner with fintech intermediaries, so reviving this
# means solving that first, and the route would have to be rewritten anyway.
