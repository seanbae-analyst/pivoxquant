"""GET /api/pick-facts — 내가 고른 회사들 (services/pick_facts).

최근 1년에 처음 산 종목마다 산 날 직전에 공시된 연간 숫자로 순손실 · 매출 감소 ·
부채가 자본보다 많음을 센다. 본인 체결만 읽는다. 개수만, 시세 없음.
"""
from __future__ import annotations

from flask import Blueprint, jsonify
from flask_login import current_user

from services.legal.disclaimers import DISCLAIMER_ARTIFACT_KR
from services.pick_facts import pick_facts

from .decorators import api_auth, legal_scrub_response
from security import general_rate_limit

pick_facts_bp = Blueprint("pick_facts", __name__, url_prefix="/api/pick-facts")


@pick_facts_bp.route("", methods=["GET"])
@api_auth
@legal_scrub_response(skip_keys=("name",))
@general_rate_limit
def get_pick_facts():
    return jsonify({"ok": True, "disclaimer": DISCLAIMER_ARTIFACT_KR, **pick_facts(current_user.id)})
