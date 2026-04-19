"""Worker configuration — hard budget caps and safety rails."""
import os

# Hard budget cap — kills worker if exceeded (prevents runaway cost)
DAILY_BUDGET_USD = float(os.getenv("AGENT_DAILY_BUDGET_USD", "5.00"))

# Max iterations per task chain (infinite loop prevention)
MAX_CHAIN_ITERATIONS = int(os.getenv("AGENT_MAX_ITERATIONS", "5"))

# Max retries per task
MAX_TASK_RETRIES = int(os.getenv("AGENT_MAX_RETRIES", "3"))

# Escalation thresholds
ESCALATION_RISK_THRESHOLD = int(os.getenv("AGENT_ESCALATION_RISK", "70"))
LOW_CONFIDENCE_THRESHOLD = int(os.getenv("AGENT_CONFIDENCE_MIN", "70"))

# Slack webhook (required)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# Anthropic API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("AGENT_MODEL", "claude-haiku-4-5-20251001")

# DB (same as Flask app)
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Target URL for health checks
TARGET_URL = os.getenv("TARGET_URL", "https://pivoxquant.com")
# SECURITY: No default value. If unset, dev-login/dev-upgrade endpoints return 404.
# Production (Railway) MUST NOT set this variable.
DEV_LOGIN_SECRET = os.getenv("DEV_LOGIN_SECRET")

# Kill switch — set to true in Railway to halt immediately
KILL_SWITCH = os.getenv("AGENT_KILL_SWITCH", "false").lower() == "true"

# Poll interval (seconds)
POLL_INTERVAL = int(os.getenv("AGENT_POLL_INTERVAL", "30"))

# Escalation triggers — maps event types to risk scores + channels
ESCALATION_TRIGGERS = {
    # Money — always escalate
    "payment_execute": {"risk": 100, "channel": "slack"},
    "trade_execute_real": {"risk": 100, "channel": "slack"},  # Should never fire (paper only)
    "api_cost_exceeds_50pct": {"risk": 90, "channel": "slack"},

    # Irreversible
    "force_push_main": {"risk": 100, "channel": "slack"},
    "db_migration_destructive": {"risk": 100, "channel": "slack"},
    "file_delete_batch": {"risk": 80, "channel": "slack"},
    "prod_deploy": {"risk": 70, "channel": "slack"},

    # Legal
    "forbidden_term_detected": {"risk": 100, "channel": "slack"},
    "privacy_data_export": {"risk": 90, "channel": "slack"},

    # Low confidence
    "agent_confidence_below_70": {"risk": 60, "channel": "slack"},
    "retry_count_exceeds_3": {"risk": 70, "channel": "slack"},
}

# Claude API cost per 1M tokens (Haiku 4.5 approx)
COST_PER_1M_INPUT = 1.00
COST_PER_1M_OUTPUT = 5.00
