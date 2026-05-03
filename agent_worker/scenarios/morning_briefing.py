"""Morning Briefing — AI-generated daily priorities + motivation.

Scheduled at 08:00 KST daily via APScheduler in worker.py.
Reads yesterday's reflection data + recent growth_daily_logs,
invokes Claude to produce today's top-3 priorities + one motivational line,
persists the result, and sends a Slack notification.

Capital-markets-law guard: scans all AI output for forbidden terms
(BUY/SELL/HOLD/etc.) and escalates at risk=100 if detected.
"""
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from agent_worker import budget
from agent_worker.claude_client import invoke_agent
from agent_worker.config import DATABASE_URL
from agent_worker.escalation import send_slack

log = logging.getLogger(__name__)

# Capital markets law: these terms must never appear in Growth OS output.
_FORBIDDEN_TERMS = ("BUY", "SELL", "HOLD", "추천", "조언", "매수", "매도", "recommend", "advice")

_SYSTEM_PROMPT = """\
You are the PivoxQuant Growth OS morning briefing assistant.

Your job:
1. Analyze the founder's recent reflection data and activity logs.
2. Produce exactly 3 actionable priorities for today, ranked by impact.
3. Add one short motivational sentence inspired by yesterday's reflection.

Output format (JSON):
{
  "priorities": ["priority 1", "priority 2", "priority 3"],
  "motivation": "one motivational sentence"
}

Rules:
- Write in Korean (한국어).
- Never use words: 추천, 조언, BUY, SELL, HOLD, 매수, 매도, recommend, advice.
- Focus on growth, learning, and execution — not investment.
- Keep each priority under 60 characters.
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


def _fetch_recent_context(engine: Engine) -> str:
    """Gather the last 5 days of briefings + yesterday's reflection."""
    yesterday = date.today() - timedelta(days=1)
    five_days_ago = date.today() - timedelta(days=5)

    with engine.connect() as conn:
        # Recent daily logs (last 5 days)
        logs = conn.execute(
            text(
                """
                SELECT date, priorities, motivation, actual_done
                FROM growth_daily_logs
                WHERE date >= :start
                ORDER BY date DESC
                LIMIT 5
                """
            ),
            {"start": five_days_ago},
        ).fetchall()

        # Yesterday's reflection
        reflection = conn.execute(
            text(
                """
                SELECT questions, answers, mood
                FROM growth_reflections
                WHERE date = :yesterday AND answers IS NOT NULL
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"yesterday": yesterday},
        ).fetchone()

        # Current streak
        streak_row = conn.execute(
            text(
                """
                SELECT streak_days
                FROM growth_scores
                WHERE date = :yesterday
                """
            ),
            {"yesterday": yesterday},
        ).fetchone()

    parts = []

    if logs:
        parts.append("=== Recent 5 days ===")
        for row in logs:
            day_str = str(row.date)
            priorities = json.dumps(row.priorities, ensure_ascii=False) if row.priorities else "none"
            done = json.dumps(row.actual_done, ensure_ascii=False) if row.actual_done else "none"
            parts.append(f"[{day_str}] priorities: {priorities} | done: {done}")

    if reflection:
        parts.append("\n=== Yesterday's reflection ===")
        q_str = json.dumps(reflection.questions, ensure_ascii=False) if reflection.questions else "none"
        a_str = json.dumps(reflection.answers, ensure_ascii=False) if reflection.answers else "none"
        parts.append(f"Questions: {q_str}")
        parts.append(f"Answers: {a_str}")
        parts.append(f"Mood: {reflection.mood}/5" if reflection.mood else "Mood: not recorded")

    streak = streak_row.streak_days if streak_row else 0
    parts.append(f"\nCurrent streak: {streak} days")
    parts.append(f"Today: {date.today().isoformat()}")

    return "\n".join(parts) if parts else "No prior data. This is the first briefing."


def _scan_forbidden(text_content: str) -> list[str]:
    """Return list of forbidden terms found in the output."""
    upper = text_content.upper()
    return [term for term in _FORBIDDEN_TERMS if term.upper() in upper]


def _persist_briefing(engine: Engine, priorities: list[str], motivation: str, raw: str) -> int:
    """INSERT into growth_daily_logs; return the row id."""
    today = date.today()
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO growth_daily_logs (date, type, priorities, motivation, raw_response, created_at)
                VALUES (:date, 'briefing', :priorities, :motivation, :raw, :now)
                ON CONFLICT (date) DO UPDATE
                  SET priorities = :priorities,
                      motivation = :motivation,
                      raw_response = :raw
                RETURNING id
                """
            ),
            {
                "date": today,
                "priorities": json.dumps(priorities, ensure_ascii=False),
                "motivation": motivation,
                "raw": raw,
                "now": datetime.now(timezone.utc).replace(tzinfo=None),
            },
        ).fetchone()
        return row.id


