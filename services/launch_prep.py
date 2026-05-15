"""Production boot-time environment validation.

Background
----------
Several production-only features silently fall back to a no-op or
dev-mode path when their environment variable is missing. The
existing patterns we've hit this session:

- ``services/email/sender.py`` — when ``SENDGRID_API_KEY`` is unset
  AND ``SMTP_HOST`` is unset, all email sends become silent no-ops
  (logger.info + return False). The weekly_memo cron fires every
  Sunday 08:00 KST regardless, so a missing key means a silent
  failure mode with no Sentry signal until a user notices "I never
  got my Sunday memo."

- ``routes/billing.py`` — Stripe checkout requires ``STRIPE_SECRET_KEY``
  + business-registration gate. Currently returns 503
  BUSINESS_REGISTRATION_PENDING (PR #397 handles this gracefully on
  the client).

- ``services/data/fmp.py`` — ``FMP_API_KEY`` missing → chart + news
  endpoints fall back to ``source: "none"`` (Wave 5 #2/#5 finding).
  Visible to users as "Chart data unavailable for this window."

- ``services/ai/service.py`` — ``ANTHROPIC_API_KEY`` missing → AI
  endpoints return 503 (Wave 5 #3 closed graceful by PR #397).

- ``services/kis/service.py`` — ``KIS_APP_KEY`` / ``KIS_APP_SECRET``
  missing → KR market endpoints lose KIS path (FMP fallback also
  402s on caret-prefixed KR symbols).

Failure mode without this module
--------------------------------
Each missing key produces a soft failure deep inside a feature
codepath. The user sees a feature break, files a bug, and the
operator hunts a config issue. With this module, the operator gets
a single boot-time CRITICAL log line listing every missing key,
visible in the Railway "Build" / "Deploy" log within seconds of
restart.

Design
------
- Pure read-only (env-only). No DB hits, no network. Safe under
  every test path.
- Distinguishes ``required`` (block boot) vs ``recommended`` (warn)
  vs ``optional`` (info). Today nothing is set as required — we
  warn loudly but don't crash, because the existing dev-mode
  behaviour is the working dev workflow.
- Production-gated (``FLASK_ENV=production``). Local dev doesn't get
  noise.
- Returns a structured dict the /api/health endpoint can echo for
  external monitoring (optional surfacing).

Cost
----
$0. stdlib only. No new dependencies.
"""
from __future__ import annotations

import logging
import os
from typing import Literal, TypedDict

logger = logging.getLogger(__name__)


class EnvCheck(TypedDict):
    """One env var check result."""
    name: str
    severity: Literal["required", "recommended", "optional"]
    present: bool
    purpose: str


# The env-var inventory. Order matters: log output renders top-to-bottom.
#
# severity guidelines (memory: feedback_no_busywork — don't crash boot
# on missing keys; the dev workflow depends on env-less local runs):
#   required    — production cannot serve any traffic without this. None
#                 today. We document the slot but it stays empty for
#                 now; flipping a key to required is a deliberate
#                 deployment-policy decision.
#   recommended — production CAN start without it, but a real feature
#                 silently degrades. Log CRITICAL so Railway log alerts
#                 fire (visible in Sentry / Slack via the existing
#                 webhook surface).
#   optional    — nice-to-have (Sentry DSN, Sentry sampling tunes,
#                 etc). Log INFO.
_INVENTORY: tuple[tuple[str, Literal["required", "recommended", "optional"], str], ...] = (
    # Core security
    ("SECRET_KEY", "recommended",
     "Flask session signing key. Falls back to a per-boot random hex; "
     "users get logged out on every restart"),
    ("CSRF_SECRET", "optional",
     "Falls back to SECRET_KEY (security.py:96). Setting both pin "
     "stable CSRF tokens across SECRET_KEY rotation"),
    ("DATABASE_URL", "recommended",
     "PostgreSQL connection (auto-set by Railway in prod). Without "
     "it SQLAlchemy falls to in-memory SQLite — useless for users"),

    # Email / artifact delivery
    ("SENDGRID_API_KEY", "recommended",
     "Without this AND without SMTP_HOST, every weekly_memo / "
     "monthly_brag / brag_card / earnings_prebrief / KPI dashboard "
     "/ DD checklist / ... 17 artifact mailers SILENTLY DROP. "
     "The cron fires anyway. See docs/ops/email-setup.md"),
    ("SMTP_HOST", "optional",
     "Fallback transport when SendGrid is unset or 5xx-failing. "
     "Postmark works; smtp.postmarkapp.com:587"),
    ("WEEKLY_MEMO_FROM_EMAIL", "optional",
     "Defaults to reports@pivoxquant.com (services/email/sender.py:75)"),

    # External APIs (memory: feedback_no_extra_cost — these are the
    # approved paid services in the budget)
    ("FMP_API_KEY", "recommended",
     "FMP Stable $29 plan. Without it chart + news + US fundamentals "
     "fall to 'source: none' empty. KIS handles KR equities."),
    ("ANTHROPIC_API_KEY", "recommended",
     "Claude API for /ai/swot + /ai/coaching + /ai/earnings-tone. "
     "Without it those endpoints 503 (PR #387 + #397 close the "
     "frontend UX gracefully). Sustained 503 = no AI features."),
    ("KIS_APP_KEY", "recommended",
     "Korea Investment & Securities OpenAPI app key. KR equity prices "
     "+ indices source. Without it KR portfolio + KOSPI/KOSDAQ break."),
    ("KIS_APP_SECRET", "recommended",
     "Companion secret to KIS_APP_KEY. Both must be present."),

    # Payment (gated separately on BUSINESS_REGISTRATION_COMPLETE)
    ("STRIPE_SECRET_KEY", "optional",
     "Stripe SDK key. Pre-business-registration prod returns 503 "
     "BUSINESS_REGISTRATION_PENDING (routes/billing.py + PR #397 "
     "client-side toast). Once registered, this becomes recommended."),
    ("STRIPE_WEBHOOK_SECRET", "optional",
     "Stripe webhook signature verification. Pair with the above."),

    # Beta gate
    ("BETA_PASSWORD", "recommended",
     "Vercel-level beta interstitial password. Closed-beta only — "
     "remove this var post-launch (Memory: 2026-05-10 rotate, "
     "/tmp/new-beta-pw.txt). Without it Vercel beta-gate breaks."),

    # Sim / CAUS
    ("SIM_ONBOARD_SECRET", "optional",
     "HMAC ticket for CAUS sim-onboard (autonomous user simulation). "
     "Without it the daily Playwright sweep falls back to manual "
     "cookie file. Production-only."),

    # Observability
    ("SENTRY_DSN", "optional",
     "Sentry error reporting. Without it errors only land in Railway "
     "logs (less searchable, no rate-limited alerts)"),
)


