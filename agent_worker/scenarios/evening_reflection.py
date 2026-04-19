"""Evening Reflection — AI-generated reflection questions for daily review.

Scheduled at 21:00 KST daily via APScheduler in worker.py.
Reads today's morning briefing, generates 3 personalized reflection questions
via Claude, persists them (answers=null), and sends a Slack notification
with a link to /growth for the user to answer.

Capital-markets-law guard: identical to morning_briefing.py.
"""
import json
import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from agent_worker import budget
from agent_worker.claude_client import invoke_agent
from agent_worker.config import DATABASE_URL, TARGET_URL
from agent_worker.escalation import send_slack

log = logging.getLogger(__name__)

_FORBIDDEN_TERMS = ("BUY", "SELL", "HOLD", "추천", "조언", "매수", "매도", "recommend", "advice")

_SYSTEM_PROMPT = """\
You are the PivoxQuant Growth OS evening reflection assistant.

Your job:
1. Review today's morning briefing (priorities + motivation).
2. Generate exactly 3 reflection questions that help the founder review their day.
3. Questions should be introspective, specific to today's priorities, and encourage growth.

Output format (JSON):
{
  "questions": ["question 1", "question 2", "question 3"]
}

Rules:
- Write in Korean (한국어).
- Never use words: 추천, 조언, BUY, SELL, HOLD, 매수, 매도, recommend, advice.
- Focus on self-awareness, learning, and personal growth.
- Make each question unique — avoid generic "how was your day" style.
- Vary question types: completion-check, emotional, forward-looking.
- End with [CONFIDENCE: N] where N is 0-100.
"""

_engine: Engine | None = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL not set")
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    return _engine


def _fetch_today_briefing(engine: Engine) -> str:
    """Get today's morning briefing for context."""
    today = date.today()

    with engine.connect() as conn:
        briefing = conn.execute(
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

        # Also get current streak for context
        score = conn.execute(
            text("SELECT streak_days FROM growth_scores WHERE date = :today"),
            {"today": today},
        ).fetchone()

    parts = [f"Date: {today.isoformat()}"]

    if briefing:
        priorities = json.dumps(briefing.priorities, ensure_ascii=False) if briefing.priorities else "none"
        parts.append(f"Today's priorities: {priorities}")
        parts.append(f"Motivation: {briefing.motivation or 'none'}")
    else:
        parts.append("No morning briefing was generated today.")

    streak = score.streak_days if score else 0
    parts.append(f"Current streak: {streak} days")

    return "\n".join(parts)


def _scan_forbidden(text_content: str) -> list[str]:
    upper = text_content.upper()
    return [term for term in _FORBIDDEN_TERMS if term.upper() in upper]


def _persist_reflection_questions(engine: Engine, questions: list[str], raw: str) -> int:
    """INSERT reflection questions (answers=null) into growth_reflections."""
    today = date.today()
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO growth_reflections (date, questions, raw_response, created_at)
                VALUES (:date, :questions, :raw, :now)
                RETURNING id
                """
            ),
            {
                "date": today,
                "questions": json.dumps(questions, ensure_ascii=False),
                "raw": raw,
                "now": datetime.now(timezone.utc).replace(tzinfo=None),
            },
        ).fetchone()
        return row.id


def run() -> dict[str, Any]:
    """Entry point -- called by APScheduler at 21:00 KST daily."""
    log.info("Evening reflection starting")
    engine = _get_engine()

    # Budget guard
    with engine.begin() as conn:
        if not budget.check_and_reserve(conn, 3000):
            send_slack("Evening reflection skipped: daily budget exhausted")
            log.warning("Budget exhausted — skipping evening reflection")
            return {"ok": False, "reason": "budget_exhausted"}

    # Gather context
    context = _fetch_today_briefing(engine)

    # Invoke Claude
    try:
        result = invoke_agent(
            system_prompt=_SYSTEM_PROMPT,
            user_message=context,
            max_tokens=512,
        )
    except Exception as exc:
        log.exception("Claude API call failed: %s", exc)
        send_slack(f"Evening reflection failed: Claude API error - {exc}")
        return {"ok": False, "reason": f"claude_error: {exc}"}

    # Record token usage
    with engine.begin() as conn:
        budget.record_usage(conn, result["input_tokens"], result["output_tokens"])

    raw_text = result["text"]

    # Forbidden term scan
    forbidden_hits = _scan_forbidden(raw_text)
    if forbidden_hits:
        log.error("LEGAL VIOLATION in evening reflection: %s", forbidden_hits)
        send_slack(
            f"[LEGAL] Evening reflection contains forbidden terms: {forbidden_hits}\n"
            f"Output suppressed. Risk=100."
        )
        return {"ok": False, "reason": "forbidden_terms", "terms": forbidden_hits}

    # Parse JSON
    questions: list[str] = []
    try:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
            cleaned = cleaned.rsplit("```", 1)[0]
        parsed = json.loads(cleaned)
        questions = parsed.get("questions", [])[:3]
    except (json.JSONDecodeError, AttributeError) as exc:
        log.warning("Failed to parse reflection JSON: %s", exc)
        questions = [
            "오늘 가장 의미있었던 순간은?",
            "오늘 배운 것 하나는?",
            "내일 가장 먼저 하고 싶은 일은?",
        ]

    # Persist
    ref_id = _persist_reflection_questions(engine, questions, raw_text)

    # Slack notification
    frontend_url = TARGET_URL.replace("pivoxquant.com", "pivoxquant.vercel.app")
    question_lines = "\n".join(f"  {i+1}. {q}" for i, q in enumerate(questions))
    slack_message = (
        f"오늘 하루 수고했습니다.\n\n"
        f"오늘의 회고 질문:\n{question_lines}\n\n"
        f"3분만 투자해서 답변해보세요:\n{frontend_url}/growth"
    )
    send_slack(slack_message)

    log.info("Evening reflection complete: ref_id=%s, questions=%s", ref_id, len(questions))
    return {
        "ok": True,
        "ref_id": ref_id,
        "questions": questions,
    }