def _upsert_activity_score(engine: Engine, score: int) -> None:
    """Create or update today's activity_score in growth_scores.

    Worker scenarios run as the founder/system user (user_id=0). Per
    SEC-005, growth_scores is now keyed on (user_id, date).
    """
    today = date.today()
    yesterday = today - timedelta(days=1)
    founder_uid = 0

    with engine.begin() as conn:
        # Calculate streak from yesterday
        prev = conn.execute(
            text(
                "SELECT streak_days FROM growth_scores "
                "WHERE date = :d AND user_id = :uid"
            ),
            {"d": yesterday, "uid": founder_uid},
        ).fetchone()
        streak = (prev.streak_days + 1) if prev else 1

        conn.execute(
            text(
                """
                INSERT INTO growth_scores (user_id, date, activity_score, streak_days)
                VALUES (:uid, :date, :score, :streak)
                ON CONFLICT (user_id, date) DO UPDATE
                  SET activity_score = :score,
                      streak_days = :streak
                """
            ),
            {"uid": founder_uid, "date": today, "score": score, "streak": streak},
        )


def run() -> dict[str, Any]:
    """Entry point -- called by APScheduler at 08:00 KST daily."""
    log.info("Morning briefing starting")
    engine = _get_engine()

    # Budget guard
    with engine.begin() as conn:
        if not budget.check_and_reserve(conn, 4000):
            send_slack("Morning briefing skipped: daily budget exhausted")
            log.warning("Budget exhausted — skipping morning briefing")
            return {"ok": False, "reason": "budget_exhausted"}

    # Gather context
    context = _fetch_recent_context(engine)

    # Invoke Claude
    try:
        result = invoke_agent(
            system_prompt=_SYSTEM_PROMPT,
            user_message=context,
            max_tokens=1024,
        )
    except Exception as exc:
        log.exception("Claude API call failed: %s", exc)
        send_slack(f"Morning briefing failed: Claude API error - {exc}")
        return {"ok": False, "reason": f"claude_error: {exc}"}

    # Record token usage
    with engine.begin() as conn:
        budget.record_usage(conn, result["input_tokens"], result["output_tokens"])

    raw_text = result["text"]

    # Forbidden term scan
    forbidden_hits = _scan_forbidden(raw_text)
    if forbidden_hits:
        log.error("LEGAL VIOLATION in morning briefing: %s", forbidden_hits)
        send_slack(
            f"[LEGAL] Morning briefing contains forbidden terms: {forbidden_hits}\n"
            f"Output suppressed. Risk=100. Raw text logged for audit."
        )
        return {"ok": False, "reason": "forbidden_terms", "terms": forbidden_hits}

    # Parse JSON from Claude response
    priorities = []
    motivation = ""
    try:
        # Claude may wrap JSON in markdown code fences
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
            cleaned = cleaned.rsplit("```", 1)[0]
        parsed = json.loads(cleaned)
        priorities = parsed.get("priorities", [])[:3]
        motivation = parsed.get("motivation", "")
    except (json.JSONDecodeError, AttributeError) as exc:
        log.warning("Failed to parse briefing JSON, using raw text: %s", exc)
        priorities = [raw_text[:100]]
        motivation = ""

    # Persist
    log_id = _persist_briefing(engine, priorities, motivation, raw_text)

    # Update activity score (briefing generated = base 50 activity)
    _upsert_activity_score(engine, 50)

    # Slack notification
    priority_lines = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(priorities))
    slack_message = (
        f"Good morning!\n\n"
        f"오늘 우선순위:\n{priority_lines}\n\n"
        f"{motivation}\n\n"
        f"[Growth OS] /growth 에서 확인"
    )
    send_slack(slack_message)

    log.info("Morning briefing complete: log_id=%s, priorities=%s", log_id, len(priorities))
    return {
        "ok": True,
        "log_id": log_id,
        "priorities": priorities,
        "motivation": motivation,
    }
