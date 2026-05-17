"""Portfolio share routes: create and read public share links."""
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, current_app
from flask_login import current_user

from extensions import db
from models import Position, SignalCache, User
from models.portfolio_share import PortfolioShare
from services import fx_service
from services.error_responses import api_error
from services.name_resolver import canonical_display_name
from services.price_overlay import parse_price_display
from .decorators import api_auth
from security import general_rate_limit

logger = logging.getLogger(__name__)

share_bp = Blueprint("share", __name__, url_prefix="/api/portfolio/share")


@share_bp.route("", methods=["POST"])
@api_auth
@general_rate_limit
def create_share():
    """Create a 7-day public share token for the authenticated user's portfolio."""
    token = secrets.token_urlsafe(16)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expires_at = now + timedelta(days=7)

    share = PortfolioShare(
        user_id=current_user.id,
        token=token,
        created_at=now,
        expires_at=expires_at,
    )
    try:
        db.session.add(share)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("share.create_share commit failed (user_id=%s)", current_user.id)
        return api_error(
            en="Failed to create share link",
            kr="공유 링크를 생성하지 못했습니다.",
            code="SHARE_CREATE_FAILED",
            status=500,
        )

    base_url = current_app.config.get("FRONTEND_URL", "http://localhost:3000")
    share_url = f"{base_url}/portfolio/shared/{token}"

    return jsonify({
        "ok": True,
        "token": token,
        "expires_at": expires_at.isoformat() + "Z",
        "share_url": share_url,
    })


@share_bp.route("/<string:token>", methods=["GET"])
def get_shared_portfolio(token):
    """Return a shared portfolio by token. No authentication required."""
    if not token or len(token) > 64:
        return api_error(
            en="Invalid token",
            kr="유효하지 않은 토큰입니다.",
            code="SHARE_TOKEN_INVALID",
            status=400,
        )

    share = PortfolioShare.query.filter_by(token=token).first()
    if not share:
        return api_error(
            en="Share link not found",
            kr="공유 링크를 찾을 수 없습니다.",
            code="SHARE_NOT_FOUND",
            status=404,
        )

    if datetime.now(timezone.utc).replace(tzinfo=None) > share.expires_at:
        return api_error(
            en="Share link has expired",
            kr="공유 링크가 만료되었습니다.",
            code="SHARE_EXPIRED",
            status=410,
        )

    owner = db.session.get(User, share.user_id)
    if not owner:
        return api_error(
            en="Owner not found",
            kr="소유자를 찾을 수 없습니다.",
            code="SHARE_OWNER_NOT_FOUND",
            status=404,
        )

    fx_service.refresh()
    fx_rate = fx_service.get_rate()

    positions = Position.query.filter_by(user_id=share.user_id).all()
    # Batch-load SignalCache for all positions in a single query (avoid N+1).
    tickers = [p.ticker for p in positions]
    cache_map = {
        c.ticker: c
        for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
    } if tickers else {}
    out = []
    total_value_usd = 0.0
    scores = []
    total_cost = 0.0
    total_current = 0.0

    for p in positions:
        cached = cache_map.get(p.ticker)
        sd = json.loads(cached.data_json) if cached and cached.data_json else {}

        is_kr = p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ")
        # Bug C parity (2026-04-24): before falling back to avg_cost, try
        # parsing price_display so stale-but-legible values don't decay
        # into the cost basis.
        cur_px = sd.get("price") or parse_price_display(sd.get("price_display")) or p.avg_cost
        pnl_pct = (cur_px - p.avg_cost) / p.avg_cost * 100 if p.avg_cost else 0
        market_value = cur_px * p.shares
        currency = sd.get("currency", "KRW" if is_kr else "USD")
        score = sd.get("score", 0)

        if currency == "USD":
            total_value_usd += market_value
        # Accumulate cost/current for total_pnl_pct (unified USD basis)
        if is_kr:
            total_cost += p.avg_cost * p.shares / fx_rate if fx_rate else 0
            total_current += cur_px * p.shares / fx_rate if fx_rate else 0
        else:
            total_cost += p.avg_cost * p.shares
            total_current += market_value

        if score:
            scores.append(score)

        # avg_cost and buy_fx_rate are intentionally excluded (sensitive fields)
        out.append({
            "ticker": p.ticker,
            "shares": p.shares,
            "price": cur_px,
            "price_display": sd.get("price_display", f"${cur_px:.2f}"),
            "market_value": round(market_value, 2),
            "pnl_pct": round(pnl_pct, 2),
            "signal": sd.get("signal", "—"),
            "score": score,
            "name": canonical_display_name(sd.get("name"), p.ticker),
            "sector": sd.get("sector", "Unknown"),
            "currency": currency,
            "is_korean": sd.get("is_korean", is_kr),
        })

    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    total_pnl_pct = round(
        (total_current - total_cost) / total_cost * 100, 2
    ) if total_cost > 0 else 0

    return jsonify({
        "owner_name": owner.name or owner.email.split("@")[0],
        "positions": out,
        "total_value_usd": round(total_value_usd, 2),
        "avg_score": avg_score,
        "total_pnl_pct": total_pnl_pct,
        "fx_rate": fx_rate,
        "created_at": share.created_at.isoformat() + "Z",
        "expires_at": share.expires_at.isoformat() + "Z",
    })
