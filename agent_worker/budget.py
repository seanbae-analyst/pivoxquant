"""Daily budget tracking — hard caps Claude API spend."""
from datetime import date
from decimal import Decimal
import logging

from sqlalchemy import text

from agent_worker.config import (
    DAILY_BUDGET_USD,
    COST_PER_1M_INPUT,
    COST_PER_1M_OUTPUT,
)

log = logging.getLogger(__name__)


def estimate_cost(input_tokens: int, output_tokens: int) -> Decimal:
    """Estimate USD cost given token counts."""
    cost = (input_tokens / 1_000_000) * COST_PER_1M_INPUT + (
        output_tokens / 1_000_000
    ) * COST_PER_1M_OUTPUT
    return Decimal(str(round(cost, 6)))


def check_and_reserve(db_session, tokens_estimate: int) -> bool:
    """
    Check if today's budget has room for this call.
    Returns False if budget exhausted (worker should halt).
    """
    today = date.today()
    row = db_session.execute(
        text(
            """
            INSERT INTO agent_budget (date, tokens_used, cost_usd, daily_cap_usd, halted)
            VALUES (:today, 0, 0, :cap, FALSE)
            ON CONFLICT (date) DO UPDATE SET date = :today
            RETURNING tokens_used, cost_usd, daily_cap_usd, halted
            """
        ),
        {"today": today, "cap": DAILY_BUDGET_USD},
    ).fetchone()

    if row.halted:
        log.warning("Budget halted for today")
        return False

    # Rough pre-check — assume all tokens are output (worst case)
    estimated_cost = estimate_cost(tokens_estimate // 2, tokens_estimate // 2)
    if Decimal(str(row.cost_usd)) + estimated_cost >= Decimal(str(row.daily_cap_usd)):
        log.error(
            "Daily budget cap reached: %s / %s",
            row.cost_usd,
            row.daily_cap_usd,
        )
        db_session.execute(
            text("UPDATE agent_budget SET halted = TRUE WHERE date = :today"),
            {"today": today},
        )
        db_session.commit()
        return False

    return True


def record_usage(db_session, input_tokens: int, output_tokens: int) -> Decimal:
    """Record actual token usage after Claude call."""
    today = date.today()
    cost = estimate_cost(input_tokens, output_tokens)
    db_session.execute(
        text(
            """
            UPDATE agent_budget
            SET tokens_used = tokens_used + :tokens,
                cost_usd = cost_usd + :cost
            WHERE date = :today
            """
        ),
        {
            "today": today,
            "tokens": input_tokens + output_tokens,
            "cost": float(cost),
        },
    )
    db_session.commit()
    return cost


def is_halted(db_session) -> bool:
    """Check if today is halted (for worker main loop)."""
    today = date.today()
    row = db_session.execute(
        text("SELECT halted FROM agent_budget WHERE date = :today"),
        {"today": today},
    ).fetchone()
    return bool(row and row.halted)
