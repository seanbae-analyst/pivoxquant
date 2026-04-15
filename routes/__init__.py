"""Blueprint registration."""
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
    from .broker_sync import broker_sync_bp
    from .billing import billing_bp
    from .push import push_bp
    from .share import share_bp
    from .simulate import simulate_bp
    from .counterfactual import counterfactual_bp
    from .morning_brief import morning_brief_bp

    blueprints = [
        auth_bp, portfolio_bp, signals_bp, discover_bp,
        market_bp, daytrade_bp, alerts_bp, trades_bp,
        autotrade_bp, ai_bp, watchlist_bp, backtest_bp,
        quant_bp, realtime_bp, profile_bp, broker_sync_bp,
        billing_bp, push_bp, share_bp, simulate_bp,
        counterfactual_bp, morning_brief_bp,
    ]

    # Command Center writes to disk without authentication — opt-in only.
    # Enable in local dev by setting ENABLE_COMMAND_CENTER=1.
    if os.environ.get("ENABLE_COMMAND_CENTER") == "1":
        from .command_center import command_center_bp
        blueprints.append(command_center_bp)

    for bp in blueprints:
        app.register_blueprint(bp)
