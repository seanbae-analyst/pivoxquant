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
from services.container import engine, fetcher, realtime
from .decorators import api_auth

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

        # Prefer cache name, fall back to name_resolver (pyKRX for KR,
        # us_stock_registry for US — covers every KRX listing + all US
        # tickers so UI can render 회사명 instead of bare ticker even when
        # SignalCache is cold or the ticker is a long-tail listing).
        from services.name_resolver import resolve_stock_name
        display_name = sd.get("name") or resolve_stock_name(p.ticker) or p.ticker

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
    name = sd.get("name", p.ticker)
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
    name = sd.get("name", ticker)
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
    name = sd.get("name", p.ticker)
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
            "shares": p.shares,
            "market_value": sd.get("price", p.avg_cost) * p.shares,
            "sector": sd.get("sector", "Unknown"),
        })
    return jsonify(engine.portfolio_analytics(pl, current_user.available_capital))


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
