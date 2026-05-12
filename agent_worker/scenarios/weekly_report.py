"""Weekly Report — AI-generated weekly growth summary.

Scheduled every Saturday at 09:00 KST via APScheduler in worker.py.
Aggregates the week's daily_logs + reflections + scores, invokes Claude
for a structured summary (patterns, growth areas, next-week items),
persists the report, and sends a Slack notification.

Capital-markets-law guard: identical to other Growth OS scenarios.
"""
from __future__ import annotations

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

_FORBIDDEN_TERMS = ("BUY", "SELL", "HOLD", "추천", "조언", "매수", "매도", "recommend", "advice")

_SYSTEM_PROMPT = """\
You are the PivoxQuant Growth OS weekly report generator.

Your job: analyze this week's daily briefings, reflections, and scores
to produce a structured weekly growth report.

Output format (JSON):
{
  "summary": "3-line summary of the week",
  "patterns": ["pattern 1", "pattern 2"],
  "growth_areas": ["growth point with evidence 1", "growth point 2"],
  "next_week_suggestions": ["actionable item 1", "item 2", "item 3"],
  "week_score": 75
}

Rules:
- Write in Korean (한국어).
- Never use words: 추천, 조언, BUY, SELL, HOLD, 매수, 매도, recommend, advice.
- Frame everything as "분석", "관찰", "패턴" — never as advice or recommendation.
- next_week_suggestions must be concrete and actionable (not vague platitudes).
- week_score: 0-100 composite based on activity consistency + reflection depth + streak.
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


def _get_week_boundaries() -> tuple[date, date]:
    """Return (monday, sunday) for the current reporting week.

    Called on Saturday, so the week being reported is Mon-Fri of the
    current week (today = Sat is the boundary).
    """
    today = date.today()
    # Monday = today - (today.weekday()) but since today is Saturday (5),
    # the Monday of this week is today - 5
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _fetch_week_data(engine: Engine, week_start: date, week_end: date) -> str:
    """Aggregate all growth data for the given week."""
    with engine.connect() as conn:
        # Daily logs
        logs = conn.execute(
            text(
                """
                SELECT date, priorities, motivation, actual_done
                FROM growth_daily_logs
                WHERE date BETWEEN :start AND :end
                ORDER BY date
                """
            ),
            {"start": week_start, "end": week_end},
        ).fetchall()

        # Reflections
        reflections = conn.execute(
            text(
                """
                SELECT date, questions, answers, mood
                FROM growth_reflections
                WHERE date BETWEEN :start AND :end
                  AND answers IS NOT NULL
                ORDER BY date
                """
            ),
            {"start": week_start, "end": week_end},
        ).fetchall()

        # Scores
        scores = conn.execute(
            text(
                """
                SELECT date, activity_score, reflection_score, streak_days, total_score
                FROM growth_scores
                WHERE date BETWEEN :start AND :end
                ORDER BY date
                """
            ),
            {"start": week_start, "end": week_end},
        ).fetchall()

    parts = [f"Week: {week_start.isoformat()} ~ {week_end.isoformat()}"]
    parts.append(f"Days with briefing: {len(logs)}/7")
    parts.append(f"Days with reflection: {len(reflections)}/7")

    if logs:
        parts.append("\n=== Daily Logs ===")
        for row in logs:
            priorities = json.dumps(row.priorities, ensure_ascii=False) if row.priorities else "none"
            done = json.dumps(row.actual_done, ensure_ascii=False) if row.actual_done else "none"
            parts.append(f"[{row.date}] priorities: {priorities} | done: {done}")

    if reflections:
        parts.append("\n=== Reflections ===")
        for row in reflections:
            answers = json.dumps(row.answers, ensure_ascii=False) if row.answers else "none"
            parts.append(f"[{row.date}] mood: {row.mood}/5 | answers: {answers}")

    if scores:
        parts.append("\n=== Daily Scores ===")
        for row in scores:
            parts.append(
                f"[{row.date}] activity={row.activity_score} "
                f"reflection={row.reflection_score} "
                f"streak={row.streak_days} total={row.total_score}"
            )
        avg_total = sum(r.total_score for r in scores if r.total_score) / max(len(scores), 1)
        parts.append(f"\nWeek average score: {avg_total:.0f}")
    else:
        parts.append("\nNo score data for this week.")

    return "\n".join(parts)


def _scan_forbidden(text_content: str) -> list[str]:
    upper = text_content.upper()
    return [term for term in _FORBIDDEN_TERMS if term.upper() in upper]


def _persist_report(
    engine: Engine,
    week_start: date,
    summary: str,
    patterns: list[str],
    growth_areas: list[str],
    suggestions: list[str],
    week_score: int,
    raw: str,
) -> int:
    """INSERT or UPDATE the weekly report."""
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO growth_weekly_reports
                  (week_start, summary, patterns, growth_areas,
                   next_week_suggestions, week_score, raw_response, created_at)
                VALUES
                  (:ws, :summary, :patterns, :growth, :suggestions, :score, :raw, :now)
                ON CONFLICT (week_start) DO UPDATE
                  SET summary = :summary,
                      patterns = :patterns,
                      growth_areas = :growth,
                      next_week_suggestions = :suggestions,
                      week_score = :score,
                      raw_response = :raw
                RETURNING id
                """
            ),
            {
                "ws": week_start,
                "summary": summary,
                "patterns": json.dumps(patterns, ensure_ascii=False),
                "growth": json.dumps(growth_areas, ensure_ascii=False),
                "suggestions": json.dumps(suggestions, ensure_ascii=False),
                "score": week_score,
                "raw": raw,
                "now": datetime.now(timezone.utc).replace(tzinfo=None),
            },
        ).fetchone()
        return row.id


