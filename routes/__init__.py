"""Blueprint registration."""
import logging
import os


def register_blueprints(app):
    from .auth import auth_bp
    from .portfolio import portfolio_bp
    from .signals import signals_bp
    from .discover import discover_bp
    from .market import market_bp
    from .daytrade import daytrade_bp
    from .alerts import alerts_bp
    from .trades import trades_bp
    from .autotrade import autotrade_bp
    from .ai import ai_bp
    from .watchlist import watchlist_bp
    from .backtest import backtest_bp
    from .quant import quant_bp
    from .realtime import realtime_bp
    from .profile import profile_bp
    from .broker_oauth import broker_oauth_bp
    from .billing import billing_bp
    from .push import push_bp
    from .share import share_bp
    from .simulate import simulate_bp
    from .counterfactual import counterfactual_bp
    from .morning_brief import morning_brief_bp
    from .alt_data import alt_data_bp
    from .artifacts import artifacts_bp
    from .health import health_bp
    from .admin_fmp import admin_fmp_bp
    from .admin_preview import admin_preview_bp

    # agent_worker is a sibling package and may be absent in some deploys
    # (it ships a Procfile + its own requirements). When it's unavailable
    # we skip the Growth blueprint rather than crashing the whole app —
    # the health probe and all other routes must stay up.
    growth_bp = None
    try:
        from agent_worker.growth_routes import growth_bp as _growth_bp
        growth_bp = _growth_bp
    except Exception as exc:  # pragma: no cover — exercised only on ImportError
        logging.getLogger(__name__).warning(
            "agent_worker.growth_routes unavailable (%s); /api/growth disabled",
            exc,
        )
        # TODO: bundle agent_worker into the main image or extract it
        # behind a feature flag before GA.

    blueprints = [
        health_bp,
        auth_bp, portfolio_bp, signals_bp, discover_bp,
        market_bp, daytrade_bp, alerts_bp, trades_bp,
        autotrade_bp, ai_bp, watchlist_bp, backtest_bp,
        quant_bp, realtime_bp, profile_bp, broker_oauth_bp,
        billing_bp, push_bp, share_bp, simulate_bp,
        counterfactual_bp, morning_brief_bp, alt_data_bp,
        artifacts_bp, admin_fmp_bp, admin_preview_bp,
    ]
    if growth_bp is not None:
        blueprints.append(growth_bp)

    # Command Center writes to disk without authentication — opt-in only.
    # Enable in local dev by setting ENABLE_COMMAND_CENTER=1.
    if os.environ.get("ENABLE_COMMAND_CENTER") == "1":
        from .command_center import command_center_bp
        blueprints.append(command_center_bp)

    # Dev-login bypass for E2E testing — only when DEV_LOGIN_SECRET is set.
    # Production (Railway) must NOT set this variable.
    if os.environ.get("DEV_LOGIN_SECRET"):
        from .dev_auth import dev_auth_bp
        blueprints.append(dev_auth_bp)

    for bp in blueprints:
        app.register_blueprint(bp)
