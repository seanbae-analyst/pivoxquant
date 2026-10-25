"""종목별 내 기록 — one stock, everything the caller wrote down about it.

    GET /api/stock-record/<ticker>  → {ok, disclaimer, ticker, name, holding,
                                       counts, events}

The composition lives in ``services/stock_record``. Read-only: no write
path, no order, no quote. Every response goes through
``@legal_scrub_response``; the user's own words (pause rationale, research
lines, note bodies) are kept verbatim through it — a sentence the user
copied from a report is their record, not ours (same rule as
routes/research_notes.py).
"""
from __future__ import annotations

from flask import Blueprint, jsonify
from flask_login import current_user

from services.error_responses import api_error
from services.legal.disclaimers import DISCLAIMER_ARTIFACT_KR
from services.stock_record import stock_record

from .decorators import api_auth, legal_scrub_response
from security import general_rate_limit

stock_record_bp = Blueprint("stock_record", __name__, url_prefix="/api/stock-record")

_USER_TEXT = ("rationale", "theses", "invalidation", "body", "tags")


@stock_record_bp.route("/<ticker>", methods=["GET"])
@api_auth
@legal_scrub_response(skip_keys=_USER_TEXT)
@general_rate_limit
def get_stock_record(ticker: str):
    try:
        result = stock_record(current_user.id, ticker)
    except ValueError as exc:
        return api_error(
            en=str(exc)[:200], kr="종목을 확인해 주세요.",
            code="STOCK_RECORD_BAD_INPUT", status=400,
        )
    return jsonify({"ok": True, "disclaimer": DISCLAIMER_ARTIFACT_KR, **result})
