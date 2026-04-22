"""Morning Brief API — personalised daily briefing.

Endpoints (all under /api/brief, all require auth):

    GET  /api/brief/today         — today's brief; {available:false,...} if not yet generated
    GET  /api/brief/archive       — last 30 days of briefs (descending)
    POST /api/brief/generate-now  — on-demand regenerate (Pro+ only)

The scheduler (app.py) calls services.morning_brief_service.run_daily_briefs
at 06:00 KST; these endpoints are read-only except for /generate-now which
is gated to paid tiers to protect the Claude Haiku budget.

Note: /api/morning-brief under market_bp is a DIFFERENT feature
(Wall-Street-wide brief) and is intentionally left untouched.
"""
from datetime import date, timedelta

from flask import Blueprint, jsonify
from flask_login import current_user

from extensions import db
from models import MorningBrief
from services.morning_brief_service import (
    ai_usage_snapshot,
    generate_brief,
    render_brief_email,
)

from .decorators import api_auth, legal_scrub_response, require_tier

morning_brief_bp = Blueprint("morning_brief", __name__, url_prefix="/api/brief")


@morning_brief_bp.route("/today", methods=["GET"])
@api_auth
@legal_scrub_response
def get_today_brief():
    """Return today's brief or an {available:false} shell."""
    today = date.today()
    brief = (
        MorningBrief.query
        .filter_by(user_id=current_user.id, brief_date=today)
        .first()
    )
    if not brief:
        return jsonify({
            "ok": True,
            "available": False,
            "message": "아직 브리핑이 준비되지 않았어요. 6시 이후 다시 확인해주세요.",
            "date": today.isoformat(),
        })
    return jsonify({
        "ok": True,
        "available": True,
        "date": brief.brief_date.isoformat(),
        "created_at": brief.created_at.isoformat() + "Z",
        "brief": brief.content or {},
    })


@morning_brief_bp.route("/archive", methods=["GET"])
@api_auth
@legal_scrub_response
def get_archive():
    """Last 30 days of briefs for the current user, newest first."""
    cutoff = date.today() - timedelta(days=30)
    rows = (
        MorningBrief.query
        .filter(MorningBrief.user_id == current_user.id,
                MorningBrief.brief_date >= cutoff)
        .order_by(MorningBrief.brief_date.desc())
        .limit(30)
        .all()
    )
    return jsonify({
        "ok": True,
        "count": len(rows),
        "briefs": [
            {
                "date":       b.brief_date.isoformat(),
                "created_at": b.created_at.isoformat() + "Z",
                "content":    b.content or {},
            }
            for b in rows
        ],
    })


@morning_brief_bp.route("/preview-email", methods=["GET"])
@api_auth
@legal_scrub_response
def preview_email():
    """Return the integrated Morning Brief Plus HTML email.

    If today's brief is missing, it is generated on the fly so Pro users
    and admins can preview the combined artefact (KPI 5-card grid + brief
    body + disclaimer) any time. Returns both the structured content and
    the rendered HTML so a frontend pane can show either.
    """
    today = date.today()
    brief = (
        MorningBrief.query
        .filter_by(user_id=current_user.id, brief_date=today)
        .first()
    )
    if not brief:
        try:
            brief = generate_brief(current_user)
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Brief generation failed: {e}"}), 500

    content = brief.content or {}
    try:
        html = render_brief_email(content, user=current_user)
    except Exception as e:
        return jsonify({"error": f"Render failed: {e}"}), 500

    return jsonify({
        "ok":         True,
        "date":       brief.brief_date.isoformat(),
        "created_at": brief.created_at.isoformat() + "Z",
        "content":    content,
        "html":       html,
    })


@morning_brief_bp.route("/generate-now", methods=["POST", "GET"])
@api_auth
@require_tier("pro")
@legal_scrub_response
def generate_now():
    """Force-regenerate today's brief. Pro+ only.

    Exists for manual testing and for Pro users who added positions after
    the 06:00 KST cron run.
    """
    try:
        brief = generate_brief(current_user)
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Brief generation failed: {e}"}), 500

    return jsonify({
        "ok": True,
        "date":       brief.brief_date.isoformat(),
        "created_at": brief.created_at.isoformat() + "Z",
        "brief":      brief.content or {},
        "ai_usage":   ai_usage_snapshot(),
    })
