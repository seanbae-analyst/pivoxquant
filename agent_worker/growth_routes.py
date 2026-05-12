"""Growth OS API routes — reflection submission, score data, today summary, weekly reports.

Blueprint registered in routes/__init__.py.
All endpoints require authentication via @api_auth.

Security
--------
SEC-005 (2026-05-02): Every query against ``growth_reflections`` and
``growth_scores`` is scoped by ``current_user.id``. Older deploys allowed
IDOR (any user could read/update another user's reflection by guessing
``reflection_id``). The fix lives in migration ``020_growth_user_id.py``.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, jsonify, request
from flask_login import current_user
from sqlalchemy import text

from extensions import db
from routes.decorators import api_auth

logger = logging.getLogger(__name__)

growth_bp = Blueprint("growth", __name__, url_prefix="/api/growth")

# ── Scoring constants ────────────────────────────────────────────────────────
# Reflection depth heuristic: total answer character count mapped to 0-100.
_MIN_ANSWER_CHARS = 10
_MAX_ANSWER_CHARS = 500
_MOOD_WEIGHT = 0.2  # mood contributes 20% to reflection_score


def _compute_reflection_score(answers: list[str], mood: int | None) -> int:
    """Compute a 0-100 reflection score from answer depth + mood.

    Heuristic:
    - Total character count across all answers → 0-80 (linear scale)
    - Mood (1-5) → 0-20
    """
    total_chars = sum(len(a.strip()) for a in answers if isinstance(a, str))
    # Linear interpolation: 10 chars → 0, 500+ chars → 80
    char_score = max(0, min(80, int(
        (total_chars - _MIN_ANSWER_CHARS)
        / max(_MAX_ANSWER_CHARS - _MIN_ANSWER_CHARS, 1)
        * 80
    )))
    mood_score = int((mood or 3) / 5 * 20)
    return min(100, char_score + mood_score)


def _compute_streak(conn, today: date, user_id: int) -> int:
    """Calculate consecutive days with a growth_scores entry for this user."""
    yesterday = today - timedelta(days=1)
    prev = conn.execute(
        text(
            "SELECT streak_days FROM growth_scores "
            "WHERE date = :d AND user_id = :uid"
        ),
        {"d": yesterday, "uid": user_id},
    ).fetchone()
    return (prev.streak_days + 1) if prev else 1


# ── POST /api/growth/reflect ─────────────────────────────────────────────────

@growth_bp.route("/reflect", methods=["POST"])
@api_auth
def submit_reflection():
    """Submit user's reflection answers + mood.

    Expected JSON body:
    {
        "reflection_id": 42,
        "answers": ["answer 1", "answer 2", "answer 3"],
        "mood": 4
    }
    """
    body = request.get_json(silent=True) or {}

    reflection_id = body.get("reflection_id")
    answers = body.get("answers")
    mood = body.get("mood")

    # Validation
    if not reflection_id:
        return jsonify({"error": "reflection_id is required"}), 400
    if not isinstance(answers, list) or len(answers) == 0:
        return jsonify({"error": "answers must be a non-empty list"}), 400
    if mood is not None and (not isinstance(mood, int) or mood < 1 or mood > 5):
        return jsonify({"error": "mood must be an integer 1-5"}), 400

    uid = int(current_user.id)

    # Verify the reflection exists AND belongs to the calling user.
    # Combining the ownership predicate with the lookup gives a uniform
    # 404 for both "doesn't exist" and "belongs to someone else" — this
    # avoids leaking ID-existence to an attacker probing for IDOR.
    row = db.session.execute(
        text(
            "SELECT id, date, answers FROM growth_reflections "
            "WHERE id = :id AND user_id = :uid"
        ),
        {"id": reflection_id, "uid": uid},
    ).fetchone()

    if not row:
        return jsonify({"error": "Reflection not found"}), 404

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    answers_json = json.dumps(answers, ensure_ascii=False)

    # Update reflection with answers
    db.session.execute(
        text(
            """
            UPDATE growth_reflections
            SET answers = :answers,
                mood = :mood,
                answered_at = :now
            WHERE id = :id AND user_id = :uid
            """
        ),
        {
            "answers": answers_json,
            "mood": mood,
            "now": now,
            "id": reflection_id,
            "uid": uid,
        },
    )

    # Compute and upsert growth_scores
    reflection_score = _compute_reflection_score(answers, mood)
    today = row.date
    # Drivers that lack a registered DATE adapter (e.g. SQLite under raw
    # ``text()`` queries) return ISO strings instead of ``datetime.date``
    # objects. Coerce so the streak math below is portable.
    if isinstance(today, str):
        today = date.fromisoformat(today)
    streak = _compute_streak(db.session, today, uid)

    db.session.execute(
        text(
            """
            INSERT INTO growth_scores (user_id, date, reflection_score, streak_days)
            VALUES (:uid, :date, :score, :streak)
            ON CONFLICT (user_id, date) DO UPDATE
              SET reflection_score = :score,
                  streak_days = :streak
            """
        ),
        {
            "uid": uid,
            "date": today,
            "score": reflection_score,
            "streak": streak,
        },
    )

    db.session.commit()

    return jsonify({
        "ok": True,
        "reflection_id": reflection_id,
        "reflection_score": reflection_score,
        "streak": streak,
    })


# ── GET /api/growth/data ─────────────────────────────────────────────────────

@growth_bp.route("/data", methods=["GET"])
@api_auth
def growth_data():
    """Return growth score history for the requested range.

    Query params:
        range: "7d" | "30d" | "90d" | "365d" (default "365d")

    Response:
    [
        {"date": "2026-04-17", "activity": 72, "reflection": 85, "total": 78, "streak": 12},
        ...
    ]
    """
    range_param = request.args.get("range", "365d")
    days_map = {"7d": 7, "30d": 30, "90d": 90, "365d": 365}
    days = days_map.get(range_param, 365)

    start_date = date.today() - timedelta(days=days)
    uid = int(current_user.id)

    rows = db.session.execute(
        text(
            """
            SELECT date, activity_score, reflection_score, streak_days, total_score
            FROM growth_scores
            WHERE date >= :start AND user_id = :uid
            ORDER BY date ASC
            """
        ),
        {"start": start_date, "uid": uid},
    ).fetchall()

    result = [
        {
            "date": r.date.isoformat(),
            "activity": r.activity_score,
            "reflection": r.reflection_score,
            "total": r.total_score or 0,
            "streak": r.streak_days,
        }
        for r in rows
    ]

    return jsonify(result)


# ── GET /api/growth/today ────────────────────────────────────────────────────

@growth_bp.route("/today", methods=["GET"])
@api_auth
def today_summary():
    """Return today's briefing, reflection questions, and score.

    Response:
    {
        "date": "2026-04-17",
        "briefing": {"priorities": [...], "motivation": "..."},
        "reflection": {"id": 42, "questions": [...], "answers": null, "mood": null},
        "score": {"activity": 50, "reflection": 0, "total": 20, "streak": 5}
    }
    """
    today = date.today()
    uid = int(current_user.id)

    # Briefing — growth_daily_logs is single-tenant founder data; not user-scoped.
    briefing_row = db.session.execute(
        text(
            """
            SELECT priorities, motivation
            FROM growth_daily_logs
            WHERE date = :today AND type = 'briefing'
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"today": today},
    ).fetchone()

    briefing = None
    if briefing_row:
        priorities = briefing_row.priorities
        if isinstance(priorities, str):
            try:
                priorities = json.loads(priorities)
            except (json.JSONDecodeError, TypeError):
                pass
        briefing = {
            "priorities": priorities,
            "motivation": briefing_row.motivation,
        }

    # Reflection — scoped to current user
    ref_row = db.session.execute(
        text(
            """
            SELECT id, questions, answers, mood
            FROM growth_reflections
            WHERE date = :today AND user_id = :uid
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"today": today, "uid": uid},
    ).fetchone()

    reflection = None
    if ref_row:
        questions = ref_row.questions
        answers = ref_row.answers
        if isinstance(questions, str):
            try:
                questions = json.loads(questions)
            except (json.JSONDecodeError, TypeError):
                pass
        if isinstance(answers, str):
            try:
                answers = json.loads(answers)
            except (json.JSONDecodeError, TypeError):
                pass
        reflection = {
            "id": ref_row.id,
            "questions": questions,
            "answers": answers,
            "mood": ref_row.mood,
        }

    # Score — scoped to current user
    score_row = db.session.execute(
        text(
            """
            SELECT activity_score, reflection_score, streak_days, total_score
            FROM growth_scores
            WHERE date = :today AND user_id = :uid
            """
        ),
        {"today": today, "uid": uid},
    ).fetchone()

    score = None
    if score_row:
        score = {
            "activity": score_row.activity_score,
            "reflection": score_row.reflection_score,
            "total": score_row.total_score or 0,
            "streak": score_row.streak_days,
        }

    return jsonify({
        "date": today.isoformat(),
        "briefing": briefing,
        "reflection": reflection,
        "score": score,
    })


# ── GET /api/growth/weekly ───────────────────────────────────────────────────

@growth_bp.route("/weekly", methods=["GET"])
@api_auth
def weekly_reports():
    """Return the most recent 4 weekly reports.

    Response:
    [
        {
            "id": 1,
            "week_start": "2026-04-14",
            "summary": "...",
            "patterns": [...],
            "growth_areas": [...],
            "next_week_suggestions": [...],
            "week_score": 75
        },
        ...
    ]
    """
    rows = db.session.execute(
        text(
            """
            SELECT id, week_start, summary, patterns, growth_areas,
                   next_week_suggestions, week_score
            FROM growth_weekly_reports
            ORDER BY week_start DESC
            LIMIT 4
            """
        )
    ).fetchall()

    def _parse_jsonb(val):
        if isinstance(val, str):
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return val
        return val

    result = [
        {
            "id": r.id,
            "week_start": r.week_start.isoformat(),
            "summary": r.summary,
            "patterns": _parse_jsonb(r.patterns),
            "growth_areas": _parse_jsonb(r.growth_areas),
            "next_week_suggestions": _parse_jsonb(r.next_week_suggestions),
            "week_score": r.week_score,
        }
        for r in rows
    ]

    return jsonify(result)
