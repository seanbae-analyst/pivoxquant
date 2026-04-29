"""Whitelist guard for ticker analysis endpoints.

§101 회피 (자본시장법 불공정 영업행위 방어):
임의 ticker 분석 가능한 endpoint 는 "투자자문업"으로 비춰질 수 있다. 사용자가
이미 보유했거나 watchlist 에 등록한 종목 = 본인의 데이터 분석 (정보 매체 면제 시도).
그 외 ticker = 일반 자문 → 거부.

Usage
-----
    from services.access_guard import is_user_allowed_ticker, access_denied_response

    if not is_user_allowed_ticker(current_user.id, ticker):
        body, status = access_denied_response()
        return jsonify(body), status

The guard is intentionally permissive on lookup errors (returns False / 403) — better
to fail closed than open.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def is_user_allowed_ticker(user_id: int, ticker: str) -> bool:
    """Return True if the user holds (Position) or watches (Watchlist) the ticker.

    Case-insensitive on ticker (normalised to upper). Returns False on any
    DB lookup error or empty/invalid input — fail-closed.
    """
    if not user_id or not ticker:
        return False

    try:
        ticker_upper = str(ticker).strip().upper()
    except Exception:
        return False
    if not ticker_upper:
        return False

    # Position table — primary holding check.
    try:
        from models.position import Position
        has_position = (
            Position.query.filter_by(user_id=user_id, ticker=ticker_upper).first()
            is not None
        )
        if has_position:
            return True
    except Exception as e:  # noqa: BLE001 — defensive
        logger.warning("access_guard: Position lookup failed for uid=%s ticker=%s: %s",
                       user_id, ticker_upper, e)
        # Continue to watchlist; do not short-circuit.

    # Watchlist table — secondary scope check.
    try:
        from models.watchlist import Watchlist
        has_watchlist = (
            Watchlist.query.filter_by(user_id=user_id, ticker=ticker_upper).first()
            is not None
        )
        if has_watchlist:
            return True
    except Exception as e:  # noqa: BLE001 — defensive
        logger.warning("access_guard: Watchlist lookup failed for uid=%s ticker=%s: %s",
                       user_id, ticker_upper, e)

    return False


def access_denied_response():
    """Standard 403 payload when a ticker falls outside the user's scope.

    Returns ``(body_dict, status_int)`` so callers can do
    ``return jsonify(body), status`` (matches the project's existing pattern,
    e.g. routes/ai.py earnings-tone tier gate).
    """
    return (
        {
            "error": "ticker_not_in_user_scope",
            "message": "보유 또는 관심등록한 종목만 분석할 수 있습니다",
            "message_en": "Analysis is limited to tickers you own or have on your watchlist.",
            "cta": "add_to_watchlist",
        },
        403,
    )
