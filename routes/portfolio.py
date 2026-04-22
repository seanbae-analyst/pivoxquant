"""Portfolio routes: positions CRUD, buy/sell, capital, analytics."""
import json
import logging
import threading
from datetime import datetime, timezone
from flask import Blueprint, current_app, request, jsonify
from flask_login import current_user

from extensions import db
from models import Position, SignalCache, TradeHistory
from security import trade_rate_limit
from services.serializers import serialize_user
from services import fx_service, cache_service, kr_stock_registry
from services.name_resolver import resolve_stock_name
from services.container import engine, fetcher, realtime
from .decorators import api_auth, legal_scrub_response

logger = logging.getLogger(__name__)

portfolio_bp = Blueprint("portfolio", __name__, url_prefix="/api/portfolio")


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
                logger.error(f"Background cache_ticker failed {ticker}: {e}")

    threading.Thread(target=_run, daemon=True).start()


@portfolio_bp.route("")
@api_auth
@legal_scrub_response
def get_portfolio():
    fx_service.refresh()
    positions = Position.query.filter_by(user_id=current_user.id).all()

    # Batch-load all SignalCache rows in a single query to avoid N+1.
    tickers = [p.ticker for p in positions]
    cache_map = {
        c.ticker: c
        for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
    } if tickers else {}

    out = []
    for p in positions:
        cached = cache_map.get(p.ticker)
        sd = json.loads(cached.data_json) if cached and cached.data_json else {}
        is_kr = p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ")
        cur_px = sd.get("price", p.avg_cost)
        pnl = (cur_px - p.avg_cost) / p.avg_cost * 100 if p.avg_cost else 0
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
@trade_rate_limit
@api_auth
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
    ticker = (d.get("ticker") or "").strip().upper()
    thesis = (d.get("thesis") or "").strip()[:500] or None
    try:
        shares = float(d.get("shares") or 0)
        cost = float(d.get("avg_cost") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "Shares and average cost must be numbers"}), 400
    if not ticker or shares <= 0 or cost <= 0:
        return jsonify({"error": "Ticker, shares, and average cost required"}), 400
    is_kr = ticker.endswith(".KS") or ticker.endswith(".KQ")
    fx_rate = fx_service.get_rate() if not is_kr else 0.0
    try:
        ex = Position.query.filter_by(user_id=current_user.id, ticker=ticker).first()
        if ex:
            total = ex.shares * ex.avg_cost + shares * cost
            if not is_kr and ex.buy_fx_rate and fx_rate:
                ex.buy_fx_rate = (ex.buy_fx_rate * ex.shares * ex.avg_cost + fx_rate * shares * cost) / total
            ex.shares += shares
            ex.avg_cost = total / ex.shares
            if thesis and not ex.thesis:
                ex.thesis = thesis
                ex.thesis_created_at = datetime.now(timezone.utc).replace(tzinfo=None)
                ex.thesis_status = "pending"
        else:
            db.session.add(Position(
                user_id=current_user.id, ticker=ticker,
                shares=shares, avg_cost=cost, buy_fx_rate=fx_rate,
                thesis=thesis,
                thesis_created_at=datetime.now(timezone.utc).replace(tzinfo=None) if thesis else None,
                thesis_status="pending" if thesis else "pending",
            ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception("add_position DB commit failed")
        return jsonify({"error": f"Failed to save position: {e}"}), 500

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
@trade_rate_limit
@api_auth
def edit_position(pid):
    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p:
        return jsonify({"error": "Position not found"}), 404
    d = request.get_json() or {}
    shares = float(d.get("shares") or 0)
    cost = float(d.get("avg_cost") or 0)
    if shares <= 0 or cost <= 0:
        return jsonify({"error": "Shares and average cost must be positive"}), 400
    p.shares = shares
    p.avg_cost = cost
    db.session.commit()
    cache_service.cache_ticker(p.ticker, current_user.available_capital, engine)
    return jsonify({"ok": True})


@portfolio_bp.route("/position/<int:pid>", methods=["DELETE"])
@trade_rate_limit
@api_auth
def del_position(pid):
    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p:
        return jsonify({"error": "Position not found"}), 404
    db.session.delete(p)
    db.session.commit()
    return jsonify({"ok": True})


@portfolio_bp.route("/position/<int:pid>/buy", methods=["POST"])
@trade_rate_limit
@api_auth
def buy_more(pid):
    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p:
        return jsonify({"error": "Position not found"}), 404
    d = request.get_json() or {}
    buy_shares = float(d.get("shares") or 0)
    buy_price = float(d.get("price") or 0)
    if buy_shares <= 0 or buy_price <= 0:
        return jsonify({"error": "Shares and price required"}), 400

    cost = buy_shares * buy_price
    # Use TTL-aware cache accessor for consistency with the rest of the codebase.
    # get_signal() returns None if the row is stale, so callers fall back to
    # safe defaults below instead of rendering stale name/currency values.
    cached = cache_service.get_signal(p.ticker)
    sd = json.loads(cached.data_json) if cached and cached.data_json else {}
    is_kr = sd.get("is_korean", False)
    name = sd.get("name") or resolve_stock_name(p.ticker) or p.ticker
    currency = sd.get("currency", "USD")

    if is_kr:
        avail = getattr(current_user, "available_capital_krw", 0) or 0
        if avail < cost:
            return jsonify({"error": f"Insufficient KRW capital (need ₩{cost:,.0f}, have ₩{avail:,.0f})"}), 400
        current_user.available_capital_krw = avail - cost
    else:
        avail = current_user.available_capital or 0
        if avail < cost:
            return jsonify({"error": f"Insufficient capital (need ${cost:,.2f}, have ${avail:,.2f})"}), 400
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
@trade_rate_limit
@api_auth
def buy_new_position():
    d = request.get_json() or {}
    ticker = (d.get("ticker") or "").strip().upper()
    shares = float(d.get("shares") or 0)
    price = float(d.get("price") or 0)
    if not ticker or shares <= 0 or price <= 0:
        return jsonify({"error": "Ticker, shares, and price required"}), 400

    cost = shares * price
    currency = fetcher.currency(ticker)
    is_kr = currency == "KRW"

    cap = (getattr(current_user, "available_capital_krw", 0) or 0) if is_kr else (current_user.available_capital or 0)
    if cap < cost:
        sym = "₩" if is_kr else "$"
        return jsonify({"error": f"Insufficient capital (need {sym}{cost:,.0f}, have {sym}{cap:,.0f})"}), 400

    p = Position.query.filter_by(ticker=ticker, user_id=current_user.id).first()
    if p:
        total = p.shares * p.avg_cost + shares * price
        p.shares += shares
        p.avg_cost = total / p.shares
    else:
        p = Position(user_id=current_user.id, ticker=ticker, shares=shares, avg_cost=price)
        db.session.add(p)

    if is_kr:
        current_user.available_capital_krw = cap - cost
    else:
        current_user.available_capital = cap - cost

    cached = cache_service.get_signal(ticker)
    sd = json.loads(cached.data_json) if cached and cached.data_json else {}
    name = sd.get("name") or resolve_stock_name(ticker) or ticker
    db.session.add(TradeHistory(
        user_id=current_user.id, ticker=ticker, name=name,
        action="BUY", shares=shares, price_per_share=round(price, 2),
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


@portfolio_bp.route("/position/<int:pid>/sell", methods=["POST"])
@trade_rate_limit
@api_auth
def sell_position(pid):
    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p:
        return jsonify({"error": "Position not found"}), 404
    d = request.get_json() or {}
    sell_shares = float(d.get("shares") or p.shares)
    sell_price = float(d.get("price") or 0)

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
    name = sd.get("name") or resolve_stock_name(p.ticker) or p.ticker
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
def set_capital():
    d = request.get_json() or {}
    cap_usd = float(d.get("capital_usd") or d.get("capital") or 0)
    cap_krw = float(d.get("capital_krw") or 0)
    if cap_usd < 0 or cap_krw < 0:
        return jsonify({"error": "Capital must be ≥ 0"}), 400
    current_user.available_capital = cap_usd
    current_user.available_capital_krw = cap_krw
    db.session.commit()
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
            "name": sd.get("name") or resolve_stock_name(p.ticker) or p.ticker,
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
    fx_service.refresh()
    positions = Position.query.filter_by(user_id=current_user.id).all()
    tickers = [p.ticker for p in positions]
    cache_map = {
        c.ticker: c
        for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
    } if tickers else {}

    out = []
    for p in positions:
        cached = cache_map.get(p.ticker)
        sd = json.loads(cached.data_json) if cached and cached.data_json else {}
        is_kr = p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ")
        cur_px = sd.get("price", p.avg_cost) or p.avg_cost
        currency = sd.get("currency", "KRW" if is_kr else "USD")
        name = _position_display_name(p, sd)
        opened_at = p.added_at.isoformat() if p.added_at else None

        out.append({
            "id": str(p.id),
            "symbol": p.ticker,
            "name": name,
            "side": "Long",  # short positions not represented in DB
            "shares": p.shares,
            "avgCost": round(p.avg_cost, 4),
            "current": round(cur_px, 4),
            "sector": _sector_for(sd),
            "purchaseDate": opened_at[:10] if opened_at else "",
            "notes": p.thesis or "",
            "currency": currency,
            "isKorean": is_kr,
        })
    return out


@portfolio_bp.route("/positions", methods=["GET"])
@api_auth
def list_positions_alias():
    """Simpler positions list tailored to the new frontend shape."""
    try:
        return jsonify({"positions": _build_positions_list()})
    except Exception as e:
        logger.exception("list_positions_alias failed")
        return jsonify({"error": f"Failed to load positions: {e}"}), 500


@portfolio_bp.route("/summary", methods=["GET"])
@api_auth
def portfolio_summary_alias():
    """KPI summary: NAV, today's P&L, unrealized, realized YTD."""
    try:
        fx_service.refresh()
        rate = fx_service.get_rate() or 0
        positions = Position.query.filter_by(user_id=current_user.id).all()
        tickers = [p.ticker for p in positions]
        cache_map = {
            c.ticker: c
            for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
        } if tickers else {}

        total_nav_usd = 0.0
        unrealized_usd = 0.0
        today_pnl_usd = 0.0

        for p in positions:
            cached = cache_map.get(p.ticker)
            sd = json.loads(cached.data_json) if cached and cached.data_json else {}
            is_kr = p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ")
            cur_px = sd.get("price", p.avg_cost) or p.avg_cost
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

            # Today's P&L from SignalCache change_pct when available.
            chg_pct = sd.get("change_pct") or sd.get("changePct") or 0
            try:
                today_pnl_usd += mv_usd * (float(chg_pct) / 100.0)
            except (TypeError, ValueError):
                pass

        today_pnl_pct = (today_pnl_usd / total_nav_usd * 100) if total_nav_usd else 0

        # Realized YTD from TradeHistory (SELL rows only).
        from datetime import datetime
        ytd_start = datetime(datetime.utcnow().year, 1, 1)
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

        return jsonify({
            "totalNav": round(total_nav_usd, 2),
            "todayPnl": round(today_pnl_usd, 2),
            "todayPnlPct": round(today_pnl_pct, 2),
            "unrealized": round(unrealized_usd, 2),
            "realizedYtd": round(realized_ytd_usd, 2),
            "currency": "USD",
            "fxRate": rate,
            "positionCount": len(positions),
        })
    except Exception as e:
        logger.exception("portfolio_summary_alias failed")
        return jsonify({"error": f"Failed to load summary: {e}"}), 500


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
    except Exception as e:
        logger.exception("list_trades_alias failed")
        return jsonify({"error": f"Failed to load trades: {e}"}), 500


@portfolio_bp.route("/positions", methods=["POST"])
@trade_rate_limit
@api_auth
def create_position_alias():
    """Accepts the new frontend shape {symbol, side, quantity, price,
    purchase_date, note} and funnels into the existing add_position flow.
    """
    d = request.get_json() or {}
    symbol = (d.get("symbol") or d.get("ticker") or "").strip().upper()
    try:
        quantity = float(d.get("quantity") or d.get("shares") or 0)
        price = float(d.get("price") or d.get("avg_cost") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "Quantity and price must be numbers"}), 400
    if not symbol or quantity <= 0 or price <= 0:
        return jsonify({"error": "Symbol, quantity, and price required"}), 400

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
    try:
        ex = Position.query.filter_by(user_id=current_user.id, ticker=symbol).first()
        if ex:
            total = ex.shares * ex.avg_cost + quantity * price
            if not is_kr and ex.buy_fx_rate and fx_rate:
                ex.buy_fx_rate = (
                    ex.buy_fx_rate * ex.shares * ex.avg_cost
                    + fx_rate * quantity * price
                ) / total
            ex.shares += quantity
            ex.avg_cost = total / ex.shares
            if note and not ex.thesis:
                ex.thesis = note
                ex.thesis_created_at = datetime.now(timezone.utc).replace(tzinfo=None)
                ex.thesis_status = "pending"
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
    except Exception as e:
        db.session.rollback()
        logger.exception("create_position_alias commit failed")
        return jsonify({"error": f"Failed to save position: {e}"}), 500

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
        "isKorean": is_kr,
    })


@portfolio_bp.route("/positions/<int:pid>", methods=["PATCH"])
@trade_rate_limit
@api_auth
def patch_position_alias(pid):
    """Partial update: note and/or avg_cost only. Shares untouched."""
    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p:
        return jsonify({"error": "Position not found"}), 404
    d = request.get_json() or {}

    if "avg_cost" in d or "avgCost" in d:
        try:
            new_cost = float(d.get("avg_cost") if "avg_cost" in d else d.get("avgCost"))
        except (TypeError, ValueError):
            return jsonify({"error": "avg_cost must be a number"}), 400
        if new_cost <= 0:
            return jsonify({"error": "avg_cost must be positive"}), 400
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
    except Exception as e:
        db.session.rollback()
        logger.exception("patch_position_alias failed")
        return jsonify({"error": f"Failed to update: {e}"}), 500
    return jsonify({"ok": True, "id": str(p.id)})


@portfolio_bp.route("/positions/<int:pid>", methods=["DELETE"])
@trade_rate_limit
@api_auth
def delete_position_alias(pid):
    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p:
        return jsonify({"error": "Position not found"}), 404
    try:
        db.session.delete(p)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception("delete_position_alias failed")
        return jsonify({"error": f"Failed to delete: {e}"}), 500
    return jsonify({"ok": True})


@portfolio_bp.route("/trades", methods=["POST"])
@trade_rate_limit
@api_auth
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
        return jsonify({"error": "position_id/quantity/price must be numeric"}), 400
    action = (d.get("action") or "").lower()

    if action not in ("buy", "sell"):
        return jsonify({"error": "action must be 'buy' or 'sell'"}), 400
    if pid <= 0 or quantity <= 0 or price <= 0:
        return jsonify({"error": "position_id, quantity, and price required"}), 400

    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p:
        return jsonify({"error": "Position not found"}), 404

    cached = cache_service.get_signal(p.ticker)
    sd = json.loads(cached.data_json) if cached and cached.data_json else {}
    is_kr = sd.get("is_korean", p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ"))
    name = sd.get("name") or resolve_stock_name(p.ticker) or p.ticker
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
        except Exception as e:
            db.session.rollback()
            logger.exception("create_trade_alias buy failed")
            return jsonify({"error": f"Failed to record trade: {e}"}), 500
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
    except Exception as e:
        db.session.rollback()
        logger.exception("create_trade_alias sell failed")
        return jsonify({"error": f"Failed to record trade: {e}"}), 500
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
    from datetime import datetime, timedelta, timezone
    positions = Position.query.filter_by(user_id=current_user.id).all()
    if not positions:
        return jsonify({"data": []})
    import fmp_service as fmp

    period = request.args.get("period", "5d")
    if period not in ("5d", "1mo", "3mo", "6mo", "1y"):
        period = "5d"
    all_values = {}
    for p in positions:
        try:
            h = fmp.get_history(p.ticker, period=period)
            if h.empty:
                continue
            for date, row in h.iterrows():
                ds = date.strftime("%Y-%m-%d")
                if ds not in all_values:
                    all_values[ds] = 0
                all_values[ds] += float(row["Close"]) * p.shares
        except Exception:
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
        pass

    data = [{"date": k, "value": round(v, 2)} for k, v in sorted(all_values.items())]
    return jsonify({"data": data})
