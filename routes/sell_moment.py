"""Sell-moment mirror routes — 매도 순간, 그 종목에 내가 먼저 적어 둔 말.

Endpoints (all under ``/api/sell-moment``, session auth, GET only):

    GET /                      ?ticker=&shares=&price=&date=&currency=
                               — a 매도 being typed in the portfolio sell modal
    GET /pending/<pending_id>  — a waiting 매도 fill (/journal?pending=<id>)

→ ``{ticker, words[], held_days, vs_cost_pct, matched_shares}``.
The logic is ``services/sell_moment.py`` (pure core + owner-filtered loader);
this file only parses input and checks ownership.

Legal posture
-------------
``@legal_scrub_response`` on every response, with the user's own quoted text
(``text`` · ``invalidation``) kept verbatim through ``skip_keys`` — the same
rule as routes/research_notes.py: a sentence the user wrote, rewritten by
the server, is no longer their record. Everything else is scrubbed. We add
two numbers computed from the user's own rows (보유 일수 · 산 값 대비 %) and
nothing else — no score, no verdict, no direction, no market data.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_login import current_user

from services.error_responses import api_error
from services.legal.disclaimers import DISCLAIMER_ARTIFACT_KR
from services.sell_moment import (
    SellInput,
    empty_moment,
    end_of_day,
    load_sell_moment,
    pending_sell_input,
)
from services.ticker_normalizer import is_korean_ticker, normalize_ticker

from .decorators import api_auth, legal_scrub_response
from security import general_rate_limit

logger = logging.getLogger(__name__)

sell_moment_bp = Blueprint("sell_moment", __name__, url_prefix="/api/sell-moment")

_BAD_INPUT = "SELL_MOMENT_BAD_INPUT"
_NOT_FOUND = "SELL_MOMENT_NOT_FOUND"
_CURRENCIES = ("KRW", "USD")

# The user's own words — kept verbatim through the scrub (see Legal posture).
_USER_TEXT = ("text", "invalidation")
_scrub = legal_scrub_response(skip_keys=_USER_TEXT)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ok(moment: dict):
    return jsonify({"ok": True, "disclaimer": DISCLAIMER_ARTIFACT_KR, **moment})


def _bad_input(en: str):
    return api_error(en=en, kr="입력값이 올바르지 않습니다.", code=_BAD_INPUT, status=400)


def _positive(raw) -> float | None:
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) and v > 0 else None


@sell_moment_bp.route("", methods=["GET"])
@sell_moment_bp.route("/", methods=["GET"])
@api_auth
@_scrub
@general_rate_limit
def for_typed_sell():
    """A 매도 not recorded yet. ``date`` is the modal's "YYYY-MM-DD"; it is
    parsed exactly like POST /api/portfolio/trades parses it, so the hold
    shown here is the hold that will be recorded."""
    from routes.portfolio import _parse_purchase_date

    ticker = normalize_ticker(request.args.get("ticker", ""))
    shares = _positive(request.args.get("shares"))
    price = _positive(request.args.get("price"))
    if not ticker or shares is None or price is None:
        return _bad_input("ticker, shares and price (> 0) are required")
    currency = (request.args.get("currency") or "").strip().upper()
    if currency not in _CURRENCIES:
        currency = "KRW" if is_korean_ticker(ticker) else "USD"
    now = _now()
    day = _parse_purchase_date(request.args.get("date"))
    sell = SellInput(ticker=ticker, shares=shares, price=price,
                     currency=currency, traded_at=day or now)
    # Date-grain: quotes written any time that day still came before it.
    cut = min(end_of_day(day), now) if day is not None else now
    return _ok(load_sell_moment(current_user.id, sell, now=now, words_before=cut))


@sell_moment_bp.route("/pending/<int:pending_id>", methods=["GET"])
@api_auth
@_scrub
@general_rate_limit
def for_pending(pending_id: int):
    """A waiting fill. Someone else's row is a 404, never a 403. A 매수 row
    or a row no longer waiting answers with an empty mirror."""
    from models.import_batch import PendingTrade

    row = PendingTrade.query.filter_by(id=pending_id, user_id=current_user.id).first()
    if row is None:
        return api_error(en="Not found", kr="대기 중인 체결을 찾을 수 없습니다.",
                         code=_NOT_FOUND, status=404)
    sell = pending_sell_input(row)
    if sell is None:
        return _ok(empty_moment(row.ticker))
    return _ok(load_sell_moment(current_user.id, sell, now=_now()))
