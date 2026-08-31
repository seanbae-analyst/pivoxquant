"""Blueprint registration."""
import os


def register_blueprints(app):
    from .auth import auth_bp, auth_alias_bp
    from .portfolio import portfolio_bp
    from .market import market_bp
    from .alerts import alerts_bp
    from .notifications import notifications_bp
    from .trades import trades_bp
    from .realtime import realtime_bp
    from .profile import profile_bp
    from .billing import billing_bp
    from .push import push_bp
    from .health import health_bp
    from .data_status import data_status_bp  # Wave G C-CS3 — public stale-banner endpoint
    from .pre_trade import pre_trade_bp  # Feature 6 — Pre-Trade Friction
    from .behavior import behavior_bp    # Feature 7 — Weekly Behavioural Score
    from .email_preferences import email_pref_bp  # 정통망법 §50 unsubscribe
    from .consents import consents_bp  # 정통망법 §50 ① marketing-consent record
    from .feedback import feedback_bp  # Wave G C-AC2 — NPS 1-click (transactional)
    from .support import support_bp  # 고객문의센터 + 지원 챗봇
    from .inbox import inbox_bp  # v57 CEO Inbox single-pane (admin only)
    from .mirror_home import mirror_home_bp  # 거울 home — composed 선언/관찰/트윈 read
    from services.email.webhook import sendgrid_webhook_bp  # SendGrid Event Webhook

    blueprints = [
        health_bp,
        data_status_bp,

        auth_bp, auth_alias_bp, portfolio_bp,
        market_bp, alerts_bp, notifications_bp, trades_bp,
        realtime_bp, profile_bp,
        billing_bp, push_bp,
        pre_trade_bp, behavior_bp,
        email_pref_bp,
        consents_bp,
        feedback_bp,
        support_bp,
        inbox_bp,
        mirror_home_bp,
        sendgrid_webhook_bp,
    ]

    # Command Center writes to disk without authentication — opt-in only.
    # Enable in local dev by setting ENABLE_COMMAND_CENTER=1.
    # Consumer: scripts/cc-hook.sh POSTs to /api/command-center/log.
    if os.environ.get("ENABLE_COMMAND_CENTER") == "1":
        from .command_center import command_center_bp
        blueprints.append(command_center_bp)

    # Dev-login bypass for E2E testing — only when DEV_LOGIN_SECRET is set.
    # Production (Railway) must NOT set this variable.
    # 2026-05-10 (security M3): fail-fast if both production AND
    # DEV_LOGIN_SECRET are set. Operator-error defense.
    # 2026-06-10 (bug-hunt W2-P3): the guard was a single env-string check —
    # if FLASK_ENV were ever unset/overridden on Railway, the bypass would
    # mount in prod with only the brute-forceable secret as a barrier. Also
    # refuse whenever a Railway environment marker is present, independent
    # of FLASK_ENV (belt and suspenders).
    if os.environ.get("DEV_LOGIN_SECRET"):
        on_railway = bool(
            os.environ.get("RAILWAY_ENVIRONMENT")
            or os.environ.get("RAILWAY_PUBLIC_DOMAIN")
        )
        if os.environ.get("FLASK_ENV") == "production" or on_railway:
            raise RuntimeError(
                "DEV_LOGIN_SECRET must NOT be set in production / on Railway. "
                "Refusing to mount dev_auth blueprint (security M3 + W2-P3)."
            )
        from .dev_auth import dev_auth_bp
        blueprints.append(dev_auth_bp)

    # Sim-onboard bypass for CAUS daily sweep (Continuous Autonomous User
    # Simulation, scripts/caus_daily_sweep.py). Mounted only when
    # SIM_ONBOARD_SECRET is set. Separate from DEV_LOGIN_SECRET — safe to
    # enable on production because the endpoint:
    #   * restricts emails to a sim-only regex (seanbae1521+sim{N}@gmail.com
    #     or sim{N}@pivoxquant-test.local),
    #   * forces is_simulated=True on every created user,
    #   * refuses to flip the flag on existing real users,
    #   * requires a 5-minute HMAC-signed ticket + PivoxQuantCAUS/ User-Agent.
    # See routes/sim_onboard.py for the full security model.
    if os.environ.get("SIM_ONBOARD_SECRET"):
        from .sim_onboard import sim_onboard_bp
        blueprints.append(sim_onboard_bp)

    for bp in blueprints:
        app.register_blueprint(bp)
