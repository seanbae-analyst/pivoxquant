"""Holdings (잔고) screenshot import — preview + commit.

The browser OCRs the brokerage holdings screen; only reviewed JSON rows reach
these endpoints (never an image, no model call). Logic and every decision
(ticker existence, currency, duplicates, fx, trade_history, tier cap, race)
are documented in ``services/imports/holdings_import.py``.
"""
from __future__ import annotations

import logging
import threading

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user

from security import trade_rate_limit
from services import cache_service, fx_service
from services.error_responses import api_error
from services.imports import holdings_import as hi
from .decorators import api_auth, legal_scrub_response
from .imports import SCRUB_SKIP

logger = logging.getLogger(__name__)

holdings_import_bp = Blueprint("holdings_import", __name__,
                               url_prefix="/api/portfolio/holdings-import")


def _json_body():
    data = request.get_json(silent=True) if request.is_json else None
    return data if isinstance(data, dict) else None


def _bad_body():
    return api_error(en="A JSON body is required.", kr="JSON 본문이 필요합니다.",
                     code="IMPORT_INVALID_FIELD", status=400)


def _err(exc: hi.HoldingsError):
    return api_error(en=exc.en, kr=exc.kr, code=exc.code, status=400, **exc.extra())


def _warm_async(app, tickers: list[str]) -> None:
    """Same side effect as create_position's ``_cache_ticker_async``, one
    thread for the whole batch instead of one per ticker."""
    if not tickers:
        return

    def _run():
        with app.app_context():
            for t in tickers:
                try:
                    cache_service.cache_ticker(t)
                except Exception as e:  # pragma: no cover - best effort
                    logger.error("holdings import cache_ticker failed %s: %s", t, e)

    threading.Thread(target=_run, daemon=True).start()


@holdings_import_bp.route("/preview", methods=["POST"])
@api_auth
@trade_rate_limit
@legal_scrub_response(skip_keys=SCRUB_SKIP)
def preview():
    data = _json_body()
    if data is None:
        return _bad_body()
    try:
        rows = hi.preview(current_user.id, data.get("rows"))
    except hi.HoldingsError as exc:
        return _err(exc)
    return jsonify({"rows": rows})


@holdings_import_bp.route("/commit", methods=["POST"])
@api_auth
@trade_rate_limit
@legal_scrub_response(skip_keys=SCRUB_SKIP)
def commit():
    data = _json_body()
    if data is None:
        return _bad_body()
    if data.get("consent") is not True:
        return api_error(
            en="Consent is required before holdings are recorded.",
            kr="보유 종목 기록에 대한 동의가 필요합니다.",
            code="IMPORT_CONSENT_REQUIRED", status=400,
        )
    try:
        rows = hi.validate_commit_rows(data.get("rows"))
    except hi.HoldingsError as exc:
        return _err(exc)
    try:
        result, written = hi.commit(current_user, rows, fx_service.get_rate)
    except hi.RaceError:
        logger.info("holdings import race user=%s", current_user.id)
        return api_error(en="Another change to these positions happened at the same time; please retry.",
                         kr="같은 종목이 동시에 변경되었습니다. 다시 시도해 주세요.",
                         code="POSITION_RACE", status=409)
    except Exception:
        logger.exception("holdings import commit failed user=%s", current_user.id)
        return api_error(en="Failed to save positions", kr="포지션 저장에 실패했습니다.",
                         code="POSITION_SAVE_FAILED", status=500)
    _warm_async(current_app._get_current_object(), written)
    return jsonify(result)