def run() -> dict[str, Any]:
    """Entry point -- called by APScheduler on Saturday 09:00 KST."""
    log.info("Weekly report starting")
    engine = _get_engine()

    # Budget guard
    with engine.begin() as conn:
        if not budget.check_and_reserve(conn, 6000):
            send_slack("Weekly report skipped: daily budget exhausted")
            log.warning("Budget exhausted — skipping weekly report")
            return {"ok": False, "reason": "budget_exhausted"}

    week_start, week_end = _get_week_boundaries()

    # Gather data
    context = _fetch_week_data(engine, week_start, week_end)

    # Invoke Claude
    try:
        result = invoke_agent(
            system_prompt=_SYSTEM_PROMPT,
            user_message=context,
            max_tokens=1536,
        )
    except Exception as exc:
        log.exception("Claude API call failed: %s", exc)
        send_slack(f"Weekly report failed: Claude API error - {exc}")
        return {"ok": False, "reason": f"claude_error: {exc}"}

    # Record token usage
    with engine.begin() as conn:
        budget.record_usage(conn, result["input_tokens"], result["output_tokens"])

    raw_text = result["text"]

    # Forbidden term scan
    forbidden_hits = _scan_forbidden(raw_text)
    if forbidden_hits:
        log.error("LEGAL VIOLATION in weekly report: %s", forbidden_hits)
        send_slack(
            f"[LEGAL] Weekly report contains forbidden terms: {forbidden_hits}\n"
            f"Output suppressed. Risk=100."
        )
        return {"ok": False, "reason": "forbidden_terms", "terms": forbidden_hits}

    # Parse JSON
    summary = ""
    patterns: list[str] = []
    growth_areas: list[str] = []
    suggestions: list[str] = []
    week_score = 0

    try:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
            cleaned = cleaned.rsplit("```", 1)[0]
        parsed = json.loads(cleaned)
        summary = parsed.get("summary", "")
        patterns = parsed.get("patterns", [])
        growth_areas = parsed.get("growth_areas", [])
        suggestions = parsed.get("next_week_suggestions", [])[:3]
        week_score = int(parsed.get("week_score", 0))
        week_score = max(0, min(100, week_score))
    except (json.JSONDecodeError, AttributeError, ValueError) as exc:
        log.warning("Failed to parse weekly report JSON: %s", exc)
        summary = raw_text[:300]

    # Persist
    report_id = _persist_report(
        engine, week_start, summary, patterns, growth_areas, suggestions, week_score, raw_text
    )

    # Slack notification
    slack_message = (
        f"[Weekly Report] {week_start.isoformat()} ~ {week_end.isoformat()}\n\n"
        f"{summary}\n\n"
        f"Week Score: {week_score}/100\n"
        f"Patterns: {len(patterns)} | Growth Areas: {len(growth_areas)}\n\n"
        f"/growth 에서 전체 확인"
    )
    send_slack(slack_message)

    log.info("Weekly report complete: report_id=%s, score=%s", report_id, week_score)
    return {
        "ok": True,
        "report_id": report_id,
        "week_start": week_start.isoformat(),
        "week_score": week_score,
    }
