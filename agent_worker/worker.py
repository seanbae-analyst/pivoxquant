"""Main worker loop — APScheduler + pending task poller.

Entry point for Railway worker service: `python -m agent_worker.worker`.
Runs independently of the Flask web process; shares only the Postgres DB.
"""
from __future__ import annotations

import logging
import signal
import sys
import threading
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from agent_worker import budget, config
from agent_worker.escalation import send_slack
from agent_worker.scenarios import daily_healthcheck
from agent_worker.scenarios import morning_briefing
from agent_worker.scenarios import evening_reflection
from agent_worker.scenarios import weekly_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("agent_worker")

_shutdown = threading.Event()
_engine: Engine | None = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        if not config.DATABASE_URL:
            raise RuntimeError("DATABASE_URL not set")
        _engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
    return _engine


def _handle_signal(signum, _frame):
    log.info("Signal %s received — graceful shutdown", signum)
    _shutdown.set()


def _claim_pending_task(engine: Engine) -> dict | None:
    """SELECT ... FOR UPDATE SKIP LOCKED to safely claim one pending task."""
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, type, assigned_to, payload, description,
                       chain_depth, retry_count, max_retries, risk_score
                FROM agent_tasks
                WHERE status = 'pending'
                ORDER BY id ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
                """
            )
        ).fetchone()
        if not row:
            return None

        conn.execute(
            text(
                "UPDATE agent_tasks SET status = 'in_progress' WHERE id = :id"
            ),
            {"id": row.id},
        )
        return {
            "id": row.id,
            "type": row.type,
            "assigned_to": row.assigned_to,
            "payload": row.payload,
            "description": row.description,
            "chain_depth": row.chain_depth,
            "retry_count": row.retry_count,
            "max_retries": row.max_retries,
            "risk_score": row.risk_score,
        }


def _log_task_pickup(engine: Engine, task: dict) -> None:
    """Phase 1: just log. Phase 2 will dispatch to actual agent handlers."""
    log.info(
        "Picked up task id=%s type=%s assigned_to=%s depth=%s",
        task["id"],
        task["type"],
        task["assigned_to"],
        task["chain_depth"],
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE agent_tasks
                SET status = 'pending',
                    retry_count = retry_count + 1
                WHERE id = :id
                """
            ),
            {"id": task["id"]},
        )
        conn.execute(
            text(
                """
                INSERT INTO agent_decisions
                  (task_id, agent, decision_type, reasoning, created_at)
                VALUES (:task_id, :agent, 'auto',
                        'Phase 1 stub: task picked up but no agent dispatcher yet',
                        :now)
                """
            ),
            {
                "task_id": task["id"],
                "agent": task["assigned_to"] or "worker",
                "now": datetime.now(timezone.utc).replace(tzinfo=None),
            },
        )


def _poll_once(engine: Engine) -> None:
    try:
        task = _claim_pending_task(engine)
        if task is None:
            return
        _log_task_pickup(engine, task)
    except Exception:
        log.exception("Poll iteration failed")


def _budget_guard_and_halt() -> bool:
    """Return True if we should halt startup."""
    engine = _get_engine()
    with engine.begin() as conn:
        if budget.is_halted(conn):
            send_slack("🛑 Worker halted: budget cap reached")
            log.error("Budget halted — exiting")
            return True
    return False


def _schedule_healthcheck(scheduler: BackgroundScheduler) -> None:
    scheduler.add_job(
        _run_healthcheck_safely,
        trigger="cron",
        hour=8,
        minute=0,
        timezone="Asia/Seoul",
        id="daily_healthcheck",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    log.info("Scheduled daily_healthcheck @ 08:00 KST")


def _schedule_growth_os(scheduler: BackgroundScheduler) -> None:
    """Register Growth OS cron jobs: morning briefing, evening reflection, weekly report."""
    scheduler.add_job(
        _run_morning_briefing_safely,
        trigger="cron",
        hour=8,
        minute=5,
        timezone="Asia/Seoul",
        id="growth_morning_briefing",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    log.info("Scheduled growth_morning_briefing @ 08:05 KST")

    scheduler.add_job(
        _run_evening_reflection_safely,
        trigger="cron",
        hour=21,
        minute=0,
        timezone="Asia/Seoul",
        id="growth_evening_reflection",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    log.info("Scheduled growth_evening_reflection @ 21:00 KST")

    scheduler.add_job(
        _run_weekly_report_safely,
        trigger="cron",
        day_of_week="sat",
        hour=9,
        minute=0,
        timezone="Asia/Seoul",
        id="growth_weekly_report",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    log.info("Scheduled growth_weekly_report @ Sat 09:00 KST")


def _run_healthcheck_safely() -> None:
    try:
        result = daily_healthcheck.run()
        log.info(
            "Healthcheck complete: all_ok=%s task_id=%s",
            result.get("all_ok"),
            result.get("task_id"),
        )
    except Exception:
        log.exception("Healthcheck job failed")
        send_slack("❌ Agent worker: daily healthcheck crashed — check logs")


def _run_morning_briefing_safely() -> None:
    try:
        result = morning_briefing.run()
        log.info("Morning briefing complete: ok=%s", result.get("ok"))
    except Exception:
        log.exception("Morning briefing job failed")
        send_slack("❌ Agent worker: morning briefing crashed — check logs")


def _run_evening_reflection_safely() -> None:
    try:
        result = evening_reflection.run()
        log.info("Evening reflection complete: ok=%s", result.get("ok"))
    except Exception:
        log.exception("Evening reflection job failed")
        send_slack("❌ Agent worker: evening reflection crashed — check logs")


def _run_weekly_report_safely() -> None:
    try:
        result = weekly_report.run()
        log.info("Weekly report complete: ok=%s", result.get("ok"))
    except Exception:
        log.exception("Weekly report job failed")
        send_slack("❌ Agent worker: weekly report crashed — check logs")


def main() -> int:
    if config.KILL_SWITCH:
        log.warning("KILL_SWITCH is ON — exiting immediately")
        send_slack("🛑 Agent worker: KILL_SWITCH=true — shutting down")
        return 0

    if not config.DATABASE_URL:
        log.error("DATABASE_URL not set")
        return 1

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    if _budget_guard_and_halt():
        return 0

    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    _schedule_healthcheck(scheduler)
    _schedule_growth_os(scheduler)
    scheduler.start()

    send_slack("🟢 PivoxQuant agent worker started")
    log.info("Worker running (poll interval=%ss)", config.POLL_INTERVAL)

    engine = _get_engine()
    try:
        while not _shutdown.is_set():
            if config.KILL_SWITCH:
                log.warning("KILL_SWITCH flipped on during run — shutting down")
                break
            _poll_once(engine)
            _shutdown.wait(timeout=config.POLL_INTERVAL)
    finally:
        scheduler.shutdown(wait=False)
        send_slack("🔴 PivoxQuant agent worker stopped")
        log.info("Worker exited cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