def check_env(*, production: bool | None = None) -> dict:
    """Run the env-var inventory and emit boot-time log lines.

    Args:
        production: Override the FLASK_ENV check (test-only). When None
            (default), reads ``FLASK_ENV`` and runs only in production.

    Returns:
        ``{"production": bool, "checks": [EnvCheck, ...], "summary":
        {"missing_recommended": int, "missing_required": int}}``.

        The /api/health endpoint can echo this for external monitoring.
    """
    if production is None:
        production = (
            os.environ.get("FLASK_ENV", "development").lower() == "production"
        )

    checks: list[EnvCheck] = []
    missing_required = 0
    missing_recommended = 0

    for name, severity, purpose in _INVENTORY:
        value = os.environ.get(name, "")
        present = bool(value.strip())
        checks.append({
            "name": name,
            "severity": severity,
            "present": present,
            "purpose": purpose,
        })
        if not present:
            if severity == "required":
                missing_required += 1
            elif severity == "recommended":
                missing_recommended += 1

    if production:
        # Loud line so it shows up in Railway "Deploy Logs" view.
        if missing_required > 0:
            logger.critical(
                "LAUNCH_PREP: %d REQUIRED env var(s) missing — "
                "boot may fail or core endpoints will 500. See per-var "
                "log lines below.",
                missing_required,
            )
        if missing_recommended > 0:
            logger.critical(
                "LAUNCH_PREP: %d RECOMMENDED env var(s) missing in "
                "production. Features will silently degrade. See "
                "per-var log lines below. Reference: docs/ops/email-setup.md "
                "+ docs/ops/launch-checklist.md (when present).",
                missing_recommended,
            )
        if missing_recommended == 0 and missing_required == 0:
            logger.info("LAUNCH_PREP: all recommended/required env vars present ✓")

        # Per-var lines.
        for c in checks:
            if not c["present"]:
                level = (
                    logging.CRITICAL if c["severity"] == "required"
                    else logging.WARNING if c["severity"] == "recommended"
                    else logging.INFO
                )
                logger.log(
                    level,
                    "LAUNCH_PREP env-missing [%s] %s — %s",
                    c["severity"].upper(),
                    c["name"],
                    c["purpose"][:160],
                )

    return {
        "production": production,
        "checks": checks,
        "summary": {
            "missing_required": missing_required,
            "missing_recommended": missing_recommended,
            "total_checked": len(checks),
        },
    }


def env_health_summary() -> dict:
    """Compact summary suitable for inclusion in /api/health.

    Excludes the full per-var purpose strings to keep the response
    payload small. The boot-time logs carry the verbose detail.

    The ``production`` flag in the summary reflects the REAL
    ``FLASK_ENV`` value (not the parameter we pass to ``check_env``).
    We pass ``production=False`` to ``check_env`` to suppress the
    logging side-effect on every /health hit, but the response must
    still tell the external monitor "is this a prod box?" so the
    alert threshold can be conditioned on it.
    """
    full = check_env(production=False)  # silence logging on every hit
    real_production = (
        os.environ.get("FLASK_ENV", "development").lower() == "production"
    )
    return {
        "production": real_production,
        "missing_required": full["summary"]["missing_required"],
        "missing_recommended": full["summary"]["missing_recommended"],
        "total_checked": full["summary"]["total_checked"],
    }
